from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tests.core.test_core_service_entrypoint import _turn_payload


ROOT = Path(__file__).resolve().parents[2]
TOKEN = "fake-asgi-host-smoke-token"


def test_core_asgi_host_keeps_health_and_turns_responsive_while_control_stream_is_open():
    core_port = _free_port()
    control_port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "services.core.main",
            "--serve",
            "--port",
            str(core_port),
            "--control-port",
            str(control_port),
        ],
        cwd=ROOT,
        env={**os.environ, "MARVEX_LOCAL_AUTH_TOKEN": TOKEN},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stream_conn: http.client.HTTPConnection | None = None
    try:
        _wait_for_health(core_port, process)
        stream_conn = http.client.HTTPConnection("127.0.0.1", control_port, timeout=5)
        stream_conn.putrequest("GET", "/control/state/stream")
        stream_conn.putheader("Accept", "text/event-stream")
        stream_conn.putheader("Authorization", f"Bearer {TOKEN}")
        stream_conn.endheaders()
        stream_response = stream_conn.getresponse()

        health = _get_json(f"http://127.0.0.1:{core_port}/health")
        turn = _post_json(
            f"http://127.0.0.1:{core_port}/v1/turns",
            _turn_payload(trace_id="trace-asgi-smoke", turn_id="turn-asgi-smoke"),
            token=TOKEN,
        )
    finally:
        if stream_conn is not None:
            stream_conn.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)

    assert stream_response.status == 200
    assert health["service"] == "marvex-core-service"
    assert turn["trace_id"] == "trace-asgi-smoke"
    assert turn["turn_id"] == "turn-asgi-smoke"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(port: int, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise AssertionError(f"Core ASGI host exited early\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")
        try:
            _get_json(f"http://127.0.0.1:{port}/health")
            return
        except Exception as exc:
            last_error = exc
            time.sleep(0.25)
    raise AssertionError(f"Core ASGI host did not become healthy: {last_error}")


def _get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict, *, token: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"POST {url} failed with {exc.code}: {body}") from exc
