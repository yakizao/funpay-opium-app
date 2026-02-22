# -*- coding: utf-8 -*-
"""
Steam Rent - Rental Models.

Rental domain: enums, dataclasses, deserialization, utilities.
- AccountStatus, RentalStatus
- Game, LotMapping, SteamAccount, Rental, PendingOrder, PendingReview
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from .proxy import ProxySettings, proxy_settings_from_dict


# =============================================================================
# ENUMS
# =============================================================================

class AccountStatus(str, Enum):
    """Статус Steam аккаунта."""
    FREE = "free"
    RENTED = "rented"


class RentalStatus(str, Enum):
    """Статус аренды."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


# =============================================================================
# CONFIGURATION MODELS (создаются вручную)
# =============================================================================

@dataclass
class Game:
    """
    Игра - создаётся вручную.
    
    Attributes:
        game_id: Уникальный ID игры (используется также как название)
        aliases: Алиасы для команд пользователя (!status cs)
                 НЕ используются для определения аренды!
        proxy_settings: Настройки прокси для игры (переопределяют настройки аккаунта)
    """
    game_id: str
    aliases: list[str] = field(default_factory=list)
    proxy_settings: ProxySettings | None = None
    frozen: bool = False
    
    def matches_alias(self, query: str) -> bool:
        """Проверяет совпадение с алиасом (для команд пользователя)."""
        q = query.lower().strip()
        if q == self.game_id.lower():
            return True
        return any(q == alias.lower() for alias in self.aliases)


@dataclass
class LotMapping:
    """
    Маппинг FunPay лота на игру и параметры аренды.
    
    Поиск лота происходит по ПОДСТРОКЕ (lot_pattern содержится в названии лота).
    Это позволяет не указывать точное название.
    
    Всё время хранится в МИНУТАХ.
    
    Attributes:
        lot_pattern: Паттерн для поиска в названии лота (регистронезависимый)
        game_id: ID игры из Game
        rent_minutes: Время аренды в минутах
        bonus_minutes: Бонусные минуты за положительный отзыв
        min_rating_for_bonus: Минимальный рейтинг для бонуса (по умолчанию 4)
    """
    lot_pattern: str
    game_id: str
    rent_minutes: int = 0
    bonus_minutes: int = 0
    min_rating_for_bonus: int = 4
    
    def matches(self, lot_name: str) -> bool:
        """Проверяет, соответствует ли название лота этому маппингу."""
        return self.lot_pattern.lower() in lot_name.lower()


@dataclass
class SteamAccount:
    """
    Steam аккаунт - добавляется вручную.
    
    Attributes:
        steam_account_id: Уникальный ID аккаунта в системе
        login: Steam логин
        password: Текущий пароль
        mafile: Данные mafile (shared_secret, identity_secret и т.д.)
        game_ids: Список ID игр, привязанных к аккаунту
        status: Текущий статус (free/rented)
        password_history: История паролей (для исключения повторов)
        change_password_on_rent: Менять пароль при выдаче аренды
        kick_devices_on_rent: Кикать устройства при выдаче аренды
        proxy_settings: Настройки прокси для аккаунта
    """
    steam_account_id: str
    login: str
    password: str
    mafile: dict[str, Any] = field(default_factory=dict)
    game_ids: list[str] = field(default_factory=list)
    status: AccountStatus = AccountStatus.FREE
    password_history: list[str] = field(default_factory=list)
    change_password_on_rent: bool = False
    kick_devices_on_rent: bool = False
    proxy_settings: ProxySettings | None = None
    frozen: bool = False
    
    @property
    def shared_secret(self) -> str:
        """Shared secret для генерации Guard кода."""
        return self.mafile.get("shared_secret", "")
    
    @property
    def identity_secret(self) -> str:
        """Identity secret для подтверждений."""
        return self.mafile.get("identity_secret", "")


# =============================================================================
# STATE MODEL (автоматически создаётся при заказе)
# =============================================================================

