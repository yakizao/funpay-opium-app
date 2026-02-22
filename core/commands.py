"""Opium Commands - система команд для взаимодействия с Account."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from enum import Enum


class CommandType(str, Enum):
    """Типы команд (соответствуют методам Account)."""
    
    # Сообщения
    SEND_MESSAGE = "send_message"
    SEND_IMAGE = "send_image"
    UPLOAD_IMAGE = "upload_image"
    GET_CHAT_HISTORY = "get_chat_history"
    GET_CHAT = "get_chat"
    
    # Заказы
    GET_ORDER = "get_order"
    GET_SELLS = "get_sells"
    REFUND = "refund"
    
    # Отзывы
    SEND_REVIEW = "send_review"
    DELETE_REVIEW = "delete_review"
    
    # Лоты
    GET_LOT_FIELDS = "get_lot_fields"
    SAVE_LOT = "save_lot"
    DELETE_LOT = "delete_lot"
    RAISE_LOTS = "raise_lots"
    GET_SUBCATEGORY_PUBLIC_LOTS = "get_subcategory_public_lots"
    GET_TRADE_PAGE_LOTS = "get_trade_page_lots"
    
    # Аккаунт
    GET_BALANCE = "get_balance"
    GET_USER = "get_user"
    CALCULATE = "calculate"
    GET_CATEGORIES = "get_categories"
    GET_MY_PROFILE = "get_my_profile"


@dataclass
class Command:
    """
    Команда для выполнения на аккаунте.
    
    Attributes:
        command_type: Тип команды
        params: Параметры команды
    """
    
    command_type: CommandType | str
    params: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        if isinstance(self.command_type, str):
            try:
                self.command_type = CommandType(self.command_type)
            except ValueError:
                pass  # Оставляем как строку для кастомных команд


@dataclass
class CommandResult:
    """
    Результат выполнения команды.
    
    Attributes:
        success: Успешно ли выполнена команда
        data: Данные результата (если успех)
        error: Сообщение об ошибке (если неудача)
    """
    
    success: bool
    data: Any = None
    error: str | None = None
    
    @classmethod
    def ok(cls, data: Any = None) -> CommandResult:
        """Создаёт успешный результат."""
        return cls(success=True, data=data)
    
    @classmethod
    def fail(cls, error: str) -> CommandResult:
        """Создаёт неуспешный результат."""
        return cls(success=False, error=error)
    
    @classmethod
    def from_exception(cls, exc: Exception) -> CommandResult:
        """Создаёт результат из исключения."""
        return cls(success=False, error=str(exc))
