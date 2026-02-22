# -*- coding: utf-8 -*-
"""Auto Raise - Storage. Типизированная обёртка над ModuleStorage."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.storage import ModuleStorage

logger = logging.getLogger("opium.auto_raise.storage")

MAX_LOG_ENTRIES = 300


class AutoRaiseStorage:
    def __init__(self, storage: "ModuleStorage") -> None:
        self._storage = storage

    # ─── Config ───────────────────────────────────────

    def get_config(self) -> dict[str, Any]:
        return self._storage.config

    def save_config(self, config: dict[str, Any]) -> None:
        self._storage.save_config(config)

    def is_enabled(self) -> bool:
        return self.get_config().get("enabled", False)

    def set_enabled(self, enabled: bool) -> None:
        cfg = self.get_config().copy()
        cfg["enabled"] = enabled
        self.save_config(cfg)

    def get_delay_range(self) -> int:
        """Максимальный случайный сдвиг (минуты). 0 = без сдвига."""
        return int(self.get_config().get("delay_range_minutes", 0))

    def set_delay_range(self, minutes: int) -> None:
        cfg = self.get_config().copy()
        cfg["delay_range_minutes"] = max(0, minutes)
        self.save_config(cfg)

    # ─── Raise Log ────────────────────────────────────

    def get_log(self, limit: int = 50) -> list[dict[str, Any]]:
        data = self._storage.read_json("raise_log.json")
        if data is None:
            return []
        entries = data if isinstance(data, list) else []
        return entries[-limit:]

    def append_log(
        self,
        category_id: int,
        category_name: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        entries = self.get_log(MAX_LOG_ENTRIES)
        entries.append({
            "timestamp": datetime.now().isoformat(),
            "category_id": category_id,
            "category_name": category_name,
            "success": success,
            "error": error,
        })
        if len(entries) > MAX_LOG_ENTRIES:
            entries = entries[-MAX_LOG_ENTRIES:]
        self._storage.write_json("raise_log.json", entries)

    def clear_log(self) -> None:
        self._storage.write_json("raise_log.json", [])
