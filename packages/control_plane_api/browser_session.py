from __future__ import annotations

from collections.abc import Callable
import secrets
import time
from urllib.parse import urlencode


SCHEMA_VERSION = "1"
BROWSER_SESSION_COOKIE = "marvex_control_plane_session"


class BrowserSessionManager:
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        token_factory: Callable[[], str] | None = None,
        claim_ttl_seconds: int = 30,
        session_ttl_seconds: int = 3600,
    ) -> None:
        self._clock = clock or time.time
        self._token_factory = token_factory or (lambda: secrets.token_urlsafe(32))
        self._claim_ttl_seconds = claim_ttl_seconds
        self._session_ttl_seconds = session_ttl_seconds
        self._claims: dict[str, float] = {}
        self._sessions: dict[str, float] = {}

    def create_lease(self) -> dict[str, object]:
        claim = self._token_factory()
        self._claims[claim] = self._clock() + self._claim_ttl_seconds
        return {
            "schema_version": SCHEMA_VERSION,
            "claim_url": f"/control/browser-session/claim?{urlencode({'claim': claim})}",
            "expires_in_seconds": self._claim_ttl_seconds,
            "token_value_logged": False,
        }

    def claim(self, claim: str | None) -> str | None:
        if not claim:
            return None
        expires_at = self._claims.pop(claim, None)
        if expires_at is None or expires_at < self._clock():
            return None
        session = self._token_factory()
        self._sessions[session] = self._clock() + self._session_ttl_seconds
        return session

    def validate_cookie_header(self, cookie_header: str | None) -> bool:
        if not cookie_header:
            return False
        session = _cookie_value(cookie_header, BROWSER_SESSION_COOKIE)
        if not session:
            return False
        expires_at = self._sessions.get(session)
        if expires_at is None or expires_at < self._clock():
            self._sessions.pop(session, None)
            return False
        return True

    def cookie_header(self, session: str) -> str:
        return (
            f"{BROWSER_SESSION_COOKIE}={session}; "
            f"Max-Age={self._session_ttl_seconds}; Path=/control; "
            "HttpOnly; SameSite=Strict"
        )


def _cookie_value(cookie_header: str, name: str) -> str | None:
    for part in cookie_header.split(";"):
        key, separator, value = part.strip().partition("=")
        if separator and key == name and value:
            return value
    return None
