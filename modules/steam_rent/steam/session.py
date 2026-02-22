# -*- coding: utf-8 -*-
"""
Steam session management: login, token handling, session cache.

Classes:
- SteamSession: Full login flow (RSA → BeginAuth → 2FA → Poll → FinalizeLogin)
- SessionCache: Thread-safe TTL cache for active sessions
- SteamUrls: URL constants for Steam help portal and mobileconf API
"""

from __future__ import annotations

import base64
import logging
import secrets
import threading
import time
import traceback
from typing import Any, TYPE_CHECKING

import requests
import rsa

from .guard import generate_device_id, generate_guard_code
from .http import SteamHTTP, USER_AGENT, _mask_secret

if TYPE_CHECKING:
    from ..models import Proxy

logger = logging.getLogger("opium.steam_rent.steam")


# =============================================================================
# SESSION CACHE — Переиспользование сессий для минимизации логинов
# =============================================================================


class SessionCache:
    """
    Thread-safe кеш для Steam сессий.
    Переиспользует активные сессии чтобы избежать множественных логинов.
    Сессии истекают через 10 минут неактивности или при смене пароля.
    """

    _cache: dict[str, tuple["SteamSession", float]] = {}
    _lock = threading.Lock()
    _ttl: float = 600.0  # 10 минут

    @classmethod
    def get(cls, login: str) -> "SteamSession | None":
        """Получить закешированную сессию если ещё валидна."""
        with cls._lock:
            if login not in cls._cache:
                return None

            session, created_at = cls._cache[login]
            if time.time() - created_at > cls._ttl:
                logger.debug(f"[SessionCache] Session expired for {login}")
                session.close()
                del cls._cache[login]
                return None

            if not session._access_token or not session._session:
                logger.debug(f"[SessionCache] Session invalid for {login}")
                del cls._cache[login]
                return None

            logger.debug(f"[SessionCache] Reusing session for {login}")
            return session

    @classmethod
    def put(cls, login: str, session: "SteamSession") -> None:
        """Закешировать сессию."""
        with cls._lock:
            if login in cls._cache:
                old_session, _ = cls._cache[login]
                if old_session != session:
                    old_session.close()

            cls._cache[login] = (session, time.time())
            logger.debug(f"[SessionCache] Cached session for {login}")

    @classmethod
    def invalidate(cls, login: str) -> None:
        """Инвалидировать сессию (например, после смены пароля)."""
        with cls._lock:
            if login in cls._cache:
                session, _ = cls._cache[login]
                session.close()
                del cls._cache[login]
                logger.debug(f"[SessionCache] Invalidated session for {login}")

    @classmethod
    def clear_all(cls) -> None:
        """Очистить все закешированные сессии."""
        with cls._lock:
            for login, (session, _) in cls._cache.items():
                session.close()
            cls._cache.clear()
            logger.debug("[SessionCache] Cleared all sessions")


# =============================================================================
# STEAM SESSION
# =============================================================================


