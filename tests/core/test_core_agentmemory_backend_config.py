from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import MemoryReadQuery, MemoryRecord, MemoryRef
from services.core.main import CoreServiceEntrypointConfig, _memory_loop_from_config


class _AgentMemoryStubState:
    def __init__(self) -> None:
        self.stored: list[dict[str, Any]] = []


class _AgentMemoryStubHandler(BaseHTTPRequestHandler):
    state: _AgentMemoryStubState

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        body = self._body()
        if path == "/agentmemory/remember":
            self.state.stored.append(body)
            self._json(200, {"ok": True})
            return
        if path == "/agentmemory/smart-search":
            query = str(body.get("query", "")).lower()
            self._json(
                200,
                {
                    "results": [
                        item
                        for item in self.state.stored
                        if query in str(item.get("content", "")).lower()
                        or query in str(item.get("title", "")).lower()
                    ]
                },
            )
            return
        self._json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/agentmemory/memories":
            self._json(200, {"memories": self.state.stored})
            return
        if path in {"/agentmemory/health", "/livez"}:
            self._json(200, {"status": "ok", "total_memories": len(self.state.stored)})
            return
        self._json(404, {"error": "not found"})


@pytest.fixture()
def agentmemory_stub() -> tuple[str, _AgentMemoryStubState]:
    state = _AgentMemoryStubState()
    _AgentMemoryStubHandler.state = state
    server = HTTPServer(("127.0.0.1", 0), _AgentMemoryStubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()


def _record() -> MemoryRecord:
    return MemoryRecord(
        schema_version="0.1.1-draft",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory.core.agentmemory"),
        scope="session",
        memory_kind="fact",
        session_ref=SessionRef(ref_type="session", ref_id="session-agentmemory"),
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation-agentmemory"),
        trace_id="trace-agentmemory",
        turn_id="turn-agentmemory",
        content="Agentmemory backend selection stores derived memory.",
        write_authorization="policy_approved",
        created_at=datetime(2026, 5, 22, tzinfo=UTC),
        tags=("agentmemory",),
        raw_transcript_persisted=False,
    )


def test_core_memory_backend_config_selects_agentmemory_store(agentmemory_stub, tmp_path) -> None:
    url, state = agentmemory_stub
    config = CoreServiceEntrypointConfig(
        memory_vault_root=str(tmp_path / "vault"),
        memory_backend="agentmemory",
        agentmemory_daemon_url=url,
        agentmemory_namespace="core-test",
    )

    loop = _memory_loop_from_config(config)
    assert loop is not None
    loop.memory_store.write_record(_record())
    result = loop.memory_store.read(
        MemoryReadQuery(
            schema_version="0.1.1-draft",
            query_id="query-agentmemory",
            scope="session",
            session_ref=SessionRef(ref_type="session", ref_id="session-agentmemory"),
            conversation_ref=None,
            max_records=3,
            policy_status="approved",
        )
    )

    assert state.stored[0]["project"] == "core-test"
    assert len(result.records) == 1
    assert result.records[0].memory_ref.ref_id == "memory.core.agentmemory"
