"""
Security Audit Log - отдельный security-focused лог.

В отличие от core/audit.py (dev audit для синхронизации между чатами),
этот лог фиксирует security-события:
- Логины (успешные/неудачные)
- Доступ к защищённым ресурсам
- IP бан/разбан
- Rate limit срабатывания
- Изменения security-конфига

Формат: JSON lines (один JSON-объект на строку) для эффективного append.
Ротация: по размеру файла (security_log_max_mb).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

logger = logging.getLogger("opium.security.audit")


class SecurityLog:
    """
    Отдельный security-focused audit log.

    Использует RotatingFileHandler для ротации по размеру.
    Формат: JSON lines.
    """

    def __init__(self, log_path: str | Path | None = None) -> None:
        self._log_path = Path(log_path) if log_path else None
        self._file_logger: logging.Logger | None = None
        self._initialized = False

    def initialize(self) -> None:
        """Инициализировать лог (вызывается при старте приложения)."""
        from security.config import security_config

        if not security_config.security_log_enabled:
            return

        log_path = self._log_path or Path(security_config.security_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Отдельный logger для security events
        self._file_logger = logging.getLogger("opium.security.events")
        self._file_logger.setLevel(logging.INFO)
        self._file_logger.propagate = False

        # Ротация по размеру
        handler = RotatingFileHandler(
            str(log_path),
            maxBytes=security_config.security_log_max_mb * 1024 * 1024,
            backupCount=security_config.security_log_backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(message)s"))  # Только JSON
        self._file_logger.addHandler(handler)

        self._initialized = True
        logger.info(f"Security log initialized: {log_path}")

    def record(
        self,
        event_type: str,
        *,
        ip: str = "",
        username: str = "",
        path: str = "",
        method: str = "",
        detail: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Записать security-событие.

        Args:
            event_type: Тип события (LOGIN_SUCCESS, LOGIN_FAILED, etc.)
            ip: IP адрес клиента
            username: Имя пользователя (если известно)
            path: Путь запроса
            method: HTTP метод
            detail: Описание
            metadata: Дополнительные данные
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "ip": ip,
            "username": username,
            "path": path,
            "method": method,
            "detail": detail,
        }
        if metadata:
            entry["metadata"] = metadata

        # В файл
        if self._initialized and self._file_logger:
            self._file_logger.info(json.dumps(entry, ensure_ascii=False))

        # В основной лог (для отладки)
        if event_type in ("LOGIN_FAILED", "BRUTE_FORCE_BAN", "IP_BLOCKED", "SUSPICIOUS_ACTIVITY"):
            logger.warning(f"SECURITY: [{event_type}] {ip} {username} - {detail}")
        else:
            logger.info(f"SECURITY: [{event_type}] {ip} {username} - {detail}")

    def get_recent(self, count: int = 100) -> list[dict[str, Any]]:
        """Прочитать последние N записей из лога."""
        from security.config import security_config
        log_path = self._log_path or Path(security_config.security_log_path)

        if not log_path.exists():
            return []

        entries: list[dict[str, Any]] = []
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-count:]:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
        except Exception as e:
            logger.error(f"Failed to read security log: {e}")

        return entries


# ── Singleton ────────────────────────────────────────────────

security_log = SecurityLog()
