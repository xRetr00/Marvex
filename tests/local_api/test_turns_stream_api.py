"""Streaming turn SSE endpoint /v1/turns/stream (docs/TODO/06)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from packages.local_api import create_local_api_asgi_app
from packages.local_api.contracts import LOCAL_TURNS_STREAM_PATH

from tests.local_api.test_turns_api import (
    EXPECTED_TOKEN,
    make_provider,
    make_request_payload,
    make_result,
)


def _stream_handler(request):
    # Mirror the Core handler shape: delta events then a terminal final event.
    result = make_result(request.assistant_turn_input)
    for chunk in ("Stubbed ", "local API ", "response."):
        yield {"type": "delta", "text": chunk}
    yield {"type": "final", "result": result.model_dump(mode="json")}


def _app(stream_handler=_stream_handler, *, token=EXPECTED_TOKEN):
    return create_local_api_asgi_app(
        make_provider(),
        stream_turn_handler=stream_handler,
        local_auth_token=token,
    )


def _parse_sse(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        line = block.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_stream_emits_deltas_then_final():
    client = TestClient(_app())
    response = client.post(
        LOCAL_TURNS_STREAM_PATH,
        headers={"Authorization": EXPECTED_TOKEN},
        json=make_request_payload(),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(response.text)
    assert [e["type"] for e in events] == ["delta", "delta", "delta", "final"]
    assert "".join(e["text"] for e in events if e["type"] == "delta") == "Stubbed local API response."
    final = events[-1]["result"]
    assert final["assistant_final_response"]["text"] == "Stubbed local API response."


def test_stream_requires_auth():
    client = TestClient(_app())
    response = client.post(LOCAL_TURNS_STREAM_PATH, json=make_request_payload())
    assert response.status_code == 401


def test_stream_handler_unavailable_returns_503():
    client = TestClient(_app(stream_handler=None))
    response = client.post(
        LOCAL_TURNS_STREAM_PATH,
        headers={"Authorization": EXPECTED_TOKEN},
        json=make_request_payload(),
    )
    assert response.status_code == 503


def test_stream_invalid_request_returns_400():
    client = TestClient(_app())
    response = client.post(
        LOCAL_TURNS_STREAM_PATH,
        headers={"Authorization": EXPECTED_TOKEN},
        json={"bad": "payload"},
    )
    assert response.status_code == 400


def test_stream_handler_exception_surfaces_error_event():
    def boom(_request):
        raise RuntimeError("boom")
        yield  # pragma: no cover - generator

    client = TestClient(_app(stream_handler=boom))
    response = client.post(
        LOCAL_TURNS_STREAM_PATH,
        headers={"Authorization": EXPECTED_TOKEN},
        json=make_request_payload(),
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert events[-1]["type"] == "error"
