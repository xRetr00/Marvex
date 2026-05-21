from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = "trace-smoke-real-provider-adapter"
TURN_ID = "turn-smoke-real-provider-adapter"
RESPONSE_TEXT = "Marvex real provider adapter smoke."


class _ResponsesHandler(BaseHTTPRequestHandler):
    response_text = RESPONSE_TEXT
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
        self._send_json(_response_payload(type(self).last_request, type(self).response_text))

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
    _ResponsesHandler.response_text = args.response_text
    _ResponsesHandler.request_count = 0
    _ResponsesHandler.last_request = {}

    server = ThreadingHTTPServer(("127.0.0.1", 0), _ResponsesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        completed = _run_core_turn(args, server.server_port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return _print_smoke_result(completed)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Developer-only Core smoke for the lmstudio_responses provider "
            "adapter path using a loopback Responses-compatible endpoint."
        )
    )
    parser.add_argument("--text", default="Reply with one short confirmation.")
    parser.add_argument("--model", default="local-smoke-model")
    parser.add_argument("--response-text", default=RESPONSE_TEXT)
    parser.add_argument("--timeout", type=float, default=10.0)
    return parser


def _run_core_turn(args: argparse.Namespace, port: int) -> subprocess.CompletedProcess[str]:
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
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=args.timeout + 15,
    )


def _print_smoke_result(completed: subprocess.CompletedProcess[str]) -> int:
    if completed.returncode != 0:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "core_cli_failed",
                    "returncode": completed.returncode,
                    "stderr_preview": _preview(completed.stderr),
                },
                sort_keys=True,
            )
        )
        return 1
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "invalid_core_json",
                    "stdout_preview": _preview(completed.stdout),
                    "stderr_preview": _preview(completed.stderr),
                },
                sort_keys=True,
            )
        )
        return 1

    response = result.get("assistant_final_response") or {}
    metadata = result.get("metadata") or {}
    provider_refs = result.get("provider_turn_refs") or []
    provider_name = ""
    if provider_refs and isinstance(provider_refs[0], dict):
        provider_name = str(provider_refs[0].get("provider_name") or "")
    payload = {
        "status": "PASS" if response.get("text") else "FAIL",
        "trace_id": result.get("trace_id"),
        "turn_id": result.get("turn_id"),
        "response_text": response.get("text", ""),
        "provider_name": provider_name,
        "provider_boundary": metadata.get("provider_boundary"),
        "assistant_turn_spine": metadata.get("assistant_turn_spine"),
        "agentic_loop": metadata.get("agentic_loop"),
        "request_count": _ResponsesHandler.request_count,
        "requested_model": _ResponsesHandler.last_request.get("model"),
        "raw_payload_persisted": False,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


def _response_payload(request: dict[str, Any], response_text: str) -> dict[str, Any]:
    return {
        "id": "resp-smoke-real-provider-adapter",
        "object": "response",
        "created_at": int(time.time()),
        "status": "completed",
        "model": request.get("model", "local-smoke-model"),
        "output": [
            {
                "id": "msg-smoke-real-provider-adapter",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": response_text,
                        "annotations": [],
                    }
                ],
            }
        ],
        "usage": {
            "input_tokens": 4,
            "output_tokens": 5,
            "total_tokens": 9,
        },
    }


def _preview(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


if __name__ == "__main__":
    raise SystemExit(main())
