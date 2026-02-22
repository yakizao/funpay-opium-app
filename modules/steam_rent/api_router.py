"""
Steam Rent - REST API Router.

Provides CRUD endpoints for all Steam Rent module data.
Mounted automatically by api/main.py at /api/accounts/{account_id}/modules/steam_rent/*
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.deps import get_module
from modules.steam_rent.models import (
    AccountStatus, RentalStatus,
    game_from_dict, lot_mapping_from_dict, steam_account_from_dict,
    proxy_from_dict, proxy_list_from_dict,
    to_dict,
)
from modules.steam_rent.storage import SteamRentStorage
from modules.steam_rent.proxy import get_proxy_manager
from modules.steam_rent.handlers import release_account

logger = logging.getLogger("opium.api.steam_rent")


def _serialize_steam_account(acc, unmask: bool = False) -> dict[str, Any]:
    """Serialize SteamAccount with proper field names for the frontend.
    
    Secrets (password, mafile, password_history) are masked by default.
    """
    d = to_dict(acc)
    # Map steam_account_id → id for frontend
    d["id"] = d.pop("steam_account_id", d.get("id", ""))
    # Add @property fields that asdict() skips
    d["shared_secret"] = acc.shared_secret or None
    d["identity_secret"] = acc.identity_secret or None
    d["has_mafile"] = bool(acc.mafile)
    
    # Mask secrets
    if not unmask:
        d["password"] = "***" if acc.password else ""
        d.pop("mafile", None)
        d.pop("password_history", None)
        if d.get("shared_secret"):
            d["shared_secret"] = "***"
        if d.get("identity_secret"):
            d["identity_secret"] = "***"
    
    return d


router = APIRouter(
    prefix="/api/accounts/{account_id}/modules/steam_rent",
    tags=["steam_rent"],
)


def _get_storage(account_id: str) -> SteamRentStorage:
    """Get SteamRentStorage for the given account."""
    module = get_module(account_id, "steam_rent")
    return module.steam_storage  # type: ignore[union-attr]


# ─── Pydantic Models ──────────────────────────────────

class GameCreate(BaseModel):
    game_id: str
    aliases: list[str] = []
    proxy_settings: dict[str, Any] | None = None

class GameUpdate(BaseModel):
    game_id: str | None = None
    aliases: list[str] | None = None
    proxy_settings: dict[str, Any] | None = None

class LotMappingCreate(BaseModel):
    lot_pattern: str
    game_id: str
    rent_minutes: int = 0
    bonus_minutes: int = 0
    min_rating_for_bonus: int = 4

class SteamAccountCreate(BaseModel):
    id: str | None = None
    login: str
    password: str
    game_ids: list[str] = []
    change_password_on_rent: bool = False
    kick_devices_on_rent: bool = True
    shared_secret: str | None = None
    identity_secret: str | None = None

class SteamAccountUpdate(BaseModel):
    login: str | None = None
    password: str | None = None
    game_ids: list[str] | None = None
    change_password_on_rent: bool | None = None
    kick_devices_on_rent: bool | None = None

class PasswordChangeRequest(BaseModel):
    new_password: str | None = None


# ═══════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════

@router.get("/overview")
async def get_overview(account_id: str):
    """Dashboard overview stats."""
    storage = _get_storage(account_id)
    active = storage.get_active_rentals()
    accounts = storage.get_steam_accounts()
    free = [a for a in accounts if a.status == AccountStatus.FREE and not a.frozen]
    return {
        "active_rentals": len(active),
        "total_rentals": len(storage.get_rentals()),
        "free_accounts": len(free),
        "total_accounts": len(accounts),
        "total_games": len(storage.get_games()),
        "lot_mappings": len(storage.get_lot_mappings()),
        "pending_orders": len(storage.get_pending_orders()),
    }


# ═══════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════

@router.get("/config")
async def get_config(account_id: str):
    """Get module config."""
    storage = _get_storage(account_id)
    return storage.get_config()


@router.put("/config")
async def update_config(account_id: str, config: dict[str, Any]):
    """Update module config."""
    storage = _get_storage(account_id)
    current = storage.get_config()
    current.update(config)
    storage._storage.save_config(current)
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# GAMES
# ═══════════════════════════════════════════════════════

@router.get("/games")
async def list_games(account_id: str):
    """List all games."""
    storage = _get_storage(account_id)
    return [to_dict(g) for g in storage.get_games()]


@router.post("/games")
async def create_game(account_id: str, data: GameCreate):
    """Create a new game."""
    storage = _get_storage(account_id)
    if storage.get_game(data.game_id):
        raise HTTPException(409, f"Game '{data.game_id}' already exists")
    game = game_from_dict({
        "game_id": data.game_id,
        "aliases": data.aliases,
        "proxy_settings": data.proxy_settings,
    })
    storage.add_game(game)
    return to_dict(game)


@router.put("/games/{game_id}")
async def update_game(account_id: str, game_id: str, data: GameUpdate):
    """Update a game."""
    storage = _get_storage(account_id)
    game = storage.get_game(game_id)
    if not game:
        raise HTTPException(404, f"Game '{game_id}' not found")
    update = to_dict(game)
    if data.aliases is not None:
        update["aliases"] = data.aliases
    if data.proxy_settings is not None:
        update["proxy_settings"] = data.proxy_settings
    updated = game_from_dict(update)
    storage.update_game(updated)
    return to_dict(updated)


@router.delete("/games/{game_id}")
async def delete_game(account_id: str, game_id: str):
    """Delete a game."""
    storage = _get_storage(account_id)
    if not storage.delete_game(game_id):
        raise HTTPException(404, f"Game '{game_id}' not found")
    return {"ok": True}


@router.post("/games/{game_id}/freeze")
async def freeze_game(account_id: str, game_id: str):
    """Toggle frozen state for a game."""
    storage = _get_storage(account_id)
    game = storage.get_game(game_id)
    if not game:
        raise HTTPException(404, f"Game '{game_id}' not found")
    game.frozen = not game.frozen
    storage.update_game(game)
    return {"ok": True, "frozen": game.frozen}


# ═══════════════════════════════════════════════════════
# LOT MAPPINGS
# ═══════════════════════════════════════════════════════

@router.get("/lot-mappings")
async def list_lot_mappings(account_id: str):
    """List all lot mappings."""
    storage = _get_storage(account_id)
    return [to_dict(m) for m in storage.get_lot_mappings()]


@router.post("/lot-mappings")
async def create_lot_mapping(account_id: str, data: LotMappingCreate):
    """Create a new lot mapping."""
    storage = _get_storage(account_id)
    mapping = lot_mapping_from_dict(data.model_dump())
    storage.add_lot_mapping(mapping)
    return to_dict(mapping)


@router.put("/lot-mappings/{index}")
async def update_lot_mapping(account_id: str, index: int, data: LotMappingCreate):
    """Update a lot mapping by index."""
    storage = _get_storage(account_id)
    mappings = storage.get_lot_mappings()
    if index < 0 or index >= len(mappings):
        raise HTTPException(404, f"Lot mapping #{index} not found")
    mapping = lot_mapping_from_dict(data.model_dump())
    storage.update_lot_mapping(index, mapping)
    return to_dict(mapping)


@router.delete("/lot-mappings/{index}")
async def delete_lot_mapping(account_id: str, index: int):
    """Delete a lot mapping by index."""
    storage = _get_storage(account_id)
    if not storage.delete_lot_mapping(index):
        raise HTTPException(404, f"Lot mapping #{index} not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# STEAM ACCOUNTS
# ═══════════════════════════════════════════════════════

@router.get("/steam-accounts")
async def list_steam_accounts(account_id: str):
    """List all steam accounts."""
    storage = _get_storage(account_id)
    return [_serialize_steam_account(a) for a in storage.get_steam_accounts()]


@router.post("/steam-accounts/{steam_id}/freeze")
async def freeze_steam_account(account_id: str, steam_id: str):
    """Toggle frozen state for a steam account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    acc.frozen = not acc.frozen
    storage.update_steam_account(acc)
    return {"ok": True, "frozen": acc.frozen}


