"""Opium Module - базовый класс модуля с файловым хранилищем."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .event_bus import OpiumEvent
    from .commands import Command
    from .storage import ModuleStorage


logger = logging.getLogger("opium.module")


@dataclass
class Subscription:
    """
    Описание подписки модуля на события.
    
    Attributes:
        event_types: Типы событий (None = все)
    """
    
    event_types: list[str] | None = None


class Module(ABC):
    """
    Базовый класс модуля Opium.
    
    Каждый инстанс модуля привязан к одному аккаунту и имеет:
    - account_id - ID аккаунта
    - storage - файловое хранилище (accounts/{account_id}/modules/{module_name}/)
    
    Структура файлов модуля:
        accounts/{account_id}/modules/{module_name}/
        ├── config.json     # Конфигурация (storage.config)
        ├── data.db         # SQLite база (storage.get_db_path())
        └── ...             # Любые другие файлы
    
    Lifecycle:
    1. Core загружает аккаунт из папки
    2. Core создаёт инстансы модулей по конфигу аккаунта
    3. Модуль получает storage с путём к своей папке
    4. При событии вызывается handle_event()
    5. Возвращённые команды выполняются на аккаунте
    
    BREAKING CHANGE v3.1: `name` теперь определяется через class-level
    атрибут `module_name: ClassVar[str]` вместо @property.
    Старый @property всё ещё работает (через фолбэк), но deprecated.
    """
    
    # Класс-атрибут: имя модуля (snake_case, без пробелов).
    # Определяется в подклассе: module_name = "steam_rent"
    module_name: ClassVar[str]
    
    def __init__(self, account_id: str, storage: "ModuleStorage") -> None:
        """
        Args:
            account_id: ID аккаунта, к которому привязан модуль
            storage: Хранилище данных модуля
        """
        self.account_id = account_id
        self.storage = storage
    
    @property
    def name(self) -> str:
        """
        Имя модуля (используется как имя папки).
        
        Возвращает module_name class-атрибут.
        Должно быть уникальным, snake_case, без пробелов.
        """
        return self.__class__.module_name
    
    def get_subscriptions(self) -> list[Subscription]:
        """
        Возвращает список подписок модуля.
        
        По умолчанию подписывается на все события.
        Переопределите для фильтрации.
        
        Returns:
            Список Subscription с фильтрами событий
        """
        return [Subscription()]
    
    @abstractmethod
    async def handle_event(self, event: "OpiumEvent") -> list["Command"]:
        """
        Обрабатывает входящее событие.
        
        Args:
            event: Событие Opium
            
        Returns:
            Список команд для выполнения (может быть пустым)
        """
        ...
    
    async def on_start(self) -> None:
        """
        Вызывается при запуске модуля.
        
        Используйте для:
        - Инициализации БД
        - Загрузки данных
        - Запуска фоновых задач
        """
        pass
    
    async def on_stop(self) -> None:
        """
        Вызывается при остановке модуля.
        
        Используйте для:
        - Сохранения состояния
        - Закрытия соединений
        - Остановки фоновых задач
        """
        pass
    
    # ========== Order Tags (universal module integration) ==========

    async def get_order_tags(
        self, orders: list[dict[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        Возвращает теги заказов, связанных с этим модулем.

        Модуль может переопределить этот метод, чтобы пометить заказы
        дополнительной информацией (игра, тип услуги и т.д.).

        Args:
            orders: Список сериализованных заказов (order_id, description, ...)
                    Передаётся из API для матчинга по описанию.
                    None если заказы недоступны.

        Returns:
            dict: order_id -> {"module": str, ...extra fields}
        """
        return {}

    # ========== Shortcuts для storage ==========
    
    @property
    def config(self) -> dict[str, Any]:
        """Конфигурация модуля из config.json."""
        return self.storage.config
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Получает значение из конфигурации."""
        return self.storage.get(key, default)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.account_id})"


# ========== Module Registry ==========

# Глобальный реестр классов модулей
_MODULE_REGISTRY: dict[str, type[Module]] = {}


def register_module_class(cls: type[Module]) -> type[Module]:
    """
    Декоратор для регистрации класса модуля.
    
    Использует module_name class-атрибут для регистрации.
    
    Пример:
        @register_module_class
        class AutoResponder(Module):
            module_name = "auto_responder"
    """
    if not hasattr(cls, 'module_name') or not isinstance(cls.module_name, str):
        raise TypeError(
            f"Module class {cls.__name__} must define "
            f"'module_name: ClassVar[str]' class attribute"
        )
    
    name = cls.module_name
    if name in _MODULE_REGISTRY:
        logger.warning(
            f"Module '{name}' re-registered: "
            f"{_MODULE_REGISTRY[name].__name__} -> {cls.__name__}"
        )
    
    _MODULE_REGISTRY[name] = cls
    logger.debug(f"Registered module: {name} ({cls.__name__})")
    return cls


def get_module_class(name: str) -> type[Module] | None:
    """Возвращает класс модуля по имени."""
    return _MODULE_REGISTRY.get(name)


def list_module_classes() -> dict[str, type[Module]]:
    """Возвращает все зарегистрированные классы модулей."""
    return dict(_MODULE_REGISTRY)

