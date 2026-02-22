# -*- coding: utf-8 -*-
"""
Steam Rent - Models Package.

Re-exports all public names for backward compatibility.
``from .models import Game, Rental, ...`` continues to work unchanged.

Shared serialization (to_dict) lives here to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Any

# ── Shared serialization ─────────────────────────────────────────────────────

def to_dict(obj: Any) -> dict[str, Any]:
    """Сериализует dataclass в dict с рекурсивной обработкой Enum."""
    if not hasattr(obj, "__dataclass_fields__"):
        return obj
    
    d = asdict(obj)
    _convert_enums(d)
    return d


def _convert_enums(obj: Any) -> Any:
    """Рекурсивно конвертирует Enum значения в строки."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, Enum):
                obj[k] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, Enum):
                obj[i] = v.value
            elif isinstance(v, (dict, list)):
                _convert_enums(v)


# ── Re-exports: Proxy domain ─────────────────────────────────────────────────

from .proxy import (  # noqa: E402
    ProxyType,
    ProxyMode,
    ProxyFallback,
    Proxy,
    ProxyList,
    ProxySettings,
    proxy_settings_from_dict,
    proxy_from_dict,
    proxy_list_from_dict,
)

# ── Re-exports: Rental domain ────────────────────────────────────────────────

from .rental import (  # noqa: E402
    AccountStatus,
    RentalStatus,
    Game,
    LotMapping,
    SteamAccount,
    Rental,
    PendingOrder,
    PendingReview,
    game_from_dict,
    lot_mapping_from_dict,
    steam_account_from_dict,
    rental_from_dict,
    pending_order_from_dict,
    pending_review_from_dict,
    extract_order_id,
    format_remaining_time,
)

__all__ = [
    # Serialization
    "to_dict",
    # Proxy domain
    "ProxyType",
    "ProxyMode",
    "ProxyFallback",
    "Proxy",
    "ProxyList",
    "ProxySettings",
    "proxy_settings_from_dict",
    "proxy_from_dict",
    "proxy_list_from_dict",
    # Rental domain
    "AccountStatus",
    "RentalStatus",
    "Game",
    "LotMapping",
    "SteamAccount",
    "Rental",
    "PendingOrder",
    "PendingReview",
    "game_from_dict",
    "lot_mapping_from_dict",
    "steam_account_from_dict",
    "rental_from_dict",
    "pending_order_from_dict",
    "pending_review_from_dict",
    "extract_order_id",
    "format_remaining_time",
]