@router.post("/steam-accounts")
async def create_steam_account(account_id: str, data: SteamAccountCreate):
    """Create a new steam account."""
    storage = _get_storage(account_id)
    acc_id = data.id or data.login
    if storage.get_steam_account(acc_id):
        raise HTTPException(409, f"Steam account '{acc_id}' already exists")
    acc = steam_account_from_dict({
        "steam_account_id": acc_id,
        "login": data.login,
        "password": data.password,
        "game_ids": data.game_ids,
        "status": "free",
        "change_password_on_rent": data.change_password_on_rent,
        "kick_devices_on_rent": data.kick_devices_on_rent,
        "shared_secret": data.shared_secret,
        "identity_secret": data.identity_secret,
    })
    storage.add_steam_account(acc)
    return _serialize_steam_account(acc)


@router.put("/steam-accounts/{steam_id}")
async def update_steam_account(account_id: str, steam_id: str, data: SteamAccountUpdate):
    """Update a steam account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    d = to_dict(acc)
    for k, v in data.model_dump(exclude_none=True).items():
        d[k] = v
    updated = steam_account_from_dict(d)
    storage.update_steam_account(updated)
    return _serialize_steam_account(updated)


@router.delete("/steam-accounts/{steam_id}")
async def delete_steam_account(account_id: str, steam_id: str):
    """Delete a steam account."""
    storage = _get_storage(account_id)
    if not storage.delete_steam_account(steam_id):
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    return {"ok": True}


# ─── Steam Account Actions ───────────────────────────


@router.get("/steam-accounts/{steam_id}/password")
async def reveal_steam_account_password(account_id: str, steam_id: str):
    """Return the real (unmasked) password for a steam account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    return {"password": acc.password or ""}


