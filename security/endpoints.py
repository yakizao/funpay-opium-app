"""
Security Endpoints — auth и health API endpoints.

Роутеры:
- auth_router:   /api/auth/login, /api/auth/me, /api/auth/refresh, /api/auth/config
- health_router: /api/health (без аутентификации)

API контракт СТАБИЛЕН — URL и формат ответа не меняются.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from security.auth import (
    AuthUser,
    create_access_token,
    decode_access_token,
    get_current_user,
    verify_password,
)
from security.brute_force import brute_force_protector
from security.config import security_config
from security.middleware import get_client_ip
from security.security_log import security_log

logger = logging.getLogger("opium.security.endpoints")


# ══════════════════════════════════════════════════════════════
# Pydantic Models
# ══════════════════════════════════════════════════════════════


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ══════════════════════════════════════════════════════════════
# Auth Router
# ══════════════════════════════════════════════════════════════

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login", response_model=LoginResponse)
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    """
    Аутентификация — получение JWT токена.

    Body:
        username: str
        password: str

    Response:
        access_token: str (JWT)
        token_type: "bearer"
        expires_in: int (секунды)
        username: str
    """
    ip = get_client_ip(request)

    # Brute-force check (raises 429 if banned)
    brute_force_protector.check_allowed(ip, body.username)

    # Проверяем credentials
    if body.username != security_config.admin_username:
        brute_force_protector.record_failure(ip, body.username, "Invalid username")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not security_config.admin_password_hash:
        raise HTTPException(
            status_code=503,
            detail="Admin password not configured. Run: python -m security.auth --setup",
        )

    if not verify_password(body.password, security_config.admin_password_hash):
        brute_force_protector.record_failure(ip, body.username, "Invalid password")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Успешный логин
    brute_force_protector.record_success(ip)

    expires_in_seconds = security_config.access_token_expire_minutes * 60
    token = create_access_token({"sub": body.username})

    security_log.record(
        "LOGIN_SUCCESS",
        ip=ip,
        username=body.username,
        path="/api/auth/login",
        method="POST",
        detail="Successful login",
    )

    return LoginResponse(
        access_token=token,
        expires_in=expires_in_seconds,
        username=body.username,
    )


@auth_router.get("/me")
async def get_me(request: Request, user: AuthUser = Depends(get_current_user)):
    """Получить информацию о текущем пользователе."""
    return {
        "username": user.username,
        "issued_at": user.issued_at,
        "expires_at": user.expires_at,
    }


@auth_router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh_token(
    request: Request, user: AuthUser = Depends(get_current_user)
) -> TokenRefreshResponse:
    """Обновить JWT токен (требует действующий токен)."""
    expires_in_seconds = security_config.access_token_expire_minutes * 60
    token = create_access_token({"sub": user.username})

    security_log.record(
        "TOKEN_REFRESHED",
        ip=get_client_ip(request),
        username=user.username,
        path="/api/auth/refresh",
        method="POST",
        detail="Token refreshed",
    )

    return TokenRefreshResponse(
        access_token=token,
        expires_in=expires_in_seconds,
    )


@auth_router.get("/config")
async def get_security_config():
    """
    Получить текущую security конфигурацию (без секретов).

    Публичный endpoint — доступен без авторизации.
    Cache-Control: no-store — запрещает кеширование,
    чтобы frontend всегда получал актуальный auth_enabled.
    """
    return JSONResponse(
        content=security_config.to_safe_dict(),
        headers={"Cache-Control": "no-store"},
    )


# ══════════════════════════════════════════════════════════════
# Health Router
# ══════════════════════════════════════════════════════════════

health_router = APIRouter(tags=["system"])


@health_router.get("/api/health")
async def health_check():
    """Health check — без аутентификации."""
    return {"status": "ok", "timestamp": time.time()}
