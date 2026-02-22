# -*- coding: utf-8 -*-
"""Auto Raise - REST API Router."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.deps import get_module
from .storage import AutoRaiseStorage

logger = logging.getLogger("opium.api.auto_raise")


def _get_storage(account_id: str) -> AutoRaiseStorage:
    module = get_module(account_id, "auto_raise")
    return module.ar_storage


def _get_module(account_id: str):
    return get_module(account_id, "auto_raise")


router = APIRouter(
    prefix="/api/accounts/{account_id}/modules/auto_raise",
    tags=["auto_raise"],
)


# ─── Pydantic Models ─────────────────────────────────

class ConfigUpdate(BaseModel):
    enabled: bool | None = None
    delay_range_minutes: int | None = None


# ─── Config ──────────────────────────────────────────

@router.get("/config")
async def get_config(account_id: str) -> dict[str, Any]:
    storage = _get_storage(account_id)
    return {
        "enabled": storage.is_enabled(),
        "delay_range_minutes": storage.get_delay_range(),
    }


@router.patch("/config")
async def update_config(account_id: str, body: ConfigUpdate) -> dict[str, Any]:
    storage = _get_storage(account_id)
    module = _get_module(account_id)

    if body.enabled is not None:
        storage.set_enabled(body.enabled)
        if body.enabled and not module.is_active:
            await module.start_scheduler()
        elif not body.enabled and module.is_active:
            await module.stop_scheduler()

    if body.delay_range_minutes is not None:
        storage.set_delay_range(body.delay_range_minutes)

    return {
        "ok": True,
        "enabled": storage.is_enabled(),
        "delay_range_minutes": storage.get_delay_range(),
    }


# ─── Status ──────────────────────────────────────────

@router.get("/status")
async def get_status(account_id: str) -> dict[str, Any]:
    module = _get_module(account_id)
    now = time.time()

    next_raises: dict[str, Any] = {}
    for cat_id, ts in module.next_raise_times.items():
        remaining = max(0, int(ts - now))
        next_raises[str(cat_id)] = {
            "next_raise_in": remaining,
            "next_raise_at": ts,
        }

    return {
        "active": module.is_active,
        "raising": module.raising,
        "enabled": module.ar_storage.is_enabled(),
        "next_raises": next_raises,
        "last_results": {
            str(k): v for k, v in module.last_results.items()
        },
    }


# ─── Manual Raise ────────────────────────────────────

@router.post("/raise")
async def raise_now(account_id: str) -> dict[str, Any]:
    module = _get_module(account_id)
    if not hasattr(module, "raise_now"):
        raise HTTPException(500, "Module does not support manual raise")
    results = await module.raise_now()
    return {
        "ok": True,
        "results": {str(k): v for k, v in results.items()},
    }


# ─── Log ──────────────────────────────────────────────

@router.get("/log")
async def get_log(account_id: str, limit: int = 50) -> list[dict[str, Any]]:
    limit = min(limit, 300)
    return _get_storage(account_id).get_log(limit)


@router.delete("/log")
async def clear_log(account_id: str) -> dict[str, Any]:
    _get_storage(account_id).clear_log()
    return {"ok": True}
