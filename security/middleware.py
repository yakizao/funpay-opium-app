"""
Security Middleware — HTTP middleware классы для FastAPI.

Содержит ТОЛЬКО middleware (без endpoints, без setup):
- AuthMiddleware — проверка JWT для защищённых эндпоинтов
- RateLimitMiddleware — ограничение запросов per IP
- IPWhitelistMiddleware — фильтрация по IP
- SecureHeadersMiddleware — HSTS, CSP, X-Frame-Options

Endpoints → security/endpoints.py
Setup     → security/setup.py
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from security.auth import AuthUser, decode_access_token
from security.config import security_config
from security.rate_limit import login_tracker, rate_limiter
from security.security_log import security_log

logger = logging.getLogger("opium.security.middleware")


# ══════════════════════════════════════════════════════════════
# Auth Middleware
# ══════════════════════════════════════════════════════════════

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки JWT на всех защищённых эндпоинтах.

    Пропускает без auth:
    - public_paths (/, /docs, /api/auth/login, /api/health)
    - static_prefixes (/assets/)
    - OPTIONS запросы (CORS preflight)

    Если auth_enabled=False - пропускает всё.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not security_config.auth_enabled:
            return await call_next(request)

        # OPTIONS - CORS preflight
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Public paths
        if path in security_config.public_paths:
            return await call_next(request)

        # Static prefixes
        for prefix in security_config.static_prefixes:
            if path.startswith(prefix):
                return await call_next(request)

        # SPA fallback - не-API пути (фронтенд роутинг)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Извлекаем токен
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            security_log.record(
                "ACCESS_DENIED",
                ip=get_client_ip(request),
                path=path,
                method=request.method,
                detail="Missing or invalid Authorization header",
            )
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header[7:]  # Remove "Bearer "

        try:
            payload = decode_access_token(token)
            username = payload.get("sub")
            if not username:
                raise ValueError("No 'sub' in token")

            # Сохраняем user в request.state для использования в эндпоинтах
            request.state.user = AuthUser(
                username=username,
                issued_at=payload.get("iat", 0),
                expires_at=payload.get("exp", 0),
            )

        except ValueError as e:
            event_type = "TOKEN_EXPIRED" if "expired" in str(e).lower() else "TOKEN_INVALID"
            security_log.record(
                event_type,
                ip=get_client_ip(request),
                path=path,
                method=request.method,
                detail=str(e),
            )
            return JSONResponse(
                status_code=401,
                content={"detail": str(e)},
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


# ══════════════════════════════════════════════════════════════
# Rate Limit Middleware
# ══════════════════════════════════════════════════════════════

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting per IP.

    Отдельные лимиты для:
    - Общий API: rate_limit_per_minute
    - Login endpoint: login_rate_limit_per_minute
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not security_config.rate_limit_enabled:
            return await call_next(request)

        # OPTIONS - CORS preflight, don't consume rate limit tokens
        if request.method == "OPTIONS":
            return await call_next(request)

        ip = get_client_ip(request)
        path = request.url.path

        # Проверяем бан (brute-force protection)
        is_banned, remaining = login_tracker.is_banned(ip)
        if is_banned:
            security_log.record(
                "IP_BLOCKED",
                ip=ip,
                path=path,
                method=request.method,
                detail=f"Banned for brute-force. Remaining: {remaining}s",
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many failed attempts. Try again in {remaining} seconds.",
                    "retry_after": remaining,
                },
                headers={"Retry-After": str(remaining)},
            )

        # Лимит для login endpoint
        if path == "/api/auth/login" and request.method == "POST":
            rate = security_config.login_rate_limit_per_minute
            key = f"login:{ip}"
        else:
            rate = security_config.rate_limit_per_minute
            key = f"api:{ip}"

        if not rate_limiter.check(key, rate):
            security_log.record(
                "RATE_LIMITED",
                ip=ip,
                path=path,
                method=request.method,
                detail=f"Rate limit exceeded ({rate}/min)",
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down."},
                headers={"Retry-After": "60"},
            )

        response = await call_next(request)

        # Добавляем rate limit headers
        remaining = rate_limiter.get_remaining(key)
        if remaining >= 0:
            response.headers["X-RateLimit-Limit"] = str(rate)
            response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


# ══════════════════════════════════════════════════════════════
# IP Whitelist Middleware
# ══════════════════════════════════════════════════════════════

class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """
    Опциональный IP whitelist.

    Если ip_whitelist_enabled=True, разрешает запросы ТОЛЬКО с IP из whitelist.
    Поддерживает CIDR нотацию (напр. 192.168.1.0/24).
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not security_config.ip_whitelist_enabled:
            return await call_next(request)

        # OPTIONS - CORS preflight, always allow
        if request.method == "OPTIONS":
            return await call_next(request)

        ip = get_client_ip(request)

        if not self._is_allowed(ip):
            security_log.record(
                "IP_BLOCKED",
                ip=ip,
                path=request.url.path,
                method=request.method,
                detail="IP not in whitelist",
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied"},
            )

        return await call_next(request)

    @staticmethod
    def _is_allowed(ip: str) -> bool:
        """Проверить IP против whitelist."""
        try:
            addr = ipaddress.ip_address(ip)
            for entry in security_config.ip_whitelist:
                try:
                    if "/" in entry:
                        network = ipaddress.ip_network(entry, strict=False)
                        if addr in network:
                            return True
                    else:
                        if addr == ipaddress.ip_address(entry):
                            return True
                except ValueError:
                    continue
        except ValueError:
            logger.warning(f"Invalid IP address: {ip}")
            return False

        return False


# ══════════════════════════════════════════════════════════════
# Secure Headers Middleware
# ══════════════════════════════════════════════════════════════

class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """
    Добавляет security headers ко всем ответам.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        if not security_config.secure_headers_enabled:
            return response

        # Защита от clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Защита от MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # XSS Protection
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer Policy
        response.headers["Referrer-Policy"] = security_config.referrer_policy
        # Permissions Policy
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        # CSP
        response.headers["Content-Security-Policy"] = security_config.csp_policy

        # HSTS (только если за reverse proxy с HTTPS)
        # Раскомментировать при HTTPS:
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════


def get_client_ip(request: Request) -> str:
    """Получить реальный IP клиента (поддержка X-Forwarded-For для reverse proxy)."""
    # X-Forwarded-For: client, proxy1, proxy2
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # X-Real-IP (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback
    if request.client:
        return request.client.host

    return "unknown"

