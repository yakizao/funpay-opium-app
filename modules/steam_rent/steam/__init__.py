# -*- coding: utf-8 -*-
"""
Steam API operations package.

This package was split from a single steam.py file into logical modules.
All public names are re-exported here for backward compatibility.

Usage (both forms work):
    from modules.steam_rent.steam import change_password, generate_guard_code
    from modules.steam_rent import steam; steam.change_password(...)
"""

# Result types
from .types import KickSessionsResult, PasswordChangeResult

# HTTP wrapper
from .http import SteamHTTP, USER_AGENT

# Guard / crypto
from .guard import (
    STEAM_ALPHABET,
    generate_confirmation_key,
    generate_device_id,
    generate_guard_code,
)

# Session management
from .session import SessionCache, SteamSession, SteamUrls

# Confirmations
from .confirmations import confirm_confirmation, get_confirmations

# High-level operations
from .operations import (
    change_password,
    generate_random_password,
    kick_all_sessions,
)

__all__ = [
    # Types
    "PasswordChangeResult",
    "KickSessionsResult",
    # HTTP
    "SteamHTTP",
    "USER_AGENT",
    # Guard / crypto
    "STEAM_ALPHABET",
    "generate_guard_code",
    "generate_device_id",
    "generate_confirmation_key",
    # Session
    "SteamSession",
    "SessionCache",
    "SteamUrls",
    # Confirmations
    "get_confirmations",
    "confirm_confirmation",
    # Operations
    "change_password",
    "kick_all_sessions",
    "generate_random_password",
]
