"""
Rate Limiter - ограничение частоты запросов per IP.

Алгоритм: Token Bucket с автоматической очисткой старых записей.
Не требует Redis - работает in-memory (для single-instance деплоя).
"""

from __future__ import annotations

import logging
import time
import threading
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger("opium.security.rate_limit")


@dataclass
class _Bucket:
    """Token bucket для одного IP."""
    tokens: float
    last_refill: float
    rate: float  # токенов в секунду
    capacity: float  # максимум токенов

    def consume(self) -> bool:
        """Попытка израсходовать 1 токен. True = разрешено."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """
    In-memory rate limiter per IP.

    Thread-safe. Автоматическая очистка неактивных buckets каждые 5 минут.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()
        self._cleanup_interval = 300  # 5 минут
        self._last_cleanup = time.monotonic()

    def check(self, key: str, rate_per_minute: int) -> bool:
        """
        Проверить rate limit для ключа (обычно IP).

        Args:
            key: Идентификатор (IP адрес)
            rate_per_minute: Максимум запросов в минуту

        Returns:
            True если запрос разрешён, False если rate limited
        """
        rate_per_second = rate_per_minute / 60.0
        capacity = float(rate_per_minute)

        with self._lock:
            self._maybe_cleanup()

            if key not in self._buckets:
                self._buckets[key] = _Bucket(
                    tokens=capacity,
                    last_refill=time.monotonic(),
                    rate=rate_per_second,
                    capacity=capacity,
                )

            bucket = self._buckets[key]
            # Обновляем rate/capacity если изменился конфиг
            bucket.rate = rate_per_second
            bucket.capacity = capacity
            return bucket.consume()

    def _maybe_cleanup(self) -> None:
        """Очистить неактивные buckets (вызывается под lock)."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        stale_keys = [
            k for k, b in self._buckets.items()
            if now - b.last_refill > self._cleanup_interval
        ]
        for k in stale_keys:
            del self._buckets[k]

        if stale_keys:
            logger.debug(f"Rate limiter cleanup: removed {len(stale_keys)} stale entries")

    def get_remaining(self, key: str) -> int:
        """Оставшиеся токены для ключа."""
        with self._lock:
            if key in self._buckets:
                return max(0, int(self._buckets[key].tokens))
            return -1  # не отслеживается

    def reset(self, key: str) -> None:
        """Сбросить rate limit для ключа."""
        with self._lock:
            self._buckets.pop(key, None)


# Счётчик неудачных логинов (для brute-force protection)

class LoginFailureTracker:
    """Трекер неудачных попыток логина per IP."""

    def __init__(self) -> None:
        self._failures: dict[str, list[float]] = defaultdict(list)
        self._bans: dict[str, float] = {}  # IP -> ban_until (monotonic)
        self._lock = threading.Lock()

    def record_failure(self, ip: str, max_failures: int, ban_minutes: int) -> bool:
        """
        Зафиксировать неудачную попытку.

        Returns:
            True если IP забанен после этой попытки
        """
        now = time.monotonic()
        window = 60 * ban_minutes  # смотрим за период бана

        with self._lock:
            # Очищаем старые записи
            self._failures[ip] = [t for t in self._failures[ip] if now - t < window]
            self._failures[ip].append(now)

            if len(self._failures[ip]) >= max_failures:
                self._bans[ip] = now + (ban_minutes * 60)
                logger.warning(f"IP {ip} banned for {ban_minutes}min after {len(self._failures[ip])} failures")
                return True

            return False

    def is_banned(self, ip: str) -> tuple[bool, int]:
        """
        Проверить бан IP.

        Returns:
            (is_banned, remaining_seconds)
        """
        now = time.monotonic()
        with self._lock:
            if ip in self._bans:
                remaining = self._bans[ip] - now
                if remaining > 0:
                    return True, int(remaining)
                else:
                    # Бан истёк
                    del self._bans[ip]
                    self._failures.pop(ip, None)

            return False, 0

    def unban(self, ip: str) -> None:
        """Снять бан с IP."""
        with self._lock:
            self._bans.pop(ip, None)
            self._failures.pop(ip, None)

    def record_success(self, ip: str) -> None:
        """Сбросить счётчик при успешном логине."""
        with self._lock:
            self._failures.pop(ip, None)


# ── Singletons ───────────────────────────────────────────────

rate_limiter = RateLimiter()
login_tracker = LoginFailureTracker()
