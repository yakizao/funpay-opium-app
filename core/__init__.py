"""Opium Core - ядро системы на базе FunPayAPI."""

from .event_bus import EventBus, OpiumEvent
from .commands import Command, CommandResult, CommandType
from .module import Module, Subscription, register_module_class, get_module_class, list_module_classes
from .runtime import AccountRuntime, AccountConfig, AccountState, ReconnectConfig
from .rate_limiter import RateLimiter, RateLimitConfig, AntiDetectConfig
from .storage import Storage, AccountStorage, ModuleStorage, AccountData
from .logging import setup_logging
from .core import OpiumCore
from .converters import convert_event

__all__ = [
    # Core
    "OpiumCore",
    
    # Storage
    "Storage",
    "AccountStorage", 
    "ModuleStorage",
    "AccountData",
    
    # Runtime
    "AccountRuntime",
    "AccountConfig", 
    "AccountState",
    "ReconnectConfig",
    
    # Events
    "EventBus",
    "OpiumEvent",
    
    # Commands
    "Command",
    "CommandResult",
    "CommandType",
    
    # Modules
    "Module",
    "Subscription",
    "register_module_class",
    "get_module_class",
    "list_module_classes",
    
    # Rate Limiting & Anti-detect
    "RateLimiter",
    "RateLimitConfig",
    "AntiDetectConfig",
    
    # Logging
    "setup_logging",
    
    # Converters
    "convert_event",
]