@router.post("/steam-accounts/{steam_id}/guard-code")
async def get_guard_code(account_id: str, steam_id: str):
    """Generate a Steam Guard code for the account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    if not acc.shared_secret:
        raise HTTPException(400, "No shared_secret available (import mafile first)")
    try:
        from modules.steam_rent.steam import generate_guard_code
        code = generate_guard_code(acc.shared_secret)
        return {"code": code}
    except Exception as e:
        raise HTTPException(500, f"Failed to generate guard code: {e}")


@router.post("/steam-accounts/{steam_id}/change-password")
async def change_password(account_id: str, steam_id: str, data: PasswordChangeRequest | None = None):
    """Change password for a steam account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    if not acc.mafile:
        raise HTTPException(400, "No mafile available (import mafile first)")
    try:
        from modules.steam_rent.steam import change_password as steam_change_password
        new_pass = data.new_password if data else None
        result = await asyncio.to_thread(
            steam_change_password,
            login=acc.login,
            password=acc.password,
            mafile=acc.mafile,
            new_password=new_pass,
            excluded_passwords=acc.password_history,
        )
        if result.success:
            acc.password_history.append(acc.password)
            acc.password = result.new_password or new_pass
            storage.update_steam_account(acc)
            return {"ok": True, "new_password": acc.password}
        else:
            raise HTTPException(500, f"Password change failed: {result.error}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"change_password error: {e}")
        raise HTTPException(500, f"Failed to change password: {e}")


@router.post("/steam-accounts/{steam_id}/kick-sessions")
async def kick_sessions(account_id: str, steam_id: str):
    """Kick all active sessions for a steam account."""
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    if not acc.mafile:
        raise HTTPException(400, "No mafile available (import mafile first)")
    try:
        from modules.steam_rent.steam import kick_all_sessions
        result = await asyncio.to_thread(
            kick_all_sessions,
            login=acc.login,
            password=acc.password,
            mafile=acc.mafile,
        )
        if result.success:
            return {"ok": True}
        else:
            raise HTTPException(500, f"Kick sessions failed: {result.error}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"kick_sessions error: {e}")
        raise HTTPException(500, f"Failed to kick sessions: {e}")


@router.post("/steam-accounts/{steam_id}/import-mafile")
async def import_mafile(account_id: str, steam_id: str, request: Request):
    """Import a mafile (Steam Guard data) for the account.

    Accepts raw JSON string (text/plain) to avoid JavaScript Number precision loss
    on SteamID fields (64-bit integers exceed JS Number.MAX_SAFE_INTEGER).
    """
    import json as _json
    storage = _get_storage(account_id)
    acc = storage.get_steam_account(steam_id)
    if not acc:
        raise HTTPException(404, f"Steam account '{steam_id}' not found")
    body = await request.body()
    try:
        mafile = _json.loads(body)
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid JSON: {e}")
    if not isinstance(mafile, dict):
        raise HTTPException(400, "mafile must be a JSON object")
    acc.mafile = mafile
    storage.update_steam_account(acc)
    return {"ok": True}


# ═══════════════════════════════════════════════════════
# RENTALS
# ═══════════════════════════════════════════════════════

@router.get("/rentals")
async def list_rentals(account_id: str):
    """List all rentals."""
    storage = _get_storage(account_id)
    return [to_dict(r) for r in storage.get_rentals()]


@router.get("/rentals/active")
async def list_active_rentals(account_id: str):
    """List active rentals only."""
    storage = _get_storage(account_id)
    return [to_dict(r) for r in storage.get_active_rentals()]


class RentalTimeUpdate(BaseModel):
    minutes: int  # positive = add time, negative = remove time


@router.patch("/rentals/{rental_id}/time")
async def update_rental_time(account_id: str, rental_id: str, data: RentalTimeUpdate):
    """Add or remove time from an active rental."""
    storage = _get_storage(account_id)
    rental = storage.get_rental(rental_id)
    if not rental:
        raise HTTPException(404, f"Rental '{rental_id}' not found")
    if rental.status != RentalStatus.ACTIVE:
        raise HTTPException(400, "Can only modify active rentals")

    # Validate: check if the new end_time would be in the past BEFORE mutating
    from datetime import datetime, timedelta
    projected_end = rental.end_datetime + timedelta(minutes=data.minutes)
    if projected_end < datetime.now():
        raise HTTPException(400, "Cannot reduce time below current moment")

    rental.extend_time_minutes(data.minutes)
    storage.update_rental(rental)
    return to_dict(rental)


@router.post("/rentals/{rental_id}/terminate")
async def terminate_rental(account_id: str, rental_id: str):
    """Terminate (revoke) an active rental."""
    storage = _get_storage(account_id)
    rental = storage.get_rental(rental_id)
    if not rental:
        raise HTTPException(404, f"Rental '{rental_id}' not found")
    if rental.status != RentalStatus.ACTIVE:
        raise HTTPException(400, "Rental is not active")

    # Освобождаем аккаунт (смена пароля + кик сессий + FREE)
    release_account(rental.steam_account_id, storage, reason="terminated")

    # Update rental status
    rental.status = RentalStatus.REVOKED
    storage.update_rental(rental)
    return to_dict(rental)


# ═══════════════════════════════════════════════════════
# PROXIES (global - not per-account)
# ═══════════════════════════════════════════════════════

def _serialize_proxy(proxy) -> dict[str, Any]:
    """Serialize Proxy with masked password."""
    d = to_dict(proxy)
    if proxy.password:
        d["password"] = "***"
    return d


# ─── Pydantic Models (Proxy) ─────────────────────────

class ProxyCreate(BaseModel):
    host: str | None = None
    port: int | None = None
    proxy_type: str = "http"
    username: str = ""
    password: str = ""
    name: str = ""
    enabled: bool = True
    url: str | None = None  # Alternative: parse from url string


class ProxyUpdate(BaseModel):
    host: str | None = None
    port: int | None = None
    proxy_type: str | None = None
    username: str | None = None
    password: str | None = None
    name: str | None = None
    enabled: bool | None = None


class ProxyListCreate(BaseModel):
    name: str
    proxy_ids: list[str] = []


# ─── Proxy CRUD ───────────────────────────────────────

@router.get("/proxies")
async def list_proxies(account_id: str):
    """List all proxies (global, not per-account). Passwords masked."""
    pm = get_proxy_manager()
    return [_serialize_proxy(p) for p in pm.get_all_proxies()]


@router.post("/proxies")
async def create_proxy(account_id: str, data: ProxyCreate):
    """Create a new proxy. Either provide host+port or a url string."""
    import uuid

    pm = get_proxy_manager()

    if data.url:
        # Parse from URL string
        proxy = pm.parse_proxy_url(data.url)
        if not proxy:
            raise HTTPException(400, f"Invalid proxy URL format: {data.url}")
        # Override with explicit fields if provided
        if data.name:
            proxy.name = data.name
        if not data.enabled:
            proxy.enabled = data.enabled
    else:
        if not data.host or not data.port:
            raise HTTPException(400, "Either 'url' or both 'host' and 'port' are required")
        proxy = proxy_from_dict({
            "proxy_id": str(uuid.uuid4())[:8],
            "host": data.host,
            "port": data.port,
            "proxy_type": data.proxy_type,
            "username": data.username,
            "password": data.password,
            "name": data.name,
            "enabled": data.enabled,
        })

    pm.add_proxy(proxy)
    return _serialize_proxy(proxy)


@router.put("/proxies/{proxy_id}")
async def update_proxy(account_id: str, proxy_id: str, data: ProxyUpdate):
    """Update an existing proxy."""
    pm = get_proxy_manager()
    proxy = pm.get_proxy(proxy_id)
    if not proxy:
        raise HTTPException(404, f"Proxy '{proxy_id}' not found")

    d = to_dict(proxy)
    for k, v in data.model_dump(exclude_none=True).items():
        d[k] = v
    updated = proxy_from_dict(d)
    pm.update_proxy(updated)
    return _serialize_proxy(updated)


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(account_id: str, proxy_id: str):
    """Delete a proxy (also removes it from all proxy lists)."""
    pm = get_proxy_manager()
    if not pm.remove_proxy(proxy_id):
        raise HTTPException(404, f"Proxy '{proxy_id}' not found")
    return {"ok": True}


@router.post("/proxies/{proxy_id}/check")
async def check_proxy_health(account_id: str, proxy_id: str):
    """Check if a proxy is healthy (makes test request to Steam)."""
    pm = get_proxy_manager()
    proxy = pm.get_proxy(proxy_id)
    if not proxy:
        raise HTTPException(404, f"Proxy '{proxy_id}' not found")

    healthy = await asyncio.to_thread(pm.check_proxy_health, proxy)
    return {"healthy": healthy, "proxy_id": proxy_id}


# ─── Proxy Lists ──────────────────────────────────────

@router.get("/proxy-lists")
async def list_proxy_lists(account_id: str):
    """List all proxy lists."""
    pm = get_proxy_manager()
    return [to_dict(pl) for pl in pm.get_all_proxy_lists()]


@router.post("/proxy-lists")
async def create_proxy_list(account_id: str, data: ProxyListCreate):
    """Create a new proxy list."""
    import uuid

    pm = get_proxy_manager()
    pl = proxy_list_from_dict({
        "list_id": str(uuid.uuid4())[:8],
        "name": data.name,
        "proxy_ids": data.proxy_ids,
    })
    pm.add_proxy_list(pl)
    return to_dict(pl)


@router.delete("/proxy-lists/{list_id}")
async def delete_proxy_list(account_id: str, list_id: str):
    """Delete a proxy list."""
    pm = get_proxy_manager()
    if not pm.remove_proxy_list(list_id):
        raise HTTPException(404, f"Proxy list '{list_id}' not found")
    return {"ok": True}


@router.post("/proxy-lists/{list_id}/proxies/{proxy_id}")
async def add_proxy_to_list(account_id: str, list_id: str, proxy_id: str):
    """Add a proxy to a proxy list."""
    pm = get_proxy_manager()
    if not pm.add_proxy_to_list(list_id, proxy_id):
        # Determine which entity is missing
        if not pm.get_proxy_list(list_id):
            raise HTTPException(404, f"Proxy list '{list_id}' not found")
        if not pm.get_proxy(proxy_id):
            raise HTTPException(404, f"Proxy '{proxy_id}' not found")
        raise HTTPException(400, "Failed to add proxy to list")

    return {"ok": True}


@router.delete("/proxy-lists/{list_id}/proxies/{proxy_id}")
async def remove_proxy_from_list(account_id: str, list_id: str, proxy_id: str):
    """Remove a proxy from a proxy list."""
    pm = get_proxy_manager()
    if not pm.remove_proxy_from_list(list_id, proxy_id):
        if not pm.get_proxy_list(list_id):
            raise HTTPException(404, f"Proxy list '{list_id}' not found")
        raise HTTPException(404, f"Proxy '{proxy_id}' not in list '{list_id}'")

    return {"ok": True}


# ═══════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═══════════════════════════════════════════════════════

@router.get("/messages")
async def get_messages(account_id: str):
    """
    Get all message templates with full metadata for the editor UI.

    Returns groups, labels, placeholders, examples — all from backend.
    Dead keys (from old versions) are auto-cleaned on read.
    """
    from modules.steam_rent.messages import DEFAULT_MESSAGES, build_api_response

    storage = _get_storage(account_id)
    overrides = storage.get_messages()

    # Auto-clean dead keys
    clean = {k: v for k, v in overrides.items() if k in DEFAULT_MESSAGES}
    if len(clean) != len(overrides):
        storage.save_messages(clean)

    return build_api_response(clean)


@router.put("/messages")
async def update_messages(account_id: str, body: dict[str, Any]):
    """
    Update message templates (partial merge).

    Body: { key: new_template, ... }
    - Only provided keys are updated.
    - null or "" resets key to default.
    - Unknown keys are ignored.
    """
    from modules.steam_rent.messages import DEFAULT_MESSAGES, build_api_response

    storage = _get_storage(account_id)
    current = storage.get_messages()

    # Drop dead keys (from old versions)
    current = {k: v for k, v in current.items() if k in DEFAULT_MESSAGES}

    for key, value in body.items():
        if key not in DEFAULT_MESSAGES:
            continue
        if value is None or value == "":
            current.pop(key, None)
        else:
            current[key] = str(value)

    storage.save_messages(current)
    return {"ok": True, **build_api_response(current)}
