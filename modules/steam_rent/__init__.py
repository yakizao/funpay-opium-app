# -*- coding: utf-8 -*-
"""
Steam Rent Module - Модуль аренды Steam-аккаунтов.

Функционал:
- Автовыдача аккаунта при покупке
- Бонусные часы за отзыв
- Множественные аренды одного пользователя
- Автоматическое освобождение по таймеру

Использование:
1. Добавить модуль в конфиг аккаунта: "modules": ["steam_rent"]
2. Настроить файлы в accounts/{id}/modules/steam_rent/

Структура файлов:
    accounts/{id}/modules/steam_rent/
    ├── config.json          # Настройки модуля
    ├── games.json           # Список игр
    ├── lot_mappings.json    # Привязка лотов FunPay к играм
    ├── steam_accounts.json  # Steam аккаунты
    ├── rentals.json         # Активные и завершённые аренды
    └── pending.json         # Заказы, ожидающие решения покупателя

Пример config.json:
{
    "change_password_on_rent": true,
    "kick_devices_on_rent": true,
    "scheduler_check_interval_sec": 60,
    "pending_ttl_minutes": 0
}

Пример games.json:
{
    "games": [
        {"game_id": "cs2", "aliases": ["cs2", "cs", "контра"]}
    ]
}

Пример lot_mappings.json:
{
    "lot_mappings": [
        {"lot_pattern": "CS2", "game_id": "cs2", "rent_minutes": 720, "bonus_minutes": 120}
    ]
}

Пример steam_accounts.json:
{
    "steam_accounts": [
        {
            "steam_account_id": "acc_001",
            "login": "steam_login",
            "password": "steam_password",
            "mafile": {"shared_secret": "...", "identity_secret": "..."},
            "game_ids": ["cs2"],
            "status": "free"
        }
    ]
}
"""

from .module import SteamRentModule
from .models import (
    Game,
    LotMapping,
    SteamAccount,
    Rental,
    AccountStatus,
    RentalStatus,
    # Proxy models
    Proxy,
    ProxyList,
    ProxySettings,
    ProxyType,
    ProxyMode,
    ProxyFallback,
)
from .storage import SteamRentStorage
from .scheduler import RentalScheduler
from .proxy import ProxyManager, get_proxy_manager

__all__ = [
    "SteamRentModule",
    "Game",
    "LotMapping",
    "SteamAccount",
    "Rental",
    "AccountStatus",
    "RentalStatus",
    "SteamRentStorage",
    "RentalScheduler",
    # Proxy
    "Proxy",
    "ProxyList",
    "ProxySettings",
    "ProxyType",
    "ProxyMode",
    "ProxyFallback",
    "ProxyManager",
    "get_proxy_manager",
]
