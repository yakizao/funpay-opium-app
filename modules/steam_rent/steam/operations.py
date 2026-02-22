# -*- coding: utf-8 -*-
"""
High-level Steam operations: change_password, kick_all_sessions.

These are the primary public functions consumed by handlers and API router.
All operations are SYNCHRONOUS (called via run_in_executor from async code).
"""

from __future__ import annotations

import base64
import logging
import secrets
import time
import traceback
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse, parse_qs

import rsa

from .guard import generate_confirmation_key, generate_device_id
from .http import SteamHTTP, USER_AGENT, _mask_secret
from .session import SessionCache, SteamSession, SteamUrls
from .types import KickSessionsResult, PasswordChangeResult

if TYPE_CHECKING:
    from ..models import Proxy

logger = logging.getLogger("opium.steam_rent.steam")


def generate_random_password(length: int = 12) -> str:
    """Генерирует безопасный пароль."""
    chars = "ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(chars) for _ in range(length))


# =============================================================================
# change_password — 12-step wizard flow
# =============================================================================


def change_password(
    login: str,
    password: str,
    mafile: dict[str, Any],
    new_password: str | None = None,
    excluded_passwords: list[str] | None = None,
    proxy: "Proxy | None" = None,
) -> PasswordChangeResult:
    """
    Меняет пароль Steam аккаунта через Help portal.

    Args:
        login: Steam логин
        password: Текущий пароль
        mafile: Данные mafile
        new_password: Новый пароль (опционально, сгенерируется)
        excluded_passwords: Пароли для исключения (история)
        proxy: Прокси для запросов (опционально)

    Returns:
        PasswordChangeResult с результатом
    """
    logger.info(f">>> change_password(login={login})")
    if proxy:
        logger.info(f"    Using proxy: {proxy.display_name}")

    # Извлекаем секреты из mafile
    shared_secret = mafile.get("shared_secret", "")
    identity_secret = mafile.get("identity_secret", "")
    steam_id = mafile.get("Session", {}).get("SteamID") or mafile.get("steamid")
    device_id = mafile.get("device_id") or generate_device_id(str(steam_id))

    if not shared_secret or not identity_secret:
        return PasswordChangeResult(
            False, error="Missing shared_secret or identity_secret"
        )

    if not steam_id:
        return PasswordChangeResult(False, error="Missing SteamID in mafile")

    steam_id = int(steam_id)

    # Генерируем новый пароль
    if not new_password:
        excluded = set(excluded_passwords or [])
        for _ in range(10):
            new_password = generate_random_password()
            if new_password not in excluded:
                break
        logger.debug(f"    Generated new_password: {_mask_secret(new_password)}")

    # Пробуем использовать закешированную сессию
    session = SessionCache.get(login)
    session_from_cache = session is not None

    if not session:
        session = SteamSession(login, password, mafile, proxy=proxy)

    try:
        # Step 1: Логин (пропускаем если есть кеш)
        if session_from_cache:
            logger.info("    Step 1: Using cached session (skipping login)")
        else:
            logger.info("    Step 1: Login to Steam...")
            if not session.login_to_steam():
                return PasswordChangeResult(
                    False, error="Login to Steam failed"
                )
            logger.info("    Login successful!")
            # Кешируем сессию
            SessionCache.put(login, session)

        # steam_id из mafile может быть неверным — берём авторитетное значение из сессии
        steam_id = session.steam_id

        s = session._session
        if not s:
            return PasswordChangeResult(False, error="No session")

        session_id = session.get_session_id()

        # Step 2: Переходим в wizard смены пароля
        logger.info("    Step 2: Start password change wizard...")
        r = SteamHTTP.get(
            SteamUrls.HELP_CHANGE_PASSWORD,
            session=s,
            allow_redirects=True,
        )

        # Проверяем что залогинены
        session_expired = (
            login.lower() not in r.text.lower() or "/login" in str(r.url)
        )

        if session_expired and session_from_cache:
            # Кеш протух — логинимся заново и повторяем
            logger.warning(
                "    Cached session expired, retrying with fresh login..."
            )
            SessionCache.invalidate(login)
            session.close()
            session = SteamSession(login, password, mafile, proxy=proxy)
            session_from_cache = False

            if not session.login_to_steam():
                return PasswordChangeResult(
                    False, error="Login to Steam failed (retry)"
                )
            SessionCache.put(login, session)
            steam_id = session.steam_id

            s = session._session
            if not s:
                return PasswordChangeResult(
                    False, error="No session after re-login"
                )
            session_id = session.get_session_id()

            r = SteamHTTP.get(
                SteamUrls.HELP_CHANGE_PASSWORD,
                session=s,
                allow_redirects=True,
            )

            if login.lower() not in r.text.lower():
                return PasswordChangeResult(
                    False,
                    error="Session expired even after fresh login",
                )
        elif session_expired:
            if "/login" in str(r.url):
                logger.error(
                    "!!! Redirected to login - cookies not set properly"
                )
                return PasswordChangeResult(
                    False,
                    error="Session invalid - redirected to login",
                )
            logger.error(
                "!!! Username not found in response - session expired?"
            )
            return PasswordChangeResult(
                False,
                error="Session expired during wizard navigation",
            )

        # Извлекаем recovery params из URL
        parsed = urlparse(str(r.url))
        query_params = parse_qs(parsed.query)

        recovery_params = {
            "s": query_params.get("s", [None])[0],
            "account": query_params.get("account", [None])[0],
            "reset": query_params.get("reset", [None])[0],
            "issueid": query_params.get("issueid", [None])[0],
            "lost": query_params.get("lost", ["0"])[0],
        }

        recovery_s = recovery_params.get("s")
        if not recovery_s:
            logger.error(f"!!! No recovery 's' param in URL: {r.url}")
            return PasswordChangeResult(
                False, error="No recovery session in URL"
            )

        logger.debug(f"    recovery_s: {recovery_s[:20]}...")

        # Step 3: Переходим на страницу ввода кода
        logger.info("    Step 3: Navigate to enter code page...")
        params = {
            "s": recovery_s,
            "account": recovery_params.get("account", ""),
            "reset": recovery_params.get("reset", ""),
            "lost": recovery_params.get("lost", ""),
            "issueid": recovery_params.get("issueid", ""),
            "sessionid": session_id,
            "wizard_ajax": "1",
            "gamepad": "0",
        }
        SteamHTTP.get(SteamUrls.ENTER_CODE, session=s, params=params)

        # Step 4: Отправляем запрос на восстановление (тригерит mobile confirmation)
        logger.info("    Step 4: Send recovery request...")
        data = {
            "sessionid": session_id,
            "wizard_ajax": "1",
            "gamepad": "0",
            "s": recovery_s,
            "method": "8",  # Mobile authenticator
            "link": "",
            "n": "1",
        }
        SteamHTTP.post(SteamUrls.SEND_RECOVERY_CODE, session=s, data=data)

        # Step 5: Принимаем mobile confirmation
        logger.info("    Step 5: Accept mobile confirmation...")
        confirmation_found = _accept_mobile_confirmation(
            session, steam_id, identity_secret, device_id, recovery_s
        )

        if not confirmation_found:
            logger.warning(
                "    No confirmation found, trying to continue anyway..."
            )

        # Step 6: Polling статуса подтверждения
        logger.info("    Step 6: Poll confirmation status...")
        for poll in range(5):
            data_poll = {
                "sessionid": session_id,
                "wizard_ajax": "1",
                "gamepad": "0",
                "s": recovery_s,
                "reset": recovery_params.get("reset", ""),
                "lost": recovery_params.get("lost", ""),
                "method": "8",
                "issueid": recovery_params.get("issueid", ""),
            }
            r = SteamHTTP.post(
                SteamUrls.POLL_CONFIRMATION, session=s, data=data_poll
            )
            poll_data = SteamHTTP.safe_json(r, {})

            if not poll_data.get("errorMsg"):
                logger.debug(f"    Poll OK at attempt {poll + 1}")
                break

            logger.debug(
                f"    Poll {poll + 1}: {poll_data.get('errorMsg', 'waiting')}"
            )
            time.sleep(3)

        # Step 7: Верифицируем recovery code
        logger.info("    Step 7: Verify recovery code...")
        params = {
            "code": "",
            "s": recovery_s,
            "reset": recovery_params.get("reset", ""),
            "lost": recovery_params.get("lost", ""),
            "method": "8",
            "issueid": recovery_params.get("issueid", ""),
            "sessionid": session_id,
            "wizard_ajax": "1",
            "gamepad": "0",
        }
        SteamHTTP.get(SteamUrls.VERIFY_RECOVERY_CODE, session=s, params=params)

        # Step 8: Получаем следующий шаг
        logger.info("    Step 8: Get next step...")
        data_next = {
            "sessionid": session_id,
            "wizard_ajax": "1",
            "s": recovery_s,
            "account": recovery_params.get("account", ""),
            "reset": recovery_params.get("reset", ""),
            "issueid": recovery_params.get("issueid", ""),
            "lost": "2",
        }
        SteamHTTP.post(SteamUrls.GET_NEXT_STEP, session=s, data=data_next)

        # Step 9: Получаем RSA ключ (один запрос — используем для verify и change)
        logger.info("    Step 9: Get RSA key...")
        r = SteamHTTP.post(
            SteamUrls.GET_RSA_KEY,
            session=s,
            data={"sessionid": session_id, "username": login},
        )
        rsa_data = SteamHTTP.safe_json(r, {})

        if not rsa_data.get("publickey_mod"):
            return PasswordChangeResult(
                False, error="Failed to get RSA key"
            )

        mod = int(rsa_data["publickey_mod"], 16)
        exp = int(rsa_data["publickey_exp"], 16)
        rsa_ts = rsa_data["timestamp"]
        key = rsa.PublicKey(mod, exp)

        # Step 10: Верифицируем старый пароль
        logger.info("    Step 10: Verify old password...")
        enc_old = base64.b64encode(
            rsa.encrypt(password.encode(), key)
        ).decode()

        data_verify = {
            "sessionid": session_id,
            "s": recovery_s,
            "lost": "2",
            "reset": "1",
            "password": enc_old,
            "rsatimestamp": rsa_ts,
        }
        r = SteamHTTP.post(
            SteamUrls.VERIFY_PASSWORD, session=s, data=data_verify
        )
        verify_data = SteamHTTP.safe_json(r, {})

        if verify_data.get("errorMsg"):
            return PasswordChangeResult(
                False,
                error=f"Old password verification failed: {verify_data.get('errorMsg')}",
            )

        # Step 11: Проверяем доступность нового пароля
        logger.info("    Step 11: Check new password...")
        data_check = {
            "sessionid": session_id,
            "wizard_ajax": "1",
            "password": new_password,
        }
        r = SteamHTTP.post(
            SteamUrls.CHECK_PASSWORD_AVAILABLE, session=s, data=data_check
        )
        check_data = SteamHTTP.safe_json(r, {})

        if not check_data.get("available"):
            return PasswordChangeResult(
                False,
                error=f"Password not available: {check_data.get('errorMsg', 'unknown')}",
            )

        # Step 12: Устанавливаем новый пароль
        logger.info("    Step 12: Set new password...")

        enc_new = base64.b64encode(
            rsa.encrypt(new_password.encode(), key)
        ).decode()

        data_change = {
            "sessionid": session_id,
            "wizard_ajax": "1",
            "s": recovery_s,
            "account": recovery_params.get("account", ""),
            "password": enc_new,
            "rsatimestamp": rsa_ts,
        }
        r = SteamHTTP.post(
            SteamUrls.CHANGE_PASSWORD, session=s, data=data_change
        )
        result = SteamHTTP.safe_json(r, {})

        if result.get("errorMsg"):
            return PasswordChangeResult(False, error=result.get("errorMsg"))

        # Пароль изменён — инвалидируем кеш (старые credentials больше не валидны)
        SessionCache.invalidate(login)

        logger.info("<<< change_password: SUCCESS")
        return PasswordChangeResult(True, new_password=new_password)

    except Exception as e:
        logger.error(
            f"!!! change_password ERROR: {e}\n{traceback.format_exc()}"
        )
        return PasswordChangeResult(False, error=str(e))
    finally:
        # Если сессия из кеша и мы завершились с ошибкой — не закрываем
        # Если не из кеша — закрываем
        if not session_from_cache:
            session.close()


