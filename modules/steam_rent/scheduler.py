# -*- coding: utf-8 -*-
"""
Steam Rent - Scheduler.

Планировщик окончания аренд.
НЕ использует sleep(24h) - работает через asyncio.

Проверяет истёкшие аренды каждые N минут и освобождает аккаунты.
Очищает просроченные PendingOrder (TTL из конфига).
Обрабатывает PendingReview через get_order (проверка рейтинга).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Awaitable

if TYPE_CHECKING:
    from .storage import SteamRentStorage

logger = logging.getLogger("opium.steam_rent.scheduler")

# Время жизни PendingOrder по умолчанию (24 часа)
DEFAULT_PENDING_TTL_MINUTES = 0


class RentalScheduler:
    """
    Планировщик окончания аренд.
    
    Запускает фоновую задачу, которая:
    1. Проверяет истёкшие аренды каждые check_interval секунд
    2. Вызывает callback для каждой истёкшей аренды
    3. Очищает просроченные PendingOrder (старше pending_ttl_minutes)
    4. Обрабатывает PendingReview — вызывает get_order, проверяет рейтинг
    5. НЕ использует sleep(24h) - только короткие интервалы
    """
    
    def __init__(
        self,
        storage: "SteamRentStorage",
        on_rental_expired: Callable[[str], Awaitable[None]],
        on_review_check: Callable[[str], Awaitable[Any]] | None = None,
        on_send_warning: Callable[[str, int | str, str, str], Awaitable[None]] | None = None,
        check_interval: float = 60.0,
        pending_ttl_minutes: int = DEFAULT_PENDING_TTL_MINUTES,
        expiry_warning_minutes: int = 0,  # 0 = disabled
    ) -> None:
        """
        Args:
            storage: Хранилище данных
            on_rental_expired: Async callback при истечении аренды (rental_id)
            on_review_check: Async callback (order_id) → order obj or None
            on_send_warning: Async callback (rental_id, chat_id, message) for expiry warnings
            check_interval: Интервал проверки в секундах
            pending_ttl_minutes: Время жизни PendingOrder в минутах (по умолчанию 24ч)
            expiry_warning_minutes: За сколько минут до конца отправлять предупреждение (0 = выкл)
        """
        self._storage = storage
        self._on_expired = on_rental_expired
        self._on_review_check = on_review_check
        self._on_send_warning = on_send_warning
        self._check_interval = check_interval
        self._pending_ttl_minutes = pending_ttl_minutes
        self._expiry_warning_minutes = expiry_warning_minutes
        self._task: asyncio.Task | None = None
        self._running: bool = False
    
    async def start(self) -> None:
        """Запускает планировщик."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler started (interval: {self._check_interval}s)")
    
    async def stop(self) -> None:
        """Останавливает планировщик."""
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Scheduler stopped")
    
    async def _run_loop(self) -> None:
        """Основной цикл планировщика."""
        while self._running:
            try:
                await self._check_expired()
                await self._check_expiry_warnings()
                self._cleanup_stale_pending()
                await self._process_pending_reviews()
            except Exception as e:
                logger.error(f"Scheduler check error: {e}")
            
            # Ждём до следующей проверки
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break
    
    async def _check_expired(self) -> None:
        """Проверяет и обрабатывает истёкшие аренды."""
        expired = self._storage.get_expired_rentals()
        
        if not expired:
            return
        
        logger.info(f"Found {len(expired)} expired rental(s)")
        
        for rental in expired:
            # Сохраняем данные до обработки (chat_id, order_id и т.д.)
            chat_id = rental.chat_id
            chat_name = rental.chat_name
            order_id = rental.order_id
            game_id = rental.game_id
            login = rental.delivered_login
            
            try:
                await self._on_expired(rental.rental_id)
            except Exception as e:
                logger.error(f"Error processing expired rental {rental.rental_id}: {e}")
                continue
            
            # Отправляем уведомление об окончании аренды
            if chat_id and self._on_send_warning:
                await self._send_expired_notification(
                    rental_id=rental.rental_id,
                    chat_id=chat_id,
                    chat_name=chat_name,
                    order_id=order_id,
                    game_id=game_id,
                    login=login,
                )
    
    async def _send_expired_notification(
        self,
        rental_id: str,
        chat_id: int | str,
        chat_name: str,
        order_id: str,
        game_id: str,
        login: str = "",
    ) -> None:
        """
        Отправляет уведомление покупателю об окончании аренды.
        
        Собирает одно сообщение из частей:
        1. rental_expired — всегда
        2. rental_expired_confirm — если заказ не подтверждён
        3. rental_expired_review — если нет отзыва
        """
        from .messages import get_msg
        
        try:
            # Проверяем статус заказа через get_order (подтверждение + отзыв)
            order_confirmed = False
            review_left = False
            
            if self._on_review_check:
                try:
                    order = await self._on_review_check(order_id)
                    if order is not None:
                        from FunPayAPI.common.enums import OrderStatuses
                        order_confirmed = getattr(order, "status", None) == OrderStatuses.CLOSED
                        review_left = getattr(order, "review", None) is not None
                except Exception as e:
                    logger.warning(f"Could not check order {order_id} status: {e}")
            
            # Собираем сообщение из частей
            parts: list[str] = [
                get_msg(self._storage, "rental_expired", game_id=game_id, login=login),
            ]
            
            if not order_confirmed:
                parts.append(get_msg(
                    self._storage, "rental_expired_confirm", order_id=order_id,
                ))
            
            if not review_left:
                parts.append(get_msg(
                    self._storage, "rental_expired_review", order_id=order_id,
                ))
            
            message = "\n\n".join(parts)
            
            await self._on_send_warning(rental_id, chat_id, message, chat_name)
            
            logger.info(
                f"[EXPIRED] Notification sent for rental {rental_id} "
                f"(confirmed={order_confirmed}, review={review_left})"
            )
        except Exception as e:
            logger.error(f"Error sending expired notification for {rental_id}: {e}")
    
    async def _check_expiry_warnings(self) -> None:
        """Отправляет предупреждения покупателям о скором истечении аренды."""
        if self._expiry_warning_minutes <= 0 or self._on_send_warning is None:
            return
        
        from .models.rental import RentalStatus, format_remaining_time
        from .messages import get_msg
        
        threshold = timedelta(minutes=self._expiry_warning_minutes)
        
        for rental in self._storage.get_active_rentals():
            if rental.warning_sent:
                continue
            if rental.status != RentalStatus.ACTIVE:
                continue
            if not rental.chat_id:
                continue
            
            remaining = rental.remaining_time
            if remaining <= timedelta(0):
                continue  # already expired, _check_expired handles it
            
            if remaining <= threshold:
                try:
                    message = get_msg(
                        self._storage, "expiry_warning",
                        game_id=rental.game_id,
                        login=rental.delivered_login,
                        remaining=format_remaining_time(remaining),
                    )
                    await self._on_send_warning(
                        rental.rental_id, rental.chat_id, message,
                        rental.chat_name,
                    )
                    rental.warning_sent = True
                    self._storage.update_rental(rental)
                    logger.info(
                        f"[WARNING] Expiry warning sent for rental {rental.rental_id} "
                        f"(buyer={rental.buyer_username}, remaining={remaining})"
                    )
                except Exception as e:
                    logger.error(f"Error sending expiry warning for {rental.rental_id}: {e}")
    
    def _cleanup_stale_pending(self) -> None:
        """Удаляет PendingOrder, просроченные по TTL. TTL=0 — безлимит (не удалять)."""
        if self._pending_ttl_minutes <= 0:
            return
        
        pending_orders = self._storage.get_pending_orders()
        if not pending_orders:
            return
        
        now = datetime.now()
        cutoff = now - timedelta(minutes=self._pending_ttl_minutes)
        stale_ids: list[str] = []
        
        for p in pending_orders:
            try:
                created = datetime.fromisoformat(p.created_at)
                if created < cutoff:
                    stale_ids.append(p.order_id)
            except (ValueError, TypeError):
                # Некорректная дата - считаем просроченным
                stale_ids.append(p.order_id)
        
        for order_id in stale_ids:
            self._storage.remove_pending_order(order_id)
            logger.info(f"[CLEANUP] Removed stale pending order {order_id} (TTL: {self._pending_ttl_minutes}min)")
    
    async def _process_pending_reviews(self) -> None:
        """
        Обрабатывает отложенные проверки отзывов.
        
        Для каждого PendingReview:
        1. Вызывает on_review_check(order_id) → order object
        2. Извлекает order.review.stars
        3. Вызывает handlers.resolve_pending_review()
        
        Если on_review_check не задан (Chat 1 не подключил),
        отзывы остаются в очереди — ничего не теряется.
        """
        if self._on_review_check is None:
            return
        
        pending_reviews = self._storage.get_pending_reviews()
        if not pending_reviews:
            return
        
        logger.debug(f"Processing {len(pending_reviews)} pending review(s)")
        
        # Импорт здесь чтобы избежать circular import
        from . import handlers
        
        for pr in list(pending_reviews):
            try:
                order = await self._on_review_check(pr.order_id)
                
                if order is None:
                    # get_order вернул None — заказ не найден
                    handlers.resolve_pending_review(
                        pr.order_id, None, pr.review_type, self._storage
                    )
                    continue
                
                # Извлекаем stars из order.review
                review = getattr(order, "review", None)
                stars = getattr(review, "stars", None) if review else None
                
                handlers.resolve_pending_review(
                    pr.order_id, stars, pr.review_type, self._storage
                )
            except Exception as e:
                logger.error(f"Error processing pending review for order {pr.order_id}: {e}")
    
    @property
    def is_running(self) -> bool:
        """Запущен ли планировщик."""
        return self._running
