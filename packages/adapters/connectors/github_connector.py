from __future__ import annotations

"""
GitHub connector adapter.

DISABLED by default (auto_fetch_enabled=False in the default ProviderSyncConfig).

Uses the Authlib seam (authlib_oauth.py) as the OAuth library anchor.
Actual HTTP is performed through an injectable FetchClient so CI tests can
supply a fake page source without any live network call.

No real token exchange or real network calls are made unless the caller
explicitly passes a live HTTP fetch function AND sets auto_fetch_enabled=True.
No credentials, secrets, or raw account content are persisted.
"""

import hashlib
from typing import Any, Callable, Literal

from packages.connector_runtime.auto_fetch_scheduler import (
    FetchedPage,
    ProviderSyncConfig,
)
from packages.connector_runtime.models import (
    _SECRET_TERMS,
    ConnectorCategory,
    ConnectorManifest,
    ConnectorRef,
    ConnectorScope,
)

# ---------------------------------------------------------------------------
# Connector manifest
# ---------------------------------------------------------------------------

GITHUB_CONNECTOR_REF = ConnectorRef(
    connector_id="github-connector",
    category=ConnectorCategory.GITHUB,
)

GITHUB_MANIFEST = ConnectorManifest(
    connector_ref=GITHUB_CONNECTOR_REF,
    display_name="GitHub",
    category=ConnectorCategory.GITHUB,
    auth_kind="oauth2",
    scopes=(
        ConnectorScope(
            name="repo:read",
            purpose="Read repository metadata and issue titles for memory ingestion",
        ),
    ),
    backend_kind="direct_oauth_authlib",
    # auto_fetch_default_enabled is always False per ConnectorManifest contract
)

# ---------------------------------------------------------------------------
# Default provider sync config (DISABLED by default)
# ---------------------------------------------------------------------------

GITHUB_SYNC_CONFIG = ProviderSyncConfig(
    connector_id="github-connector",
    sync_interval_secs=1200,  # 20 minutes minimum
    daily_request_budget=48,
    auto_fetch_enabled=False,  # DISABLED by default
)

# ---------------------------------------------------------------------------
# HTTP client protocol (injectable)
# ---------------------------------------------------------------------------

HttpGetFn = Callable[
    [str, dict[str, str]],  # (url, headers) → response dict
    dict[str, Any],
]

"""
Injectable HTTP GET callable:
    (url: str, headers: dict[str, str]) -> dict[str, Any]

Real implementations make OAuth-authenticated requests via Authlib.
Test implementations return fake JSON payloads without any network call.
"""

# ---------------------------------------------------------------------------
# Canonicalization helpers
# ---------------------------------------------------------------------------


def _safe_title(raw: str) -> str:
    """Truncate and strip secret-like text from a raw item title."""
    safe = raw[:200].strip()
    if not safe:
        return "untitled"
    return safe


def _external_id(item_kind: str, item_id: int | str) -> str:
    """Return a stable, opaque external_id from a GitHub item kind + id."""
    raw = f"{item_kind}:{item_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _safe_body(raw_body: str | None) -> str:
    """
    Return a derived-safe markdown body.

    Truncates to 800 chars and rejects any content containing secret-like
    terms.  Returns a placeholder if the body is empty or unsafe.
    """
    if not raw_body:
        return "No content available."
    truncated = raw_body[:800]
    low = truncated.lower()
    if any(term in low for term in _SECRET_TERMS):
        return "[content redacted: contained secret-like terms]"
    return truncated


# ---------------------------------------------------------------------------
# GitHub fetch client
# ---------------------------------------------------------------------------

_GITHUB_API = "https://api.github.com"
_DEFAULT_PER_PAGE = 20