def _accept_mobile_confirmation(
    session: SteamSession,
    steam_id: int,
    identity_secret: str,
    device_id: str,
    recovery_s: str,
) -> bool:
    """
    Step 5 helper: ищет и принимает mobile confirmation для смены пароля.

    Returns:
        True если подтверждение найдено и принято.
    """
    steam_login_secure = f"{steam_id}||{session._access_token}"

    for attempt in range(5):
        ts = int(time.time())
        conf_key = generate_confirmation_key(identity_secret, "conf", ts)

        cookies = {
            "steamLoginSecure": steam_login_secure,
            "mobileClient": "android",
            "mobileClientVersion": "777777 3.7.2",
            "steamid": str(steam_id),
        }

        params = {
            "p": device_id,
            "a": str(steam_id),
            "k": conf_key,
            "t": str(ts),
            "m": "react",
            "tag": "conf",
        }

        logger.debug(f"    Confirmation attempt {attempt + 1}/5...")
        r = SteamHTTP.get(
            SteamUrls.MOBILECONF_GETLIST,
            params=params,
            cookies=cookies,
            headers={"User-Agent": USER_AGENT},
        )

        data_conf = SteamHTTP.safe_json(r, {})
        if not data_conf.get("success"):
            logger.debug(
                f"    getlist failed: {data_conf.get('message', 'unknown')}"
            )
            time.sleep(3)
            continue

        confirmations = data_conf.get("conf", [])
        logger.debug(f"    Found {len(confirmations)} confirmations")

        for conf in confirmations:
            conf_type = conf.get("type", -1)
            creator_id = str(conf.get("creator_id", ""))

            # Type 6 = Account details, creator_id должен совпадать с recovery_s
            if conf_type == 6 and creator_id == recovery_s:
                logger.info(
                    f"    Found matching confirmation: id={conf.get('id')}"
                )

                accept_ts = int(time.time())
                accept_key = generate_confirmation_key(
                    identity_secret, "allow", accept_ts
                )

                accept_params = {
                    "op": "allow",
                    "p": device_id,
                    "a": str(steam_id),
                    "k": accept_key,
                    "t": str(accept_ts),
                    "m": "react",
                    "tag": "allow",
                    "cid": str(conf.get("id")),
                    "ck": conf.get("nonce"),
                }

                r_accept = SteamHTTP.get(
                    SteamUrls.MOBILECONF_AJAXOP,
                    params=accept_params,
                    cookies=cookies,
                    headers={"User-Agent": USER_AGENT},
                )

                accept_data = SteamHTTP.safe_json(r_accept, {})
                if accept_data.get("success"):
                    logger.info("    Confirmation accepted!")
                    return True
                else:
                    logger.error(f"    Accept failed: {accept_data}")

        time.sleep(3)

    return False


