"""Opium Account Runtime - изолированный runtime с антидетект-функциями."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from FunPayAPI import Account
from FunPayAPI.common.exceptions import MessageNotDeliveredError, RaiseError as FPRaiseError
from FunPayAPI.updater.runner import Runner

from .commands import Command, CommandResult, CommandType
from .converters import convert_event
from .rate_limiter import RateLimiter, RateLimitConfig, AntiDetectConfig

# Sentinel for required command parameters (no default value).
_REQUIRED: Any = object()

if TYPE_CHECKING:
    from .event_bus import EventBus


logger = logging.getLogger("opium.runtime")


# ── Dispatch table for simple Account commands ──────────────────
# Maps CommandType → (account_method_name, ((param_key, default), ...))
# _REQUIRED means the param must exist in command.params.
# SEND_MESSAGE is excluded — it has special handling (warm, throttle, per-chat lock).

_SIMPLE_DISPATCH: dict[CommandType, tuple[str, tuple[tuple[str, Any], ...]]] = {
    CommandType.SEND_IMAGE: ("send_image", (
        ("chat_id", _REQUIRED),
        ("image", _REQUIRED),
    )),
    CommandType.UPLOAD_IMAGE: ("upload_image", (
        ("image", _REQUIRED),
    )),
    CommandType.GET_CHAT_HISTORY: ("get_chat_history", (
        ("chat_id", _REQUIRED),
        ("last_message_id", 99999999999999),
    )),
    CommandType.GET_CHAT: ("get_chat", (
        ("chat_id", _REQUIRED),
    )),
    CommandType.GET_ORDER: ("get_order", (
        ("order_id", _REQUIRED),
    )),
    CommandType.GET_SELLS: ("get_sells", (
        ("start_from", None),
        ("include_paid", True),
        ("include_closed", True),
        ("include_refunded", True),
    )),
    CommandType.REFUND: ("refund", (
        ("order_id", _REQUIRED),
    )),
    CommandType.SEND_REVIEW: ("send_review", (
        ("order_id", _REQUIRED),
        ("text", ""),
        ("rating", 5),
    )),
    CommandType.DELETE_REVIEW: ("delete_review", (
        ("order_id", _REQUIRED),
    )),
    CommandType.GET_LOT_FIELDS: ("get_lot_fields", (
        ("lot_id", _REQUIRED),
    )),
    CommandType.SAVE_LOT: ("save_lot", (
        ("lot_fields", _REQUIRED),
    )),
    CommandType.DELETE_LOT: ("delete_lot", (
        ("lot_id", _REQUIRED),
    )),
    CommandType.RAISE_LOTS: ("raise_lots", (
        ("category_id", _REQUIRED),
        ("subcategories", None),
        ("exclude", None),
    )),
    CommandType.GET_SUBCATEGORY_PUBLIC_LOTS: ("get_subcategory_public_lots", (
        ("subcategory_type", _REQUIRED),
        ("subcategory_id", _REQUIRED),
    )),
    CommandType.GET_TRADE_PAGE_LOTS: ("get_trade_page_lots", (
        ("subcategory_type", _REQUIRED),
        ("subcategory_id", _REQUIRED),
    )),
    CommandType.GET_BALANCE: ("get_balance", ()),
    CommandType.GET_USER: ("get_user", (
        ("user_id", _REQUIRED),
    )),
    CommandType.CALCULATE: ("calculate", (
        ("subcategory_type", _REQUIRED),
        ("subcategory_id", _REQUIRED),
        ("price", _REQUIRED),
    )),
}


class AccountState(Enum):
    """Состояние аккаунта."""
    CREATED = "created"
    INITIALIZING = "initializing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ReconnectConfig:
    """
    Конфигурация авто-переподключения.
    
    Attributes:
        enabled: Включено ли авто-переподключение
        max_attempts: Максимум попыток (0 = бесконечно, default=50)
        base_delay: Базовая задержка между попытками (сек)
        max_delay: Максимальная задержка (сек)
        backoff_factor: Множитель для exponential backoff
    """
    
    enabled: bool = True
    max_attempts: int = 50  # Circuit breaker: stop after 50 failed reconnects
    base_delay: float = 5.0
    max_delay: float = 300.0  # 5 минут
    backoff_factor: float = 2.0


@dataclass
class AccountConfig:
    """
    Конфигурация аккаунта.
    
    Attributes:
        golden_key: Токен авторизации FunPay
        user_agent: User-Agent браузера
        proxy: Прокси (опционально)
        disable_messages: Отключить события сообщений
        disable_orders: Отключить события заказов
        anti_detect: Конфигурация антидетекта
        rate_limit: Конфигурация rate limiting
        reconnect: Конфигурация переподключения
    """
    
    golden_key: str
    user_agent: str
    proxy: dict[str, str] | None = None
    disable_messages: bool = False
    disable_orders: bool = False
    anti_detect: AntiDetectConfig = field(default_factory=AntiDetectConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    reconnect: ReconnectConfig = field(default_factory=ReconnectConfig)


class AccountRuntime:
    """
    Изолированный runtime для одного FunPay аккаунта с антидетект-функциями.
    
    Особенности:
    - Рандомизация таймингов для имитации человека
    - Rate limiting с jitter
    - Авто-переподключение с exponential backoff
    - Изоляция от других аккаунтов
    - Выделенный ThreadPoolExecutor (не блокирует дефолтный asyncio пул)
    """
    
    # Shared executor for all blocking I/O (FunPay HTTP requests).
    # Separate from asyncio's default pool to prevent starvation.
    _executor: ThreadPoolExecutor = ThreadPoolExecutor(
        max_workers=20, thread_name_prefix="opium-io"
    )
    
    # Min interval between messages to the same chat (seconds)
    _CHAT_MIN_INTERVAL: float = 1.5
    
    def __init__(
        self, 
        account_id: str, 
        config: AccountConfig, 
        event_bus: "EventBus"
    ) -> None:
        """
        Args:
            account_id: Уникальный ID аккаунта в системе
            config: Конфигурация аккаунта
            event_bus: Ссылка на Event Bus
        """
        self.account_id = account_id
        self.config = config
        self.event_bus = event_bus
        
        # Создаём FunPayAPI объекты
        self._account = Account(
            golden_key=config.golden_key,
            user_agent=config.user_agent,
            proxy=config.proxy,
        )
        self._runner: Runner | None = None
        
        # Rate limiter
        self._rate_limiter = RateLimiter(config.rate_limit)
        
        # State management
        self._state = AccountState.CREATED
        self._task: asyncio.Task | None = None
        self._runner_task: asyncio.Task | None = None
        self._session_refresh_task: asyncio.Task | None = None
        self._running: bool = False
        self._initialized: bool = False
        
        # Reconnect tracking
        self._reconnect_attempts: int = 0
        self._last_error: str | None = None
        
        # Per-chat message throttling
        self._chat_locks: dict[int | str, asyncio.Lock] = {}
        self._chat_last_send: dict[int | str, float] = {}

        # Чаты, "открытые" через runner/ POST (chat_node) в текущей сессии.
        # FunPay требует POST chat_node на runner/ перед отправкой сообщений.
        self._warmed_chats: set[int | str] = set()
    
    @property
    def state(self) -> AccountState:
        """Текущее состояние аккаунта."""
        return self._state
    
    @property
    def is_running(self) -> bool:
        """Runtime запущен."""
        return self._running
    
    @property
    def is_initialized(self) -> bool:
        """Account инициализирован."""
        return self._initialized
    
    @property
    def username(self) -> str | None:
        """Никнейм аккаунта (если инициализирован)."""
        return self._account.username if self._initialized else None
    
    @property
    def fp_account_id(self) -> int | None:
        """FunPay ID аккаунта (если инициализирован)."""
        return self._account.id if self._initialized else None
    
    @property
    def last_error(self) -> str | None:
        """Последняя ошибка."""
        return self._last_error
    
    # ========== Config Update ==========
    
    def update_config(self, **kwargs: Any) -> None:
        """
        Update runtime config fields at runtime (hot-reload).
        
        Accepts any top-level AccountConfig field name (e.g. anti_detect,
        rate_limit, reconnect, disable_messages, disable_orders).
        
        Unknown keys are silently ignored so the API layer can forward
        a raw dict without pre-filtering.
        
        Usage from API:
            runtime.update_config(anti_detect=new_anti_detect_config)
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.debug(f"[{self.account_id}] Config updated: {key}")
            else:
                logger.warning(f"[{self.account_id}] Unknown config key ignored: {key}")
    
    # ========== Public Data Access Methods ==========
    
    async def get_chats(self, update: bool = True) -> dict:
        """
        Получает список чатов.
        
        Args:
            update: Запросить актуальные данные с FunPay
            
        Returns:
            Словарь {chat_id: ChatShortcut}
        """
        if not self._initialized:
            raise RuntimeError("Account not initialized")
        
        logger.debug(f"[{self.account_id}] get_chats(update={update})")
        await self._rate_limiter.acquire()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self._executor,
            lambda: self._account.get_chats(update=update)
        )
        logger.debug(f"[{self.account_id}] get_chats returned {len(result)} chats")
        return result
    
    async def initialize(self) -> None:
        """
        Инициализирует Account с антидетект-задержкой.
        
        Raises:
            Exception: При ошибке инициализации
        """
        if self._initialized:
            return
        
        self._state = AccountState.INITIALIZING
        logger.info(f"[{self.account_id}] Initializing account...")
        
        # Антидетект: задержка перед "открытием сайта"
        startup_delay = self.config.anti_detect.get_startup_delay()
        if startup_delay > 0:
            logger.info(f"[{self.account_id}] Startup delay: {startup_delay:.1f}s")
            await asyncio.sleep(startup_delay)
        
        # Запускаем блокирующий account.get() в executor
        logger.debug(f"[{self.account_id}] Calling account.get() (FunPay HTTP)...")
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(self._executor, self._account.get)
        
        # Создаём Runner
        self._runner = Runner(
            account=self._account,
            disable_message_requests=self.config.disable_messages,
            disabled_order_requests=self.config.disable_orders,
        )
        
        self._initialized = True
        self._state = AccountState.READY
        logger.info(
            f"[{self.account_id}] Initialized as {self._account.username} "
            f"(fp_id={self._account.id}, messages={'off' if self.config.disable_messages else 'on'}, "
            f"orders={'off' if self.config.disable_orders else 'on'})"
        )
    
    async def start(self) -> None:
        """
        Запускает Runner в фоне (non-blocking).
        
        Сразу переводит state в STARTING и возвращает управление.
        startup_delay и запуск Runner происходят в фоновой задаче.
        
        Raises:
            RuntimeError: Если не инициализирован
        """
        if not self._initialized:
            raise RuntimeError(f"Runtime {self.account_id} not initialized")
        
        if self._running:
            return
        
        self._state = AccountState.STARTING
        self._running = True
        self._reconnect_attempts = 0
        
        # Запуск в фоне - API не блокируется на startup_delay
        self._task = asyncio.create_task(self._start_sequence())
    
    async def _start_sequence(self) -> None:
        """Фоновая последовательность запуска (delay → runner + session refresh)."""
        try:
            # Антидетект: задержка перед "открытием сайта"
            startup_delay = self.config.anti_detect.get_startup_delay()
            if startup_delay > 0:
                logger.info(f"[{self.account_id}] startup delay: {startup_delay:.1f}s")
                await asyncio.sleep(startup_delay)
            
            if not self._running:
                # stop() вызван во время delay
                self._state = AccountState.STOPPED
                return
            
            # Запускаем основной цикл и обновление сессии
            self._runner_task = asyncio.create_task(self._runner_loop())
            self._session_refresh_task = asyncio.create_task(self._session_refresh_loop())
            
            self._state = AccountState.RUNNING
            logger.info(f"[{self.account_id}] started")
            
            # Ждём завершения runner (stop или crash)
            await self._runner_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.account_id}] Start sequence error: {e}")
            self._last_error = str(e)
            self._state = AccountState.ERROR
    
    async def stop(self) -> None:
        """
        Останавливает Runner (non-blocking).
        
        Сразу переводит state в STOPPING, отменяет задачи.
        shutdown_delay выполняется в фоне.
        """
        if not self._running:
            return
            
        self._state = AccountState.STOPPING
        self._running = False
        
        # Отменяем задачи
        tasks_to_cancel = [
            t for t in [self._task, getattr(self, '_runner_task', None), self._session_refresh_task]
            if t is not None
        ]
        for task in tasks_to_cancel:
            task.cancel()
        
        # Ждём завершения отменённых задач (без блокировки на delay)
        for task in tasks_to_cancel:
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._task = None
        self._runner_task = None
        self._session_refresh_task = None
        
        # Антидетект: shutdown delay в фоне, не блокируем вызывающий код
        shutdown_delay = self.config.anti_detect.get_shutdown_delay()
        if shutdown_delay > 0:
            asyncio.create_task(self._shutdown_delay(shutdown_delay))
        else:
            self._state = AccountState.STOPPED
            logger.info(f"[{self.account_id}] stopped")
    
    async def _shutdown_delay(self, delay: float) -> None:
        """Фоновая задержка после остановки (антидетект)."""
        logger.info(f"[{self.account_id}] shutdown delay: {delay:.1f}s")
        await asyncio.sleep(delay)
        self._state = AccountState.STOPPED
        logger.info(f"[{self.account_id}] stopped")
    
    async def _session_refresh_loop(self) -> None:
        """Периодически обновляет PHPSESSID для поддержания сессии."""
        while self._running:
            try:
                # Ждём интервал обновления
                interval = self.config.anti_detect.get_session_refresh_interval()
                logger.debug(f"[{self.account_id}] Session refresh in {interval:.0f}s")
                await asyncio.sleep(interval)
                
                if not self._running:
                    break
                
                # Обновляем сессию
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    self._executor,
                    lambda: self._account.get(update_phpsessid=True)
                )
                self._warmed_chats.clear()
                logger.info(f"[{self.account_id}] Session refreshed (PHPSESSID updated, warm cache cleared)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"[{self.account_id}] Session refresh error: {e}")
    
    async def _runner_loop(self) -> None:
        """Основной цикл Runner с авто-переподключением."""
        if not self._runner:
            return
        
        while self._running:
            try:
                # Rate limiting перед запросом
                await self._rate_limiter.acquire()
                
                # Запускаем блокирующий get_updates в executor
                loop = asyncio.get_running_loop()
                updates = await loop.run_in_executor(self._executor, self._runner.get_updates)
                
                # Успешный запрос - сбрасываем счётчик переподключений
                self._reconnect_attempts = 0
                self._last_error = None
                
                # Парсим события
                events = self._runner.parse_updates(updates)
                
                if events:
                    from collections import Counter
                    counts = Counter(type(e).__name__ for e in events)
                    summary = ", ".join(f"{name}×{cnt}" if cnt > 1 else name for name, cnt in counts.items())
                    logger.debug(
                        f"[{self.account_id}] Runner got {len(events)} event(s): {summary}"
                    )
                
                # Конвертируем и публикуем
                published = 0
                for event in events:
                    opium_event = convert_event(self.account_id, event)
                    if opium_event:
                        # Все модули могут фильтровать свои сообщения по fp_user_id
                        opium_event.payload["fp_user_id"] = self._account.id
                        await self.event_bus.publish(opium_event)
                        published += 1
                    else:
                        logger.debug(
                            f"[{self.account_id}] Unknown FunPay event skipped: "
                            f"{type(event).__name__}"
                        )
                
                if published:
                    logger.debug(
                        f"[{self.account_id}] Published {published}/{len(events)} events to EventBus"
                    )
                
                # Антидетект: рандомная задержка между запросами
                delay = self.config.anti_detect.get_runner_delay()
                await asyncio.sleep(delay)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._last_error = str(e)
                logger.error(f"[{self.account_id}] Runner error: {e}")
                
                # Авто-переподключение
                if not await self._handle_error(e):
                    break
    
    async def _handle_error(self, error: Exception) -> bool:
        """
        Обрабатывает ошибку и решает, продолжать ли работу.
        
        Returns:
            True если нужно продолжить, False если нужно остановиться
        """
        if not self.config.reconnect.enabled:
            self._state = AccountState.ERROR
            return False
        
        while True:
            self._reconnect_attempts += 1
            max_attempts = self.config.reconnect.max_attempts
            
            # Проверяем лимит попыток
            if max_attempts > 0 and self._reconnect_attempts > max_attempts:
                logger.error(f"[{self.account_id}] Max reconnect attempts reached")
                self._state = AccountState.ERROR
                return False
            
            self._state = AccountState.RECONNECTING
            
            # Exponential backoff с jitter
            delay = min(
                self.config.reconnect.base_delay * (self.config.reconnect.backoff_factor ** (self._reconnect_attempts - 1)),
                self.config.reconnect.max_delay
            )
            # Добавляем jitter ±20%
            delay *= random.uniform(0.8, 1.2)
            
            logger.warning(
                f"[{self.account_id}] Reconnecting in {delay:.1f}s "
                f"(attempt {self._reconnect_attempts})"
            )
            await asyncio.sleep(delay)
            
            # Пытаемся переинициализировать сессию
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(
                    self._executor,
                    lambda: self._account.get(update_phpsessid=True)
                )
                self._state = AccountState.RUNNING
                logger.info(f"[{self.account_id}] reconnected successfully")
                return True
            except Exception as e:
                logger.error(f"[{self.account_id}] Reconnect failed: {e}")
                # Цикл продолжится на следующую попытку
    
    async def execute(self, command: Command) -> CommandResult:
        """
        Выполняет команду через Account с rate limiting и retry.
        
        Args:
            command: Команда для выполнения
            
        Returns:
            Результат выполнения команды
        """
        if not self._running:
            return CommandResult.fail(f"Account {self.account_id} is not running")

        if not self._initialized:
            return CommandResult.fail("Runtime not initialized")
        
        # Логируем каждую команду
        safe_params = {k: v for k, v in command.params.items() if k not in ('text', 'image', 'lot_fields')}
        logger.info(
            f"[{self.account_id}] Executing command: {command.command_type} "
            f"params={safe_params}"
        )
        
        max_retries = 3 if command.command_type == CommandType.SEND_MESSAGE else 1
        last_error: Exception | None = None
        
        for attempt in range(max_retries):
            try:
                # Rate limiting перед выполнением команды
                await self._rate_limiter.acquire()
                
                result = await self._execute_command(command)
                return CommandResult.ok(result)
            except MessageNotDeliveredError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = (attempt + 1) * 2 + random.uniform(0.5, 1.5)
                    logger.warning(
                        f"[{self.account_id}] send_message failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {delay:.1f}s: {e.short_str()}"
                    )
                    # "Доступ запрещен" - сбрасываем тёплый кеш чата,
                    # обновляем сессию + csrf, чтобы повторный warm + send
                    # прошли с чистой сессией.
                    if e.error_message and "Доступ запрещен" in e.error_message:
                        # Сбрасываем warm-кеш для этого чата
                        chat_id = command.params.get("chat_id")
                        self._warmed_chats.discard(chat_id)
                        try:
                            loop = asyncio.get_running_loop()
                            await loop.run_in_executor(
                                self._executor,
                                lambda: self._account.get(update_phpsessid=True),
                            )
                            logger.info(
                                f"[{self.account_id}] Session refreshed + chat {chat_id} warm reset"
                            )
                        except Exception as refresh_err:
                            logger.warning(
                                f"[{self.account_id}] Session refresh failed: {refresh_err}"
                            )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"[{self.account_id}] send_message failed after {max_retries} attempts: {e.short_str()}")
            except FPRaiseError as e:
                return CommandResult(
                    success=False,
                    error=e.short_str(),
                    data={"wait_time": e.wait_time},
                )
            except Exception as e:
                logger.error(f"[{self.account_id}] Command {command.command_type} failed: {e}")
                return CommandResult.from_exception(e)
        
        return CommandResult.from_exception(last_error)
    
    async def _execute_command(self, command: Command) -> Any:
        """Dispatch command to the appropriate Account method."""
        cmd_type = command.command_type

        # Special case: SEND_MESSAGE needs warm + throttle + per-chat lock
        if cmd_type == CommandType.SEND_MESSAGE:
            logger.debug(f"[{self.account_id}] Dispatch SEND_MESSAGE -> _cmd_send_message")
            return await self._cmd_send_message(command.params)

        # Special case: GET_CATEGORIES - property access, no I/O
        if cmd_type == CommandType.GET_CATEGORIES:
            logger.debug(f"[{self.account_id}] Dispatch GET_CATEGORIES -> property access")
            return self._account.categories

        # Special case: GET_MY_PROFILE - get own user profile
        if cmd_type == CommandType.GET_MY_PROFILE:
            logger.debug(f"[{self.account_id}] Dispatch GET_MY_PROFILE -> get_user({self._account.id})")
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                self._executor, lambda: self._account.get_user(self._account.id)
            )

        # Generic dispatch for all other commands
        spec = _SIMPLE_DISPATCH.get(cmd_type)
        if spec is None:
            raise ValueError(f"Unknown command type: {cmd_type}")

        method_name, param_spec = spec
        logger.debug(
            f"[{self.account_id}] Dispatch {cmd_type} -> account.{method_name}()"
        )
        return await self._run_simple_command(method_name, command.params, param_spec)

    async def _run_simple_command(
        self,
        method_name: str,
        params: dict[str, Any],
        param_spec: tuple[tuple[str, Any], ...],
    ) -> Any:
        """Execute a simple Account method via the shared thread pool."""
        kwargs: dict[str, Any] = {}
        for key, default in param_spec:
            if default is _REQUIRED:
                kwargs[key] = params[key]
            else:
                kwargs[key] = params.get(key, default)

        method = getattr(self._account, method_name)
        logger.debug(
            f"[{self.account_id}] Calling account.{method_name}({kwargs})"
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(self._executor, lambda: method(**kwargs))
        logger.debug(
            f"[{self.account_id}] account.{method_name}() returned: "
            f"{type(result).__name__}"
        )
        return result

    async def _cmd_send_message(self, params: dict[str, Any]) -> Any:
        """SEND_MESSAGE with per-chat lock, chat warm, and throttle."""
        loop = asyncio.get_running_loop()
        chat_id = params["chat_id"]
        text_preview = (params.get("text", "") or "")[:80]

        logger.debug(
            f"[{self.account_id}] send_message to chat {chat_id}: "
            f"\"{text_preview}{'...' if len(params.get('text', '')) > 80 else ''}\""
        )

        # Per-chat lock — messages to one chat go sequentially
        if chat_id not in self._chat_locks:
            self._chat_locks[chat_id] = asyncio.Lock()

        async with self._chat_locks[chat_id]:
            # Warm: POST chat_node к runner/ (без сообщения) чтобы
            # FunPay "открыл" чат в сессии.  Без этого send_message
            # возвращает "Доступ запрещен".
            if chat_id not in self._warmed_chats:
                try:
                    await loop.run_in_executor(
                        self._executor,
                        lambda cid=chat_id: self._account.get_chats_histories(
                            {cid: None}
                        ),
                    )
                    self._warmed_chats.add(chat_id)
                    logger.debug(
                        f"[{self.account_id}] Chat {chat_id} warmed via runner/ POST"
                    )
                except Exception as warm_err:
                    logger.warning(
                        f"[{self.account_id}] Chat warm failed for {chat_id}: {warm_err}"
                    )

            # Throttle — минимальный интервал между сообщениями в один чат
            now = time.time()
            last_send = self._chat_last_send.get(chat_id, 0)
            elapsed = now - last_send
            if elapsed < self._CHAT_MIN_INTERVAL:
                wait = self._CHAT_MIN_INTERVAL - elapsed + random.uniform(0.2, 0.8)
                await asyncio.sleep(wait)

            result = await loop.run_in_executor(
                self._executor,
                lambda: self._account.send_message(
                    chat_id=chat_id,
                    text=params.get("text", ""),
                    chat_name=params.get("chat_name"),
                    image_id=params.get("image_id"),
                ),
            )
            self._chat_last_send[chat_id] = time.time()
            logger.info(
                f"[{self.account_id}] Message sent to chat {chat_id} "
                f"({len(params.get('text', ''))} chars)"
            )
            return result
    
    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        name = self.username or "not initialized"
        return f"AccountRuntime({self.account_id}, {name}, {status})"