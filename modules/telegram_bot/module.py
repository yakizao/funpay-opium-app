# -*- coding: utf-8 -*-
"""
Telegram Bot Module - главный класс модуля.

Уведомления и мониторинг FunPay через Telegram-бота:
- Подписка на все события
- Фильтрация по конфигу (notify_events)
- Broadcast в вайтлист
- Команды бота (/start, /status, /events, /help)

АРХИТЕКТУРА:
- Модуль наследуется от core.Module
- Подписывается на ВСЕ события (Subscription())
- Фильтрация по notify_events в handle_event()
- Бот работает через long polling (aiohttp)
"""

from __future__ import annotations

import html
import json
import logging
from typing import Any, ClassVar

import aiohttp

from core.module import Module, register_module_class, Subscription
from core.storage import ModuleStorage
from core import Command, OpiumEvent

from .storage import TelegramBotStorage
from .bot import TelegramBot
from .formatters import format_event
from .log_handler import TelegramLogHandler

logger = logging.getLogger("opium.telegram_bot")


@register_module_class
class TelegramBotModule(Module):
    """
    Модуль Telegram-бота.

    Конфигурация в accounts/{id}/modules/telegram_bot/:
    - config.json      — настройки (bot_token, notify_events)
    - whitelist.json   — вайтлист Telegram ID
    - event_log.json   — лог отправленных уведомлений
    """

    module_name: ClassVar[str] = "telegram_bot"

    def __init__(self, account_id: str, storage: ModuleStorage) -> None:
        super().__init__(account_id, storage)
        self._tg_storage = TelegramBotStorage(storage)
        self._bot: TelegramBot | None = None
        self._log_handler: TelegramLogHandler | None = None
        # Пользователи, которым уже показано сообщение "доступ запрещён".
        # Повторные обращения игнорируются (защита от спама).
        self._denied_users: set[int] = set()
        logger.info(f"[{self.name}] Initialized for account {account_id}")

    @property
    def tg_storage(self) -> TelegramBotStorage:
        """Public access to typed storage (used by api_router.py)."""
        return self._tg_storage

    @property
    def bot(self) -> TelegramBot | None:
        """Текущий экземпляр бота (None если не запущен)."""
        return self._bot

    def get_subscriptions(self) -> list[Subscription]:
        """Подписка на ВСЕ события (фильтрация в handle_event)."""
        return [Subscription()]

    async def handle_event(self, event: OpiumEvent) -> list[Command]:
        """
        Обрабатывает входящее событие.

        Проверяет notify_events, форматирует и рассылает.
        Всегда возвращает пустой список (бот не генерирует команды).
        """
        if not self._bot or not self._bot.is_running:
            logger.debug(f"[{self.name}] Bot not running, skipping event {event.event_type}")
            return []

        # Фильтрация по настроенным типам событий
        notify_events = self._tg_storage.get_notify_events()
        if event.event_type not in notify_events:
            logger.debug(
                f"[{self.name}] Event {event.event_type} not in notify_events "
                f"({notify_events}), skipping"
            )
            return []

        # Форматирование
        text = format_event(event)
        if not text:
            logger.debug(f"[{self.name}] No text from formatter for {event.event_type}")
            return []

        # Рассылка всем в вайтлисте
        user_ids = self._tg_storage.get_whitelisted_ids()
        if not user_ids:
            logger.debug(f"[{self.name}] No whitelisted users for broadcast")
            return []

        try:
            logger.info(
                f"[{self.name}] Broadcasting {event.event_type} to {len(user_ids)} user(s)"
            )
            sent = await self._bot.broadcast(user_ids, text)
            if sent:
                self._tg_storage.append_event({
                    "event_type": event.event_type,
                    "text_preview": text[:200],
                    "sent_to": sent,
                    "total": len(user_ids),
                })
                logger.info(
                    f"[{self.name}] Broadcast {event.event_type}: "
                    f"{sent}/{len(user_ids)} delivered"
                )
            else:
                logger.warning(
                    f"[{self.name}] Broadcast {event.event_type}: 0/{len(user_ids)} delivered"
                )
        except Exception as e:
            logger.error(f"[{self.name}] Broadcast error: {e}")

        return []

    async def on_start(self) -> None:
        """Запускает Telegram-бота (long polling)."""
        token = self._tg_storage.get_bot_token()
        if not token:
            logger.warning(
                f"[{self.name}] No bot token configured — "
                "set it via UI or config.json"
            )
            return

        self._bot = TelegramBot(
            token=token,
            on_command=self._handle_bot_command,
            on_callback=self._handle_callback,
        )
        await self._bot.start()

        if self._bot.is_running:
            bot_info = self._bot.bot_info or {}
            logger.info(
                f"[{self.name}] Bot started: @{bot_info.get('username', '?')} "
                f"for account {self.account_id}"
            )
            # Подключаем log handler
            self._attach_log_handler()
        else:
            logger.error(f"[{self.name}] Bot failed to start (invalid token?)")
            self._bot = None

    async def on_stop(self) -> None:
        """Останавливает бота."""
        self._detach_log_handler()
        if self._bot:
            await self._bot.stop()
            self._bot = None
        logger.info(f"[{self.name}] Stopped")

    async def restart_bot(self) -> bool:
        """
        Перезапускает бота (после смены токена).

        Returns:
            True если бот успешно запущен
        """
        if self._bot:
            self._detach_log_handler()
            await self._bot.stop()
            self._bot = None

        token = self._tg_storage.get_bot_token()
        if not token:
            return False

        self._bot = TelegramBot(
            token=token,
            on_command=self._handle_bot_command,
            on_callback=self._handle_callback,
        )
        await self._bot.start()

        if not self._bot.is_running:
            self._bot = None
            return False

        # Переподключаем log handler
        self._attach_log_handler()
        return True

    def _attach_log_handler(self) -> None:
        """Подключает перехват логов."""
        self._detach_log_handler()
        if self._bot and self._bot.is_running:
            self._log_handler = TelegramLogHandler(
                storage=self._tg_storage,
                bot=self._bot,
                account_id=self.account_id,
            )
            import logging as _logging
            self._log_handler.setFormatter(
                _logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
            )
            self._log_handler.attach()

    def _detach_log_handler(self) -> None:
        """Отключает перехват логов."""
        if self._log_handler:
            self._log_handler.detach()
            self._log_handler = None

    # ─── Bot Command Handler ────────────────────────

    async def _handle_bot_command(
        self, command: str, user_id: int, text: str,
    ) -> str | None:
        """
        Обработчик команд бота.

        /start — не в вайтлисте: показывает ID для добавления.
                 в вайтлисте: приветствие + список команд.
        Остальные команды доступны только из вайтлиста.
        """
        # /start доступен всем (показывает ID если не в вайтлисте)
        if command == "/start":
            logger.info(f"[{self.name}] Bot command /start from user {user_id}")
            if not self._tg_storage.is_whitelisted(user_id):
                if user_id in self._denied_users:
                    return None  # уже показали, молчим
                self._denied_users.add(user_id)
                return (
                    f"⛔ Доступ запрещён.\n\n"
                    f"Ваш Telegram ID: <code>{user_id}</code>\n"
                    f"Передайте его администратору для добавления в вайтлист."
                )
            return (
                f"👋 Привет! Я бот Opium.\n\n"
                f"Аккаунт: <b>{self.account_id}</b>\n\n"
                f"Команды:\n"
                f"/menu — панель управления\n"
                f"/status — статус аккаунта\n"
                f"/events — последние события\n"
                f"/help — помощь"
            )

        # Остальные команды — только для вайтлиста
        if not self._tg_storage.is_whitelisted(user_id):
            logger.debug(f"[{self.name}] Command {command} from non-whitelisted user {user_id}, ignoring")
            return None  # Silent ignore

        logger.info(f"[{self.name}] Bot command {command} from whitelisted user {user_id}")

        if command == "/status":
            bot_info = self._bot.bot_info if self._bot else {}
            username = bot_info.get("username", "?")
            wl_count = len(self._tg_storage.get_whitelist())
            events_count = len(self._tg_storage.get_event_log(100))
            notify = ", ".join(self._tg_storage.get_notify_events())

            return (
                f"✅ <b>Статус</b>\n\n"
                f"Аккаунт: <b>{self.account_id}</b>\n"
                f"Бот: @{username}\n"
                f"Вайтлист: {wl_count} пользователей\n"
                f"Событий в логе: {events_count}\n"
                f"Подписки: {notify}"
            )

        elif command == "/menu":
            return await self._build_menu(user_id)

        elif command == "/events":
            events = self._tg_storage.get_event_log(10)
            if not events:
                return "📭 Нет событий"

            lines = ["📋 <b>Последние события:</b>\n"]
            for e in reversed(events):
                ts = e.get("timestamp", "?")[:16]
                et = e.get("event_type", "?")
                sent = e.get("sent_to", 0)
                total = e.get("total", 0)
                lines.append(f"• {ts} — {et} ({sent}/{total})")

            return "\n".join(lines)

        elif command == "/help":
            return (
                "ℹ️ <b>Команды бота:</b>\n\n"
                "/start — приветствие\n"
                "/menu — панель управления (кнопки)\n"
                "/status — статус аккаунта и бота\n"
                "/events — последние 10 событий\n"
                "/help — эта справка"
            )

        return None

    # ─── Menu & Callbacks ───────────────────────────

    async def _build_menu(self, user_id: int) -> str | None:
        """
        Строит /menu — отправляет сообщение с inline-кнопками.
        Возвращает None (сообщение отправляется напрямую с reply_markup).
        """
        buttons = self._tg_storage.get_bot_buttons()
        enabled = [b for b in buttons if b.get("enabled", True)]

        if not enabled:
            return "📭 Команды не настроены.\nДобавьте кнопки в настройках бота."

        # Формируем inline keyboard (по 2 кнопки в ряд)
        keyboard: list[list[dict[str, str]]] = []
        row: list[dict[str, str]] = []
        for btn in enabled:
            cb_data = f"btn:{btn['id']}"
            if btn.get("confirm"):
                cb_data = f"confirm:{btn['id']}"
            row.append({"text": btn["label"], "callback_data": cb_data})
            if len(row) >= 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        reply_markup = {"inline_keyboard": keyboard}

        if self._bot:
            # Отправляем напрямую с клавиатурой
            await self._bot.send_message(
                chat_id=user_id,
                text=f"🎛 <b>Панель управления</b>\nАккаунт: {self.account_id}",
                reply_markup=reply_markup,
            )
        return None

    async def _handle_callback(
        self, data: str, user_id: int, message_id: int,
    ) -> str | None:
        """Обработчик inline-кнопок."""
        logger.info(f"[{self.name}] Callback from user {user_id}: data='{data}'")
        if not self._tg_storage.is_whitelisted(user_id):
            logger.warning(f"[{self.name}] Callback from non-whitelisted user {user_id}")
            return None

        # confirm:btn_id → показать подтверждение
        if data.startswith("confirm:"):
            btn_id = data[8:]
            btn = self._tg_storage.get_bot_button_by_id(btn_id)
            if not btn:
                return "❌ Кнопка не найдена"

            # Отправляем сообщение-подтверждение с да/нет
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Да", "callback_data": f"btn:{btn_id}"},
                        {"text": "❌ Отмена", "callback_data": "cancel"},
                    ]
                ]
            }
            if self._bot:
                await self._bot.send_message(
                    chat_id=user_id,
                    text=f"⚠️ <b>Подтвердите:</b> {html.escape(btn['label'])}",
                    reply_markup=keyboard,
                )
            return None

        # cancel → просто отвечаем
        if data == "cancel":
            return "❌ Отменено"

        # btn:btn_id → выполнить
        if data.startswith("btn:"):
            btn_id = data[4:]
            btn = self._tg_storage.get_bot_button_by_id(btn_id)
            if not btn:
                return "❌ Кнопка не найдена"
            return await self._execute_button(btn)

        return None

    async def _execute_button(self, btn: dict[str, Any]) -> str:
        """Вызывает API-эндпоинт кнопки и возвращает результат."""
        endpoint = btn.get("api_endpoint", "")
        method = btn.get("api_method", "GET").upper()
        body = btn.get("api_body")
        label = btn.get("label", "?")
        logger.info(
            f"[{self.name}] Executing button '{label}': "
            f"{method} {endpoint}"
        )
        if not endpoint:
            return "❌ Не указан API endpoint"

        # Подставляем {account_id} в endpoint
        endpoint = endpoint.replace("{account_id}", self.account_id)

        url = f"http://localhost:8000{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                kwargs: dict[str, Any] = {
                    "timeout": aiohttp.ClientTimeout(total=30),
                }
                if body and method == "POST":
                    kwargs["json"] = body

                async with session.request(method, url, **kwargs) as resp:
                    status = resp.status
                    try:
                        data = await resp.json()
                    except Exception:
                        text = await resp.text()
                        data = text[:500]

                    if status >= 400:
                        detail = ""
                        if isinstance(data, dict):
                            detail = data.get("detail", str(data))
                        else:
                            detail = str(data)
                        return (
                            f"❌ <b>{html.escape(label)}</b>\n"
                            f"Ошибка {status}: {html.escape(str(detail)[:300])}"
                        )

                    # Форматируем ответ
                    return self._format_api_response(label, data)

        except aiohttp.ClientError as e:
            return f"❌ <b>{html.escape(label)}</b>\nОшибка сети: {html.escape(str(e)[:200])}"
        except Exception as e:
            return f"❌ <b>{html.escape(label)}</b>\nОшибка: {html.escape(str(e)[:200])}"

    @staticmethod
    def _format_api_response(label: str, data: Any) -> str:
        """Форматирует JSON-ответ API в читаемый текст для Telegram."""
        header = f"✅ <b>{html.escape(label)}</b>\n\n"

        if isinstance(data, dict):
            lines: list[str] = []
            for key, value in data.items():
                if key.startswith("_"):
                    continue
                k = html.escape(str(key))
                if isinstance(value, (dict, list)):
                    v = html.escape(json.dumps(value, ensure_ascii=False, indent=1)[:300])
                    lines.append(f"<b>{k}:</b>\n<pre>{v}</pre>")
                else:
                    v = html.escape(str(value)[:200])
                    lines.append(f"<b>{k}:</b> {v}")
            return header + "\n".join(lines) if lines else header + "<i>ok</i>"

        if isinstance(data, list):
            if not data:
                return header + "<i>пусто</i>"
            preview = json.dumps(data[:10], ensure_ascii=False, indent=1)
            if len(preview) > 1500:
                preview = preview[:1500] + "..."
            return header + f"<pre>{html.escape(preview)}</pre>"

        return header + html.escape(str(data)[:500])