# =============================================================================
# kick_all_sessions
# =============================================================================


def kick_all_sessions(
    login: str,
    password: str,
    mafile: dict[str, Any],
    proxy: "Proxy | None" = None,
) -> KickSessionsResult:
    """
    Кикает все активные сессии Steam аккаунта (web метод через store.steampowered.com).

    Логика: Cache → Login → Kick (как в V1, без restore_from_mafile).
    """
    logger.info(f">>> kick_all_sessions(login={login})")
    if proxy:
        logger.info(f"    Using proxy: {proxy.display_name}")

    # Пробуем использовать закешированную сессию (экономит ~8 запросов)
    session = SessionCache.get(login)
    session_from_cache = session is not None

    if not session:
        session = SteamSession(login, password, mafile, proxy=proxy)

    try:
        # Step 1: Login (пропускаем если есть кеш)
        if session_from_cache:
            logger.debug("    Step 1: Using cached session (skipping login)")
        else:
            logger.debug("    Step 1: Login to Steam...")
            if not session.login_to_steam():
                logger.error("!!! kick_all_sessions: Login failed")
                return KickSessionsResult(False, error="Login failed")
            logger.debug("    Login successful!")
            SessionCache.put(login, session)

        # Step 2: Kick
        result = _try_kick(session)
        if result and result.success:
            return result

        # Если кеш протух — инвалидируем и пробуем с полным логином
        if session_from_cache:
            logger.warning(
                "    Cached session failed, retrying with fresh login..."
            )
            SessionCache.invalidate(login)
            session = SteamSession(login, password, mafile, proxy=proxy)
            if not session.login_to_steam():
                logger.error("!!! kick_all_sessions: Re-login failed")
                return KickSessionsResult(False, error="Login failed")
            SessionCache.put(login, session)
            result = _try_kick(session)
            if result and result.success:
                return result

        error_msg = result.error if result else "Kick failed"
        return KickSessionsResult(False, error=error_msg)

    except Exception as e:
        logger.error(
            f"!!! kick_all_sessions error: {e}\n{traceback.format_exc()}"
        )
        return KickSessionsResult(False, error=str(e))
    finally:
        # Если сессия НЕ из кеша — закрываем (кешированные сессии управляются SessionCache)
        if not session_from_cache and session:
            session.close()


