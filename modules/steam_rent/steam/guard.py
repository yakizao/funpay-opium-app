# -*- coding: utf-8 -*-
"""
Steam Guard code generation and crypto helpers.

- generate_guard_code: TOTP code for Steam Guard
- generate_device_id: SDA-format device ID
- generate_confirmation_key: HMAC key for mobileconf API
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import struct
import time
import traceback

from .http import _mask_secret

logger = logging.getLogger("opium.steam_rent.steam")

# Steam Guard alphabet for TOTP
STEAM_ALPHABET = "23456789BCDFGHJKMNPQRTVWXY"


def generate_guard_code(shared_secret: str) -> str:
    """
    Генерирует Steam Guard TOTP код.

    Args:
        shared_secret: Shared secret из mafile

    Returns:
        5-символьный Guard код

    Raises:
        ValueError: Если shared_secret невалиден
    """
    logger.debug(
        f">>> generate_guard_code(shared_secret={_mask_secret(shared_secret)})"
    )
    if not shared_secret:
        raise ValueError("shared_secret is empty")

    try:
        timestamp = int(time.time()) // 30
        logger.debug(f"    timestamp={timestamp}, time={int(time.time())}")
        msg = struct.pack(">Q", timestamp)
        key = base64.b64decode(shared_secret)
        logger.debug(f"    key_len={len(key)}")
        hmac_hash = hmac.new(key, msg, hashlib.sha1).digest()
        offset = hmac_hash[-1] & 0x0F
        code = struct.unpack(">I", hmac_hash[offset : offset + 4])[0] & 0x7FFFFFFF

        chars = []
        for _ in range(5):
            chars.append(STEAM_ALPHABET[code % len(STEAM_ALPHABET)])
            code //= len(STEAM_ALPHABET)

        result = "".join(chars)
        logger.debug(f"<<< generate_guard_code: code generated (len={len(result)})")
        return result
    except Exception as e:
        logger.error(f"!!! generate_guard_code ERROR: {e}\n{traceback.format_exc()}")
        raise ValueError(f"Invalid shared_secret: {e}")


def generate_device_id(steam_id: str) -> str:
    """Генерирует Device ID в формате SDA."""
    logger.debug(f">>> generate_device_id(steam_id={steam_id})")
    h = hashlib.sha1(steam_id.encode()).hexdigest()
    result = f"android:{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
    logger.debug(f"<<< generate_device_id: {result}")
    return result


def generate_confirmation_key(
    identity_secret: str, tag: str, timestamp: int
) -> str:
    """Генерирует ключ подтверждения для mobileconf."""
    logger.debug(
        f">>> generate_confirmation_key(identity={_mask_secret(identity_secret)}, "
        f"tag={tag}, ts={timestamp})"
    )
    try:
        msg = struct.pack(">Q", timestamp) + tag.encode("utf-8")
        key = base64.b64decode(identity_secret)
        result = base64.b64encode(hmac.new(key, msg, hashlib.sha1).digest()).decode()
        logger.debug(f"<<< generate_confirmation_key: key={_mask_secret(result)}")
        return result
    except Exception as e:
        logger.error(
            f"!!! generate_confirmation_key ERROR: {e}\n{traceback.format_exc()}"
        )
        raise
