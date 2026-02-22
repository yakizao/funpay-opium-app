"""
Security Setup — интеграция всех security-компонентов в FastAPI.

Единая точка входа: setup_security(app) подключает middleware, роутеры, логи.
Вызывать ПОСЛЕ CORS middleware.

Использование:
    from security.setup import setup_security
    setup_security(app)
"""

from __future__ import annotations

import logging

from fastapi import FastAPI

from security.config import security_config
from security.endpoints import auth_router, health_router
from security.middleware import (
    AuthMiddleware,
    IPWhitelistMiddleware,
    RateLimitMiddleware,
    SecureHeadersMiddleware,
)
from security.security_log import security_log

logger = logging.getLogger("opium.security.setup")


def setup_security(app: FastAPI) -> None:
    """
    Подключить все security компоненты к FastAPI приложению.

    Порядок middleware ВАЖЕН (выполняются в ОБРАТНОМ порядке добавления):
    1. SecureHeaders  (последний добавленный = первый по выполнению)
    2. IPWhitelist
    3. RateLimit
    4. Auth

    Вызывать ПОСЛЕ CORS middleware.
    """
    # Загружаем конфигурацию
    security_config.load()

    # Инициализируем security log
    security_log.initialize()

    # Подключаем роутеры
    app.include_router(auth_router)
    app.include_router(health_router)

    # Middleware (порядок: последний добавленный = первый выполняемый)
    # Поэтому добавляем в обратном порядке:

    # 4. Auth — последний по выполнению
    app.add_middleware(AuthMiddleware)

    # 3. Rate Limit
    app.add_middleware(RateLimitMiddleware)

    # 2. IP Whitelist
    app.add_middleware(IPWhitelistMiddleware)

    # 1. Secure Headers — первый по выполнению
    app.add_middleware(SecureHeadersMiddleware)

    logger.info(
        f"Security initialized: "
        f"auth={'ON' if security_config.auth_enabled else 'OFF'}, "
        f"rate_limit={'ON' if security_config.rate_limit_enabled else 'OFF'}, "
        f"ip_whitelist={'ON' if security_config.ip_whitelist_enabled else 'OFF'}, "
        f"secure_headers={'ON' if security_config.secure_headers_enabled else 'OFF'}"
    )
