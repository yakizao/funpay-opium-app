"""
Global dependency injection for API routers.
Avoids circular imports when module routers need access to OpiumCore.

Usage in endpoints:
    from api.deps import get_core, get_module

    @router.get("/something")
    async def handler(core: OpiumCore = Depends(get_core)):
        ...
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import HTTPException

if TYPE_CHECKING:
    from core import OpiumCore, Module

_core: OpiumCore | None = None


def set_core(core: OpiumCore) -> None:
    """Called once from api/main.py lifespan to share the core instance."""
    global _core
    _core = core


def get_core() -> OpiumCore:
    """FastAPI dependency — returns the OpiumCore instance.

    Can be used directly or via ``Depends(get_core)``.
    """
    if _core is None:
        raise HTTPException(503, "Core not initialized")
    return _core


def get_module(account_id: str, module_name: str) -> Module:
    """Get a module instance for a specific account, or raise 404."""
    core = get_core()
    runtime = core.get_runtime(account_id)
    if runtime is None:
        raise HTTPException(404, f"Account '{account_id}' not found")
    module = core.get_account_module(account_id, module_name)
    if module is None:
        raise HTTPException(404, f"Module '{module_name}' not found on account '{account_id}'")
    return module
