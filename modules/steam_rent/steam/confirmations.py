# -*- coding: utf-8 -*-
"""
Steam mobile confirmations: fetch and accept/cancel.
"""

from __future__ import annotations

import logging
import traceback
import time
from typing import Any

from .guard import generate_confirmation_key, generate_device_id
from .http import SteamHTTP, USER_AGENT
from .session import SteamUrls

logger = logging.getLogger("opium.steam_rent.steam")


def get_confirmations(
    mafile: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], str | None]:
    """
    Получает ожидающие подтверждения.

    Returns: (success, confirmations, error)
    """
    logger.debug(">>> get_confirmations()")
    steam_id = mafile.get("Session", {}).get("SteamID") or mafile.get("steamid")
    identity_secret = mafile.get("identity_secret")
    device_id = mafile.get("device_id") or generate_device_id(str(steam_id))
    login_secure = mafile.get("Session", {}).get("SteamLoginSecure", "")

    logger.debug(f"    steam_id={steam_id}, device_id={device_id}")
    logger.debug(f"    identity_secret present: {bool(identity_secret)}")
    logger.debug(f"    login_secure present: {bool(login_secure)}")

    if not all([steam_id, identity_secret, login_secure]):
        logger.error("!!! get_confirmations: Missing mafile data")
        return False, [], "Missing mafile data"

    ts = int(time.time())
    conf_key = generate_confirmation_key(identity_secret, "conf", ts)

    try:
        logger.debug("    Fetching confirmations...")
        r = SteamHTTP.get(
            SteamUrls.MOBILECONF_GETLIST,
            params={
                "p": device_id,
                "a": str(steam_id),
                "k": conf_key,
                "t": str(ts),
                "m": "react",
                "tag": "conf",
            },
            cookies={"steamLoginSecure": login_secure},
            headers={"User-Agent": USER_AGENT},
        )

        data = SteamHTTP.safe_json(r, {})
        logger.debug(
            f"    getlist response: success={data.get('success')}, "
            f"conf_count={len(data.get('conf', []))}"
        )

        if not data.get("success"):
            error = data.get("message", "Unknown error")
            logger.error(f"!!! get_confirmations: {error}")
            return False, [], error

        confirmations = data.get("conf", [])
        logger.info(
            f"<<< get_confirmations: Found {len(confirmations)} confirmations"
        )
        return True, confirmations, None

    except Exception as e:
        logger.error(
            f"!!! get_confirmations ERROR: {e}\n{traceback.format_exc()}"
        )
        return False, [], str(e)


def confirm_confirmation(
    mafile: dict[str, Any],
    confirmation_id: str,
    confirmation_nonce: str,
    action: str = "allow",
) -> tuple[bool, str | None]:
    """
    Подтверждает или отклоняет операцию.

    Args:
        mafile: Данные mafile
        confirmation_id: ID подтверждения
        confirmation_nonce: Nonce подтверждения
        action: "allow" или "cancel"

    Returns: (success, error)
    """
    logger.debug(
        f">>> confirm_confirmation(id={confirmation_id}, action={action})"
    )
    steam_id = mafile.get("Session", {}).get("SteamID") or mafile.get("steamid")
    identity_secret = mafile.get("identity_secret")
    device_id = mafile.get("device_id") or generate_device_id(str(steam_id))
    login_secure = mafile.get("Session", {}).get("SteamLoginSecure", "")

    if not all([steam_id, identity_secret, login_secure]):
        return False, "Missing mafile data"

    ts = int(time.time())
    conf_key = generate_confirmation_key(identity_secret, action, ts)

    try:
        r = SteamHTTP.get(
            SteamUrls.MOBILECONF_AJAXOP,
            params={
                "op": action,
                "p": device_id,
                "a": str(steam_id),
                "k": conf_key,
                "t": str(ts),
                "m": "react",
                "tag": action,
                "cid": confirmation_id,
                "ck": confirmation_nonce,
            },
            cookies={"steamLoginSecure": login_secure},
            headers={"User-Agent": USER_AGENT},
        )

        data = SteamHTTP.safe_json(r, {})
        if data.get("success"):
            logger.info("<<< confirm_confirmation: SUCCESS")
            return True, None
        else:
            error = data.get("message", "Unknown error")
            logger.error(f"!!! confirm_confirmation: {error}")
            return False, error

    except Exception as e:
        logger.error(
            f"!!! confirm_confirmation ERROR: {e}\n{traceback.format_exc()}"
        )
        return False, str(e)
