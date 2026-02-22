# -*- coding: utf-8 -*-
"""
Steam Rent - Proxy Manager.

Управление прокси для Steam запросов:
- Хранение и CRUD для прокси
- Выбор прокси по режиму (direct/fixed/mix/mix-list)
- Проверка доступности прокси
- Fallback логика при недоступности
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
from pathlib import Path
from typing import Any

import requests

from .models import (
    Proxy,
    ProxyList,
    ProxySettings,
    ProxyMode,
    ProxyFallback,
    ProxyType,
    proxy_from_dict,
    proxy_list_from_dict,
    to_dict,
)

logger = logging.getLogger("opium.steam_rent.proxy")


class ProxyManager:
    """
    Менеджер прокси для Steam запросов.
    
    Используйте get_proxy_manager() для получения экземпляра.
    Thread-safe.
    """
    
    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Path("data/steam_rent")
        self._proxies: dict[str, Proxy] = {}
        self._proxy_lists: dict[str, ProxyList] = {}
        self._health_cache: dict[str, tuple[bool, float]] = {}  # proxy_id -> (healthy, timestamp)
        self._health_ttl: float = 300.0  # 5 минут кеш здоровья
        self._lock_internal = threading.Lock()
        
        self._load()
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    def _proxies_file(self) -> Path:
        return self._data_dir / "proxies.json"
    
    def _proxy_lists_file(self) -> Path:
        return self._data_dir / "proxy_lists.json"
    
    def _load(self) -> None:
        """Загружает прокси и списки из файлов."""
        # Proxies
        proxies_file = self._proxies_file()
        if proxies_file.exists():
            try:
                with open(proxies_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        proxy = proxy_from_dict(item)
                        self._proxies[proxy.proxy_id] = proxy
                logger.info(f"Loaded {len(self._proxies)} proxies")
            except Exception as e:
                logger.error(f"Failed to load proxies: {e}")
        
        # Proxy lists
        lists_file = self._proxy_lists_file()
        if lists_file.exists():
            try:
                with open(lists_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        pl = proxy_list_from_dict(item)
                        self._proxy_lists[pl.list_id] = pl
                logger.info(f"Loaded {len(self._proxy_lists)} proxy lists")
            except Exception as e:
                logger.error(f"Failed to load proxy lists: {e}")
    
    def _save_proxies(self) -> None:
        """Сохраняет прокси в файл."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._proxies_file(), "w", encoding="utf-8") as f:
            json.dump([to_dict(p) for p in self._proxies.values()], f, indent=2)
    
    def _save_proxy_lists(self) -> None:
        """Сохраняет списки прокси в файл."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        with open(self._proxy_lists_file(), "w", encoding="utf-8") as f:
            json.dump([to_dict(pl) for pl in self._proxy_lists.values()], f, indent=2)
    
    # =========================================================================
    # PROXY CRUD
    # =========================================================================
    
    def add_proxy(self, proxy: Proxy) -> None:
        """Добавляет прокси."""
        with self._lock_internal:
            self._proxies[proxy.proxy_id] = proxy
            self._save_proxies()
        logger.info(f"Added proxy: {proxy.display_name}")
    
    def remove_proxy(self, proxy_id: str) -> bool:
        """Удаляет прокси."""
        with self._lock_internal:
            if proxy_id in self._proxies:
                proxy = self._proxies.pop(proxy_id)
                # Удаляем из всех списков
                for pl in self._proxy_lists.values():
                    if proxy_id in pl.proxy_ids:
                        pl.proxy_ids.remove(proxy_id)
                self._save_proxies()
                self._save_proxy_lists()
                logger.info(f"Removed proxy: {proxy.display_name}")
                return True
            return False
    
    def get_proxy(self, proxy_id: str) -> Proxy | None:
        """Возвращает прокси по ID."""
        return self._proxies.get(proxy_id)
    
    def get_all_proxies(self) -> list[Proxy]:
        """Возвращает все прокси."""
        return list(self._proxies.values())
    
    def get_enabled_proxies(self) -> list[Proxy]:
        """Возвращает все включенные прокси."""
        return [p for p in self._proxies.values() if p.enabled]
    
    def update_proxy(self, proxy: Proxy) -> None:
        """Обновляет прокси."""
        with self._lock_internal:
            self._proxies[proxy.proxy_id] = proxy
            self._save_proxies()
        logger.debug(f"Updated proxy: {proxy.display_name}")
    
    # =========================================================================
    # PROXY LIST CRUD
    # =========================================================================
    
    def add_proxy_list(self, proxy_list: ProxyList) -> None:
        """Добавляет список прокси."""
        with self._lock_internal:
            self._proxy_lists[proxy_list.list_id] = proxy_list
            self._save_proxy_lists()
        logger.info(f"Added proxy list: {proxy_list.name}")
    
    def remove_proxy_list(self, list_id: str) -> bool:
        """Удаляет список прокси."""
        with self._lock_internal:
            if list_id in self._proxy_lists:
                pl = self._proxy_lists.pop(list_id)
                self._save_proxy_lists()
                logger.info(f"Removed proxy list: {pl.name}")
                return True
            return False
    
    def get_proxy_list(self, list_id: str) -> ProxyList | None:
        """Возвращает список прокси по ID."""
        return self._proxy_lists.get(list_id)
    
    def get_all_proxy_lists(self) -> list[ProxyList]:
        """Возвращает все списки прокси."""
        return list(self._proxy_lists.values())
    
    def add_proxy_to_list(self, list_id: str, proxy_id: str) -> bool:
        """Добавляет прокси в список."""
        with self._lock_internal:
            if list_id not in self._proxy_lists:
                return False
            if proxy_id not in self._proxies:
                return False
            pl = self._proxy_lists[list_id]
            if proxy_id not in pl.proxy_ids:
                pl.proxy_ids.append(proxy_id)
                self._save_proxy_lists()
            return True
    
    def remove_proxy_from_list(self, list_id: str, proxy_id: str) -> bool:
        """Удаляет прокси из списка."""
        with self._lock_internal:
            if list_id not in self._proxy_lists:
                return False
            pl = self._proxy_lists[list_id]
            if proxy_id in pl.proxy_ids:
                pl.proxy_ids.remove(proxy_id)
                self._save_proxy_lists()
                return True
            return False
    
    # =========================================================================
    # HEALTH CHECK
    # =========================================================================
    
    def check_proxy_health(self, proxy: Proxy, timeout: float = 10.0) -> bool:
        """
        Проверяет доступность прокси.
        
        Делает тестовый запрос к Steam API через прокси.
        """
        logger.debug(f"Checking health of proxy: {proxy.display_name}")
        
        try:
            r = requests.get(
                "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/",
                params={"appid": "730", "count": "1"},
                proxies=proxy.to_requests_format(),
                timeout=timeout,
            )
            healthy = r.status_code == 200
            logger.debug(f"Proxy {proxy.display_name} health: {healthy} (status={r.status_code})")
            return healthy
        except Exception as e:
            logger.warning(f"Proxy {proxy.display_name} health check failed: {e}")
            return False
    
    def is_proxy_healthy(self, proxy_id: str, force_check: bool = False) -> bool:
        """
        Проверяет здоровье прокси (с кешированием).
        """
        with self._lock_internal:
            # Проверяем кеш
            if not force_check and proxy_id in self._health_cache:
                healthy, timestamp = self._health_cache[proxy_id]
                if time.time() - timestamp < self._health_ttl:
                    return healthy
            
            proxy = self._proxies.get(proxy_id)
            if not proxy:
                return False
        
        # Проверка вне lock (может быть долгой)
        healthy = self.check_proxy_health(proxy)
        
        with self._lock_internal:
            self._health_cache[proxy_id] = (healthy, time.time())
        
        return healthy
    
    def invalidate_health_cache(self, proxy_id: str | None = None) -> None:
        """Инвалидирует кеш здоровья."""
        with self._lock_internal:
            if proxy_id:
                self._health_cache.pop(proxy_id, None)
            else:
                self._health_cache.clear()
    
    # =========================================================================
    # PROXY SELECTION
    # =========================================================================
    
    def select_proxy(
        self,
        settings: ProxySettings | None,
        fallback_settings: ProxySettings | None = None,
    ) -> Proxy | None:
        """
        Выбирает прокси согласно настройкам.
        
        Args:
            settings: Настройки прокси (например, от игры)
            fallback_settings: Fallback настройки (например, от аккаунта)
        
        Returns:
            Прокси или None если режим direct или прокси недоступны
        """
        # Приоритет: settings > fallback_settings
        effective = settings or fallback_settings
        
        if not effective:
            logger.debug("No proxy settings, using direct connection")
            return None
        
        if effective.mode == ProxyMode.DIRECT:
            logger.debug("Proxy mode is DIRECT")
            return None
        
        if effective.mode == ProxyMode.FIXED:
            return self._select_fixed(effective)
        
        if effective.mode == ProxyMode.MIX:
            return self._select_mix(effective)
        
        if effective.mode == ProxyMode.MIX_LIST:
            return self._select_mix_list(effective)
        
        return None
    
    def _select_fixed(self, settings: ProxySettings) -> Proxy | None:
        """Выбирает фиксированный прокси."""
        if not settings.fixed_proxy_id:
            logger.warning("FIXED mode but no fixed_proxy_id set")
            return self._apply_fallback(settings, [])
        
        proxy = self._proxies.get(settings.fixed_proxy_id)
        if not proxy:
            logger.warning(f"Fixed proxy not found: {settings.fixed_proxy_id}")
            return self._apply_fallback(settings, [])
        
        if not proxy.enabled:
            logger.warning(f"Fixed proxy is disabled: {proxy.display_name}")
            return self._apply_fallback(settings, [proxy])
        
        if not self.is_proxy_healthy(proxy.proxy_id):
            logger.warning(f"Fixed proxy is unhealthy: {proxy.display_name}")
            return self._apply_fallback(settings, [proxy])
        
        logger.debug(f"Selected fixed proxy: {proxy.display_name}")
        return proxy
    
    def _select_mix(self, settings: ProxySettings) -> Proxy | None:
        """Выбирает случайный прокси из всех доступных."""
        candidates = self.get_enabled_proxies()
        if not candidates:
            logger.warning("MIX mode but no enabled proxies")
            return self._apply_fallback(settings, [])
        
        # Перемешиваем и пробуем
        random.shuffle(candidates)
        for proxy in candidates:
            if self.is_proxy_healthy(proxy.proxy_id):
                logger.debug(f"Selected mix proxy: {proxy.display_name}")
                return proxy
        
        logger.warning("All proxies unhealthy in MIX mode")
        return self._apply_fallback(settings, candidates)
    
    def _select_mix_list(self, settings: ProxySettings) -> Proxy | None:
        """Выбирает случайный прокси из выбранного списка."""
        if not settings.proxy_list_id:
            logger.warning("MIX_LIST mode but no proxy_list_id set")
            return self._apply_fallback(settings, [])
        
        proxy_list = self._proxy_lists.get(settings.proxy_list_id)
        if not proxy_list:
            logger.warning(f"Proxy list not found: {settings.proxy_list_id}")
            return self._apply_fallback(settings, [])
        
        candidates = [
            self._proxies[pid]
            for pid in proxy_list.proxy_ids
            if pid in self._proxies and self._proxies[pid].enabled
        ]
        
        if not candidates:
            logger.warning(f"No enabled proxies in list: {proxy_list.name}")
            return self._apply_fallback(settings, [])
        
        # Перемешиваем и пробуем
        random.shuffle(candidates)
        for proxy in candidates:
            if self.is_proxy_healthy(proxy.proxy_id):
                logger.debug(f"Selected mix-list proxy: {proxy.display_name}")
                return proxy
        
        logger.warning(f"All proxies unhealthy in list: {proxy_list.name}")
        return self._apply_fallback(settings, candidates)
    
    def _apply_fallback(
        self,
        settings: ProxySettings,
        tried_proxies: list[Proxy],
    ) -> Proxy | None:
        """Применяет fallback логику при недоступности прокси."""
        if settings.fallback == ProxyFallback.DIRECT_IMMEDIATELY:
            logger.info("Fallback: using direct connection immediately")
            return None
        
        # TRY_ALL_THEN_DIRECT
        logger.info("Fallback: trying all other proxies...")
        tried_ids = {p.proxy_id for p in tried_proxies}
        
        all_enabled = self.get_enabled_proxies()
        remaining = [p for p in all_enabled if p.proxy_id not in tried_ids]
        
        random.shuffle(remaining)
        for proxy in remaining:
            if self.is_proxy_healthy(proxy.proxy_id, force_check=True):
                logger.info(f"Fallback: found working proxy: {proxy.display_name}")
                return proxy
        
        logger.warning("Fallback: all proxies failed, using direct connection")
        return None
    
    def parse_proxy_url(self, url: str) -> Proxy | None:
        """
        Парсит прокси из URL формата.
        
        Форматы:
        - host:port
        - type://host:port
        - type://user:pass@host:port
        """
        import re
        import uuid
        
        # Убираем пробелы
        url = url.strip()
        if not url:
            return None
        
        # Определяем тип
        proxy_type = ProxyType.HTTP
        if url.startswith("https://"):
            proxy_type = ProxyType.HTTPS
            url = url[8:]
        elif url.startswith("http://"):
            proxy_type = ProxyType.HTTP
            url = url[7:]
        elif url.startswith("socks5://"):
            proxy_type = ProxyType.SOCKS5
            url = url[9:]
        
        # Парсим auth
        username = ""
        password = ""
        if "@" in url:
            auth, url = url.rsplit("@", 1)
            if ":" in auth:
                username, password = auth.split(":", 1)
            else:
                username = auth
        
        # Парсим host:port
        match = re.match(r"^([^:]+):(\d+)$", url)
        if not match:
            logger.warning(f"Invalid proxy URL format: {url}")
            return None
        
        host = match.group(1)
        port = int(match.group(2))
        
        return Proxy(
            proxy_id=str(uuid.uuid4())[:8],
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=username,
            password=password,
        )


# Глобальный экземпляр
_proxy_manager: ProxyManager | None = None


def get_proxy_manager(data_dir: Path | None = None) -> ProxyManager:
    """Возвращает глобальный экземпляр ProxyManager."""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager(data_dir)
    return _proxy_manager
