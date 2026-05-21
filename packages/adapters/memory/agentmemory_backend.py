"""AgentMemory external-daemon backend.

This module is the REST client that speaks to an agentmemory daemon.
It is OPTIONAL and DISABLED by default — the default backend remains the
local in-process / SQLite store provided by ``packages.memory_runtime``.

Design rules (enforced by scripts/check_agentmemory_backend_boundaries.py):
- stdlib ``urllib`` only — no requests / httpx dependency added.
- No credentials or raw account content persisted (bearer token lives only
  in-memory for the process lifetime).
- Loopback HTTP is allowed; a warning is emitted for plaintext non-loopback.
- The Memory Tree pipeline (``packages.memory_tree_runtime``) is not
  referenced here and must not be coupled to this backend.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import warnings
from datetime import datetime, timezone
from typing import Any

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime.models import (
    MemoryForgetResult,
    MemoryReadResult,
    MemoryRecord,
    MemoryRef,
)
from packages.memory_runtime.store import SCHEMA_VERSION

from .config import AgentMemoryBackendConfig


_LOG = logging.getLogger(__name__)

# Same character set used by memory_runtime.models._REF_ID_SAFE_CHARS —
# kept local to avoid a cross-package import of a private symbol.
_REF_ID_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_"
)

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _is_loopback_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname in _LOOPBACK_HOSTS


def _check_plaintext_warning(url: str, *, warn: bool) -> None:
    if url.startswith("http://") and not _is_loopback_url(url) and warn:
        warnings.warn(
            f"agentmemory daemon URL uses plaintext HTTP on a non-loopback "
            f"address: {url!r}.  Use HTTPS for non-local deployments.",
            stacklevel=3,
        )


def _kind_to_category(memory_kind: str) -> str:
    if memory_kind in ("fact", "preference", "instruction"):
        return "fact"
    return "conversation"


def _category_to_kind(category: str | None) -> str:
    if category == "conversation":
        return "summary"
    return "fact"


def _record_to_wire(record: MemoryRecord, *, namespace: str) -> dict[str, Any]:
    session_ids: list[str] = (
        [record.session_ref.ref_id] if record.session_ref is not None else []
    )
    return {
        "title": record.memory_ref.ref_id,
        "content": record.content,
        "project": namespace,
        "type": _kind_to_category(record.memory_kind),
        "sessionIds": session_ids,
    }


def _wire_to_record(
    item: dict[str, Any],
    *,
    namespace: str,
    schema_version: str = SCHEMA_VERSION,
) -> MemoryRecord | None:
    """Convert an agentmemory wire item to a MemoryRecord (best-effort).

    Returns None if the item cannot be mapped safely.
    """
    title = item.get("title", "")
    content = item.get("content", "")
    if not title or not content:
        return None

    if any(c not in _REF_ID_SAFE_CHARS for c in title):
        _LOG.debug("agentmemory: skipping item with unsafe title chars: %r", title)
        return None

    updated_at_str: str | None = item.get("updatedAt")
    try:
        created_at = (
            datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            if updated_at_str
            else datetime.now(tz=timezone.utc)
        )
    except ValueError:
        created_at = datetime.now(tz=timezone.utc)

    session_ids: list[str] = item.get("sessionIds") or []
    session_ref: SessionRef | None = None
    if session_ids:
        raw_sid = session_ids[0]
        if raw_sid and all(c in _REF_ID_SAFE_CHARS for c in raw_sid):
            session_ref = SessionRef(ref_type="session", ref_id=raw_sid)

    memory_kind_str = _category_to_kind(item.get("type"))

    scope: str
    conversation_ref: ConversationRef | None
    if session_ref is not None:
        scope = "session"
        conversation_ref = None
    else:
        scope = "conversation"
        conv_id = f"{namespace}-{title}"
        if any(c not in _REF_ID_SAFE_CHARS for c in conv_id):
            _LOG.debug("agentmemory: cannot build safe conversation_ref for %r", title)
            return None
        conversation_ref = ConversationRef(ref_type="conversation", ref_id=conv_id)

    try:
        return MemoryRecord(
            schema_version=schema_version,
            memory_ref=MemoryRef(ref_type="memory", ref_id=title),
            scope=scope,  # type: ignore[arg-type]
            memory_kind=memory_kind_str,  # type: ignore[arg-type]
            session_ref=session_ref,
            conversation_ref=conversation_ref,
            trace_id="agentmemory-import",
            turn_id="agentmemory-import",
            content=content,
            write_authorization="policy_approved",
            created_at=created_at,
            tags=(),
            raw_transcript_persisted=False,
        )
    except Exception as exc:  # noqa: BLE001
        _LOG.debug("agentmemory: could not reconstruct MemoryRecord for %r: %s", title, exc)
        return None


class AgentMemoryRequestError(Exception):
    """Raised when the agentmemory daemon returns an unexpected response."""


def _http_request(
    url: str,
    *,
    method: str,
    body: dict[str, Any] | None = None,
    bearer_token: str | None = None,
    timeout: float = 5.0,
) -> dict[str, Any] | list[Any]:
    """Perform a stdlib urllib HTTP request and return parsed JSON.

    Raises ``AgentMemoryRequestError`` on HTTP errors or unexpected payloads.
    """
    payload_bytes = (
        json.dumps(body, separators=(",", ":")).encode() if body is not None else None
    )
    req = urllib.request.Request(url, data=payload_bytes, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    if bearer_token:
        req.add_header("Authorization", f"Bearer {bearer_token}")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise AgentMemoryRequestError(
            f"agentmemory daemon returned HTTP {exc.code} for {method} {url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AgentMemoryRequestError(
            f"agentmemory daemon unreachable at {url}: {exc.reason}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise AgentMemoryRequestError(
            f"agentmemory daemon returned non-JSON response for {method} {url}"
        ) from exc


def _items_to_records(
    items: list[Any], *, namespace: str
) -> tuple[MemoryRecord, ...]:
    return tuple(
        record
        for item in items
        if isinstance(item, dict)
        if (record := _wire_to_record(item, namespace=namespace)) is not None
    )


class AgentMemoryBackend:
    """Thin REST client that delegates memory storage to an agentmemory daemon.

    This is an OPTIONAL external backend.  The default local backend is
    *not* replaced; callers must explicitly construct this class with an
    ``AgentMemoryBackendConfig`` that has ``backend="agentmemory"``.

    HTTP is done via stdlib ``urllib`` — no new package dependency.
    """

    def __init__(self, config: AgentMemoryBackendConfig) -> None:
        self._cfg = config
        _check_plaintext_warning(
            config.daemon_url,
            warn=config.warn_non_loopback_plaintext,
        )

    def store(self, record: MemoryRecord) -> None:
        """Store a MemoryRecord in the agentmemory daemon.

        Only a safe bounded projection is sent — raw content is never
        persisted as credentials or account-level secrets (the
        MemoryRecord validator already rejects such content).
        """
        self._post("/agentmemory/remember", _record_to_wire(record, namespace=self._cfg.namespace))

    def recall(self, query: str, *, max_results: int = 10) -> MemoryReadResult:
        """Hybrid-search the daemon and return mapped MemoryRecords."""
        raw = self._post(
            "/agentmemory/smart-search",
            {"query": query, "project": self._cfg.namespace, "limit": max_results},
        )
        all_items = raw if isinstance(raw, list) else raw.get("results", [])
        all_records = _items_to_records(all_items, namespace=self._cfg.namespace)
        return MemoryReadResult(
            schema_version=SCHEMA_VERSION,
            query_ref=f"agentmemory-recall:{query[:64]}",
            records=all_records[:max_results],
            truncated=len(all_records) > max_results,
        )

    def get(self, memory_ref: MemoryRef) -> MemoryRecord | None:
        """Retrieve a single MemoryRecord by its ref_id (title filter)."""
        raw = self._post(
            "/agentmemory/smart-search",
            {"query": memory_ref.ref_id, "project": self._cfg.namespace, "limit": 20},
        )
        items = raw if isinstance(raw, list) else raw.get("results", [])
        for item in items:
            if isinstance(item, dict) and item.get("title") == memory_ref.ref_id:
                return _wire_to_record(item, namespace=self._cfg.namespace)
        return None

    def list_recent(self) -> MemoryReadResult:
        """List recent memories for the configured namespace."""
        params = urllib.parse.urlencode({"latest": "true", "project": self._cfg.namespace})
        raw = self._get(f"{self._cfg.daemon_url}/agentmemory/memories?{params}")
        items = raw if isinstance(raw, list) else raw.get("memories", [])
        return MemoryReadResult(
            schema_version=SCHEMA_VERSION,
            query_ref=f"agentmemory-list:{self._cfg.namespace}",
            records=_items_to_records(items, namespace=self._cfg.namespace),
            truncated=False,
        )

    def forget(self, memory_ref: MemoryRef) -> MemoryForgetResult:
        """Remove a memory from the daemon by ref_id."""
        daemon_id = self._resolve_daemon_id(memory_ref.ref_id)
        if daemon_id is None:
            return MemoryForgetResult(
                schema_version=SCHEMA_VERSION,
                memory_ref=memory_ref,
                forgotten=False,
            )
        self._post("/agentmemory/forget", {"id": daemon_id})
        return MemoryForgetResult(
            schema_version=SCHEMA_VERSION,
            memory_ref=memory_ref,
            forgotten=True,
        )

    def namespace_summaries(self) -> list[str]:
        """Return the list of project/namespace names known to the daemon."""
        raw = self._get(f"{self._cfg.daemon_url}/agentmemory/projects")
        if isinstance(raw, list):
            return [str(item) for item in raw if item]
        return raw.get("projects", [])

    def count(self) -> int:
        """Return total memory count reported by daemon health endpoint."""
        raw = self._get(f"{self._cfg.daemon_url}/agentmemory/health")
        if isinstance(raw, dict):
            return int(raw.get("total_memories", raw.get("count", 0)))
        return 0

    def health(self) -> dict[str, object]:
        """Return a safe projection of the daemon health response."""
        try:
            raw = self._get(f"{self._cfg.daemon_url}/agentmemory/health")
        except AgentMemoryRequestError as exc:
            return {"status": "unreachable", "detail": str(exc)}

        try:
            self._get(f"{self._cfg.daemon_url}/livez")
            live = True
        except AgentMemoryRequestError:
            live = False

        if isinstance(raw, dict):
            return {
                "status": raw.get("status", "ok"),
                "total_memories": raw.get("total_memories", 0),
                "live": live,
            }
        return {"status": "ok", "live": live}

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any] | list[Any]:
        return _http_request(  # type: ignore[return-value]
            f"{self._cfg.daemon_url}{path}",
            method="POST",
            body=body,
            bearer_token=self._cfg.bearer_token,
            timeout=self._cfg.timeout_seconds,
        )

    def _get(self, url: str) -> dict[str, Any] | list[Any]:
        return _http_request(  # type: ignore[return-value]
            url,
            method="GET",
            bearer_token=self._cfg.bearer_token,
            timeout=self._cfg.timeout_seconds,
        )

    def _resolve_daemon_id(self, title: str) -> str | None:
        """Search for a memory by title and return the daemon-side id field.

        The agentmemory API has no direct get-by-id endpoint, so we use
        smart-search with a title filter as the resolution step.
        """
        try:
            raw = self._post(
                "/agentmemory/smart-search",
                {"query": title, "project": self._cfg.namespace, "limit": 20},
            )
        except AgentMemoryRequestError:
            return None
        items = raw if isinstance(raw, list) else raw.get("results", [])
        for item in items:
            if isinstance(item, dict) and item.get("title") == title:
                return item.get("id") or item.get("_id") or title
        return None
