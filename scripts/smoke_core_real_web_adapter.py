from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
TRACE_ID = "trace-smoke-real-web-adapter"
TURN_ID = "turn-smoke-real-web-adapter"


class _SearXNGHandler(BaseHTTPRequestHandler):
    request_count = 0
    last_query: dict[str, Any] = {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_error(404)
            return
        query = parse_qs(parsed.query)
        type(self).request_count += 1
        type(self).last_query = {
            key: values[0] if values else ""
            for key, values in query.items()
        }
        self._send_json(_search_payload())

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
    _SearXNGHandler.request_count = 0
    _SearXNGHandler.last_query = {}

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SearXNGHandler)
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
            "Developer-only Core smoke for the SearXNG web-search adapter path "
            "using a loopback SearXNG-compatible JSON endpoint."
        )
    )
    parser.add_argument(
        "--text",
        default="Give a grounded answer with current web evidence about browser-use",
    )
    parser.add_argument("--model", default="fake-model")
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
        "fake",
        "--model",
        args.model,
        "--web-search",
        "searxng",
        "--web-base-url",
        f"http://127.0.0.1:{port}",
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
        timeout=args.timeout + 20,
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
    grounding = metadata.get("grounding") or {}
    text = str(response.get("text") or "")
    payload = {
        "status": "PASS"
        if grounding.get("citation_validation") == "citation.validated"
        and "[web.evidence.1]" in text
        and _SearXNGHandler.request_count == 1
        else "FAIL",
        "trace_id": result.get("trace_id"),
        "turn_id": result.get("turn_id"),
        "web_provider": "searxng",
        "citation_validation": grounding.get("citation_validation"),
        "fabricated": grounding.get("fabricated"),
        "response_contains_citation": "[web.evidence.1]" in text,
        "request_count": _SearXNGHandler.request_count,
        "requested_format": _SearXNGHandler.last_query.get("format"),
        "requested_query_present": bool(_SearXNGHandler.last_query.get("q")),
        "raw_payload_persisted": False,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


def _search_payload() -> dict[str, Any]:
    return {
        "results": [
            {
                "title": "Current browser-use release",
                "url": "https://example.test/browser-use-release",
                "content": "Current browser-use release evidence.",
                "publishedDate": "2026-05-21",
            }
        ]
    }


def _preview(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


if __name__ == "__main__":
    raise SystemExit(main())