@dataclass
class Rental:
    """
    Аренда - основная сущность модуля.
    
    КРИТИЧНО:
    - Один пользователь может иметь НЕСКОЛЬКО активных аренд
    - Каждая аренда НЕЗАВИСИМА
    - Аренды НЕ перезаписывают друг друга
    
    Attributes:
        rental_id: Уникальный ID аренды (UUID)
        order_id: ID заказа FunPay
        buyer_id: ID покупателя на FunPay
        buyer_username: Username покупателя
        game_id: ID игры
        steam_account_id: ID выданного Steam аккаунта
        start_time: Время начала аренды (ISO format)
        end_time: Время окончания аренды (ISO format)
        bonus_minutes: Накопленные бонусные минуты
        status: Статус аренды
        
        # Данные выдачи (сохраняются на момент выдачи)
        delivered_login: Логин на момент выдачи
        delivered_password: Пароль на момент выдачи
        delivery_pending: Ожидает доставки данных покупателю (True = ещё не отправлено)
    """
    rental_id: str
    order_id: str
    buyer_id: int
    buyer_username: str
    game_id: str
    steam_account_id: str
    start_time: str
    end_time: str
    entitled_bonus_minutes: int = 0
    min_rating_for_bonus: int = 4
    bonus_minutes: int = 0
    status: RentalStatus = RentalStatus.ACTIVE
    delivered_login: str = ""
    delivered_password: str = ""
    delivery_pending: bool = False
    chat_id: int | str = 0
    chat_name: str = ""
    warning_sent: bool = False
    
    @property
    def start_datetime(self) -> datetime:
        """Время начала как datetime."""
        return datetime.fromisoformat(self.start_time)
    
    @property
    def end_datetime(self) -> datetime:
        """Время окончания как datetime."""
        return datetime.fromisoformat(self.end_time)
    
    @property
    def remaining_time(self) -> timedelta:
        """Оставшееся время аренды."""
        now = datetime.now()
        end = self.end_datetime
        if now >= end:
            return timedelta(0)
        return end - now
    
    @property
    def is_expired(self) -> bool:
        """Истекла ли аренда по времени."""
        return datetime.now() >= self.end_datetime
    
    def add_bonus_minutes(self, minutes: int) -> None:
        """Добавляет бонусные минуты и пересчитывает end_time."""
        self.bonus_minutes += minutes
        end = self.end_datetime + timedelta(minutes=minutes)
        self.end_time = end.isoformat()
    
    def remove_bonus_minutes(self, minutes: int) -> None:
        """Убирает бонусные минуты и пересчитывает end_time."""
        minutes_to_remove = min(minutes, self.bonus_minutes)
        self.bonus_minutes -= minutes_to_remove
        end = self.end_datetime - timedelta(minutes=minutes_to_remove)
        # Не позволяем end_time уйти в прошлое
        if end < datetime.now():
            end = datetime.now()
        self.end_time = end.isoformat()
    
    def extend_time_minutes(self, minutes: int) -> None:
        """Продлевает аренду на указанное количество минут."""
        end = self.end_datetime + timedelta(minutes=minutes)
        self.end_time = end.isoformat()


@dataclass
class PendingOrder:
    """
    Ожидающий обработки заказ.
    
    Создаётся когда покупатель оплатил лот, но у него уже есть
    активная аренда на эту игру. Покупатель должен выбрать:
    - !аренда игра → новый аккаунт
    - !продлить логин → продление существующей аренды
    
    Attributes:
        order_id: ID заказа FunPay
        buyer_id: ID покупателя
        buyer_username: Username покупателя
        game_id: ID игры (из LotMapping)
        rent_minutes: Оплаченное время в минутах
        bonus_minutes: Бонус за отзыв (из LotMapping)
        min_rating_for_bonus: Мин. рейтинг для бонуса
        chat_id: ID чата для ответа
        chat_name: Имя чата
        created_at: Время создания (ISO format)
    """
    order_id: str
    buyer_id: int
    buyer_username: str
    game_id: str
    rent_minutes: int
    bonus_minutes: int = 0
    min_rating_for_bonus: int = 4
    chat_id: int | str = 0
    chat_name: str = ""
    created_at: str = ""


@dataclass
class PendingReview:
    """
    Отложенная проверка отзыва.

    Создаётся при NEW_FEEDBACK (3) или FEEDBACK_CHANGED (4).
    Планировщик вызывает get_order(), проверяет review.stars
    против min_rating_for_bonus и начисляет/убирает бонус.

    Attributes:
        order_id: ID заказа FunPay
        rental_id: ID аренды
        review_type: Тип сообщения (3=new, 4=changed)
        created_at: Время создания (ISO format)
    """
    order_id: str
    rental_id: str
    review_type: int  # MESSAGE_TYPE_NEW_FEEDBACK=3 or MESSAGE_TYPE_FEEDBACK_CHANGED=4
    created_at: str  # ISO format


# =============================================================================
# DESERIALIZATION
# =============================================================================

def game_from_dict(data: dict[str, Any]) -> Game:
    """Десериализует Game из dict."""
    return Game(
        game_id=data["game_id"],
        aliases=data.get("aliases", []),
        proxy_settings=proxy_settings_from_dict(data.get("proxy_settings")),
        frozen=data.get("frozen", False),
    )


