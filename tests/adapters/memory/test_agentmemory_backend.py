"""Tests for the agentmemory external-daemon memory backend.

All tests use an in-process stub HTTP server (stdlib http.server).
No real network connections are made.
"""
from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime.models import MemoryReadQuery, MemoryRecord, MemoryRef
from packages.adapters.memory.config import (
    AgentMemoryBackendConfig,
    MemoryBackendConfig,
    default_memory_backend_config,
)
from packages.adapters.memory.agentmemory_backend import (
    AgentMemoryBackend,
    AgentMemoryRequestError,
)


# ---------------------------------------------------------------------------
# Stub HTTP server fixture
# ---------------------------------------------------------------------------

class _StubState:
    """Mutable state shared between the stub handler and tests."""

    def __init__(self) -> None:
        self.stored: list[dict[str, Any]] = []
        self.forget_calls: list[dict[str, Any]] = []


class _StubHandler(BaseHTTPRequestHandler):
    """Minimal agentmemory-compatible stub server."""

    # Populated by fixture before the server starts.
    state: _StubState

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress noisy test output

    def _read_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def _send_json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/agentmemory/remember":
            self.state.stored.append(body)
            self._send_json(200, {"ok": True})

        elif path == "/agentmemory/smart-search":
            query = body.get("query", "")
            results = [
                item
                for item in self.state.stored
                if query.lower() in item.get("title", "").lower()
                or query.lower() in item.get("content", "").lower()
            ]
            self._send_json(200, {"results": results})

        elif path == "/agentmemory/forget":
            self.state.forget_calls.append(body)
            # Remove matching stored item by title (stub uses title as id).
            before = len(self.state.stored)
            self.state.stored = [
                item for item in self.state.stored if item.get("title") != body.get("id")
            ]
            self._send_json(200, {"forgotten": len(self.state.stored) < before})

        else:
            self._send_json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/agentmemory/health":
            self._send_json(200, {"status": "ok", "total_memories": len(self.state.stored)})

        elif path == "/livez":
            self._send_json(200, {"status": "live"})

        elif path == "/agentmemory/memories":
            self._send_json(200, {"memories": list(self.state.stored)})

        elif path == "/agentmemory/projects":
            projects = list({item.get("project", "") for item in self.state.stored} - {""})
            self._send_json(200, {"projects": projects})

        else:
            self._send_json(404, {"error": "not found"})


@pytest.fixture()
def stub_server():
    """Spin up an in-process stub agentmemory server on a random loopback port."""
    state = _StubState()

    # Patch the class-level state attribute so the handler can reach it.
    _StubHandler.state = state  # type: ignore[attr-defined]

    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{port}", state
    finally:
        server.shutdown()


def _backend(daemon_url: str, namespace: str = "test-ns") -> AgentMemoryBackend:
    cfg = AgentMemoryBackendConfig(daemon_url=daemon_url, namespace=namespace)
    return AgentMemoryBackend(cfg)


def _record(memory_id: str = "mem-001", content: str = "User prefers concise updates.") -> MemoryRecord:
    return MemoryRecord(
        schema_version="0.1.1-draft",
        memory_ref=MemoryRef(ref_type="memory", ref_id=memory_id),
        scope="session",
        memory_kind="fact",
        session_ref=SessionRef(ref_type="session", ref_id="session-001"),
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-001"),
        trace_id="trace-test-001",
        turn_id="turn-test-001",
        content=content,
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 21, 10, 0, tzinfo=UTC),
        tags=("preference",),
        raw_transcript_persisted=False,
    )


# ---------------------------------------------------------------------------
# store
# ---------------------------------------------------------------------------

def test_store_sends_record_to_daemon(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record())

    assert len(state.stored) == 1
    assert state.stored[0]["title"] == "mem-001"
    assert state.stored[0]["project"] == "test-ns"
    assert "content" in state.stored[0]


def test_agentmemory_backend_implements_memory_store_read_write_interface(stub_server) -> None:
    url, _state = stub_server
    backend = _backend(url)
    record = _record("mem-core-001", "User preferred project codename is Lumen.")

    backend.write_record(record)
    result = backend.read(
        MemoryReadQuery(
            schema_version=record.schema_version,
            query_id="query-core-001",
            scope="session",
            session_ref=record.session_ref,
            conversation_ref=None,
            max_records=3,
            policy_status="approved",
        )
    )
    inspected = tuple(backend.safe_inspect(max_records=5))

    assert len(result.records) == 1
    assert result.records[0].memory_ref.ref_id == "mem-core-001"
    assert len(inspected) == 1
    assert inspected[0]["raw_transcript_persisted"] is False


