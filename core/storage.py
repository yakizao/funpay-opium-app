"""Opium Storage - файловое хранилище для аккаунтов и модулей."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from .runtime import AccountConfig, ReconnectConfig
from .rate_limiter import AntiDetectConfig, RateLimitConfig


logger = logging.getLogger("opium.storage")


@dataclass
class AccountData:
    """
    Данные аккаунта из файла.
    
    Attributes:
        account_id: ID аккаунта (имя папки)
        golden_key: Токен авторизации
        user_agent: User-Agent браузера
        proxy: Прокси (опционально)
        enabled: Включён ли аккаунт
        anti_detect: Настройки антидетекта
        rate_limit: Настройки rate limiting
        reconnect: Настройки переподключения
        disable_messages: Отключить события сообщений
        disable_orders: Отключить события заказов
    """
    
    account_id: str
    golden_key: str
    user_agent: str
    proxy: dict[str, str] | None = None
    enabled: bool = True
    anti_detect: dict[str, Any] | None = None
    rate_limit: dict[str, Any] | None = None
    reconnect: dict[str, Any] | None = None
    disable_messages: bool = False
    disable_orders: bool = False
    
    def to_config(self) -> AccountConfig:
        """Конвертирует в AccountConfig."""
        return AccountConfig(
            golden_key=self.golden_key,
            user_agent=self.user_agent,
            proxy=self.proxy,
            disable_messages=self.disable_messages,
            disable_orders=self.disable_orders,
            anti_detect=AntiDetectConfig(**self.anti_detect) if self.anti_detect else AntiDetectConfig(),
            rate_limit=RateLimitConfig(**self.rate_limit) if self.rate_limit else RateLimitConfig(),
            reconnect=ReconnectConfig(**self.reconnect) if self.reconnect else ReconnectConfig(),
        )


class ModuleStorage:
    """
    Хранилище данных модуля для конкретного аккаунта.
    
    Предоставляет доступ к:
    - config.json - конфигурация модуля
    - Любым файлам/папкам в директории модуля
    """
    
    def __init__(self, module_path: Path) -> None:
        """
        Args:
            module_path: Путь к папке модуля (accounts/{account_id}/modules/{module_name}/)
        """
        self.path = module_path
        self.path.mkdir(parents=True, exist_ok=True)
        self._config_path = self.path / "config.json"
        self._config_cache: dict[str, Any] | None = None
    
    @property
    def config(self) -> dict[str, Any]:
        """Конфигурация модуля (lazy load + cache)."""
        if self._config_cache is None:
            self._config_cache = self.load_config()
        return self._config_cache
    
    def load_config(self) -> dict[str, Any]:
        """Загружает конфигурацию из config.json."""
        if not self._config_path.exists():
            return {}
        try:
            return json.loads(self._config_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load config from {self._config_path}: {e}")
            return {}
    
    def save_config(self, config: dict[str, Any]) -> None:
        """Сохраняет конфигурацию в config.json."""
        self._config_cache = config
        self._config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def update_config(self, **kwargs: Any) -> None:
        """Обновляет отдельные поля конфигурации."""
        cfg = self.config.copy()
        cfg.update(kwargs)
        self.save_config(cfg)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение из конфигурации."""
        return self.config.get(key, default)
    
    def get_file_path(self, filename: str) -> Path:
        """Возвращает путь к файлу в директории модуля."""
        return self.path / filename
    
    def get_db_path(self, name: str = "data") -> Path:
        """Возвращает путь к SQLite базе данных."""
        return self.path / f"{name}.db"
    
    def file_exists(self, filename: str) -> bool:
        """Проверяет существование файла."""
        return (self.path / filename).exists()
    
    def read_json(self, filename: str) -> dict[str, Any] | list[Any] | None:
        """Читает JSON файл."""
        path = self.path / filename
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read JSON {path}: {e}")
            return None
    
    def write_json(self, filename: str, data: Any) -> None:
        """Записывает JSON файл."""
        path = self.path / filename
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )


