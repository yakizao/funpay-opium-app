# -*- coding: utf-8 -*-
"""
Telegram Bot Module - уведомления и мониторинг через Telegram.

Функционал:
- Уведомления о новых заказах, сообщениях, изменениях статусов
- Вайтлист по Telegram ID
- Команды бота (/start, /status, /events, /help)
- Расширяемая система форматирования (интеграции с другими модулями)

Использование:
1. Добавить модуль в аккаунт: создать папку accounts/{id}/modules/telegram_bot/
2. Настроить через UI: указать токен бота, добавить ID в вайтлист

Структура файлов:
    accounts/{id}/modules/telegram_bot/
    ├── config.json        # Настройки (bot_token, notify_events)
    ├── whitelist.json     # Список разрешённых Telegram ID
    └── event_log.json     # Лог отправленных уведомлений
"""

from .module import TelegramBotModule
from .storage import TelegramBotStorage
from .bot import TelegramBot
from .formatters import format_event, register_formatter

__all__ = [
    "TelegramBotModule",
    "TelegramBotStorage",
    "TelegramBot",
    "format_event",
    "register_formatter",
]