def test_store_does_not_send_raw_credentials(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record())

    wire = state.stored[0]
    dumped = json.dumps(wire).lower()
    for forbidden in ("bearer", "secret", "authorization", "raw_transcript"):
        assert forbidden not in dumped, f"wire payload contains forbidden term: {forbidden!r}"


# ---------------------------------------------------------------------------
# recall
# ---------------------------------------------------------------------------

def test_recall_returns_mapped_memory_records(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record("mem-002", "User prefers dark mode."))
    result = backend.recall("dark mode")

    assert result.record_count >= 1
    assert any(r.memory_ref.ref_id == "mem-002" for r in result.records)


def test_recall_returns_empty_on_no_match(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    result = backend.recall("this will not match anything stored")

    assert result.record_count == 0
    assert result.records == ()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_retrieves_record_by_ref_id(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record("mem-get-001", "User is an engineer."))
    retrieved = backend.get(MemoryRef(ref_type="memory", ref_id="mem-get-001"))

    assert retrieved is not None
    assert retrieved.memory_ref.ref_id == "mem-get-001"


def test_get_returns_none_when_not_found(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    result = backend.get(MemoryRef(ref_type="memory", ref_id="does-not-exist"))

    assert result is None


# ---------------------------------------------------------------------------
# forget
# ---------------------------------------------------------------------------

def test_forget_removes_stored_memory(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record("mem-forget-001"))
    # Stub uses title as the daemon id.
    state.stored[0]["id"] = "mem-forget-001"

    result = backend.forget(MemoryRef(ref_type="memory", ref_id="mem-forget-001"))

    assert result.forgotten is True
    assert result.memory_ref.ref_id == "mem-forget-001"


def test_forget_returns_not_forgotten_when_missing(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    result = backend.forget(MemoryRef(ref_type="memory", ref_id="nonexistent-mem"))

    assert result.forgotten is False


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def test_health_returns_ok_when_daemon_is_reachable(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    h = backend.health()

    assert h["status"] == "ok"
    assert h.get("live") is True


def test_health_returns_unreachable_when_daemon_is_down() -> None:
    backend = _backend("http://127.0.0.1:19999")  # nothing listening

    h = backend.health()

    assert h["status"] == "unreachable"


# ---------------------------------------------------------------------------
# list_recent
# ---------------------------------------------------------------------------

def test_list_recent_returns_all_stored_memories(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record("mem-list-001"))
    backend.store(_record("mem-list-002", "User prefers Python."))

    result = backend.list_recent()

    assert result.record_count == 2


# ---------------------------------------------------------------------------
# namespace_summaries
# ---------------------------------------------------------------------------

def test_namespace_summaries_returns_known_projects(stub_server) -> None:
    url, state = stub_server
    backend = _backend(url)

    backend.store(_record("ns-mem-001"))
    summaries = backend.namespace_summaries()

    assert "test-ns" in summaries


# ---------------------------------------------------------------------------
# Default config does NOT use agentmemory
# ---------------------------------------------------------------------------

def test_default_config_does_not_enable_agentmemory() -> None:
    cfg = default_memory_backend_config()

    assert cfg.backend == "local"
    assert cfg.is_agentmemory_enabled is False
    assert cfg.agentmemory is None


def test_memory_backend_config_defaults_to_local() -> None:
    cfg = MemoryBackendConfig()

    assert cfg.backend == "local"
    assert not cfg.is_agentmemory_enabled


def test_agentmemory_config_requires_explicit_opt_in() -> None:
    local_cfg = MemoryBackendConfig(backend="local")
    agent_cfg = MemoryBackendConfig(
        backend="agentmemory",
        agentmemory=AgentMemoryBackendConfig(daemon_url="http://localhost:3111"),
    )

    assert not local_cfg.is_agentmemory_enabled
    assert agent_cfg.is_agentmemory_enabled


# ---------------------------------------------------------------------------
# Bearer token is not persisted in wire payload
# ---------------------------------------------------------------------------

def test_bearer_token_is_not_included_in_wire_payload(stub_server) -> None:
    url, state = stub_server
    cfg = AgentMemoryBackendConfig(
        daemon_url=url,
        namespace="ns-token-test",
        bearer_token="super-secret-token",  # noqa: S106 — test only
    )
    backend = AgentMemoryBackend(cfg)

    backend.store(_record("tok-mem-001"))

    wire_dump = json.dumps(state.stored)
    assert "super-secret-token" not in wire_dump


# ---------------------------------------------------------------------------
# AgentMemoryRequestError is raised on HTTP errors
# ---------------------------------------------------------------------------

def test_request_error_raised_on_http_error(stub_server) -> None:
    url, _ = stub_server
    backend = _backend(url)

    with pytest.raises(AgentMemoryRequestError):
        backend._post("/agentmemory/nonexistent-path-404", {})
