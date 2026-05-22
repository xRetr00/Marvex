from __future__ import annotations

"""
Public RSS/Atom connector adapter.

DISABLED by default (auto_fetch_enabled=False in the default ProviderSyncConfig).

This adapter is intentionally free/open and does not require credentials or API
keys. HTTP/text retrieval is fully injectable so CI and tests can run offline
with fake feed payloads and zero network calls.
"""

import hashlib
import html
import re
import xml.etree.ElementTree as ET
from typing import Callable, Literal

from packages.connector_runtime.auto_fetch_scheduler import FetchedPage, ProviderSyncConfig
from packages.connector_runtime.models import (
    _SECRET_TERMS,
    ConnectorCategory,
    ConnectorManifest,
    ConnectorRef,
    ConnectorScope,
)

PUBLIC_RSS_CONNECTOR_REF = ConnectorRef(
    connector_id="public-rss-connector",
    category=ConnectorCategory.GENERIC_OAUTH,
)

PUBLIC_RSS_MANIFEST = ConnectorManifest(
    connector_ref=PUBLIC_RSS_CONNECTOR_REF,
    display_name="Public RSS/Atom",
    category=ConnectorCategory.GENERIC_OAUTH,
    auth_kind="api_key_placeholder",
    scopes=(
        ConnectorScope(
            name="feed:read",
            purpose="Read publicly accessible RSS/Atom feed entries for safe ingestion",
        ),
    ),
    backend_kind="rss_public_feed",
)

PUBLIC_RSS_SYNC_CONFIG = ProviderSyncConfig(
    connector_id="public-rss-connector",
    sync_interval_secs=1200,
    daily_request_budget=48,
    auto_fetch_enabled=False,
)

FetchTextFn = Callable[[str, dict[str, str]], str]

_WS_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")
_MAX_TITLE = 200
_MAX_BODY = 800


def _normalize_text(raw: str, *, limit: int) -> str:
    text = html.unescape(_TAG_RE.sub(" ", raw or ""))
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""
    return text[:limit]


def _safe_title(raw: str) -> str:
    title = _normalize_text(raw, limit=_MAX_TITLE)
    if not title:
        return "untitled"
    low = title.lower()
    if any(term in low for term in _SECRET_TERMS):
        return "untitled"
    return title


def _safe_body(raw: str) -> str:
    body = _normalize_text(raw, limit=_MAX_BODY)
    if not body:
        return "No content available."
    low = body.lower()
    if any(term in low for term in _SECRET_TERMS):
        return "[content redacted: contained secret-like terms]"
    return body


def _external_id(seed: str) -> str:
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]


def _child_text(elem: ET.Element, local_name: str) -> str:
    for child in list(elem):
        if child.tag.rsplit("}", 1)[-1] == local_name:
            return (child.text or "").strip()
    return ""


def _rss_items(root: ET.Element) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    for item in root.findall(".//item"):
        guid = _child_text(item, "guid")
        link = _child_text(item, "link")
        title = _safe_title(_child_text(item, "title"))
        description = _child_text(item, "description")
        body_source = description
        if link:
            body_source = f"{description}\nSource: {link}".strip()
        body = _safe_body(body_source)
        seed = guid or link or f"{title}:{body[:64]}"
        items.append((_external_id(seed), title, body))
    return items


def _atom_items(root: ET.Element) -> list[tuple[str, str, str]]:
    items: list[tuple[str, str, str]] = []
    for entry in root.findall(".//{*}entry"):
        entry_id = _child_text(entry, "id")
        title = _safe_title(_child_text(entry, "title"))
        summary = _child_text(entry, "summary") or _child_text(entry, "content")
        link = ""
        for child in list(entry):
            if child.tag.rsplit("}", 1)[-1] == "link":
                link = (child.attrib.get("href") or "").strip()
                if link:
                    break
        body_source = summary
        if link:
            body_source = f"{summary}\nSource: {link}".strip()
        body = _safe_body(body_source)
        seed = entry_id or link or f"{title}:{body[:64]}"
        items.append((_external_id(seed), title, body))
    return items


class PublicRssConnectorAdapter:
    """
    RSS/Atom connector adapter backed by an injectable text fetch function.

    No credentials or tokens are accepted or persisted. The caller supplies a
    feed URL and a fetch function, which can be a fake in CI.
    """

    _raw_credentials_persisted: Literal[False] = False
    _raw_token_persisted: Literal[False] = False

    def __init__(
        self,
        *,
        feed_url: str,
        fetch_text: FetchTextFn,
        connector_ref: ConnectorRef = PUBLIC_RSS_CONNECTOR_REF,
    ) -> None:
        self._feed_url = feed_url
        self._fetch_text = fetch_text
        self._connector_ref = connector_ref

    def fetch_page(self, connector_ref: ConnectorRef, cursor: str | None) -> FetchedPage:
        del cursor  # RSS/Atom does not require server-side pagination in this adapter.
        payload = self._fetch_text(
            self._feed_url,
            {"Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"},
        )
        root = ET.fromstring(payload)
        local_root = root.tag.rsplit("}", 1)[-1].lower()
        if local_root == "rss":
            items = tuple(_rss_items(root))
        elif local_root == "feed":
            items = tuple(_atom_items(root))
        else:
            items = ()
        return FetchedPage(
            connector_ref=connector_ref,
            connection_id=connector_ref.connector_id,
            items=items,
            next_cursor=None,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "connector_id": self._connector_ref.connector_id,
            "category": self._connector_ref.category,
            "raw_credentials_persisted": False,
            "raw_token_persisted": False,
            "network_call_started": False,
            "auto_fetch_default_enabled": False,
        }
