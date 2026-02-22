"""
API Serialization helpers.

Converts internal Python objects into JSON-safe dicts for the REST API.
Keeps frontend-facing field names stable (backward-compatible).

NOTE: core.converters provides canonical serializers (serialize_message,
serialize_order_shortcut, serialize_chat_shortcut) used for EventBus
payloads. These API serializers produce a DIFFERENT format optimised
for the frontend. When Chat 6 migrates to the canonical format, this
module can be replaced with thin wrappers around core.converters.
"""

from __future__ import annotations

from typing import Any


def serialize_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Serialize a list of FunPayAPI Message objects for the frontend."""
    return [_serialize_message(msg) for msg in messages]


def _serialize_message(msg: Any) -> dict[str, Any]:
    return {
        "id": getattr(msg, "id", 0),
        "text": getattr(msg, "text", ""),
        "html": getattr(msg, "html", getattr(msg, "text", "")),
        "author": getattr(msg, "author", "Unknown"),
        "author_id": getattr(msg, "author_id", 0),
        "is_my": getattr(msg, "by_bot", False),
        "image_url": getattr(msg, "image_link", None),
    }


def normalize_status(raw: Any) -> str:
    """Extract a human-readable status string from an enum or raw value."""
    if hasattr(raw, "name"):
        return raw.name.lower()
    s = str(raw)
    # fallback: 'OrderStatuses.REFUNDED' -> 'refunded'
    if "." in s:
        s = s.rsplit(".", 1)[-1]
    return s.lower()


def serialize_order_shortcut(order: Any) -> dict[str, Any]:
    """Serialize an OrderShortcut for the frontend list view."""
    return {
        "order_id": getattr(order, "id", ""),
        "description": getattr(order, "description", ""),
        "price": str(getattr(order, "price", 0)),
        "buyer": getattr(order, "buyer_username", ""),
        "buyer_id": getattr(order, "buyer_id", 0),
        "status": normalize_status(getattr(order, "status", "")),
        "date": str(getattr(order, "date", getattr(order, "created_at", ""))),
    }


def serialize_order(order: Any) -> dict[str, Any]:
    """Serialize a full Order object for the detail view."""
    return {
        "order_id": getattr(order, "id", ""),
        "status": normalize_status(getattr(order, "status", "")),
        "description": getattr(order, "description", ""),
        "price": str(getattr(order, "price", 0)),
        "buyer": getattr(order, "buyer_username", ""),
        "buyer_id": getattr(order, "buyer_id", 0),
        "review": getattr(order, "review", None),
        "chat_id": getattr(order, "chat_id", None),
        "date": str(getattr(order, "date", getattr(order, "created_at", ""))),
    }
