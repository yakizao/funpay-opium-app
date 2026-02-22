# -*- coding: utf-8 -*-
"""Auto Raise Module - автоматическое поднятие всех лотов."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Callable, Awaitable, ClassVar

from core.module import Module, register_module_class, Subscription
from core.storage import ModuleStorage
from core import Command, CommandResult, OpiumEvent
from core.commands import CommandType

from .storage import AutoRaiseStorage

logger = logging.getLogger("opium.auto_raise")

# Интервал проверки cooldowns (секунды). Не отображается пользователю.
POLL_INTERVAL = 30
# Интервал обновления списка категорий (секунды). 6 часов.
CATEGORY_REFRESH_INTERVAL = 6 * 3600


@register_module_class
class AutoRaiseModule(Module):
    module_name: ClassVar[str] = "auto_raise"

    def __init__(self, account_id: str, storage: ModuleStorage) -> None:
        super().__init__(account_id, storage)
        self._ar_storage = AutoRaiseStorage(storage)
        self._execute_command: Callable[[Command], Awaitable[CommandResult]] | None = None
        self._task: asyncio.Task | None = None

        # per-category next raise timestamp
        self._next_raise: dict[int, float] = {}
        # last raise results for status API
        self._last_results: dict[int, dict[str, Any]] = {}
        self._raising: bool = False

        # cached categories {cat_id: cat_name}
        self._cached_categories: dict[int, str] = {}
        self._categories_fetched_at: float = 0

        logger.info(f"[{self.name}] Initialized for account {account_id}")

    @property
    def ar_storage(self) -> AutoRaiseStorage:
        return self._ar_storage

    @property
    def is_active(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def raising(self) -> bool:
        return self._raising

    @property
    def next_raise_times(self) -> dict[int, float]:
        return dict(self._next_raise)

    @property
    def last_results(self) -> dict[int, dict[str, Any]]:
        return dict(self._last_results)

    def get_subscriptions(self) -> list[Subscription]:
        return [Subscription()]

    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        logger.debug(f"[{self.name}] Event {event.event_type} received (no-op)")
        return []

    def set_execute_command(self, fn: Callable[[Command], Awaitable[Any]]) -> None:
        self._execute_command = fn
        logger.info(f"[{self.name}] execute_command callback set")

    # ─── Lifecycle ────────────────────────────────────

    async def on_start(self) -> None:
        if self._ar_storage.is_enabled():
            await self.start_scheduler()

    async def on_stop(self) -> None:
        await self.stop_scheduler()

    async def start_scheduler(self) -> None:
        await self.stop_scheduler()
        self._task = asyncio.create_task(
            self._raise_loop(),
            name=f"auto-raise-{self.account_id}",
        )
        logger.info(f"[{self.name}] Scheduler started")

    async def stop_scheduler(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info(f"[{self.name}] Scheduler stopped")

    # ─── Main Loop ────────────────────────────────────

    async def _raise_loop(self) -> None:
        # маленькая задержка чтобы runtime успел стартовать
        await asyncio.sleep(5)

        while True:
            try:
                if self._ar_storage.is_enabled():
                    logger.debug(f"[{self.name}] Raise loop tick")
                    await self._do_raise_all()
                else:
                    logger.debug(f"[{self.name}] Raise loop tick (disabled, skipping)")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.name}] Raise loop error: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    async def _get_my_category_ids(self) -> dict[int, str]:
        """
        Получает категории, в которых у пользователя реально есть лоты,
        через парсинг собственного профиля (get_user(self.id)).
        Возвращает {category_id: category_name}.
        """
        profile_result = await self._execute_command(
            Command(command_type=CommandType.GET_MY_PROFILE)
        )
        if not profile_result.success:
            logger.error(f"[{self.name}] Failed to get own profile: {profile_result.error}")
            return {}

        profile = profile_result.data
        if not profile:
            return {}

        from FunPayAPI.common.enums import SubCategoryTypes

        # Собираем уникальные category_id из лотов профиля (только COMMON)
        categories: dict[int, str] = {}
        for lot in profile.get_lots():
            subcat = lot.subcategory
            if subcat.type is not SubCategoryTypes.COMMON:
                continue
            cat = subcat.category
            if cat.id not in categories:
                categories[cat.id] = cat.name

        return categories

    async def _refresh_categories_if_needed(self) -> dict[int, str]:
        """Обновить кеш категорий если прошло больше CATEGORY_REFRESH_INTERVAL."""
        now = time.time()
        if self._cached_categories and (now - self._categories_fetched_at) < CATEGORY_REFRESH_INTERVAL:
            return self._cached_categories

        fresh = await self._get_my_category_ids()
        if fresh:
            self._cached_categories = fresh
            self._categories_fetched_at = now
            logger.info(
                f"[{self.name}] Refreshed categories ({len(fresh)}): "
                f"{', '.join(fresh.values())}"
            )
        elif not self._cached_categories:
            logger.debug(f"[{self.name}] No categories with lots found on profile")
        return self._cached_categories

    async def _do_raise_all(self) -> dict[int, dict[str, Any]]:
        """Поднять категории где у пользователя есть лоты. Возвращает результаты по category_id."""
        if not self._execute_command:
            logger.warning(f"[{self.name}] execute_command not set, skipping")
            return {}

        self._raising = True
        results: dict[int, dict[str, Any]] = {}

        try:
            # Получаем категории (из кеша или парсим заново)
            my_categories = await self._refresh_categories_if_needed()
            if not my_categories:
                logger.debug(f"[{self.name}] No categories to raise")
                return {}

            now = time.time()
            logger.info(
                f"[{self.name}] Raise cycle: {len(my_categories)} categories "
                f"({', '.join(my_categories.values())})"
            )

            for cat_id, cat_name in my_categories.items():
                # Проверяем cooldown
                next_time = self._next_raise.get(cat_id, 0)
                if now < next_time:
                    remaining = int(next_time - now)
                    results[cat_id] = {
                        "category_name": cat_name,
                        "success": False,
                        "skipped": True,
                        "wait_seconds": remaining,
                    }
                    continue

                # Поднимаем
                raise_result = await self._execute_command(
                    Command(
                        command_type=CommandType.RAISE_LOTS,
                        params={"category_id": cat_id},
                    )
                )

                if raise_result.success:
                    self._ar_storage.append_log(cat_id, cat_name, True)
                    logger.info(f"[{self.name}] Raised: {cat_name} (id={cat_id})")

                    # Сразу пробуем ещё раз — FunPay вернёт wait_time (реальный кулдаун)
                    await asyncio.sleep(1)
                    probe = await self._execute_command(
                        Command(
                            command_type=CommandType.RAISE_LOTS,
                            params={"category_id": cat_id},
                        )
                    )
                    delay_range = self._ar_storage.get_delay_range()
                    jitter = random.randint(0, delay_range * 60) if delay_range > 0 else 0
                    probe_wait = None
                    if isinstance(probe.data, dict):
                        probe_wait = probe.data.get("wait_time")
                    if probe_wait:
                        self._next_raise[cat_id] = now + probe_wait + jitter
                    else:
                        # fallback: 4 часа (стандартный кулдаун FunPay)
                        self._next_raise[cat_id] = now + 14400 + jitter

                    results[cat_id] = {
                        "category_name": cat_name,
                        "success": True,
                        "wait_seconds": probe_wait,
                    }
                else:
                    wait_time = None
                    if isinstance(raise_result.data, dict):
                        wait_time = raise_result.data.get("wait_time")

                    delay_range = self._ar_storage.get_delay_range()
                    jitter = random.randint(0, delay_range * 60) if delay_range > 0 else 0

                    if wait_time:
                        self._next_raise[cat_id] = now + wait_time + jitter
                    else:
                        # fallback: попробуем через 60 секунд
                        self._next_raise[cat_id] = now + 60

                    results[cat_id] = {
                        "category_name": cat_name,
                        "success": False,
                        "error": raise_result.error,
                        "wait_seconds": wait_time,
                    }
                    self._ar_storage.append_log(
                        cat_id, cat_name, False, raise_result.error
                    )
                    logger.debug(
                        f"[{self.name}] Raise cooldown for {cat_name}: "
                        f"wait {wait_time}s"
                    )

                # Небольшая пауза между категориями
                await asyncio.sleep(0.5)

        finally:
            self._raising = False
            self._last_results = results

        return results

    async def raise_now(self) -> dict[int, dict[str, Any]]:
        """Ручной запуск поднятия (из API). Сбрасывает cooldowns и кеш категорий."""
        logger.info(f"[{self.name}] Manual raise_now triggered")
        self._next_raise.clear()
        self._categories_fetched_at = 0  # force refresh
        return await self._do_raise_all()
