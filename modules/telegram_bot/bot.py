# -*- coding: utf-8 -*-
"""
Telegram Bot - Bot Client.

Минимальный async Telegram-бот на aiohttp.
Поддерживает long polling, отправку сообщений и broadcast.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

import aiohttp

logger = logging.getLogger("opium.telegram_bot.bot")

API_BASE = "https://api.telegram.org/bot{token}"

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


class TelegramBot:
    """
    Минимальный async Telegram-бот.

    Использует raw Bot API через aiohttp.
    Поддерживает long polling для получения команд
    и broadcast для отправки уведомлений.
    """

    def __init__(
        self,
        token: str,
        on_command: Callable[[str, int, str], Awaitable[str | None]] | None = None,
        on_callback: Callable[[str, int, int], Awaitable[str | None]] | None = None,
    ) -> None:
        """
        Args:
            token: Telegram Bot API token
            on_command: Async callback (command, user_id, text) -> response text or None
            on_callback: Async callback (callback_data, user_id, message_id) -> response text or None
        """
        self._token = token
        self._on_command = on_command
        self._on_callback = on_callback
        self._session: aiohttp.ClientSession | None = None
        self._running: bool = False
        self._task: asyncio.Task | None = None
        self._offset: int = 0
        self._bot_info: dict[str, Any] | None = None

    @property
    def api_url(self) -> str:
        return API_BASE.format(token=self._token)

    @property
    def bot_info(self) -> dict[str, Any] | None:
        """Информация о боте (getMe result)."""
        return self._bot_info

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        """Запускает бота (long polling)."""
        if self._running:
            return

        self._session = aiohttp.ClientSession()

        # Проверяем токен
        me = await self._api_call("getMe")
        if me is None:
            logger.error("Failed to verify bot token (getMe returned None)")
            await self._session.close()
            self._session = None
            return

        self._bot_info = me
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"Telegram bot started: @{me.get('username', '?')}")

    async def stop(self) -> None:
        """Останавливает бота."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._session:
            await self._session.close()
            self._session = None

        logger.info("Telegram bot stopped")

    async def _api_call(self, method: str, **params: Any) -> Any | None:
        """Выполняет вызов Telegram Bot API."""
        if not self._session:
            return None

        url = f"{self.api_url}/{method}"
        try:
            async with self._session.post(
                url,
                json=params,
                timeout=aiohttp.ClientTimeout(total=35),
            ) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    desc = data.get("description", "unknown error")
                    logger.warning(f"Telegram API error ({method}): {desc}")
                    return None
                return data.get("result")
        except asyncio.TimeoutError:
            # Normal for long polling
            if method != "getUpdates":
                logger.warning(f"Telegram API timeout ({method})")
            return None
        except Exception as e:
            logger.error(f"Telegram API call failed ({method}): {e}")
            return None

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Отправляет сообщение. Возвращает True при успехе."""
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[: MAX_MESSAGE_LENGTH - 3] + "..."

        params: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            params["reply_markup"] = reply_markup

        result = await self._api_call("sendMessage", **params)
        ok = result is not None
        if ok:
            logger.debug(f"Message sent to chat_id={chat_id} ({len(text)} chars)")
        else:
            logger.warning(f"Failed to send message to chat_id={chat_id}")
        return ok

    async def edit_message(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: dict[str, Any] | None = None,
    ) -> bool:
        """Редактирует существующее сообщение."""
        if len(text) > MAX_MESSAGE_LENGTH:
            text = text[: MAX_MESSAGE_LENGTH - 3] + "..."

        params: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode,
        }
        if reply_markup:
            params["reply_markup"] = reply_markup

        result = await self._api_call("editMessageText", **params)
        return result is not None

    async def answer_callback_query(
        self, callback_query_id: str, text: str = "", show_alert: bool = False,
    ) -> bool:
        """Отвечает на callback_query (убирает часики)."""
        result = await self._api_call(
            "answerCallbackQuery",
            callback_query_id=callback_query_id,
            text=text,
            show_alert=show_alert,
        )
        return result is not None

    async def broadcast(self, user_ids: list[int], text: str) -> int:
        """
        Рассылает сообщение всем пользователям.

        Returns:
            Количество успешно отправленных сообщений
        """
        logger.debug(f"Broadcasting to {len(user_ids)} user(s), text={len(text)} chars")
        sent = 0
        for uid in user_ids:
            if await self.send_message(uid, text):
                sent += 1
        logger.info(f"Broadcast complete: {sent}/{len(user_ids)} delivered")
        return sent

    async def get_me(self) -> dict[str, Any] | None:
        """Возвращает информацию о боте."""
        return await self._api_call("getMe")

    # ─── Polling ────────────────────────────────────

    async def _poll_loop(self) -> None:
        """Long polling loop для получения обновлений."""
        logger.info("Starting long polling...")
        while self._running:
            try:
                updates = await self._api_call(
                    "getUpdates",
                    offset=self._offset,
                    timeout=25,
                    allowed_updates=["message", "callback_query"],
                )
                if updates:
                    logger.debug(f"Poll received {len(updates)} update(s)")
                    for update in updates:
                        self._offset = update["update_id"] + 1
                        await self._handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling error: {e}")
                await asyncio.sleep(5)

    async def _handle_update(self, update: dict[str, Any]) -> None:
        """Обрабатывает одно обновление от Telegram."""
        # Callback query (inline button press)
        callback_query = update.get("callback_query")
        if callback_query:
            await self._handle_callback_query(callback_query)
            return

        message = update.get("message")
        if not message:
            return

        text = message.get("text", "")
        user = message.get("from", {})
        user_id = user.get("id", 0)
        chat_id = message.get("chat", {}).get("id", 0)

        if not text or not user_id:
            return

        # Извлекаем команду (убираем @botname)
        command = ""
        if text.startswith("/"):
            command = text.split()[0].split("@")[0]

        logger.info(f"Update: user={user_id} text='{text[:60]}' command='{command}'")

        if self._on_command:
            try:
                response = await self._on_command(command, user_id, text)
                if response and chat_id:
                    await self.send_message(chat_id, response)
            except Exception as e:
                logger.error(f"Command handler error: {e}")

    async def _handle_callback_query(self, cq: dict[str, Any]) -> None:
        """Обрабатывает нажатие inline-кнопки."""
        cq_id = cq.get("id", "")
        user = cq.get("from", {})
        user_id = user.get("id", 0)
        data = cq.get("data", "")
        message = cq.get("message", {})
        chat_id = message.get("chat", {}).get("id", 0)
        message_id = message.get("message_id", 0)

        if not user_id or not data:
            await self.answer_callback_query(cq_id)
            return

        logger.info(f"Callback query: user={user_id} data='{data}' msg_id={message_id}")

        if self._on_callback:
            try:
                response = await self._on_callback(data, user_id, message_id)
                await self.answer_callback_query(cq_id)
                if response and chat_id:
                    await self.send_message(chat_id, response)
            except Exception as e:
                logger.error(f"Callback handler error: {e}")
                await self.answer_callback_query(cq_id, "Error", show_alert=True)
        else:
            await self.answer_callback_query(cq_id)
