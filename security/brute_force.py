"""
Brute-Force Protection — отдельный сервис для защиты от перебора паролей.

Инкапсулирует:
- Проверку бана IP
- Запись неудачных попыток (с автоматическим баном)
- Сброс при успехе
- Логирование security-событий

Использование:
    from security.brute_force import brute_force_protector

    # В login():
    brute_force_protector.check_allowed(ip, username)  # raises HTTPException(429) if banned
    brute_force_protector.record_failure(ip, username, "Invalid password")
    brute_force_protector.record_success(ip)
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from security.config import security_config
from security.rate_limit import login_tracker
from security.security_log import security_log

logger = logging.getLogger("opium.security.brute_force")


class BruteForceProtector:
    """
    Фасад для brute-force protection.

    Оборачивает LoginFailureTracker (rate_limit.py) и SecurityLog
    в единый API с чистой семантикой.
    """

    def check_allowed(self, ip: str, username: str = "") -> None:
        """
        Проверить, не забанен ли IP.

        Raises:
            HTTPException(429) если IP забанен.
        """
        is_banned, remaining = login_tracker.is_banned(ip)
        if is_banned:
            security_log.record(
                "IP_BLOCKED",
                ip=ip,
                username=username,
                path="/api/auth/login",
                method="POST",
                detail=f"Banned. Remaining: {remaining}s",
            )
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed attempts. Try again in {remaining} seconds.",
                headers={"Retry-After": str(remaining)},
            )

    def record_failure(self, ip: str, username: str, detail: str) -> None:
        """
        Зафиксировать неудачную попытку логина.

        Логирует LOGIN_FAILED, и если порог превышен — BRUTE_FORCE_BAN.
        """
        security_log.record(
            "LOGIN_FAILED",
            ip=ip,
            username=username,
            path="/api/auth/login",
            method="POST",
            detail=detail,
        )

        banned = login_tracker.record_failure(
            ip,
            max_failures=security_config.login_max_failures,
            ban_minutes=security_config.login_ban_minutes,
        )

        if banned:
            security_log.record(
                "BRUTE_FORCE_BAN",
                ip=ip,
                username=username,
                path="/api/auth/login",
                method="POST",
                detail=f"Banned for {security_config.login_ban_minutes} minutes",
            )

    def record_success(self, ip: str) -> None:
        """Сбросить счётчик неудачных попыток при успешном логине."""
        login_tracker.record_success(ip)


# ── Singleton ────────────────────────────────────────────────

brute_force_protector = BruteForceProtector()
