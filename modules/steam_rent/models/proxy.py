# -*- coding: utf-8 -*-
"""
Steam Rent - Proxy Models.

Proxy domain: enums, dataclasses, deserialization.
- ProxyType, ProxyMode, ProxyFallback
- Proxy, ProxyList, ProxySettings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# =============================================================================
# ENUMS
# =============================================================================

class ProxyType(str, Enum):
    """Тип прокси."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS5 = "socks5"


class ProxyMode(str, Enum):
    """Режим работы прокси."""
    DIRECT = "direct"       # Напрямую без прокси
    FIXED = "fixed"         # Фиксированный 1 прокси
    MIX = "mix"             # Случайный из всех доступных
    MIX_LIST = "mix-list"   # Случайный из выбранного списка


class ProxyFallback(str, Enum):
    """Поведение при недоступности прокси."""
    TRY_ALL_THEN_DIRECT = "try-all"   # Пробовать все прокси, потом напрямую
    DIRECT_IMMEDIATELY = "direct"      # Сразу напрямую без попыток


# =============================================================================
# DATACLASSES
# =============================================================================

@dataclass
class Proxy:
    """
    Прокси-сервер для Steam запросов.
    
    Attributes:
        proxy_id: Уникальный ID прокси
        host: Хост прокси
        port: Порт прокси
        proxy_type: Тип прокси (http/https/socks5)
        username: Логин (опционально)
        password: Пароль (опционально)
        name: Человекочитаемое название (опционально)
        enabled: Включен ли прокси
    """
    proxy_id: str
    host: str
    port: int
    proxy_type: ProxyType = ProxyType.HTTP
    username: str = ""
    password: str = ""
    name: str = ""
    enabled: bool = True
    
    @property
    def display_name(self) -> str:
        """Отображаемое имя прокси."""
        if self.name:
            return self.name
        return f"{self.host}:{self.port}"
    
    def to_url(self) -> str:
        """Возвращает URL прокси для requests."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        
        # Для SOCKS5 используем socks5:// или socks5h:// (h = hostname resolution through proxy)
        scheme = self.proxy_type.value
        if scheme == "https":
            scheme = "http"  # requests использует http:// для HTTPS прокси
        elif scheme == "socks5":
            scheme = "socks5h"  # используем socks5h для резолва DNS через прокси
        
        return f"{scheme}://{auth}{self.host}:{self.port}"
    
    def to_requests_format(self) -> dict[str, str]:
        """Возвращает dict для requests proxies параметра."""
        url = self.to_url()
        return {
            "http": url,
            "https": url,
        }


@dataclass
class ProxyList:
    """
    Список прокси для режима mix-list.
    
    Attributes:
        list_id: Уникальный ID списка
        name: Название списка
        proxy_ids: ID прокси в этом списке
    """
    list_id: str
    name: str
    proxy_ids: list[str] = field(default_factory=list)


@dataclass
class ProxySettings:
    """
    Настройки прокси для аккаунта или игры.
    
    Attributes:
        mode: Режим работы прокси
        fixed_proxy_id: ID прокси для режима fixed
        proxy_list_id: ID списка для режима mix-list
        fallback: Поведение при недоступности прокси
    """
    mode: ProxyMode = ProxyMode.DIRECT
    fixed_proxy_id: str | None = None
    proxy_list_id: str | None = None
    fallback: ProxyFallback = ProxyFallback.TRY_ALL_THEN_DIRECT


# =============================================================================
# DESERIALIZATION
# =============================================================================

def proxy_settings_from_dict(data: dict[str, Any] | None) -> ProxySettings | None:
    """Десериализует ProxySettings из dict."""
    if not data:
        return None
    
    mode = data.get("mode", "direct")
    if isinstance(mode, str):
        mode = ProxyMode(mode)
    
    fallback = data.get("fallback", "try-all")
    if isinstance(fallback, str):
        fallback = ProxyFallback(fallback)
    
    return ProxySettings(
        mode=mode,
        fixed_proxy_id=data.get("fixed_proxy_id"),
        proxy_list_id=data.get("proxy_list_id"),
        fallback=fallback,
    )


def proxy_from_dict(data: dict[str, Any]) -> Proxy:
    """Десериализует Proxy из dict."""
    proxy_type = data.get("proxy_type", "http")
    if isinstance(proxy_type, str):
        proxy_type = ProxyType(proxy_type)
    
    return Proxy(
        proxy_id=data["proxy_id"],
        host=data["host"],
        port=data["port"],
        proxy_type=proxy_type,
        username=data.get("username", ""),
        password=data.get("password", ""),
        name=data.get("name", ""),
        enabled=data.get("enabled", True),
    )


def proxy_list_from_dict(data: dict[str, Any]) -> ProxyList:
    """Десериализует ProxyList из dict."""
    return ProxyList(
        list_id=data["list_id"],
        name=data["name"],
        proxy_ids=data.get("proxy_ids", []),
    )