class AccountStorage:
    """
    Хранилище данных аккаунта.
    
    Структура:
        accounts/{account_id}/
        ├── account.json      # Конфигурация аккаунта
        └── modules/          # Папки модулей
            ├── module_1/
            └── module_2/
    """
    
    def __init__(self, account_path: Path) -> None:
        """
        Args:
            account_path: Путь к папке аккаунта
        """
        self.path = account_path
        self.account_id = account_path.name
        self._modules_path = self.path / "modules"
        self._config_path = self.path / "account.json"
        self._module_storages: dict[str, ModuleStorage] = {}
    
    def exists(self) -> bool:
        """Проверяет существование папки аккаунта."""
        return self.path.exists() and self._config_path.exists()
    
    def load_account_data(self) -> AccountData | None:
        """Загружает данные аккаунта из account.json."""
        if not self._config_path.exists():
            return None
        try:
            data = json.loads(self._config_path.read_text(encoding="utf-8"))
            data["account_id"] = self.account_id
            return AccountData(**data)
        except Exception as e:
            logger.error(f"Failed to load account {self.account_id}: {e}")
            return None
    
    def save_account_data(self, data: AccountData) -> None:
        """Сохраняет данные аккаунта."""
        self.path.mkdir(parents=True, exist_ok=True)
        d: dict[str, Any] = {
            "golden_key": data.golden_key,
            "user_agent": data.user_agent,
            "proxy": data.proxy,
            "enabled": data.enabled,
            "anti_detect": data.anti_detect,
            "rate_limit": data.rate_limit,
            "reconnect": data.reconnect,
            "disable_messages": data.disable_messages,
            "disable_orders": data.disable_orders,
        }
        self._config_path.write_text(
            json.dumps(d, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def get_module_storage(self, module_name: str) -> ModuleStorage:
        """
        Возвращает хранилище для модуля.
        
        Args:
            module_name: Имя модуля
            
        Returns:
            ModuleStorage для данного модуля
        """
        if module_name not in self._module_storages:
            module_path = self._modules_path / module_name
            self._module_storages[module_name] = ModuleStorage(module_path)
        return self._module_storages[module_name]
    
    def list_module_configs(self) -> list[str]:
        """Возвращает список модулей, установленных для аккаунта.
        
        Модуль считается установленным если его директория существует
        (config.json может отсутствовать — модуль использует дефолты).
        """
        if not self._modules_path.exists():
            return []
        return [
            d.name for d in self._modules_path.iterdir()
            if d.is_dir()
        ]


class Storage:
    """
    Главное хранилище - менеджер всех аккаунтов.
    
    Структура:
        {base_path}/
        └── accounts/
            ├── shop_1/
            ├── shop_2/
            └── ...
    """
    
    def __init__(self, base_path: str | Path = ".") -> None:
        """
        Args:
            base_path: Базовый путь (по умолчанию текущая директория)
        """
        self.base_path = Path(base_path)
        self.accounts_path = self.base_path / "accounts"
        self._account_storages: dict[str, AccountStorage] = {}
    
    def get_account_storage(self, account_id: str) -> AccountStorage:
        """
        Возвращает хранилище для аккаунта.
        
        Args:
            account_id: ID аккаунта
            
        Returns:
            AccountStorage для данного аккаунта
        """
        if account_id not in self._account_storages:
            account_path = self.accounts_path / account_id
            self._account_storages[account_id] = AccountStorage(account_path)
        return self._account_storages[account_id]
    
    def list_accounts(self, enabled_only: bool = True) -> list[AccountData]:
        """
        Возвращает список всех аккаунтов.
        
        Args:
            enabled_only: Только включённые аккаунты
            
        Returns:
            Список AccountData
        """
        if not self.accounts_path.exists():
            return []
        
        accounts: list[AccountData] = []
        for account_dir in self.accounts_path.iterdir():
            if not account_dir.is_dir():
                continue
            
            storage = self.get_account_storage(account_dir.name)
            data = storage.load_account_data()
            
            if data is None:
                continue
            if enabled_only and not data.enabled:
                continue
                
            accounts.append(data)
        
        return accounts
    
    def create_account(
        self,
        account_id: str,
        golden_key: str,
        user_agent: str,
        **kwargs: Any
    ) -> AccountData:
        """
        Создаёт новый аккаунт.
        
        Args:
            account_id: ID аккаунта
            golden_key: Токен авторизации
            user_agent: User-Agent
            **kwargs: Дополнительные параметры AccountData
            
        Returns:
            Созданный AccountData
        """
        storage = self.get_account_storage(account_id)
        
        data = AccountData(
            account_id=account_id,
            golden_key=golden_key,
            user_agent=user_agent,
            **kwargs
        )
        storage.save_account_data(data)
        logger.info(f"Created account: {account_id}")
        return data
    
    def delete_account(self, account_id: str) -> bool:
        """
        Удаляет аккаунт (помечает как disabled, не удаляет файлы).
        
        Args:
            account_id: ID аккаунта
            
        Returns:
            True если аккаунт существовал
        """
        storage = self.get_account_storage(account_id)
        data = storage.load_account_data()
        
        if data is None:
            return False
        
        data.enabled = False
        storage.save_account_data(data)
        logger.info(f"Disabled account: {account_id}")
        return True