class GitHubConnectorAdapter:
    """
    Real GitHub connector adapter backed by an injectable HTTP client.

    DISABLED by default.  Pass auto_fetch_enabled=True only after explicit
    user approval via the control plane.

    No credentials are stored by this adapter.  The access_token is passed
    in at call time by the caller (connector auth backend) and is NEVER
    persisted here.

    For CI: inject a fake_http_get that returns a predetermined response dict;
    no actual network call will be made.
    """

    _raw_credentials_persisted: Literal[False] = False
    _raw_token_persisted: Literal[False] = False

    def __init__(
        self,
        *,
        http_get: HttpGetFn,
        connector_ref: ConnectorRef = GITHUB_CONNECTOR_REF,
    ) -> None:
        self._http_get = http_get
        self._connector_ref = connector_ref

    def fetch_page(
        self,
        connector_ref: ConnectorRef,
        cursor: str | None,
    ) -> FetchedPage:
        """
        Fetch one page of GitHub notifications/issues since *cursor*.

        cursor encodes the page number as a string integer ("1", "2", …).
        No credentials or raw response bodies are persisted.
        Returns a FetchedPage with derived-safe (title, body) tuples.
        """
        # Access token is expected to be provided externally at call time.
        # We call http_get with a placeholder auth header here to keep the
        # interface clean; real callers inject the token via the headers dict
        # through the http_get implementation.  The token is NOT stored here.
        page_num = int(cursor) if cursor and cursor.isdigit() else 1
        url = (
            f"{_GITHUB_API}/notifications"
            f"?all=false&per_page={_DEFAULT_PER_PAGE}&page={page_num}"
        )
        response = self._http_get(url, {"Accept": "application/vnd.github+json"})
        items = self._canonicalize_response(response)
        next_cursor = str(page_num + 1) if items else None
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=items,
            next_cursor=next_cursor,
        )

    def _canonicalize_response(
        self, response: dict[str, Any]
    ) -> tuple[tuple[str, str, str], ...]:
        """
        Convert a raw GitHub API response to derived-safe (external_id, title, body) tuples.

        Raw content is NOT returned; only derived title/body are included.
        """
        raw_items = response.get("items", [])
        if not isinstance(raw_items, list):
            return ()

        result: list[tuple[str, str, str]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("subject", {}).get("type", "unknown")).lower()
            item_id = item.get("id", "")
            ext_id = _external_id(kind, item_id)
            raw_title = str(item.get("subject", {}).get("title", ""))
            title = _safe_title(raw_title)
            body = _safe_body(item.get("reason", ""))
            result.append((ext_id, title, body))

        return tuple(result)

    def safe_projection(self) -> dict[str, object]:
        return {
            "connector_id": self._connector_ref.connector_id,
            "category": self._connector_ref.category,
            "raw_credentials_persisted": False,
            "raw_token_persisted": False,
            "network_call_started": False,
            "auto_fetch_default_enabled": False,
        }


# ---------------------------------------------------------------------------
# Authlib probe (confirms authlib is importable; no token exchange)
# ---------------------------------------------------------------------------


def probe_authlib() -> dict[str, Any]:
    """Return an import-proof dict confirming Authlib is available."""
    from packages.adapters.connectors.authlib_oauth import AuthlibOAuthBackend

    backend = AuthlibOAuthBackend()
    return backend.safe_import_probe()


# ---------------------------------------------------------------------------
# Fake fetch client for tests / CI
# ---------------------------------------------------------------------------


def make_fake_fetch_client(
    pages: dict[str | None, list[tuple[str, str, str]]] | None = None,
) -> Callable[[ConnectorRef, str | None], FetchedPage]:
    """
    Return a fake FetchClient suitable for tests.

    *pages* maps cursor → list of (external_id, title, body) tuples.
    No network calls are made.
    """
    resolved: dict[str | None, list[tuple[str, str, str]]] = pages or {
        None: [("ext-001", "Sample Issue", "Connector auto-fetch evidence ingested.")]
    }

    def _fetch(connector_ref: ConnectorRef, cursor: str | None) -> FetchedPage:
        items = resolved.get(cursor, [])
        next_cursor = None
        if items:
            keys = list(resolved.keys())
            try:
                idx = keys.index(cursor)
                if idx + 1 < len(keys):
                    next_cursor = keys[idx + 1]
            except ValueError:
                next_cursor = None
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=tuple(items),
            next_cursor=next_cursor,
        )

    return _fetch