class SteamSession:
    """Сессия Steam для выполнения операций."""

    def __init__(
        self,
        login: str,
        password: str,
        mafile: dict[str, Any],
        proxy: "Proxy | None" = None,
    ) -> None:
        logger.debug(
            f">>> SteamSession.__init__(login={login}, pwd={_mask_secret(password)})"
        )
        logger.debug(f"    mafile keys: {list(mafile.keys())}")
        self.login = login
        self.password = password
        self.mafile = mafile
        self.steam_id = self._get_steam_id()
        self.device_id = mafile.get("device_id") or generate_device_id(
            str(self.steam_id)
        )
        self._session: requests.Session | None = None
        self._access_token: str | None = None
        self._proxy = proxy
        self._proxy_dict: dict[str, str] | None = None

        if proxy:
            self._proxy_dict = proxy.to_requests_format()
            logger.info(f"    Using proxy: {proxy.display_name}")
        else:
            logger.debug("    No proxy configured (direct connection)")

        logger.debug(f"    steam_id={self.steam_id}, device_id={self.device_id}")
        logger.debug(
            f"    shared_secret present: {bool(mafile.get('shared_secret'))}"
        )
        logger.debug(
            f"    identity_secret present: {bool(mafile.get('identity_secret'))}"
        )

    @property
    def session(self) -> requests.Session | None:
        """Возвращает HTTP сессию."""
        return self._session

    @property
    def proxy(self) -> "Proxy | None":
        """Возвращает прокси."""
        return self._proxy

    def _get_steam_id(self) -> int:
        """Извлекает SteamID из mafile."""
        if s := self.mafile.get("Session", {}).get("SteamID"):
            return int(s)
        if s := self.mafile.get("steamid"):
            return int(s)
        return 0

    @property
    def shared_secret(self) -> str:
        return self.mafile.get("shared_secret", "")

    @property
    def identity_secret(self) -> str:
        return self.mafile.get("identity_secret", "")

    def _create_session(self) -> requests.Session:
        """Создаёт HTTP сессию с прокси если настроен."""
        logger.debug("    Creating requests session...")
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        s.trust_env = False

        # Устанавливаем прокси если настроен
        if self._proxy_dict:
            s.proxies = self._proxy_dict
            logger.debug(
                f"    Session proxies set: "
                f"{self._proxy.display_name if self._proxy else 'unknown'}"
            )

        return s

    def _encrypt_password(self, password: str) -> tuple[str, str]:
        """RSA шифрование пароля."""
        logger.debug(">>> _encrypt_password()")

        logger.debug(f"    Getting RSA key for account: {self.login}")
        r = SteamHTTP.get(
            "https://api.steampowered.com/IAuthenticationService/GetPasswordRSAPublicKey/v1/",
            params={"account_name": self.login},
            session=self._session,  # Используем сессию с прокси
        )
        resp = SteamHTTP.safe_json(r, {}).get("response", {})
        logger.debug(f"    RSA response keys: {list(resp.keys())}")

        mod = int(resp.get("publickey_mod", "0"), 16)
        exp = int(resp.get("publickey_exp", "0"), 16)
        ts = resp.get("timestamp", "")
        logger.debug(f"    RSA timestamp: {ts}")

        key = rsa.PublicKey(mod, exp)
        encrypted = rsa.encrypt(password.encode(), key)
        result = base64.b64encode(encrypted).decode()
        logger.debug(f"<<< _encrypt_password: encrypted_len={len(result)}")
        return result, ts

    def login_to_steam(self) -> bool:
        """Полный процесс логина с 2FA."""
        logger.debug(f">>> login_to_steam() for {self.login}")
        self._session = self._create_session()

        try:
            enc_pwd, ts = self._encrypt_password(self.password)
        except Exception as e:
            logger.error(f"!!! RSA encrypt failed: {e}\n{traceback.format_exc()}")
            return False

        # Begin auth (с retry при interval/rate-limit)
        logger.debug("    Beginning auth session...")

        client_id = None
        request_id = None
        steamid = None
        data: dict[str, Any] = {}

        for auth_attempt in range(5):
            r = SteamHTTP.post(
                "https://api.steampowered.com/IAuthenticationService/BeginAuthSessionViaCredentials/v1/",
                session=self._session,
                data={
                    "account_name": self.login,
                    "encrypted_password": enc_pwd,
                    "encryption_timestamp": ts,
                    "remember_login": "true",
                    "platform_type": "2",
                    "persistence": "1",
                    "website_id": "Community",
                },
            )

            if r.status_code != 200:
                logger.error(
                    f"!!! BeginAuth failed: {r.status_code} - {r.text[:500]}"
                )
                return False

            data = SteamHTTP.safe_json(r, {}).get("response", {})
            logger.debug(f"    BeginAuth response keys: {list(data.keys())}")
            client_id = data.get("client_id")
            request_id = data.get("request_id")
            steamid = data.get("steamid")
            logger.debug(f"    client_id={client_id}, steamid={steamid}")

            if client_id:
                logger.info(
                    f"    BeginAuth OK: client_id={client_id}, steamid={steamid}"
                )
                # Steam — авторитетный источник steam_id, mafile может содержать неверный
                if steamid and int(steamid) != self.steam_id:
                    logger.warning(
                        f"    steam_id mismatch: mafile={self.steam_id}, "
                        f"auth={steamid} — using auth value"
                    )
                    self.steam_id = int(steamid)
                break

            # Steam rate limit — interval means "wait and retry"
            interval = data.get("interval", 0)
            if interval and auth_attempt < 4:
                logger.warning(
                    f"    BeginAuth: no client_id, interval={interval}s - "
                    f"retrying in {interval}s (attempt {auth_attempt + 1}/5)"
                )
                time.sleep(interval)
                # Re-encrypt password (timestamp may expire)
                try:
                    enc_pwd, ts = self._encrypt_password(self.password)
                except Exception as e:
                    logger.error(f"!!! RSA re-encrypt failed: {e}")
                    return False
                continue
            else:
                logger.error(f"!!! No client_id in response: {data}")
                return False

        # 2FA if needed
        allowed_confirmations = data.get("allowed_confirmations", [])
        logger.debug(f"    allowed_confirmations: {allowed_confirmations}")
        needs_2fa = any(
            c.get("confirmation_type") == 3 for c in allowed_confirmations
        )
        logger.debug(f"    needs_2fa: {needs_2fa}")

        if needs_2fa:
            code = generate_guard_code(self.shared_secret)
            logger.info("    Submitting 2FA code (generated)")
            r2fa = SteamHTTP.post(
                "https://api.steampowered.com/IAuthenticationService/UpdateAuthSessionWithSteamGuardCode/v1/",
                session=self._session,
                data={
                    "client_id": client_id,
                    "steamid": steamid,
                    "code": code,
                    "code_type": "3",
                },
            )
            if r2fa.status_code != 200:
                logger.error(
                    f"!!! 2FA submission failed: HTTP {r2fa.status_code} - "
                    f"{r2fa.text[:300]}"
                )
                return False
            r2fa_data = SteamHTTP.safe_json(r2fa, {})
            logger.info(f"    2FA response: {r2fa_data}")
        else:
            logger.info("    No 2FA required")

        # Poll for tokens
        logger.info("    Polling for tokens...")
        for attempt in range(15):
            time.sleep(3)
            r = SteamHTTP.post(
                "https://api.steampowered.com/IAuthenticationService/PollAuthSessionStatus/v1/",
                session=self._session,
                data={"client_id": client_id, "request_id": request_id},
                max_retries=1,
            )
            if r.status_code == 200:
                d = SteamHTTP.safe_json(r, {}).get("response", {})
                if token := d.get("access_token"):
                    logger.info(f"    Got access_token on attempt {attempt + 1}")
                    self._access_token = token
                    self._finalize_login(d.get("refresh_token", ""))
                    logger.info("<<< login_to_steam: SUCCESS")
                    return True
                # Log what we DID get so we can diagnose
                if attempt % 3 == 0:
                    logger.info(
                        f"    Poll attempt {attempt + 1}/15: keys={list(d.keys())}"
                    )
            else:
                logger.warning(
                    f"    Poll attempt {attempt + 1}/15: HTTP {r.status_code}"
                )

        logger.error("!!! login_to_steam: Failed after 15 poll attempts")
        return False

    def _finalize_login(self, refresh_token: str) -> None:
        """Финализирует логин и устанавливает cookies."""
        logger.debug(
            f">>> _finalize_login(refresh_token={_mask_secret(refresh_token)})"
        )
        if not self._session:
            logger.error("!!! _finalize_login: no session")
            return

        # Finalize
        logger.debug("    Finalizing login...")
        r = SteamHTTP.post(
            "https://login.steampowered.com/jwt/finalizelogin",
            session=self._session,
            data={
                "nonce": refresh_token,
                "sessionid": "0",
                "redir": "https://steamcommunity.com/login/home/?goto=",
            },
        )

        # CRITICAL: Обрабатываем transfer_info — Steam устанавливает токены для каждого домена
        # Эти токены ОБЯЗАТЕЛЬНЫ для работы mobileconf API и help.steampowered.com
        try:
            finalize_result = SteamHTTP.safe_json(r, {})
            transfer_info = finalize_result.get("transfer_info", [])
            logger.debug(f"    transfer_info count: {len(transfer_info)}")

            # Выполняем ВСЕ transfer запросы — Steam устанавливает токены для каждого домена
            for i, transfer in enumerate(transfer_info):
                url = transfer.get("url")
                params = transfer.get("params", {})
                if url and params:
                    tr = SteamHTTP.post(
                        url, session=self._session, data=params, skip_rate_limit=True
                    )
                    logger.debug(
                        f"    transfer {i}: {url[:50]}... status={tr.status_code}"
                    )
        except Exception as e:
            logger.warning(f"    transfer_info error: {e}")

        # Устанавливаем cookies для ВСЕХ доменов
        login_secure = f"{self.steam_id}||{self._access_token}"
        logger.debug(f"    Setting cookies for steam_id={self.steam_id}")

        # Генерируем sessionid если нет
        session_id = None
        for c in self._session.cookies:
            if c.name == "sessionid" and "steampowered" in c.domain:
                session_id = c.value
                break
        if not session_id:
            session_id = secrets.token_hex(12)

        # ВАЖНО: cookies для всех 4 доменов включая help.steampowered.com и store.steampowered.com
        for domain in [
            ".steampowered.com",
            ".steamcommunity.com",
            "help.steampowered.com",
            "store.steampowered.com",
        ]:
            self._session.cookies.set(
                "steamLoginSecure", login_secure, domain=domain
            )
            self._session.cookies.set("sessionid", session_id, domain=domain)

        logger.debug("<<< _finalize_login: done")

    def get_session_id(self) -> str:
        """Возвращает session ID из cookies."""
        if self._session:
            for c in self._session.cookies:
                if c.name == "sessionid" and "steampowered" in c.domain:
                    return c.value
        return secrets.token_hex(12)

    def close(self) -> None:
        """Закрывает сессию."""
        logger.debug("    SteamSession.close()")
        if self._session:
            self._session.close()
            self._session = None

    def restore_from_mafile(self) -> bool:
        """
        Восстанавливает сессию из токенов в mafile (без логина через Steam API).
        Используется для операций которые не требуют полной авторизации.
        """
        session_data = self.mafile.get("Session", {})
        access_token = session_data.get("AccessToken", "")
        steam_login_secure = session_data.get("SteamLoginSecure", "")
        session_id = session_data.get("SessionID", "")

        if not steam_login_secure:
            logger.debug(
                "    restore_from_mafile: no SteamLoginSecure in mafile"
            )
            return False

        logger.debug(
            "    restore_from_mafile: restoring session from mafile tokens"
        )
        self._session = self._create_session()
        self._access_token = access_token

        if not session_id:
            session_id = secrets.token_hex(12)

        for domain in [
            ".steampowered.com",
            ".steamcommunity.com",
            "help.steampowered.com",
            "store.steampowered.com",
        ]:
            self._session.cookies.set(
                "steamLoginSecure", steam_login_secure, domain=domain
            )
            self._session.cookies.set("sessionid", session_id, domain=domain)

        logger.debug(
            f"    restore_from_mafile: session restored, sessionid={session_id[:8]}..."
        )
        return True


