"""
Opium Security - аутентификация, rate limiting, secure headers, IP whitelist.

Модуль безопасности для FastAPI приложения Opium.
Все компоненты конфигурируются через security/config.py и .env файл.

Структура:
    security/config.py       — SecurityConfig singleton
    security/auth.py         — JWT, хеширование, FastAPI Depends
    security/middleware.py   — HTTP middleware классы
    security/endpoints.py    — Auth/Health API endpoints
    security/brute_force.py  — BruteForceProtector
    security/rate_limit.py   — RateLimiter, LoginFailureTracker
    security/security_log.py — Security аудит лог
    security/setup.py        — setup_security() интеграция

Использование:
    from security.setup import setup_security
    setup_security(app)  # вызывать ПОСЛЕ CORS middleware
"""

from security.config import SecurityConfig, security_config
from security.auth import (
    create_access_token,
    verify_password,
    hash_password,
    get_current_user,
    AuthUser,
)
from security.setup import setup_security
from security.security_log import security_log
from security.brute_force import brute_force_protector

__all__ = [
    "SecurityConfig",
    "security_config",
    "create_access_token",
    "verify_password",
    "hash_password",
    "get_current_user",
    "AuthUser",
    "setup_security",
    "security_log",
    "brute_force_protector",
]
