"""Opium Converters - конвертеры FunPayAPI событий в OpiumEvent.

Канонические сериализаторы для payload'ов.
"""

from __future__ import annotations

from typing import Any

from FunPayAPI.updater.events import (
    InitialChatEvent,
    ChatsListChangedEvent,
    LastChatMessageChangedEvent,
    NewMessageEvent,
    InitialOrderEvent,
    OrdersListChangedEvent,
    NewOrderEvent,
    OrderStatusChangedEvent,
)
from FunPayAPI.common.enums import MessageTypes, OrderStatuses

from .event_bus import OpiumEvent

import logging

logger = logging.getLogger("opium.converters")


# ═══════════════════════════════════════════════════════════
# Маппинг FunPayAPI событий на типы OpiumEvent
# ═══════════════════════════════════════════════════════════

_EVENT_TYPE_MAP: dict[type, str] = {
    InitialChatEvent: "initial_chat",
    ChatsListChangedEvent: "chats_list_changed",
    LastChatMessageChangedEvent: "last_message_changed",
    NewMessageEvent: "new_message",
    InitialOrderEvent: "initial_order",
    OrdersListChangedEvent: "orders_list_changed",
    NewOrderEvent: "new_order",
    OrderStatusChangedEvent: "order_status_changed",
}


# ═══════════════════════════════════════════════════════════
# Канонические сериализаторы (Problem 1)
# Публичные — другие модули импортируют отсюда.
# Используют getattr() для защиты от отсутствующих атрибутов.
# ═══════════════════════════════════════════════════════════

def serialize_message(message: Any) -> dict[str, Any]:
    """Сериализует объект Message в dict."""
    msg_type = getattr(message, "type", None)
    return {
        "id": getattr(message, "id", 0),
        "text": getattr(message, "text", None),
        "chat_id": getattr(message, "chat_id", 0),
        "chat_name": getattr(message, "chat_name", None),
        "author": getattr(message, "author", None),
        "author_id": getattr(message, "author_id", 0),
        "type": msg_type.value if isinstance(msg_type, MessageTypes) else (msg_type or 0),
        "image_link": getattr(message, "image_link", None),
        "by_bot": getattr(message, "by_bot", False),
        "badge": getattr(message, "badge", None),
    }


def serialize_chat_shortcut(chat: Any) -> dict[str, Any]:
    """Сериализует объект ChatShortcut в dict."""
    lmt = getattr(chat, "last_message_type", None)
    return {
        "id": getattr(chat, "id", 0),
        "name": getattr(chat, "name", ""),
        "last_message_text": getattr(chat, "last_message_text", ""),
        "unread": getattr(chat, "unread", False),
        "last_message_type": lmt.value if isinstance(lmt, MessageTypes) else (lmt or 0),
    }


def serialize_order_shortcut(order: Any) -> dict[str, Any]:
    """Сериализует объект OrderShortcut в dict."""
    status = getattr(order, "status", None)
    date = getattr(order, "date", None)
    return {
        "id": getattr(order, "id", ""),
        "description": getattr(order, "description", ""),
        "price": getattr(order, "price", 0),
        "currency": getattr(order, "currency", None),
        "amount": getattr(order, "amount", 1),
        "buyer_username": getattr(order, "buyer_username", ""),
        "buyer_id": getattr(order, "buyer_id", 0),
        "status": status.value if isinstance(status, OrderStatuses) else (status or ""),
        "date": date.isoformat() if hasattr(date, "isoformat") else str(date) if date else None,
        "subcategory_name": getattr(order, "subcategory_name", None),
    }


# ═══════════════════════════════════════════════════════════
# Конвертер событий
# ═══════════════════════════════════════════════════════════

def convert_event(account_id: str, event: Any) -> OpiumEvent | None:
    """
    Конвертирует FunPayAPI событие в OpiumEvent.

    Args:
        account_id: ID аккаунта
        event: FunPayAPI событие

    Returns:
        OpiumEvent или None если тип события неизвестен
    """
    event_type = _EVENT_TYPE_MAP.get(type(event))

    if event_type is None:
        logger.warning(
            f"[{account_id}] Unknown FunPayAPI event type: {type(event).__name__}"
        )
        return None

    payload: dict[str, Any] = {}

    # Обработка событий чатов
    if isinstance(event, NewMessageEvent):
        payload = {
            "message": serialize_message(event.message),
            "chat_id": event.message.chat_id,
        }
        # Добавляем стек сообщений если есть
        if event.stack:
            stack_events = event.stack.get_stack()
            if stack_events:
                payload["stack"] = [serialize_message(e.message) for e in stack_events]
        
        msg = event.message
        logger.debug(
            f"[{account_id}] Converted {event_type}: "
            f"chat={msg.chat_id}, author={getattr(msg, 'author', '?')} "
            f"(id={getattr(msg, 'author_id', 0)}), "
            f"type={getattr(msg, 'type', 0)}, "
            f"text=\"{(getattr(msg, 'text', '') or '')[:60]}\"{'...' if len(getattr(msg, 'text', '') or '') > 60 else ''}"
        )

    elif isinstance(event, (InitialChatEvent, LastChatMessageChangedEvent)):
        payload = {
            "chat": serialize_chat_shortcut(event.chat),
            "chat_id": event.chat.id,
        }
        logger.debug(
            f"[{account_id}] Converted {event_type}: "
            f"chat={event.chat.id}, name={getattr(event.chat, 'name', '?')}"
        )

    elif isinstance(event, ChatsListChangedEvent):
        payload = {}
        logger.debug(f"[{account_id}] Converted {event_type}")

    # Обработка событий заказов
    elif isinstance(event, (NewOrderEvent, OrderStatusChangedEvent, InitialOrderEvent)):
        payload = {
            "order": serialize_order_shortcut(event.order),
            "order_id": event.order.id,
        }
        order = event.order
        logger.debug(
            f"[{account_id}] Converted {event_type}: "
            f"order={order.id}, desc=\"{getattr(order, 'description', '?')[:50]}\", "
            f"buyer={getattr(order, 'buyer_username', '?')}, "
            f"price={getattr(order, 'price', 0)}"
        )

    elif isinstance(event, OrdersListChangedEvent):
        payload = {
            "purchases": event.purchases,
            "sales": event.sales,
        }
        logger.debug(
            f"[{account_id}] Converted {event_type}: "
            f"purchases={event.purchases}, sales={event.sales}"
        )

    return OpiumEvent(
        account_id=account_id,
        event_type=event_type,
        payload=payload,
        raw=event,
    )
