"""Opium Rate Limiter - контроль частоты запросов с антидетект-функциями."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass


logger = logging.getLogger("opium.rate_limiter")


@dataclass
class RateLimitConfig:
    """
    Конфигурация Rate Limiter.
    
    Attributes:
        base_delay: Базовая задержка между запросами (сек)
        jitter_min: Минимальный jitter (множитель, напр. 0.8 = -20%)
        jitter_max: Максимальный jitter (множитель, напр. 1.2 = +20%)
        burst_limit: Максимум запросов в burst
        burst_window: Окно для burst (сек)
        cooldown_after_burst: Задержка после burst (сек)
    """
    
    base_delay: float = 1.0
    jitter_min: float = 0.8
    jitter_max: float = 1.3
    burst_limit: int = 5
    burst_window: float = 10.0
    cooldown_after_burst: float = 5.0


class RateLimiter:
    """
    Rate Limiter с поддержкой jitter для антидетекта.
    
    Особенности:
    - Рандомизация задержек (jitter) для имитации человека
    - Burst protection - ограничение пачек запросов
    - Per-operation delays
    """
    
    def __init__(self, config: RateLimitConfig | None = None) -> None:
        self.config = config or RateLimitConfig()
        self._last_request_time: float = 0
        self._burst_timestamps: list[float] = []
        self._lock = asyncio.Lock()
    
    def _get_jittered_delay(self, base: float | None = None) -> float:
        """Возвращает задержку с рандомным jitter."""
        base = base or self.config.base_delay
        jitter = random.uniform(self.config.jitter_min, self.config.jitter_max)
        return base * jitter
    
    def _cleanup_burst_window(self) -> None:
        """Очищает устаревшие записи из burst окна."""
        now = time.time()
        cutoff = now - self.config.burst_window
        self._burst_timestamps = [t for t in self._burst_timestamps if t > cutoff]
    
    async def acquire(self) -> float:
        """
        Ожидает разрешения на выполнение запроса.
            
        Returns:
            Фактическая задержка (сек)
        """
        async with self._lock:
            now = time.time()
            
            # Очищаем старые записи burst
            self._cleanup_burst_window()
            
            # Проверяем burst limit
            if len(self._burst_timestamps) >= self.config.burst_limit:
                # Нужен cooldown после burst
                cooldown = self._get_jittered_delay(self.config.cooldown_after_burst)
                await asyncio.sleep(cooldown)
                self._burst_timestamps.clear()
                now = time.time()
            
            # Вычисляем задержку с момента последнего запроса
            elapsed = now - self._last_request_time
            required_delay = self._get_jittered_delay()
            
            if elapsed < required_delay:
                wait_time = required_delay - elapsed
                await asyncio.sleep(wait_time)
            else:
                wait_time = 0
            
            # Обновляем состояние
            self._last_request_time = time.time()
            self._burst_timestamps.append(self._last_request_time)
            
            return wait_time


@dataclass  
class AntiDetectConfig:
    """
    Конфигурация антидетект-поведения аккаунта.
    
    Attributes:
        startup_delay_min: Мин. задержка перед началом работы (сек)
        startup_delay_max: Макс. задержка перед началом работы (сек)
        shutdown_delay_min: Мин. задержка перед закрытием сессии (сек)
        shutdown_delay_max: Макс. задержка перед закрытием сессии (сек)
        runner_delay_min: Мин. задержка между запросами Runner (сек)
        runner_delay_max: Макс. задержка между запросами Runner (сек)
        session_refresh_interval: Интервал обновления PHPSESSID (сек), ~40-60 мин
        session_refresh_jitter: Jitter для обновления сессии (сек)
    """
    
    startup_delay_min: float = 0.0
    startup_delay_max: float = 0.0
    shutdown_delay_min: float = 0.0
    shutdown_delay_max: float = 0.0
    runner_delay_min: float = 4.0
    runner_delay_max: float = 8.0
    session_refresh_interval: float = 2400.0  # 40 минут
    session_refresh_jitter: float = 600.0     # ±10 минут
    
    def get_startup_delay(self) -> float:
        """Возвращает рандомную задержку старта."""
        return random.uniform(self.startup_delay_min, self.startup_delay_max)
    
    def get_shutdown_delay(self) -> float:
        """Возвращает рандомную задержку остановки."""
        return random.uniform(self.shutdown_delay_min, self.shutdown_delay_max)
    
    def get_runner_delay(self) -> float:
        """Возвращает рандомную задержку Runner."""
        return random.uniform(self.runner_delay_min, self.runner_delay_max)
    
    def get_session_refresh_interval(self) -> float:
        """Возвращает рандомный интервал обновления сессии."""
        base = self.session_refresh_interval
        jitter = random.uniform(-self.session_refresh_jitter, self.session_refresh_jitter)
        return max(base + jitter, 300.0)  # Минимум 5 минут
