"""Opium Event Bus - асинхронная шина событий."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from datetime import datetime


logger = logging.getLogger("opium.event_bus")


@dataclass
class OpiumEvent:
    """
    Событие Opium - обёртка над FunPayAPI событием.
    
    Attributes:
        account_id: ID аккаунта, от которого пришло событие
        event_type: Тип события (new_message, new_order, etc.)
        payload: Сериализованные данные события
        timestamp: UNIX timestamp получения события
        raw: Оригинальный FunPayAPI event (опционально)
    """
    
    account_id: str
    event_type: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())
    raw: Any = None
    
    def __repr__(self) -> str:
        return f"OpiumEvent({self.event_type}, account={self.account_id})"


@dataclass
class _Subscription:
    """Внутреннее представление подписки."""
    
    handler: Callable[[OpiumEvent], Awaitable[None]]
    event_types: set[str] | None
    account_ids: set[str] | None


class EventBus:
    """
    Асинхронная шина событий с фильтрацией.
    
    Поддерживает:
    - Подписку на определённые типы событий
    - Подписку на определённые аккаунты
    - Fan-out (одно событие → много обработчиков)
    - Асинхронную обработку
    """
    
    def __init__(self) -> None:
        self._subscriptions: dict[str, _Subscription] = {}
        self._queue: asyncio.Queue[OpiumEvent] = asyncio.Queue()
        self._running: bool = False
        self._processor_task: asyncio.Task | None = None
    
    def subscribe(
        self,
        handler: Callable[[OpiumEvent], Awaitable[None]],
        event_types: list[str] | None = None,
        account_ids: list[str] | None = None,
    ) -> str:
        """
        Подписывает обработчик на события.
        
        Args:
            handler: Асинхронная функция-обработчик
            event_types: Фильтр по типам событий (None = все)
            account_ids: Фильтр по аккаунтам (None = все)
            
        Returns:
            ID подписки для последующей отписки
        """
        subscription_id = str(uuid.uuid4())
        
        self._subscriptions[subscription_id] = _Subscription(
            handler=handler,
            event_types=set(event_types) if event_types else None,
            account_ids=set(account_ids) if account_ids else None,
        )
        
        logger.debug(
            f"Subscribe {handler.__qualname__}: "
            f"events={event_types or 'ALL'}, accounts={account_ids or 'ALL'} "
            f"(sub_id={subscription_id[:8]})"
        )
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Отписывает обработчик.
        
        Args:
            subscription_id: ID подписки
            
        Returns:
            True если подписка была найдена и удалена
        """
        if subscription_id in self._subscriptions:
            sub = self._subscriptions[subscription_id]
            logger.debug(
                f"Unsubscribe {sub.handler.__qualname__} (sub_id={subscription_id[:8]})"
            )
            del self._subscriptions[subscription_id]
            return True
        return False
    
    async def publish(self, event: OpiumEvent) -> None:
        """
        Публикует событие в шину.
        
        Args:
            event: Событие для публикации
        """
        logger.debug(
            f"[{event.account_id}] Event published: {event.event_type} "
            f"(queue_size={self._queue.qsize()})"
        )
        await self._queue.put(event)
    
    async def _process_event(self, event: OpiumEvent) -> None:
        """Обрабатывает одно событие, вызывая подходящие обработчики."""
        tasks = []
        matched_handlers: list[str] = []
        
        # Snapshot: копируем список подписок, чтобы handler мог
        # безопасно вызывать subscribe/unsubscribe во время обработки.
        subscriptions = list(self._subscriptions.values())
        
        for sub in subscriptions:
            # Проверяем фильтр по типу события
            if sub.event_types and event.event_type not in sub.event_types:
                continue
            
            # Проверяем фильтр по аккаунту
            if sub.account_ids and event.account_id not in sub.account_ids:
                continue
            
            # Создаём задачу для обработчика
            matched_handlers.append(sub.handler.__qualname__)
            tasks.append(asyncio.create_task(self._safe_call(sub.handler, event)))
        
        logger.debug(
            f"[{event.account_id}] Processing {event.event_type}: "
            f"{len(tasks)}/{len(subscriptions)} handlers matched "
            f"({', '.join(matched_handlers) if matched_handlers else 'none'})"
        )
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _safe_call(
        self, 
        handler: Callable[[OpiumEvent], Awaitable[None]], 
        event: OpiumEvent
    ) -> None:
        """Безопасный вызов обработчика с перехватом исключений."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"Handler {handler.__qualname__} failed on {event}: {e}",
                exc_info=True,
            )
    
    async def _processor_loop(self) -> None:
        """Основной цикл обработки событий."""
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                await self._process_event(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    async def start(self) -> None:
        """Запускает обработку событий."""
        if self._running:
            return
        
        self._running = True
        self._processor_task = asyncio.create_task(self._processor_loop())
        logger.info(f"EventBus started ({self.subscription_count} subscriptions)")
    
    async def stop(self) -> None:
        """Останавливает обработку событий с graceful drain очереди."""
        self._running = False
        
        # Graceful drain: обрабатываем оставшиеся события в очереди
        drained = 0
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                await self._process_event(event)
                self._queue.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error draining event: {e}")
        
        if drained:
            logger.info(f"EventBus drained {drained} pending events")
        
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
            self._processor_task = None
        
        logger.info("EventBus stopped")
    
    @property
    def subscription_count(self) -> int:
        """Количество активных подписок."""
        return len(self._subscriptions)
    
    @property
    def queue_size(self) -> int:
        """Размер очереди событий."""
        return self._queue.qsize()
