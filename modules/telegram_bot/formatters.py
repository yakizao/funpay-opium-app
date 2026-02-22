# -*- coding: utf-8 -*-
"""
Telegram Bot - Event Formatters.

Преобразует OpiumEvent в читаемые HTML-сообщения для Telegram.

Интеграция с другими модулями:
    from modules.telegram_bot.formatters import register_formatter

    def my_formatter(event: OpiumEvent) -> str | None:
        return f"Custom: {event.payload}"

    register_formatter("my_custom_event", my_formatter)
"""

from __future__ import annotations

import html
import logging
from typing import Any, Callable

from core.event_bus import OpiumEvent

logger = logging.getLogger("opium.telegram_bot.formatters")

# Type alias
Formatter = Callable[[OpiumEvent], str | None]

# Реестр кастомных форматтеров (точка интеграции для других модулей)
_custom_formatters: dict[str, Formatter] = {}


def register_formatter(event_type: str, formatter: Formatter) -> None:
    """
    Регистрирует кастомный форматтер для типа события.

    Другие модули могут вызвать эту функцию для добавления
    своих форматов уведомлений:

        from modules.telegram_bot.formatters import register_formatter

        def format_rental_expired(event: OpiumEvent) -> str:
            p = event.payload
            return f"⏰ Аренда истекла: {p.get('game_id')}"

        register_formatter("rental_expired", format_rental_expired)
    """
    _custom_formatters[event_type] = formatter
    logger.debug(f"Registered custom formatter for event: {event_type}")


def get_registered_formatters() -> dict[str, Formatter]:
    """Возвращает все зарегистрированные кастомные форматтеры."""
    return dict(_custom_formatters)


def format_event(event: OpiumEvent) -> str | None:
    """
    Форматирует OpiumEvent в HTML-строку для Telegram.

    Приоритет:
    1. Кастомные форматтеры (зарегистрированные другими модулями)
    2. Встроенные форматтеры
    3. Общий формат (fallback)

    Returns:
        HTML-строка или None (если событие не нужно отправлять)
    """
    result: str | None = None
    handled = False  # форматтер найден (даже если вернул None = "не отправлять")

    # 1. Кастомный форматтер
    if event.event_type in _custom_formatters:
        handled = True
        try:
            result = _custom_formatters[event.event_type](event)
        except Exception as e:
            logger.warning(f"Custom formatter error for {event.event_type}: {e}")

    # 2. Встроенный форматтер
    if not handled:
        formatter = _BUILTIN_FORMATTERS.get(event.event_type)
        if formatter:
            handled = True
            try:
                result = formatter(event)
            except Exception as e:
                logger.warning(f"Builtin formatter error for {event.event_type}: {e}")

    # 3. Fallback — только для неизвестных типов (без форматтера)
    if not handled:
        result = _format_generic(event)

    # None = форматтер решил не отправлять (напр. собственное сообщение)
    if not result:
        return None

    # Подпись аккаунта (чтобы различать при одном боте на N аккаунтов)
    return f"[{html.escape(event.account_id)}] {result}"


# ═══════════════════════════════════════════════════════
# Встроенные форматтеры
# ═══════════════════════════════════════════════════════


def _format_new_order(event: OpiumEvent) -> str:
    order = event.payload.get("order", {})
    order_id = order.get("id", "?")
    desc = html.escape(order.get("description", ""))
    buyer = html.escape(order.get("buyer_username", ""))
    price = order.get("price", "?")
    currency = html.escape(str(order.get("currency", "")))
    status = order.get("status", "")

    lines = [
        f"🛒 <b>Новый заказ</b> #{order_id}",
        desc,
        f"Покупатель: {buyer}",
        f"Сумма: {price} {currency}".strip(),
    ]
    if status:
        lines.append(f"Статус: {html.escape(str(status))}")

    return "\n".join(lines)


def _format_new_message(event: OpiumEvent) -> str | None:
    msg = event.payload.get("message", {})

    # Пропускаем собственные сообщения (бот или ручной ввод владельца)
    if msg.get("by_bot"):
        return None
    fp_user_id = event.payload.get("fp_user_id")
    if fp_user_id and msg.get("author_id") == fp_user_id:
        return None

    author = html.escape(msg.get("author") or msg.get("chat_name") or "?")
    text = msg.get("text") or ""

    if not text:
        if msg.get("image_link"):
            text = "[изображение]"
        else:
            return None

    text = html.escape(text)

    # Обрезаем длинные сообщения
    if len(text) > 500:
        text = text[:497] + "..."

    return f"💬 <b>Сообщение</b> от {author}\n{text}"


def _format_order_status_changed(event: OpiumEvent) -> str:
    order = event.payload.get("order", {})
    order_id = order.get("id", "?")
    status = html.escape(str(order.get("status", "?")))
    desc = html.escape(order.get("description", ""))

    return (
        f"📋 <b>Статус заказа</b> #{order_id}\n"
        f"Статус: {status}\n"
        f"{desc}"
    )


def _format_orders_list_changed(event: OpiumEvent) -> str:
    purchases = event.payload.get("purchases", 0)
    sales = event.payload.get("sales", 0)
    return (
        f"📊 <b>Обновление заказов</b>\n"
        f"Покупки: {purchases} | Продажи: {sales}"
    )


def _format_generic(event: OpiumEvent) -> str:
    """Общий формат для неизвестных типов событий."""
    return (
        f"📌 <b>{html.escape(event.event_type)}</b>\n"
        f"Аккаунт: {html.escape(event.account_id)}"
    )


_BUILTIN_FORMATTERS: dict[str, Formatter] = {
    "new_order": _format_new_order,
    "new_message": _format_new_message,
    "order_status_changed": _format_order_status_changed,
    "orders_list_changed": _format_orders_list_changed,
}
