"""
Authentication - JWT аутентификация для Opium API.

Поддерживает:
- JWT Bearer tokens
- bcrypt хеширование паролей
- Dependency injection для FastAPI

Использование:
    # В роутерах:
    from security.auth import get_current_user, AuthUser

    @app.get("/protected")
    async def protected(user: AuthUser = Depends(get_current_user)):
        return {"user": user.username}

    # Создать токен:
    from security.auth import create_access_token
    token = create_access_token({"sub": "admin"})

CLI:
    python -m security.auth --setup    # Создать пароль admin
    python -m security.auth --hash     # Хешировать пароль
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger("opium.security.auth")

# JWT реализация без PyJWT - минимальная зависимость
import base64


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 encoding без padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """URL-safe base64 decoding с padding."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def _create_jwt(payload: dict[str, Any], secret: str, algorithm: str = "HS256") -> str:
    """Создать JWT токен (минимальная реализация без зависимостей)."""
    header = {"alg": algorithm, "typ": "JWT"}
    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    message = f"{header_b64}.{payload_b64}"

    if algorithm == "HS256":
        signature = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).digest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    sig_b64 = _b64url_encode(signature)
    return f"{message}.{sig_b64}"


def _decode_jwt(token: str, secret: str, algorithm: str = "HS256") -> dict[str, Any]:
    """Декодировать и верифицировать JWT токен."""
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")

    header_b64, payload_b64, sig_b64 = parts
    message = f"{header_b64}.{payload_b64}"

    # Проверяем подпись
    if algorithm == "HS256":
        expected_sig = hmac.new(
            secret.encode(), message.encode(), hashlib.sha256
        ).digest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid signature")

    # Декодируем payload
    payload = json.loads(_b64url_decode(payload_b64))

    # Проверяем exp
    if "exp" in payload:
        if time.time() > payload["exp"]:
            raise ValueError("Token expired")

    return payload


# ── Password Hashing ─────────────────────────────────────────
# Используем PBKDF2 (stdlib) вместо bcrypt для минимальных зависимостей

_HASH_ITERATIONS = 600_000  # OWASP рекомендация для PBKDF2-SHA256
_SALT_LENGTH = 32


def hash_password(password: str) -> str:
    """Хешировать пароль через PBKDF2-SHA256."""
    salt = secrets.token_hex(_SALT_LENGTH)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _HASH_ITERATIONS
    )
    return f"pbkdf2:sha256:{_HASH_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль против хеша."""
    try:
        if not password_hash.startswith("pbkdf2:sha256:"):
            return False
        prefix, rest = password_hash.split("$", 1)
        salt, hash_hex = rest.split("$", 1)
        iterations = int(prefix.split(":")[-1])
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
        )
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# ── Auth User ────────────────────────────────────────────────

@dataclass
class AuthUser:
    """Аутентифицированный пользователь."""
    username: str
    issued_at: float
    expires_at: float


# ── Token Functions ──────────────────────────────────────────

def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Создать JWT access token."""
    from security.config import security_config

    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(minutes=security_config.access_token_expire_minutes)

    to_encode.update({
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    })

    return _create_jwt(to_encode, security_config.secret_key, security_config.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Декодировать JWT access token."""
    from security.config import security_config

    return _decode_jwt(token, security_config.secret_key, security_config.algorithm)


# ── FastAPI Dependencies ─────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AuthUser:
    """
    FastAPI Dependency - извлекает и верифицирует пользователя из JWT.

    Если auth_enabled=False - пропускает всех (returns dummy user).
    """
    from security.config import security_config

    if not security_config.auth_enabled:
        return AuthUser(username="anonymous", issued_at=0, expires_at=0)

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
        username = payload.get("sub")
        if username is None:
            raise ValueError("No 'sub' in token")

        return AuthUser(
            username=username,
            issued_at=payload.get("iat", 0),
            expires_at=payload.get("exp", 0),
        )
    except ValueError as e:
        logger.warning(f"Invalid token from {request.client.host}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── CLI ──────────────────────────────────────────────────────

def _cli():
    """CLI для управления паролями."""
    import argparse
    import getpass

    parser = argparse.ArgumentParser(description="Opium Security - Auth Management")
    parser.add_argument("--setup", action="store_true", help="Setup admin password")
    parser.add_argument("--hash", action="store_true", help="Hash a password")
    parser.add_argument("--verify", action="store_true", help="Verify password against hash")
    parser.add_argument("--generate-key", action="store_true", help="Generate a secure secret key")
    args = parser.parse_args()

    if args.setup:
        print("=== Opium Admin Password Setup ===")
        password = getpass.getpass("Enter admin password: ")
        confirm = getpass.getpass("Confirm admin password: ")
        if password != confirm:
            print("ERROR: Passwords do not match!")
            return
        if len(password) < 8:
            print("ERROR: Password must be at least 8 characters!")
            return
        hashed = hash_password(password)
        print(f"\nPassword hash generated.")
        print(f"Add to your .env file:")
        print(f"  OPIUM_ADMIN_PASSWORD_HASH={hashed}")
        print(f"\nOr set as environment variable.")

    elif args.hash:
        password = getpass.getpass("Enter password to hash: ")
        print(hash_password(password))

    elif args.verify:
        password = getpass.getpass("Enter password: ")
        hash_val = input("Enter hash: ")
        result = verify_password(password, hash_val)
        print(f"Verification: {'✓ OK' if result else '✗ FAILED'}")

    elif args.generate_key:
        key = secrets.token_hex(32)
        print(f"Generated secret key:")
        print(f"  OPIUM_SECRET_KEY={key}")

    else:
        parser.print_help()


if __name__ == "__main__":
    _cli()