# =============================================================================
# URL CONSTANTS
# =============================================================================


class SteamUrls:
    """URL constants for Steam help portal and mobileconf API."""

    HELP_CHANGE_PASSWORD = (
        "https://help.steampowered.com/wizard/HelpChangePassword"
        "?redir=store/account/"
    )
    ENTER_CODE = (
        "https://help.steampowered.com/en/wizard/HelpWithLoginInfoEnterCode"
    )
    SEND_RECOVERY_CODE = (
        "https://help.steampowered.com/en/wizard/AjaxSendAccountRecoveryCode"
    )
    POLL_CONFIRMATION = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxPollAccountRecoveryConfirmation"
    )
    VERIFY_RECOVERY_CODE = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxVerifyAccountRecoveryCode"
    )
    GET_NEXT_STEP = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxAccountRecoveryGetNextStep"
    )
    VERIFY_PASSWORD = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxAccountRecoveryVerifyPassword/"
    )
    CHANGE_PASSWORD = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxAccountRecoveryChangePassword/"
    )
    GET_RSA_KEY = "https://help.steampowered.com/en/login/getrsakey/"
    CHECK_PASSWORD_AVAILABLE = (
        "https://help.steampowered.com/en/wizard/"
        "AjaxCheckPasswordAvailable/"
    )
    MOBILECONF_GETLIST = "https://steamcommunity.com/mobileconf/getlist"
    MOBILECONF_AJAXOP = "https://steamcommunity.com/mobileconf/ajaxop"
