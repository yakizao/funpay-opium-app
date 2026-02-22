"""
Opium Logging — централизованная настройка логирования.

Все компоненты используют logging.getLogger("opium.{компонент}").
Этот модуль настраивает root logger "opium" с двумя handler'ами:
  1. StreamHandler → консоль (INFO+ по умолчанию)
  2. TimedRotatingFileHandler → logs/opium_YYYY-MM-DD.log (DEBUG)

Использование:
    from core.logging import setup_logging
    setup_logging()                     # defaults
    setup_logging(console_level="DEBUG") # verbose console

Расширение для модулей:
    Любой модуль просто делает:
        logger = logging.getLogger("opium.steam_rent.handlers")
    Логи автоматически попадают в файл и консоль через
    иерархию "opium" → "opium.steam_rent" → "opium.steam_rent.handlers".
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Шумные библиотеки — ограничиваем уровень
_NOISY_LOGGERS = [
    "urllib3",
    "requests",
    "uvicorn.access",
    "uvicorn.error",
    "httpcore",
    "httpx",
    "asyncio",
    "watchfiles",
]


def setup_logging(
    *,
    log_dir: str | Path = "logs",
    console_level: str = "DEBUG",
    file_level: str = "DEBUG",
    noisy_level: str = "WARNING",
) -> None:
    """
    Настраивает логирование для всей системы Opium.

    Args:
        log_dir: Папка для лог-файлов (создаётся если не существует).
        console_level: Уровень логирования для консоли.
        file_level: Уровень логирования для файла.
        noisy_level: Уровень для шумных библиотек (urllib3, httpx и т.д.).
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # ── Root logger "opium" ──────────────────────────
    opium_logger = logging.getLogger("opium")
    opium_logger.setLevel(logging.DEBUG)  # Пропускаем всё, фильтруют handler'ы
    opium_logger.propagate = False  # Не дублировать в root logger

    # Очищаем существующие handler'ы (при повторном вызове)
    opium_logger.handlers.clear()

    # ── Console handler ──────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(getattr(logging, console_level.upper(), logging.DEBUG))
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    opium_logger.addHandler(console)

    # ── File handler (daily rotation) ────────────────
    # Файл: logs/opium_2026-02-12.log
    # При ротации старые файлы: opium_2026-02-12.log.2026-02-11 и т.д.
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = log_dir / f"opium_{today}.log"

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=30,  # Храним 30 дней
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    opium_logger.addHandler(file_handler)

    # ── Глушим шумные библиотеки ─────────────────────
    noise_lvl = getattr(logging, noisy_level.upper(), logging.WARNING)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(noise_lvl)

    opium_logger.info(
        f"Logging initialized: console={console_level}, file={file_level}, "
        f"log_file={log_file}"
    )
