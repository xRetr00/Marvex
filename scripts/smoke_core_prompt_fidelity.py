from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from packages.contracts import ConversationRef, SessionRef
from packages.memory_runtime import MemoryRecord, MemoryRef, SQLiteMemoryStore


ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = "trace-smoke-prompt-fidelity"
TURN_ID = "turn-smoke-prompt-fidelity"
SESSION_ID = "session-smoke-prompt-fidelity"


class _ResponsesHandler(BaseHTTPRequestHandler):
    request_count = 0
    last_request: dict[str, Any] = {}

    def do_POST(self) -> None:
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {}
        type(self).request_count += 1
        type(self).last_request = payload if isinstance(payload, dict) else {}
        self._send_json(
            {
                "id": "resp-smoke-prompt-fidelity",
                "object": "response",
                "created_at": int(time.time()),
                "status": "completed",
                "model": payload.get("model", "local-smoke-model") if isinstance(payload, dict) else "local-smoke-model",
                "output": [
                    {
                        "id": "msg-smoke-prompt-fidelity",
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": "Prompt fidelity smoke response.",
                                "annotations": [],
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
            }
        )

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="marvex-memory-smoke-") as temp_dir:
        vault_root = Path(temp_dir) / "vault"
        _seed_memory(vault_root=vault_root, content=args.seed_memory)
        server = ThreadingHTTPServer(("127.0.0.1", 0), _ResponsesHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            completed = _run_core_turn(args, server.server_port, vault_root)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    return _print_result(completed, args)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Developer smoke proving Core prompt fidelity through a loopback Responses-compatible provider.")
    parser.add_argument("--text", required=True)
    parser.add_argument("--seed-memory", required=True)
    parser.add_argument("--seed-evidence", required=True)
    parser.add_argument("--model", default="local-smoke-model")
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def _seed_memory(*, vault_root: Path, content: str) -> None:
    vault_root.mkdir(parents=True, exist_ok=True)
    store = SQLiteMemoryStore(memory_db_path=vault_root / "memory.sqlite", local_user_root=vault_root)
    store.write_record(
        MemoryRecord(
            schema_version="0.1.1-draft",
            memory_ref=MemoryRef(ref_type="memory", ref_id="memory-smoke-prompt-fidelity"),
            scope="session",
            memory_kind="fact",
            session_ref=SessionRef(ref_type="session", ref_id=SESSION_ID),
            conversation_ref=ConversationRef(ref_type="conversation", ref_id=f"conversation.{SESSION_ID}"),
            trace_id="trace-smoke-seed-memory",
            turn_id="turn-smoke-seed-memory",
            content=content,
            write_authorization="policy_approved",
            created_at=datetime(2026, 5, 21, 9, 10, tzinfo=UTC),
            tags=("profile",),
            raw_transcript_persisted=False,
        )
    )


def _run_core_turn(args: argparse.Namespace, port: int, vault_root: Path) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "services.core.main",
        "--turn-once",
        args.text,
        "--provider",
        "provider_worker",
        "--worker-provider",
        "lmstudio_responses",
        "--model",
        args.model,
        "--base-url",
        f"http://127.0.0.1:{port}/v1",
        "--timeout",
        str(args.timeout),
        "--trace-id",
        TRACE_ID,
        "--turn-id",
        TURN_ID,
        "--session-id",
        SESSION_ID,
        "--memory-vault-root",
        str(vault_root),
        "--demo-memory-evidence",
    ]
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=args.timeout + 15)


def _print_result(completed: subprocess.CompletedProcess[str], args: argparse.Namespace) -> int:
    request = _ResponsesHandler.last_request
    input_text = str(request.get("input", ""))
    instructions = str(request.get("instructions", ""))
    result = {
        "status": "PASS" if completed.returncode == 0 and _ResponsesHandler.request_count == 1 else "FAIL",
        "provider_name": "lmstudio_responses",
        "request_count": _ResponsesHandler.request_count,
        "request_has_instructions": bool(instructions),
        "request_has_real_question": args.text in input_text,
        "request_has_real_memory": args.seed_memory in input_text,
        "request_has_real_evidence": "Demo memory evidence preview." in input_text or args.seed_evidence in input_text,
        "request_uses_adaptive_budget": "Continue with only included safe context sections." in input_text and "Marvex policy remains authoritative" in instructions,
        "raw_payload_persisted": False,
    }
    if not all(result[key] for key in ("request_has_instructions", "request_has_real_question", "request_has_real_memory", "request_has_real_evidence", "request_uses_adaptive_budget")):
        result["status"] = "FAIL"
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