def lot_mapping_from_dict(data: dict[str, Any]) -> LotMapping:
    """
    Десериализует LotMapping из dict.
    
    Backward compat:
    - rent_hours/rent_minutes → rent_minutes
    - bonus_hours/bonus_minutes → bonus_minutes
    - bonus_minutes_on_review → bonus_minutes
    """
    # Rent: hours*60 + minutes, or just minutes
    rent_minutes = data.get("rent_hours", 0) * 60 + data.get("rent_minutes", 0)
    
    # Bonus: hours*60 + minutes, with old-format fallback
    bonus_minutes = data.get("bonus_hours", 0) * 60 + data.get("bonus_minutes", 0)
    if bonus_minutes == 0 and "bonus_minutes_on_review" in data:
        bonus_minutes = data["bonus_minutes_on_review"]
    
    return LotMapping(
        lot_pattern=data["lot_pattern"],
        game_id=data["game_id"],
        rent_minutes=rent_minutes,
        bonus_minutes=bonus_minutes,
        min_rating_for_bonus=data.get("min_rating_for_bonus", 4),
    )


def _parse_game_ids(data: dict[str, Any]) -> list[str]:
    """Parse game_ids from dict, with backward compat for old 'game_id' field."""
    if "game_ids" in data:
        return list(data["game_ids"])
    # Backward compat: old format had single "game_id"
    game_id = data.get("game_id", "")
    return [game_id] if game_id else []


def steam_account_from_dict(data: dict[str, Any]) -> SteamAccount:
    """Десериализует SteamAccount из dict."""
    status = data.get("status", "free")
    if isinstance(status, str):
        status = AccountStatus(status)
    
    return SteamAccount(
        steam_account_id=data["steam_account_id"],
        login=data["login"],
        password=data["password"],
        mafile=data.get("mafile", {}),
        game_ids=_parse_game_ids(data),
        status=status,
        password_history=data.get("password_history", []),
        change_password_on_rent=data.get("change_password_on_rent", False),
        kick_devices_on_rent=data.get("kick_devices_on_rent", False),
        proxy_settings=proxy_settings_from_dict(data.get("proxy_settings")),
        frozen=data.get("frozen", False),
    )


def rental_from_dict(data: dict[str, Any]) -> Rental:
    """Десериализует Rental из dict."""
    status = data.get("status", "active")
    if isinstance(status, str):
        status = RentalStatus(status)
    
    return Rental(
        rental_id=data["rental_id"],
        order_id=data["order_id"],
        buyer_id=data["buyer_id"],
        buyer_username=data.get("buyer_username", ""),
        game_id=data["game_id"],
        steam_account_id=data["steam_account_id"],
        start_time=data["start_time"],
        end_time=data["end_time"],
        entitled_bonus_minutes=data.get("entitled_bonus_minutes", 0),
        min_rating_for_bonus=data.get("min_rating_for_bonus", 4),
        bonus_minutes=data.get("bonus_minutes", data.get("bonus_hours", 0) * 60),
        status=status,
        delivered_login=data.get("delivered_login", ""),
        delivered_password=data.get("delivered_password", ""),
        delivery_pending=data.get("delivery_pending", False),
        chat_id=data.get("chat_id", 0),
        chat_name=data.get("chat_name", ""),
        warning_sent=data.get("warning_sent", False),
    )


def pending_order_from_dict(data: dict[str, Any]) -> PendingOrder:
    """Десериализует PendingOrder из dict."""
    return PendingOrder(
        order_id=data["order_id"],
        buyer_id=data["buyer_id"],
        buyer_username=data.get("buyer_username", ""),
        game_id=data["game_id"],
        rent_minutes=data["rent_minutes"],
        bonus_minutes=data.get("bonus_minutes", 0),
        min_rating_for_bonus=data.get("min_rating_for_bonus", 4),
        chat_id=data.get("chat_id", 0),
        chat_name=data.get("chat_name", ""),
        created_at=data.get("created_at", ""),
    )


def pending_review_from_dict(data: dict[str, Any]) -> PendingReview:
    """Десериализует PendingReview из dict."""
    return PendingReview(
        order_id=data["order_id"],
        rental_id=data["rental_id"],
        review_type=data["review_type"],
        created_at=data["created_at"],
    )


# =============================================================================
# UTILS
# =============================================================================

# Regex для извлечения order_id из системных сообщений FunPay
ORDER_ID_REGEX = re.compile(r"#([A-Z0-9]{8})")


def extract_order_id(text: str) -> str | None:
    """
    Извлекает order_id из текста системного сообщения FunPay.
    
    Пример: "Покупатель Username написал отзыв к заказу #ABCD1234." -> "ABCD1234"
    """
    match = ORDER_ID_REGEX.search(text)
    return match.group(1) if match else None


def format_remaining_time(td: timedelta) -> str:
    """Форматирует оставшееся время в читаемый вид."""
    total_seconds = int(td.total_seconds())
    if total_seconds <= 0:
        return "истекло"
    
    hours, remainder = divmod(total_seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}ч {minutes}м"
    return f"{minutes}м"
