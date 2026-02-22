# -*- coding: utf-8 -*-
"""
Telegram Bot - REST API Router.

CRUD эндпоинты для настроек модуля Telegram Bot.
Автоматически монтируется api/main.py через pkgutil авто-обнаружение.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.deps import get_module
from .storage import TelegramBotStorage, ALL_EVENT_TYPES

logger = logging.getLogger("opium.api.telegram_bot")


def _get_storage(account_id: str) -> TelegramBotStorage:
    """Получает TelegramBotStorage для аккаунта или кидает 404."""
    module = get_module(account_id, "telegram_bot")
    return module.tg_storage  # type: ignore[attr-defined]


def _get_module(account_id: str):
    """Получает TelegramBotModule для аккаунта."""
    return get_module(account_id, "telegram_bot")


router = APIRouter(
    prefix="/api/accounts/{account_id}/modules/telegram_bot",
    tags=["telegram_bot"],
)


# ═══════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════


class ConfigUpdate(BaseModel):
    bot_token: str | None = None
    notify_events: list[str] | None = None


@router.get("/config")
async def get_config(account_id: str) -> dict[str, Any]:
    """Возвращает конфигурацию модуля (токен маскируется)."""
    storage = _get_storage(account_id)
    config = storage.get_config()

    # Маскируем токен
    token = config.get("bot_token", "")
    masked_token = ""
    if token:
        masked_token = token[:4] + ":" + "*" * 20 if ":" in token else "***"

    return {
        "bot_token": masked_token,
        "has_token": bool(token),
        "notify_events": storage.get_notify_events(),
        "available_events": ALL_EVENT_TYPES,
    }


@router.patch("/config")
async def update_config(account_id: str, body: ConfigUpdate) -> dict[str, Any]:
    """Обновляет конфигурацию. При смене токена перезапускает бота."""
    storage = _get_storage(account_id)
    module = _get_module(account_id)
    restart_needed = False

    if body.bot_token is not None:
        # Не обновляем если передана маска
        if "***" not in body.bot_token:
            storage.set_bot_token(body.bot_token)
            restart_needed = True

    if body.notify_events is not None:
        storage.set_notify_events(body.notify_events)

    # Перезапускаем бота при смене токена
    if restart_needed and hasattr(module, "restart_bot"):
        ok = await module.restart_bot()
        if not ok and body.bot_token:
            raise HTTPException(400, "Invalid bot token — bot restart failed")

    return {"ok": True, "restarted": restart_needed}


# ═══════════════════════════════════════════════════════
# Whitelist
# ═══════════════════════════════════════════════════════


class WhitelistAdd(BaseModel):
    telegram_id: int
    label: str = ""


class WhitelistUpdate(BaseModel):
    label: str


@router.get("/whitelist")
async def get_whitelist(account_id: str) -> list[dict[str, Any]]:
    """Возвращает вайтлист."""
    return _get_storage(account_id).get_whitelist()


@router.post("/whitelist")
async def add_to_whitelist(account_id: str, body: WhitelistAdd) -> dict[str, Any]:
    """Добавляет Telegram ID в вайтлист."""
    storage = _get_storage(account_id)
    if not storage.add_to_whitelist(body.telegram_id, body.label):
        raise HTTPException(409, f"Telegram ID {body.telegram_id} already in whitelist")
    return {"ok": True, "telegram_id": body.telegram_id}


@router.patch("/whitelist/{telegram_id}")
async def update_whitelist_entry(
    account_id: str, telegram_id: int, body: WhitelistUpdate,
) -> dict[str, Any]:
    """Обновляет label пользователя в вайтлисте."""
    storage = _get_storage(account_id)
    if not storage.update_whitelist_label(telegram_id, body.label):
        raise HTTPException(404, f"Telegram ID {telegram_id} not found in whitelist")
    return {"ok": True}


@router.delete("/whitelist/{telegram_id}")
async def remove_from_whitelist(account_id: str, telegram_id: int) -> dict[str, Any]:
    """Удаляет Telegram ID из вайтлиста."""
    storage = _get_storage(account_id)
    if not storage.remove_from_whitelist(telegram_id):
        raise HTTPException(404, f"Telegram ID {telegram_id} not found in whitelist")
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# Events Log
# ═══════════════════════════════════════════════════════


@router.get("/events")
async def get_events(account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    """Возвращает лог отправленных уведомлений (новые в конце)."""
    limit = min(limit, 200)
    return _get_storage(account_id).get_event_log(limit)


@router.delete("/events")
async def clear_events(account_id: str) -> dict[str, Any]:
    """Очищает лог событий."""
    _get_storage(account_id).clear_event_log()
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# Bot Control
# ═══════════════════════════════════════════════════════


@router.get("/bot-info")
async def get_bot_info(account_id: str) -> dict[str, Any]:
    """Возвращает информацию о боте (username, id, статус)."""
    module = _get_module(account_id)
    bot = getattr(module, "bot", None)

    if not bot or not bot.is_running:
        return {"online": False, "username": None, "bot_id": None}

    info = bot.bot_info or {}
    return {
        "online": True,
        "username": info.get("username"),
        "first_name": info.get("first_name"),
        "bot_id": info.get("id"),
    }


@router.post("/restart")
async def restart_bot(account_id: str) -> dict[str, Any]:
    """Перезапускает бота."""
    module = _get_module(account_id)

    if not hasattr(module, "restart_bot"):
        raise HTTPException(500, "Module does not support restart")

    ok = await module.restart_bot()
    if not ok:
        raise HTTPException(400, "Bot restart failed (check token)")

    return {"ok": True}


@router.post("/test")
async def send_test_message(account_id: str) -> dict[str, Any]:
    """Отправляет тестовое сообщение всем в вайтлисте."""
    module = _get_module(account_id)
    bot = getattr(module, "bot", None)

    if not bot or not bot.is_running:
        raise HTTPException(400, "Bot is not running")

    storage = _get_storage(account_id)
    user_ids = storage.get_whitelisted_ids()

    if not user_ids:
        raise HTTPException(400, "Whitelist is empty")

    text = f"🧪 <b>Тест</b>\n\nАккаунт: {account_id}\nБот работает ✅"
    sent = await bot.broadcast(user_ids, text)

    return {"ok": True, "sent": sent, "total": len(user_ids)}


# ═══════════════════════════════════════════════════════
# Log Watchers
# ═══════════════════════════════════════════════════════


class LogWatcherAdd(BaseModel):
    pattern: str
    custom_message: str = ""
    enabled: bool = True


class LogWatcherUpdate(BaseModel):
    pattern: str | None = None
    custom_message: str | None = None
    enabled: bool | None = None


@router.get("/log-watchers")
async def get_log_watchers(account_id: str) -> list[dict[str, Any]]:
    """Возвращает все log watchers."""
    return _get_storage(account_id).get_log_watchers()


@router.post("/log-watchers")
async def add_log_watcher(account_id: str, body: LogWatcherAdd) -> dict[str, Any]:
    """Добавляет новый log watcher."""
    if not body.pattern.strip():
        raise HTTPException(400, "Pattern cannot be empty")
    storage = _get_storage(account_id)
    watcher = storage.add_log_watcher(
        pattern=body.pattern.strip(),
        custom_message=body.custom_message.strip(),
        enabled=body.enabled,
    )
    return watcher


@router.patch("/log-watchers/{watcher_id}")
async def update_log_watcher(
    account_id: str, watcher_id: str, body: LogWatcherUpdate,
) -> dict[str, Any]:
    """Обновляет log watcher."""
    storage = _get_storage(account_id)
    updates: dict[str, Any] = {}
    if body.pattern is not None:
        if not body.pattern.strip():
            raise HTTPException(400, "Pattern cannot be empty")
        updates["pattern"] = body.pattern.strip()
    if body.custom_message is not None:
        updates["custom_message"] = body.custom_message.strip()
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    if not storage.update_log_watcher(watcher_id, updates):
        raise HTTPException(404, f"Log watcher {watcher_id} not found")
    return {"ok": True}


@router.delete("/log-watchers/{watcher_id}")
async def delete_log_watcher(account_id: str, watcher_id: str) -> dict[str, Any]:
    """Удаляет log watcher."""
    storage = _get_storage(account_id)
    if not storage.remove_log_watcher(watcher_id):
        raise HTTPException(404, f"Log watcher {watcher_id} not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# Bot Buttons (Remote Control)
# ═══════════════════════════════════════════════════════


class BotButtonAdd(BaseModel):
    label: str
    api_endpoint: str
    api_method: str = "GET"
    api_body: dict[str, Any] | None = None
    description: str = ""
    confirm: bool = False
    enabled: bool = True


class BotButtonUpdate(BaseModel):
    label: str | None = None
    api_endpoint: str | None = None
    api_method: str | None = None
    api_body: dict[str, Any] | None = None
    description: str | None = None
    confirm: bool | None = None
    enabled: bool | None = None


@router.get("/bot-buttons")
async def get_bot_buttons(account_id: str) -> list[dict[str, Any]]:
    """Возвращает все кнопки бота."""
    return _get_storage(account_id).get_bot_buttons()


@router.post("/bot-buttons")
async def add_bot_button(account_id: str, body: BotButtonAdd) -> dict[str, Any]:
    """Добавляет кнопку бота."""
    if not body.label.strip():
        raise HTTPException(400, "Label cannot be empty")
    if not body.api_endpoint.strip():
        raise HTTPException(400, "API endpoint cannot be empty")

    storage = _get_storage(account_id)
    button = storage.add_bot_button(
        label=body.label.strip(),
        api_endpoint=body.api_endpoint.strip(),
        api_method=body.api_method.upper(),
        api_body=body.api_body,
        description=body.description.strip(),
        confirm=body.confirm,
        enabled=body.enabled,
    )
    return button


@router.patch("/bot-buttons/{button_id}")
async def update_bot_button(
    account_id: str, button_id: str, body: BotButtonUpdate,
) -> dict[str, Any]:
    """Обновляет кнопку бота."""
    storage = _get_storage(account_id)
    updates: dict[str, Any] = {}
    if body.label is not None:
        updates["label"] = body.label.strip()
    if body.api_endpoint is not None:
        updates["api_endpoint"] = body.api_endpoint.strip()
    if body.api_method is not None:
        updates["api_method"] = body.api_method.upper()
    if body.api_body is not None:
        updates["api_body"] = body.api_body
    if body.description is not None:
        updates["description"] = body.description.strip()
    if body.confirm is not None:
        updates["confirm"] = body.confirm
    if body.enabled is not None:
        updates["enabled"] = body.enabled

    if not storage.update_bot_button(button_id, updates):
        raise HTTPException(404, f"Button {button_id} not found")
    return {"ok": True}


@router.delete("/bot-buttons/{button_id}")
async def delete_bot_button(account_id: str, button_id: str) -> dict[str, Any]:
    """Удаляет кнопку бота."""
    storage = _get_storage(account_id)
    if not storage.remove_bot_button(button_id):
        raise HTTPException(404, f"Button {button_id} not found")
    return {"ok": True}
