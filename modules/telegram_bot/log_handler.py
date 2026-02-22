# -*- coding: utf-8 -*-
"""
Telegram Bot - Log Handler.

logging.Handler, который перехватывает лог-записи по заданным паттернам
и пересылает их в Telegram. Ни один модуль не нужно менять — они уже
пишут через стандартный logging.getLogger("opium.xxx").

Паттерн — обычная подстрока (не regex). Если подстрока найдена в
форматированном лог-сообщении → отправляем.
"""

from __future__ import annotations

import asyncio
import html
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .bot import TelegramBot
    from .storage import TelegramBotStorage

logger = logging.getLogger("opium.telegram_bot.log_handler")


class TelegramLogHandler(logging.Handler):
    """
    Ловит лог-записи из любого логгера opium.* и отправляет в Telegram
    если сообщение совпадает с одним из настроенных паттернов.
    """

    def __init__(
        self,
        storage: "TelegramBotStorage",
        bot: "TelegramBot",
        account_id: str,
    ) -> None:
        super().__init__(level=logging.DEBUG)
        self._storage = storage
        self._bot = bot
        self._account_id = account_id
        self._loop: asyncio.AbstractEventLoop | None = None

    def attach(self) -> None:
        """Вешает handler на корневой логгер opium."""
        self._loop = asyncio.get_event_loop()
        root = logging.getLogger("opium")
        root.addHandler(self)
        logger.debug("TelegramLogHandler attached to opium.*")

    def detach(self) -> None:
        """Снимает handler."""
        root = logging.getLogger("opium")
        root.removeHandler(self)
        logger.debug("TelegramLogHandler detached")

    def emit(self, record: logging.LogRecord) -> None:
        """Вызывается logging для каждой записи."""
        # Не ловим свои собственные логи (избегаем рекурсии)
        if record.name.startswith("opium.telegram_bot"):
            return

        if not self._bot or not self._bot.is_running:
            return

        try:
            watchers = self._storage.get_log_watchers()
            if not watchers:
                return

            # Форматируем как в консоли
            formatted = self.format(record) if self.formatter else record.getMessage()

            for w in watchers:
                if not w.get("enabled", True):
                    continue

                pattern = w.get("pattern", "")
                if not pattern:
                    continue

                if pattern not in formatted:
                    continue

                # Совпадение! Формируем текст для TG
                custom = w.get("custom_message", "").strip()
                if custom:
                    text = f"[{html.escape(self._account_id)}] {html.escape(custom)}"
                else:
                    # Отправляем сам лог
                    text = f"[{html.escape(self._account_id)}] <pre>{html.escape(formatted)}</pre>"

                # Отправляем асинхронно
                user_ids = self._storage.get_whitelisted_ids()
                if user_ids and self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(
                        asyncio.ensure_future,
                        self._safe_broadcast(user_ids, text),
                    )
                break  # один лог — один match (первый подходящий watcher)

        except Exception:
            # Никогда не ломаем logging
            pass

    async def _safe_broadcast(self, user_ids: list[int], text: str) -> None:
        """Broadcast с подавлением ошибок."""
        try:
            await self._bot.broadcast(user_ids, text)
        except Exception as e:
            # Логгируем через print чтобы не вызвать рекурсию
            pass
