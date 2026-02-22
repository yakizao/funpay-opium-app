# -*- coding: utf-8 -*-
"""
Telegram Bot - Storage.

Типизированная обёртка над ModuleStorage.
Хранит конфигурацию, вайтлист и лог событий.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.storage import ModuleStorage

logger = logging.getLogger("opium.telegram_bot.storage")

# Максимальное количество записей в логе событий
MAX_EVENT_LOG = 200

# Типы событий по умолчанию для уведомлений
DEFAULT_NOTIFY_EVENTS = [
    "new_order",
    "new_message",
    "order_status_changed",
]

# Все доступные типы событий (для UI фильтрации)
ALL_EVENT_TYPES = [
    {"key": "new_message", "label": "Новое сообщение"},
    {"key": "new_order", "label": "Новый заказ"},
    {"key": "order_status_changed", "label": "Изменение статуса заказа"},
    {"key": "orders_list_changed", "label": "Обновление списка заказов"},
    {"key": "initial_chat", "label": "Начальный чат (запуск)"},
    {"key": "initial_order", "label": "Начальный заказ (запуск)"},
    {"key": "chats_list_changed", "label": "Обновление списка чатов"},
    {"key": "last_message_changed", "label": "Изменение последнего сообщения"},
]


class TelegramBotStorage:
    """Типизированное хранилище модуля telegram_bot."""

    def __init__(self, storage: "ModuleStorage") -> None:
        self._storage = storage

    # ─── Config ─────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        return self._storage.config

    def save_config(self, config: dict[str, Any]) -> None:
        self._storage.save_config(config)

    def get_bot_token(self) -> str:
        return self.get_config().get("bot_token", "")

    def set_bot_token(self, token: str) -> None:
        cfg = self.get_config().copy()
        cfg["bot_token"] = token
        self.save_config(cfg)

    def get_notify_events(self) -> list[str]:
        return self.get_config().get("notify_events", list(DEFAULT_NOTIFY_EVENTS))

    def set_notify_events(self, events: list[str]) -> None:
        cfg = self.get_config().copy()
        cfg["notify_events"] = events
        self.save_config(cfg)

    # ─── Whitelist ──────────────────────────────────

    def get_whitelist(self) -> list[dict[str, Any]]:
        """Возвращает вайтлист [{telegram_id: int, label: str}, ...]."""
        data = self._storage.read_json("whitelist.json")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def save_whitelist(self, whitelist: list[dict[str, Any]]) -> None:
        self._storage.write_json("whitelist.json", whitelist)

    def add_to_whitelist(self, telegram_id: int, label: str = "") -> bool:
        """Добавляет пользователя в вайтлист. Возвращает False если уже есть."""
        wl = self.get_whitelist()
        if any(u["telegram_id"] == telegram_id for u in wl):
            return False
        wl.append({"telegram_id": telegram_id, "label": label})
        self.save_whitelist(wl)
        return True

    def remove_from_whitelist(self, telegram_id: int) -> bool:
        """Удаляет пользователя из вайтлиста. Возвращает False если не найден."""
        wl = self.get_whitelist()
        new_wl = [u for u in wl if u["telegram_id"] != telegram_id]
        if len(new_wl) == len(wl):
            return False
        self.save_whitelist(new_wl)
        return True

    def update_whitelist_label(self, telegram_id: int, label: str) -> bool:
        """Обновляет label пользователя в вайтлисте."""
        wl = self.get_whitelist()
        for u in wl:
            if u["telegram_id"] == telegram_id:
                u["label"] = label
                self.save_whitelist(wl)
                return True
        return False

    def is_whitelisted(self, telegram_id: int) -> bool:
        return any(u["telegram_id"] == telegram_id for u in self.get_whitelist())

    def get_whitelisted_ids(self) -> list[int]:
        return [u["telegram_id"] for u in self.get_whitelist()]

    # ─── Event Log ──────────────────────────────────

    def get_event_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Возвращает последние события (новые в конце)."""
        data = self._storage.read_json("event_log.json")
        if data is None:
            return []
        events = data if isinstance(data, list) else []
        return events[-limit:]

    def append_event(self, event: dict[str, Any]) -> None:
        """Добавляет событие в лог (автоматический timestamp + ротация)."""
        events = self.get_event_log(MAX_EVENT_LOG)
        events.append({
            **event,
            "timestamp": datetime.now().isoformat(),
        })
        # Ротация — оставляем только последние MAX_EVENT_LOG
        if len(events) > MAX_EVENT_LOG:
            events = events[-MAX_EVENT_LOG:]
        self._storage.write_json("event_log.json", events)

    def clear_event_log(self) -> None:
        """Очищает лог событий."""
        self._storage.write_json("event_log.json", [])

    # ─── Log Watchers ──────────────────────────────

    def get_log_watchers(self) -> list[dict[str, Any]]:
        """
        Возвращает список наблюдателей за логами.

        Каждый watcher:
        {
            "id": str (uuid),
            "pattern": str (подстрока для поиска в лог-сообщении),
            "custom_message": str (опционально, замена текста),
            "enabled": bool
        }
        """
        data = self._storage.read_json("log_watchers.json")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def save_log_watchers(self, watchers: list[dict[str, Any]]) -> None:
        self._storage.write_json("log_watchers.json", watchers)

    def add_log_watcher(
        self, pattern: str, custom_message: str = "", enabled: bool = True,
    ) -> dict[str, Any]:
        """Добавляет новый watcher. Возвращает созданный объект."""
        import uuid
        watchers = self.get_log_watchers()
        watcher = {
            "id": str(uuid.uuid4())[:8],
            "pattern": pattern,
            "custom_message": custom_message,
            "enabled": enabled,
        }
        watchers.append(watcher)
        self.save_log_watchers(watchers)
        return watcher

    def update_log_watcher(self, watcher_id: str, updates: dict[str, Any]) -> bool:
        """Обновляет watcher по ID. Возвращает False если не найден."""
        watchers = self.get_log_watchers()
        for w in watchers:
            if w["id"] == watcher_id:
                for k in ("pattern", "custom_message", "enabled"):
                    if k in updates:
                        w[k] = updates[k]
                self.save_log_watchers(watchers)
                return True
        return False

    def remove_log_watcher(self, watcher_id: str) -> bool:
        """Удаляет watcher по ID."""
        watchers = self.get_log_watchers()
        new = [w for w in watchers if w["id"] != watcher_id]
        if len(new) == len(watchers):
            return False
        self.save_log_watchers(new)
        return True

    # ─── Bot Buttons ───────────────────────────────

    def get_bot_buttons(self) -> list[dict[str, Any]]:
        """
        Возвращает список кнопок бота.

        Каждая кнопка:
        {
            "id": str,
            "label": str,        # Текст кнопки в Telegram (с эмодзи)
            "api_endpoint": str,  # /api/accounts/.../...
            "api_method": str,    # GET / POST / DELETE
            "api_body": dict|None,# Тело для POST
            "description": str,   # Описание (для UI)
            "confirm": bool,      # Подтверждение перед выполнением
            "enabled": bool
        }
        """
        data = self._storage.read_json("bot_buttons.json")
        if data is None:
            return []
        return data if isinstance(data, list) else []

    def save_bot_buttons(self, buttons: list[dict[str, Any]]) -> None:
        self._storage.write_json("bot_buttons.json", buttons)

    def add_bot_button(
        self,
        label: str,
        api_endpoint: str,
        api_method: str = "GET",
        api_body: dict[str, Any] | None = None,
        description: str = "",
        confirm: bool = False,
        enabled: bool = True,
    ) -> dict[str, Any]:
        """Добавляет кнопку. Возвращает созданный объект."""
        import uuid
        buttons = self.get_bot_buttons()
        button = {
            "id": str(uuid.uuid4())[:8],
            "label": label,
            "api_endpoint": api_endpoint,
            "api_method": api_method.upper(),
            "api_body": api_body,
            "description": description,
            "confirm": confirm,
            "enabled": enabled,
        }
        buttons.append(button)
        self.save_bot_buttons(buttons)
        return button

    def update_bot_button(self, button_id: str, updates: dict[str, Any]) -> bool:
        """Обновляет кнопку по ID."""
        buttons = self.get_bot_buttons()
        for b in buttons:
            if b["id"] == button_id:
                for k in ("label", "api_endpoint", "api_method", "api_body",
                           "description", "confirm", "enabled"):
                    if k in updates:
                        b[k] = updates[k]
                self.save_bot_buttons(buttons)
                return True
        return False

    def remove_bot_button(self, button_id: str) -> bool:
        """Удаляет кнопку по ID."""
        buttons = self.get_bot_buttons()
        new = [b for b in buttons if b["id"] != button_id]
        if len(new) == len(buttons):
            return False
        self.save_bot_buttons(new)
        return True

    def get_bot_button_by_id(self, button_id: str) -> dict[str, Any] | None:
        """Находит кнопку по ID."""
        for b in self.get_bot_buttons():
            if b["id"] == button_id:
                return b
        return None
