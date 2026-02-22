# -*- coding: utf-8 -*-
"""
Steam Rent Module - главный класс модуля.

Аренда Steam-аккаунтов через FunPay:
- Автовыдача при покупке
- Бонусные часы за отзыв
- Снятие бонуса при удалении отзыва
- Множественные аренды у одного пользователя

АРХИТЕКТУРА:
- Модуль наследуется от core.Module
- События обрабатываются через handle_event()
- Подписки указываются в get_subscriptions()
- Команды возвращаются модулем, отправляются ядром
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from core.module import Module, register_module_class, Subscription
from core.storage import ModuleStorage
from core import Command, CommandResult, OpiumEvent
from core.commands import CommandType

from .storage import SteamRentStorage
from .scheduler import RentalScheduler
from . import handlers


logger = logging.getLogger("opium.steam_rent")


@register_module_class
class SteamRentModule(Module):
    """
    Модуль аренды Steam-аккаунтов.
    
    Конфигурация в accounts/{id}/modules/steam_rent/:
    - config.json - настройки модуля 
    - games.json - список игр
    - lot_mappings.json - привязка лотов FunPay к играм
    - steam_accounts.json - Steam аккаунты
    - rentals.json - история аренд
    """
    
    module_name = "steam_rent"
    
    def __init__(self, account_id: str, storage: ModuleStorage) -> None:
        super().__init__(account_id, storage)
        
        # Типизированное хранилище
        self._steam_storage = SteamRentStorage(storage)
        
        # Планировщик истечения аренд
        self._scheduler: RentalScheduler | None = None
        
        # Callback для выполнения команд (устанавливается ядром через set_execute_command)
        # Нужен для get_order при проверке рейтинга отзывов
        self._execute_command: Callable[[Command], Awaitable[CommandResult]] | None = None
        
        # Настройки из конфига
        config = self._steam_storage.get_config()
        self._scheduler_check_interval: float = float(config.get("scheduler_check_interval_sec", 60))
        self._pending_ttl_minutes: int = int(config.get("pending_ttl_minutes", 1440))
        self._expiry_warning_minutes: int = int(config.get("expiry_warning_minutes", 0))
        
        logger.info(f"[{self.name}] Initialized for account {account_id}")
    
    @property
    def steam_storage(self) -> SteamRentStorage:
        """Public access to typed storage (used by api_router.py)."""
        return self._steam_storage
    
    def get_subscriptions(self) -> list[Subscription]:
        """
        Подписки на события:
        - new_order - для автовыдачи
        - new_message - для команд и событий отзывов
        """
        return [
            Subscription(event_types=["new_order", "new_message"]),
        ]
    
    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        """
        Обрабатывает события и возвращает команды.
        """
        event_type = event.event_type
        logger.debug(
            f"[{self.name}] handle_event: {event_type} "
            f"(account={event.account_id})"
        )
        
        if event_type == "new_order":
            commands = handlers.handle_new_order(
                event,
                self._steam_storage,
            )
            if commands:
                logger.info(
                    f"[{self.name}] new_order produced {len(commands)} command(s): "
                    f"{[c.command_type for c in commands]}"
                )
            return commands
        
        elif event_type == "new_message":
            commands = handlers.handle_new_message(
                event,
                self._steam_storage,
                self.account_id,
            )
            if commands:
                logger.info(
                    f"[{self.name}] new_message produced {len(commands)} command(s): "
                    f"{[c.command_type for c in commands]}"
                )
            return commands
        
        return []
    
    def set_execute_command(self, fn: Callable[[Command], Awaitable[Any]]) -> None:
        """
        Устанавливает callback для выполнения команд на аккаунте.
        
        Вызывается ядром (core) после создания модуля.
        Без этого PendingReview остаются в очереди.
        """
        self._execute_command = fn
        logger.info(f"[{self.name}] execute_command callback set")
    
    async def on_start(self) -> None:
        """
        Вызывается при запуске модуля.
        - Запускает планировщик истечения аренд
        """
        logger.info(f"[{self.name}] Starting...")
        
        # Async callback для истёкших аренд
        async def on_expired(rental_id: str) -> None:
            handlers.handle_rental_expired(rental_id, self._steam_storage)
        
        # Async callback для проверки отзывов (get_order)
        async def on_review_check(order_id: str) -> Any:
            if self._execute_command is None:
                raise RuntimeError("execute_command not set")
            cmd = Command(
                command_type=CommandType.GET_ORDER,
                params={"order_id": order_id},
            )
            result = await self._execute_command(cmd)
            if hasattr(result, 'success') and not result.success:
                logger.warning(f"get_order({order_id}) failed: {getattr(result, 'error', 'unknown')}")
                return None
            # CommandResult.data содержит Order object
            return getattr(result, 'data', result)
        
        # Callback для review check - только если execute_command доступен
        review_cb = on_review_check if self._execute_command is not None else None
        
        # Async callback для отправки предупреждений об истечении аренды
        async def on_send_warning(rental_id: str, chat_id: int | str, text: str, chat_name: str = "") -> None:
            if self._execute_command is None:
                logger.warning(f"Cannot send expiry warning for {rental_id}: execute_command not set")
                return
            cmd = Command(
                command_type=CommandType.SEND_MESSAGE,
                params={"chat_id": chat_id, "text": text, "chat_name": chat_name},
            )
            await self._execute_command(cmd)

        warning_cb = on_send_warning if self._execute_command is not None else None
        
        # Запускаем планировщик
        self._scheduler = RentalScheduler(
            storage=self._steam_storage,
            on_rental_expired=on_expired,
            on_review_check=review_cb,
            check_interval=self._scheduler_check_interval,
            pending_ttl_minutes=self._pending_ttl_minutes,
            on_send_warning=warning_cb,
            expiry_warning_minutes=self._expiry_warning_minutes,
        )
        await self._scheduler.start()
        
        logger.info(f"[{self.name}] Started, scheduler running (review_check={'enabled' if review_cb else 'disabled'})")
    
    async def on_stop(self) -> None:
        """
        Вызывается при остановке модуля.
        - Останавливает планировщик
        """
        logger.info(f"[{self.name}] Stopping...")
        
        if self._scheduler:
            await self._scheduler.stop()
            self._scheduler = None
        
        logger.info(f"[{self.name}] Stopped")

    async def get_order_tags(
        self, orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Возвращает теги заказов для сортировки на странице Orders.

        Источники (по приоритету):
        1. Активные аренды (Rental) — точный game_id
        2. Ожидающие заказы (PendingOrder) — точный game_id
        3. Все переданные orders — матчинг описания по LotMapping.lot_pattern

        Третий источник покрывает завершённые/возвращённые заказы,
        которые отстуствуют в rentals/pending, но видны в FunPay.
        """
        rentals = self._steam_storage.get_rentals()
        pending = self._steam_storage.get_pending_orders()
        lot_mappings = self._steam_storage.get_lot_mappings()
        games = {g.game_id: g for g in self._steam_storage.get_games()}
        tags: dict[str, dict[str, Any]] = {}

        def _make_tag(game_id: str) -> dict[str, Any]:
            return {
                "module": self.module_name,
                "game_id": game_id,
            }

        # 1. Active rentals (most precise)
        for r in rentals:
            tags[r.order_id] = _make_tag(r.game_id)

        # 2. Pending orders
        for p in pending:
            if p.order_id not in tags:
                tags[p.order_id] = _make_tag(p.game_id)

        # 3. Match ALL orders by description against LotMapping patterns,
        #    then fallback to game_id / aliases substring match.
        if orders:
            for order in orders:
                oid = order.get("order_id", "")
                if oid in tags:
                    continue  # already tagged by rental/pending
                desc = order.get("description", "")
                desc_lower = desc.lower()

                # 3a. Lot pattern match (most specific)
                matched = False
                for mapping in lot_mappings:
                    if mapping.lot_pattern.lower() in desc_lower:
                        tags[oid] = _make_tag(mapping.game_id)
                        matched = True
                        break
                if matched:
                    continue

                # 3b. Game name / alias substring match (broader fallback)
                for game in games.values():
                    if game.game_id.lower() in desc_lower:
                        tags[oid] = _make_tag(game.game_id)
                        matched = True
                        break
                    for alias in game.aliases:
                        if alias.lower() in desc_lower:
                            tags[oid] = _make_tag(game.game_id)
                            matched = True
                            break
                    if matched:
                        break

        return tags