def _try_kick(session: SteamSession) -> KickSessionsResult | None:
    """Пробует выполнить kick используя текущую сессию."""
    s = session._session
    if not s:
        return KickSessionsResult(False, error="No session")

    session_id = session.get_session_id()
    logger.debug(
        f"    sessionid: {session_id[:8]}..."
        if session_id
        else "    sessionid: None"
    )

    if not session_id:
        logger.error("!!! _try_kick: No sessionid in cookies")
        return None

    # Вызываем web endpoint для деавторизации всех устройств
    logger.debug("    Calling /twofactor/manage_action...")

    r = SteamHTTP.post(
        "https://store.steampowered.com/twofactor/manage_action",
        session=s,
        data={
            "action": "deauthorize",
            "sessionid": session_id,
        },
        headers={
            "Referer": "https://store.steampowered.com/twofactor/manage",
            "Origin": "https://store.steampowered.com",
        },
    )

    resp_text = r.text[:500] if r.text else ""
    logger.debug(f"    Response: status={r.status_code}, body={resp_text}")

    if r.status_code == 200:
        resp_data = SteamHTTP.safe_json(r, {})
        success = resp_data.get("success", False)

        if success:
            logger.info("<<< _try_kick: SUCCESS (JSON)")
            return KickSessionsResult(True)

        if not resp_data:
            # Steam возвращает HTML "Steam Guard Mobile Authenticator" при успешном kick
            # Проверяем что это страница управления, а не логин-страница
            text_lower = r.text.lower() if r.text else ""
            if "login" in text_lower and "signin" in text_lower:
                logger.warning(
                    "!!! _try_kick: Got login page - session invalid"
                )
                return KickSessionsResult(
                    False, error="Invalid session (redirected to login)"
                )
            # HTML 200 от /twofactor/manage_action = успех
            logger.info("<<< _try_kick: SUCCESS (HTML 200)")
            return KickSessionsResult(True)

        error = resp_data.get("error", "Unknown error")
        logger.error(f"!!! _try_kick: API returned success=false: {error}")
        return KickSessionsResult(False, error=error)
    else:
        logger.error(f"!!! _try_kick: HTTP {r.status_code}")
        return KickSessionsResult(False, error=f"HTTP {r.status_code}")
