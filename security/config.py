"""
Security Configuration - центральный конфиг для всех security-компонентов.

Загружается из переменных окружения (.env файл) и/или security.json.
Все секреты ТОЛЬКО через переменные окружения.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("opium.security")

# Путь к конфигу безопасности (не содержит секретов!)
_CONFIG_PATH = Path(__file__).parent.parent / "security.json"


@dataclass
class SecurityConfig:
    """Конфигурация безопасности Opium."""

    # ── Auth ─────────────────────────────────────────────
    # JWT secret key (обязательно через env!)
    secret_key: str = ""
    # Алгоритм JWT
    algorithm: str = "HS256"
    # Время жизни access token в минутах
    access_token_expire_minutes: int = 1440  # 24 часа
    # Включена ли аутентификация
    auth_enabled: bool = True
    # Логин администратора
    admin_username: str = "admin"
    # Хеш пароля администратора (bcrypt)
    admin_password_hash: str = ""

    # ── Rate Limiting ────────────────────────────────────
    rate_limit_enabled: bool = True
    # Общий лимит: запросов в минуту per IP
    rate_limit_per_minute: int = 60
    # Лимит на /auth/login: попыток в минуту per IP
    login_rate_limit_per_minute: int = 5
    # Бан после N неудачных попыток логина
    login_max_failures: int = 10
    # Время бана в минутах
    login_ban_minutes: int = 30

    # ── IP Whitelist ─────────────────────────────────────
    ip_whitelist_enabled: bool = False
    # Список разрешённых IP/CIDR (пустой = разрешить все)
    ip_whitelist: list[str] = field(default_factory=lambda: ["127.0.0.1", "::1"])

    # ── Secure Headers ───────────────────────────────────
    secure_headers_enabled: bool = True
    # Content Security Policy
    csp_policy: str = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:"
    # Referrer Policy
    referrer_policy: str = "strict-origin-when-cross-origin"

    # ── CORS (для продакшена) ────────────────────────────
    cors_origins: list[str] = field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # ── Security Log ─────────────────────────────────────
    security_log_enabled: bool = True
    security_log_path: str = "logs/security.log"
    # Максимальный размер лог-файла в МБ
    security_log_max_mb: int = 50
    # Количество backup-файлов
    security_log_backup_count: int = 5

    # ── Public paths (не требуют auth) ───────────────────
    public_paths: list[str] = field(
        default_factory=lambda: [
            "/",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/auth/login",
            "/api/auth/config",
            "/api/health",
        ]
    )
    # Префиксы статических файлов (не требуют auth)
    static_prefixes: list[str] = field(
        default_factory=lambda: ["/assets/"]
    )

    _loaded: bool = False

    def load(self) -> None:
        """Загрузить конфиг из файла и переменных окружения."""
        if self._loaded:
            return
        self._loaded = True

        # 1. Из файла (не секретные настройки)
        if _CONFIG_PATH.exists():
            try:
                data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
                self._apply_dict(data)
                logger.info(f"Security config loaded from {_CONFIG_PATH}")
            except Exception as e:
                logger.error(f"Failed to load security config: {e}")

        # 2. Из переменных окружения (секреты и overrides)
        self._load_from_env()

        # 3. Генерируем secret_key если не задан
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)
            logger.warning(
                "OPIUM_SECRET_KEY not set! Generated random key. "
                "Tokens will invalidate on restart. "
                "Set OPIUM_SECRET_KEY in .env for persistence."
            )

        # 4. Валидация
        self._validate()

    def _apply_dict(self, data: dict[str, Any]) -> None:
        """Применить значения из словаря."""
        for key, value in data.items():
            if hasattr(self, key) and key not in ("secret_key", "admin_password_hash"):
                setattr(self, key, value)

    def _load_from_env(self) -> None:
        """Загрузить значения из переменных окружения."""
        # Секреты
        if env_key := os.getenv("OPIUM_SECRET_KEY"):
            self.secret_key = env_key
        if env_hash := os.getenv("OPIUM_ADMIN_PASSWORD_HASH"):
            self.admin_password_hash = env_hash

        # Overrides
        if env_user := os.getenv("OPIUM_ADMIN_USERNAME"):
            self.admin_username = env_user
        if env_enabled := os.getenv("OPIUM_AUTH_ENABLED"):
            self.auth_enabled = env_enabled.lower() in ("true", "1", "yes")
        if env_expire := os.getenv("OPIUM_TOKEN_EXPIRE_MINUTES"):
            self.access_token_expire_minutes = int(env_expire)
        if env_rate := os.getenv("OPIUM_RATE_LIMIT_ENABLED"):
            self.rate_limit_enabled = env_rate.lower() in ("true", "1", "yes")
        if env_rpm := os.getenv("OPIUM_RATE_LIMIT_PER_MINUTE"):
            self.rate_limit_per_minute = int(env_rpm)
        if env_ip := os.getenv("OPIUM_IP_WHITELIST_ENABLED"):
            self.ip_whitelist_enabled = env_ip.lower() in ("true", "1", "yes")
        if env_origins := os.getenv("OPIUM_CORS_ORIGINS"):
            self.cors_origins = [o.strip() for o in env_origins.split(",")]

    def _validate(self) -> None:
        """Валидация конфига."""
        if self.auth_enabled and not self.admin_password_hash:
            logger.warning(
                "Auth enabled but OPIUM_ADMIN_PASSWORD_HASH not set! "
                "Run: python -m security.auth --setup to create admin password."
            )

        if self.access_token_expire_minutes < 5:
            logger.warning("Token expire time < 5 minutes - too short for production")

        if len(self.secret_key) < 32:
            logger.warning("OPIUM_SECRET_KEY is too short (< 32 chars). Use a strong key.")

    def save(self) -> None:
        """Сохранить не-секретные настройки в файл."""
        data = {
            "auth_enabled": self.auth_enabled,
            "access_token_expire_minutes": self.access_token_expire_minutes,
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "login_rate_limit_per_minute": self.login_rate_limit_per_minute,
            "login_max_failures": self.login_max_failures,
            "login_ban_minutes": self.login_ban_minutes,
            "ip_whitelist_enabled": self.ip_whitelist_enabled,
            "ip_whitelist": self.ip_whitelist,
            "secure_headers_enabled": self.secure_headers_enabled,
            "csp_policy": self.csp_policy,
            "cors_origins": self.cors_origins,
            "public_paths": self.public_paths,
            "static_prefixes": self.static_prefixes,
        }
        _CONFIG_PATH.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Security config saved to {_CONFIG_PATH}")

    def to_safe_dict(self) -> dict[str, Any]:
        """Конфиг без секретов для отображения."""
        return {
            "auth_enabled": self.auth_enabled,
            "algorithm": self.algorithm,
            "access_token_expire_minutes": self.access_token_expire_minutes,
            "admin_username": self.admin_username,
            "has_password": bool(self.admin_password_hash),
            "has_secret_key": bool(self.secret_key),
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "login_rate_limit_per_minute": self.login_rate_limit_per_minute,
            "login_max_failures": self.login_max_failures,
            "login_ban_minutes": self.login_ban_minutes,
            "ip_whitelist_enabled": self.ip_whitelist_enabled,
            "ip_whitelist": self.ip_whitelist,
            "secure_headers_enabled": self.secure_headers_enabled,
            "cors_origins": self.cors_origins,
            "public_paths": self.public_paths,
        }


# ── Singleton ────────────────────────────────────────────────

security_config = SecurityConfig()
