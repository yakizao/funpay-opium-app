# -*- coding: utf-8 -*-
"""
Steam HTTP wrapper with rate limiting, retry, and debug logging.

Thread-safe: uses a class-level lock to serialize requests and enforce
a minimum 3-second interval between calls (Steam rate limit).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests

logger = logging.getLogger("opium.steam_rent.steam")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"


def _mask_secret(s: str, show: int = 4) -> str:
    """Маскирует секрет для логов."""
    if not s or len(s) <= show * 2:
        return "***"
    return f"{s[:show]}...{s[-show:]}"


class SteamHTTP:
    """HTTP wrapper с rate limiting, debug logging и обработкой 429."""

    _last_request_time: float = 0
    _min_request_interval: float = 3.0  # 3 секунды между запросами
    _lock = threading.Lock()

    @classmethod
    def _wait_for_rate_limit(cls) -> None:
        """Ждём если нужно для соблюдения rate limit."""
        while True:
            with cls._lock:
                now = time.time()
                elapsed = now - cls._last_request_time
                if elapsed >= cls._min_request_interval:
                    cls._last_request_time = now
                    return
                wait = cls._min_request_interval - elapsed
            # Sleep OUTSIDE the lock so other threads aren't blocked
            logger.debug(f"[HTTP] Rate limit: waiting {wait:.1f}s")
            time.sleep(wait)

    @staticmethod
    def request(
        method: str,
        url: str,
        session: requests.Session | None = None,
        max_retries: int = 3,
        retry_delay: float = 10.0,
        skip_rate_limit: bool = False,
        **kwargs: Any,
    ) -> requests.Response:
        """HTTP запрос с rate limiting, debug и retry при 429."""

        if not skip_rate_limit:
            SteamHTTP._wait_for_rate_limit()

        requester = session if session else requests

        # Ensure User-Agent is always set
        if not session:
            kwargs.setdefault("headers", {})
            kwargs["headers"].setdefault("User-Agent", USER_AGENT)

        # Логируем запрос
        logger.debug(f"[HTTP] >>> {method} {url}")
        if kwargs.get("params"):
            safe_params = {
                k: (
                    _mask_secret(str(v))
                    if "secret" in k.lower()
                    or "password" in k.lower()
                    or "token" in k.lower()
                    else v
                )
                for k, v in kwargs["params"].items()
            }
            logger.debug(f"[HTTP]     params: {safe_params}")
        if kwargs.get("data"):
            safe_data = {
                k: (
                    _mask_secret(str(v))
                    if "secret" in k.lower()
                    or "password" in k.lower()
                    or "token" in k.lower()
                    else v
                )
                for k, v in (
                    kwargs["data"].items()
                    if isinstance(kwargs["data"], dict)
                    else {}
                )
            }
            logger.debug(f"[HTTP]     data: {safe_data}")

        for attempt in range(max_retries):
            try:
                kwargs.setdefault("timeout", 30)
                if method.upper() == "GET":
                    r = requester.get(url, **kwargs)
                elif method.upper() == "POST":
                    r = requester.post(url, **kwargs)
                else:
                    r = requester.request(method, url, **kwargs)

                logger.debug(f"[HTTP] <<< {r.status_code} {url}")

                # Обработка rate limit
                if r.status_code == 429:
                    try:
                        interval = r.json().get("response", {}).get("interval", 10)
                    except Exception:
                        interval = 10

                    wait_time = interval * (attempt + 2)
                    logger.warning(
                        f"[HTTP] !!! 429 Rate Limited, waiting {wait_time}s "
                        f"(attempt {attempt + 1}/{max_retries})"
                    )

                    if attempt < max_retries - 1:
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"[HTTP] !!! Max retries reached for {url}")
                        return r

                # Логируем body
                try:
                    body = r.text[:500] if len(r.text) > 500 else r.text
                    logger.debug(f"[HTTP]     body: {body}")
                except Exception:
                    pass

                return r

            except requests.RequestException as e:
                logger.error(f"[HTTP] !!! Request error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                raise

        raise requests.RequestException(f"Failed after {max_retries} retries")

    @staticmethod
    def get(
        url: str, session: requests.Session | None = None, **kwargs: Any
    ) -> requests.Response:
        return SteamHTTP.request("GET", url, session, **kwargs)

    @staticmethod
    def post(
        url: str, session: requests.Session | None = None, **kwargs: Any
    ) -> requests.Response:
        return SteamHTTP.request("POST", url, session, **kwargs)

    @staticmethod
    def safe_json(response: requests.Response, default: Any = None) -> Any:
        """Безопасный парсинг JSON, возвращает default при ошибке."""
        if not response.text or not response.text.strip():
            logger.warning("[HTTP] Empty response body")
            return default if default is not None else {}
        try:
            return response.json()
        except Exception as e:
            logger.error(
                f"[HTTP] JSON parse error: {e}, body: {response.text[:200]}"
            )
            return default if default is not None else {}
