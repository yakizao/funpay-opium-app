"""Opium Core - главный класс системы с файловым хранилищем."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from .event_bus import EventBus, OpiumEvent
from .commands import Command, CommandResult
from .module import Module, get_module_class
from .runtime import AccountRuntime
from .storage import Storage, AccountStorage, AccountData


logger = logging.getLogger("opium.core")


class OpiumCore:
    """
    Ядро системы Opium с файловым хранилищем per-account.
    
    Структура данных:
        accounts/
        ├── shop_1/
        │   ├── account.json          # Конфиг аккаунта
        │   └── modules/
        │       ├── auto_responder/   # Папка модуля
        │       │   ├── config.json   # Конфиг модуля
        │       │   └── data.db       # БД модуля
        │       └── auto_delivery/
        ├── shop_2/
        └── ...
    
    Архитектура:
    - Каждый аккаунт имеет СВОИ инстансы модулей
    - Модули НЕ шарятся между аккаунтами
    - Каждый модуль имеет свою папку с данными
    
    Поток данных:
    1. Runner получает FunPayAPI event
    2. AccountRuntime конвертирует в OpiumEvent
    3. EventBus вызывает модули ТОЛЬКО этого аккаунта
    4. Module.handle_event() возвращает Commands
    5. Core.execute() выполняет команды на Runtime
    """
    
    def __init__(self, base_path: str | Path = ".") -> None:
        """
        Args:
            base_path: Базовый путь для хранилища (где находится папка accounts/)
        """
        self.storage = Storage(base_path)
        self.event_bus = EventBus()
        
        self._runtimes: dict[str, AccountRuntime] = {}
        
        # account_id -> {module_name -> Module instance}
        self._account_modules: dict[str, dict[str, Module]] = {}
        
        # account_id -> [subscription_ids] для отписки при удалении
        self._account_subscriptions: dict[str, list[str]] = {}
        
        self._running: bool = False
    
    # ========== Account Management ==========
    
    async def load_accounts(self, auto_start: bool = False) -> list[str]:
        """
        Загружает все аккаунты из папки accounts/ (non-blocking).
        
        Создаёт Runtime-объекты синхронно, затем запускает
        initialize() каждого аккаунта как фоновую задачу.
        API сервер не блокируется - клиент поллит GET /accounts/{id}
        для отслеживания прогресса (state: initializing → ready → running).
        
        Args:
            auto_start: Автоматически запускать аккаунты
            
        Returns:
            Список ID зарегистрированных аккаунтов
        """
        registered: list[str] = []
        
        for account_data in self.storage.list_accounts(enabled_only=True):
            try:
                self._register_account(account_data)
                registered.append(account_data.account_id)
            except Exception as e:
                logger.error(f"Failed to register account {account_data.account_id}: {e}")
        
        # Загружаем модули синхронно (чтение JSON с диска — мгновенно)
        for account_id in registered:
            try:
                account_storage = self.storage.get_account_storage(account_id)
                await self._load_account_modules(account_id, account_storage)
            except Exception as e:
                logger.error(f"[{account_id}] Failed to load modules: {e}")
        
        # Запускаем сетевую инициализацию в фоне
        for account_id in registered:
            asyncio.create_task(
                self._background_init(account_id, auto_start=auto_start),
                name=f"init-{account_id}",
            )
        
        logger.info(f"registered {len(registered)} accounts (initializing in background)")
        return registered
    
    def _register_account(self, account_data: AccountData) -> AccountRuntime:
        """Регистрирует аккаунт синхронно (без сетевых вызовов)."""
        account_id = account_data.account_id
        
        if account_id in self._runtimes:
            raise ValueError(f"Account {account_id} already loaded")
        
        config = account_data.to_config()
        runtime = AccountRuntime(account_id, config, self.event_bus)
        
        self._runtimes[account_id] = runtime
        self._account_modules[account_id] = {}
        self._account_subscriptions[account_id] = []
        
        logger.info(
            f"[{account_id}] Registered account "
            f"(proxy={'yes' if config.proxy else 'no'}, "
            f"messages={'off' if config.disable_messages else 'on'}, "
            f"orders={'off' if config.disable_orders else 'on'})"
        )
        return runtime
    
    async def _background_init(
        self,
        account_id: str,
        auto_start: bool = False,
    ) -> None:
        """Фоновая инициализация аккаунта (delay + network + on_start + start).
        
        Модули уже загружены синхронно при регистрации.
        Здесь выполняется только то, что требует сеть.
        """
        runtime = self._runtimes.get(account_id)
        if not runtime:
            return
        
        try:
            await runtime.initialize()
            
            logger.info(f"initialized account: {account_id} ({runtime.username})")
            
            if auto_start and self._running:
                # Запускаем on_start для модулей
                for module in self._account_modules.get(account_id, {}).values():
                    try:
                        await module.on_start()
                    except Exception as e:
                        logger.error(f"[{account_id}] Module {module.name} on_start error: {e}")
                
                await runtime.start()
        except Exception as e:
            logger.error(f"Failed to initialize account {account_id}: {e}")
            runtime._last_error = str(e)
    
    async def _load_account_modules(
        self, 
        account_id: str, 
        account_storage: AccountStorage
    ) -> None:
        """Загружает модули аккаунта из папки modules/."""
        module_names = account_storage.list_module_configs()
        logger.info(f"[{account_id}] Loading {len(module_names)} module(s): {module_names}")
        
        for module_name in module_names:
            module_class = get_module_class(module_name)
            if module_class is None:
                logger.warning(
                    f"[{account_id}] Unknown module: {module_name}. "
                    "Register it with @register_module_class"
                )
                continue
            
            try:
                await self._create_account_module(
                    account_id, 
                    module_class, 
                    account_storage
                )
            except Exception as e:
                logger.error(f"[{account_id}] Failed to load module {module_name}: {e}")
    
    async def _create_account_module(
        self,
        account_id: str,
        module_class: type[Module],
        account_storage: AccountStorage,
    ) -> Module:
        """Создаёт инстанс модуля для аккаунта."""
        module_name = module_class.module_name
        
        module_storage = account_storage.get_module_storage(module_name)
        
        # Создаём инстанс модуля
        module = module_class(account_id, module_storage)
        self._account_modules[account_id][module_name] = module
        
        # Inject command executor for modules that need it (e.g. review rating check)
        if hasattr(module, 'set_execute_command'):
            module.set_execute_command(lambda cmd, _aid=account_id: self.execute(_aid, cmd))
            logger.debug(f"[{account_id}] Injected execute_command into {module_name}")
        
        # Создаём подписки (только на события этого аккаунта)
        subscriptions = module.get_subscriptions()
        for subscription in subscriptions:
            sub_id = self.event_bus.subscribe(
                handler=self._create_module_handler(module),
                event_types=subscription.event_types,
                account_ids=[account_id],  # Только этот аккаунт!
            )
            self._account_subscriptions[account_id].append(sub_id)
        
        logger.info(
            f"[{account_id}] Created module: {module_name} "
            f"(subscriptions={len(subscriptions)}, "
            f"events={subscriptions[0].event_types if subscriptions else 'ALL'})"
        )
        return module
    
    async def add_account(
        self,
        account_id: str,
        golden_key: str,
        user_agent: str,
        proxy: dict[str, str] | None = None,
        anti_detect: dict[str, Any] | None = None,
        rate_limit: dict[str, Any] | None = None,
        reconnect: dict[str, Any] | None = None,
        disable_messages: bool = False,
        disable_orders: bool = False,
        auto_start: bool = True,
    ) -> AccountRuntime:
        """
        Создаёт и добавляет новый аккаунт (non-blocking).
        
        Создаёт папку accounts/{account_id}/ с account.json.
        Инициализация и запуск происходят в фоне.
        
        Args:
            account_id: Уникальный ID аккаунта (имя папки)
            golden_key: Токен авторизации FunPay
            user_agent: User-Agent браузера
            proxy: Прокси (опционально)
            anti_detect: Настройки антидетекта (dict)
            rate_limit: Настройки rate limiting (dict)
            reconnect: Настройки переподключения (dict)
            disable_messages: Отключить события сообщений
            disable_orders: Отключить события заказов
            auto_start: Автоматически запустить
            
        Returns:
            Созданный AccountRuntime (в состоянии CREATED - инициализация идёт в фоне)
        """
        if account_id in self._runtimes:
            raise ValueError(f"Account {account_id} already exists")
        
        # Создаём запись в storage
        account_data = self.storage.create_account(
            account_id=account_id,
            golden_key=golden_key,
            user_agent=user_agent,
            proxy=proxy,
            anti_detect=anti_detect,
            rate_limit=rate_limit,
            reconnect=reconnect,
            disable_messages=disable_messages,
            disable_orders=disable_orders,
        )
        
        # Регистрируем синхронно, загружаем модули, инициализируем сеть в фоне
        runtime = self._register_account(account_data)
        
        # Модули — чтение JSON с диска, мгновенно
        account_storage = self.storage.get_account_storage(account_id)
        await self._load_account_modules(account_id, account_storage)
        
        asyncio.create_task(
            self._background_init(account_id, auto_start=auto_start),
            name=f"init-{account_id}",
        )
        
        return runtime
    
    async def remove_account(self, account_id: str) -> bool:
        """
        Останавливает и удаляет аккаунт из Core (не из файловой системы).
        
        Args:
            account_id: ID аккаунта
            
        Returns:
            True если аккаунт был найден и удалён
        """
        runtime = self._runtimes.get(account_id)
        if not runtime:
            return False
        
        logger.info(f"[{account_id}] Removing account...")
        
        # Останавливаем модули
        modules = self._account_modules.get(account_id, {})
        for module in modules.values():
            try:
                logger.debug(f"[{account_id}] Stopping module: {module.name}")
                await module.on_stop()
            except Exception as e:
                logger.error(f"[{account_id}] Module {module.name} on_stop error: {e}")
        
        # Отписываем от событий
        sub_count = len(self._account_subscriptions.get(account_id, []))
        for sub_id in self._account_subscriptions.get(account_id, []):
            self.event_bus.unsubscribe(sub_id)
        
        # Останавливаем runtime
        await runtime.stop()
        
        # Очищаем
        del self._runtimes[account_id]
        self._account_modules.pop(account_id, None)
        self._account_subscriptions.pop(account_id, None)
        
        logger.info(
            f"[{account_id}] Account removed "
            f"(modules={len(modules)}, subscriptions={sub_count})"
        )
        return True
    
    def get_runtime(self, account_id: str) -> AccountRuntime | None:
        """Возвращает Runtime по ID аккаунта."""
        return self._runtimes.get(account_id)
    
    def get_all_runtimes(self) -> dict[str, AccountRuntime]:
        """Возвращает все Runtimes."""
        return dict(self._runtimes)
    
    # ========== Module Management ==========
    
    async def add_module_to_account(
        self,
        account_id: str,
        module_name: str,
        config: dict[str, Any] | None = None,
    ) -> Module | None:
        """
        Добавляет модуль к аккаунту.
        
        Создаёт папку accounts/{account_id}/modules/{module_name}/ с config.json.
        
        Args:
            account_id: ID аккаунта
            module_name: Имя модуля (должен быть зарегистрирован)
            config: Начальная конфигурация модуля
            
        Returns:
            Созданный Module или None если не удалось
        """
        if account_id not in self._runtimes:
            logger.error(f"Account {account_id} not found")
            return None
        
        if account_id in self._account_modules and module_name in self._account_modules[account_id]:
            logger.error(f"[{account_id}] Module {module_name} already exists")
            return None
        
        module_class = get_module_class(module_name)
        if module_class is None:
            logger.error(f"Unknown module: {module_name}")
            return None
        
        account_storage = self.storage.get_account_storage(account_id)
        module_storage = account_storage.get_module_storage(module_name)
        
        # Сохраняем конфиг если передан
        if config:
            module_storage.save_config(config)
        
        module = await self._create_account_module(
            account_id, 
            module_class, 
            account_storage
        )
        
        # Запускаем если Core работает
        if self._running:
            try:
                await module.on_start()
            except Exception as e:
                logger.error(f"[{account_id}] Module {module_name} on_start error: {e}")
        
        logger.info(f"[{account_id}] Added module: {module_name}")
        return module
    
    def get_account_module(self, account_id: str, module_name: str) -> Module | None:
        """Возвращает модуль аккаунта."""
        return self._account_modules.get(account_id, {}).get(module_name)
    
    def get_account_modules(self, account_id: str) -> dict[str, Module]:
        """Возвращает все модули аккаунта."""
        return dict(self._account_modules.get(account_id, {}))
    
    def _create_module_handler(self, module: Module) -> Callable[[OpiumEvent], Awaitable[None]]:
        """Создаёт обработчик событий для модуля."""
        
        async def handler(event: OpiumEvent) -> None:
            try:
                commands = await module.handle_event(event)
                
                for command in commands:
                    result = await self.execute(event.account_id, command)
                    if result.success:
                        logger.info(
                            f"[{event.account_id}] Command {command.command_type} "
                            f"executed by {module.name}: {result.data}"
                        )
                    else:
                        logger.error(
                            f"[{event.account_id}] Command {command.command_type} "
                            f"FAILED (module={module.name}): {result.error}"
                        )
                    
            except Exception as e:
                logger.error(f"[{module.account_id}] Module {module.name} error: {e}")
        
        return handler
    
    # ========== Command Execution ==========
    
    async def execute(self, account_id: str, command: Command) -> CommandResult:
        """
        Выполняет команду на указанном аккаунте.
        
        Args:
            account_id: ID аккаунта
            command: Команда для выполнения
            
        Returns:
            Результат выполнения команды
        """
        runtime = self._runtimes.get(account_id)
        if not runtime:
            logger.warning(f"Command {command.command_type} rejected: account {account_id} not found")
            return CommandResult.fail(f"Account {account_id} not found")

        if not runtime.is_running:
            logger.warning(
                f"[{account_id}] Command {command.command_type} rejected: "
                f"account is stopped (state={runtime.state.value})"
            )
            return CommandResult.fail(
                f"Account {account_id} is stopped. "
                "Start the account before executing commands."
            )
        
        logger.debug(
            f"[{account_id}] Routing command {command.command_type} to runtime"
        )
        return await runtime.execute(command)
    
    # ========== Lifecycle ==========
    
    async def start(self) -> None:
        """
        Запускает Core: Event Bus и все Runtimes (non-blocking).
        
        Runtime.start() и module.on_start() сами non-blocking,
        поэтому этот метод завершается мгновенно.
        """
        if self._running:
            return
        
        self._running = True
        logger.info("Starting Opium Core...")
        
        # Запускаем Event Bus
        await self.event_bus.start()
        
        # Запускаем on_start для модулей уже инициализированных аккаунтов
        for account_id, modules in self._account_modules.items():
            for module in modules.values():
                try:
                    logger.debug(f"[{account_id}] Starting module: {module.name}")
                    await module.on_start()
                    logger.info(f"[{account_id}] Module started: {module.name}")
                except Exception as e:
                    logger.error(f"[{account_id}] Module {module.name} on_start error: {e}")
        
        # Запускаем все инициализированные Runtimes (start() non-blocking)
        started = 0
        for runtime in self._runtimes.values():
            if runtime.is_initialized:
                await runtime.start()
                started += 1
        
        logger.info(
            f"Opium Core started: {self.account_count} accounts, "
            f"{started} running, {self.get_total_module_count()} modules"
        )
    
    async def stop(self) -> None:
        """Останавливает Core: все Runtimes, модули и Event Bus."""
        if not self._running:
            return
        
        self._running = False
        
        # Останавливаем все Runtimes
        for runtime in self._runtimes.values():
            await runtime.stop()
        
        # Запускаем on_stop для всех модулей
        for account_id, modules in self._account_modules.items():
            for module in modules.values():
                try:
                    await module.on_stop()
                except Exception as e:
                    logger.error(f"[{account_id}] Module {module.name} on_stop error: {e}")
        
        # Останавливаем Event Bus
        await self.event_bus.stop()
        
        logger.info("opium core stopped")
    
    @property
    def is_running(self) -> bool:
        """Core запущен."""
        return self._running
    
    @property
    def account_count(self) -> int:
        """Количество аккаунтов."""
        return len(self._runtimes)
    
    def get_total_module_count(self) -> int:
        """Общее количество инстансов модулей."""
        return sum(len(modules) for modules in self._account_modules.values())
    
    def __repr__(self) -> str:
        status = "running" if self._running else "stopped"
        modules = self.get_total_module_count()
        return f"OpiumCore({status}, accounts={self.account_count}, modules={modules})"
