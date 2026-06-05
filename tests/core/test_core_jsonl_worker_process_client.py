from __future__ import annotations

import queue

import pytest


class _FakeJsonlStdin:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)

    def flush(self) -> None:
        pass


class _FakeJsonlStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines

    def readline(self) -> str:
        return self._lines.pop(0) if self._lines else ""


class _FakeJsonlProcess:
    def __init__(self, lines: list[str]) -> None:
        self.stdin = _FakeJsonlStdin()
        self.stdout = _FakeJsonlStdout(lines)
        self.killed = False
        self.terminated = False
        self.waited = False

    def poll(self):
        return None if not self.killed and not self.terminated else 1

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None):
        self.waited = True
        return 0


def test_jsonl_worker_process_client_reuses_one_process_for_multiple_commands():
    from services.core.main import _JsonlWorkerProcessClient

    process = _FakeJsonlProcess(
        [
            '{"command":"start","ok":true,"trace_id":"trace-start"}\n',
            '{"command":"status","ok":true,"trace_id":"trace-one"}\n',
            '{"command":"status","ok":true,"trace_id":"trace-two"}\n',
            '{"command":"stop","ok":true,"trace_id":"trace-stop"}\n',
        ]
    )
    spawned: list[tuple[object, dict[str, object]]] = []

    def process_factory(argv, **kwargs):
        spawned.append((argv, kwargs))
        return process

    client = _JsonlWorkerProcessClient(
        module="services.intent_worker.main",
        start_trace_id="trace-start",
        stop_trace_id="trace-stop",
        process_factory=process_factory,
    )

    first = client.request({"command": "status", "trace_id": "trace-one"})
    second = client.request({"command": "status", "trace_id": "trace-two"})
    client.shutdown()

    assert len(spawned) == 1
    assert spawned[0][0][1:] == ("-m", "services.intent_worker.main", "--jsonl")
    assert first["trace_id"] == "trace-one"
    assert second["trace_id"] == "trace-two"
    written = "".join(process.stdin.lines)
    assert '"command": "start"' in written
    assert '"trace_id": "trace-one"' in written
    assert '"trace_id": "trace-two"' in written
    assert '"command": "stop"' in written


class _BlockingStdout:
    """stdout whose readline blocks until a line is pushed (then EOF on '')."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()

    def push(self, line: str) -> None:
        self._queue.put(line)

    def readline(self) -> str:
        return self._queue.get()


class _BlockingProcess:
    def __init__(self) -> None:
        self.stdin = _FakeJsonlStdin()
        self.stdout = _BlockingStdout()
        self.killed = False
        self.terminated = False

    def poll(self):
        return 1 if (self.killed or self.terminated) else None

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout=None):
        return 0


def test_idle_timeout_does_not_kill_worker_and_skips_stale_frame():
    from services.core.main import _JsonlWorkerProcessClient

    process = _BlockingProcess()
    process.stdout.push('{"command":"start","ok":true,"trace_id":"trace-start"}\n')

    client = _JsonlWorkerProcessClient(
        module="services.provider_worker.main",
        start_trace_id="trace-start",
        stop_trace_id="trace-stop",
        timeout_seconds=0.2,
        process_factory=lambda argv, **kwargs: process,
    )

    # No response arrives within the idle window -> TimeoutError, but the worker
    # must stay alive (never killed) so the next turn can reuse it.
    with pytest.raises(TimeoutError):
        client.request({"command": "status", "trace_id": "trace-slow"})
    assert process.killed is False
    assert process.terminated is False

    # The late (stale) frame from the timed-out request arrives, followed by the
    # fresh response. The stale frame must be discarded by trace_id.
    process.stdout.push('{"command":"status","ok":true,"trace_id":"trace-slow"}\n')
    process.stdout.push('{"command":"status","ok":true,"trace_id":"trace-next"}\n')

    result = client.request({"command": "status", "trace_id": "trace-next"})
    assert result["trace_id"] == "trace-next"


def test_stream_consumes_frames_until_terminal_final():
    from services.core.main import _JsonlWorkerProcessClient

    process = _FakeJsonlProcess(
        [
            '{"command":"start","ok":true,"trace_id":"trace-start"}\n',
            '{"command":"stream","trace_id":"trace-s","type":"delta","text":"He"}\n',
            '{"command":"stream","trace_id":"trace-s","type":"delta","text":"llo"}\n',
            '{"command":"stream","trace_id":"trace-s","type":"final","response":{"output_text":"Hello"}}\n',
        ]
    )
    client = _JsonlWorkerProcessClient(
        module="services.provider_worker.main",
        start_trace_id="trace-start",
        stop_trace_id="trace-stop",
        process_factory=lambda argv, **kwargs: process,
    )

    frames: list[dict] = []
    client.stream({"command": "stream", "trace_id": "trace-s"}, on_frame=frames.append)

    assert [f["type"] for f in frames] == ["delta", "delta", "final"]
    assert frames[-1]["response"]["output_text"] == "Hello"


def test_provider_worker_process_provider_stream_send_assembles_response():
    from packages.contracts import ProviderRequest
    from services.core.main import _ProviderWorkerProcessProvider, _set_live_event_sink

    class _FakeClient:
        def stream(self, command, *, on_frame, timeout_seconds=None):
            on_frame({"type": "response", "response_id": "r1"})
            on_frame({"type": "delta", "text": "Mar"})
            on_frame({"type": "delta", "text": "vex"})
            on_frame({
                "type": "final",
                "response": {
                    "schema_version": "1",
                    "trace_id": "trace-p",
                    "turn_id": "turn-p",
                    "provider_name": "lmstudio_responses",
                    "response_id": "r1",
                    "output_text": "Marvex",
                    "finish_reason": "stop",
                    "usage": {},
                    "raw_metadata": {},
                    "error": None,
                    "tool_calls": None,
                },
            })

    provider = _ProviderWorkerProcessProvider(provider_name="lmstudio_responses", worker_client=_FakeClient())
    request = ProviderRequest(
        schema_version="1", trace_id="trace-p", turn_id="turn-p", model="m",
        input_text="hi", instructions=None, previous_response_id=None, provider_options={},
    )
    deltas: list[str] = []
    live_events: list[dict[str, object]] = []
    _set_live_event_sink(live_events.append)
    try:
        response = provider.stream_send(request, on_delta=deltas.append)
    finally:
        _set_live_event_sink(None)

    assert deltas == ["Mar", "vex"]
    assert live_events == [{"type": "response", "response_id": "r1"}]
    assert response.output_text == "Marvex"
    assert response.response_id == "r1"


def test_send_streams_when_live_sink_active_else_uses_request():
    from packages.contracts import ProviderRequest
    from services.core.main import _ProviderWorkerProcessProvider, _set_live_token_sink

    class _FakeClient:
        def __init__(self):
            self.used_request = False
        def stream(self, command, *, on_frame, timeout_seconds=None):
            on_frame({"type": "delta", "text": "live"})
            on_frame({"type": "final", "response": {
                "schema_version": "1", "trace_id": "t", "turn_id": "u",
                "provider_name": "lmstudio_responses", "response_id": "r",
                "output_text": "live", "finish_reason": "stop", "usage": {},
                "raw_metadata": {}, "error": None, "tool_calls": None,
            }})
        def request(self, command, *, timeout_seconds=None):
            self.used_request = True
            return {"response": {
                "schema_version": "1", "trace_id": "t", "turn_id": "u",
                "provider_name": "lmstudio_responses", "response_id": "r",
                "output_text": "blocking", "finish_reason": "stop", "usage": {},
                "raw_metadata": {}, "error": None, "tool_calls": None,
            }}

    client = _FakeClient()
    provider = _ProviderWorkerProcessProvider(provider_name="lmstudio_responses", worker_client=client)
    request = ProviderRequest(
        schema_version="1", trace_id="t", turn_id="u", model="m",
        input_text="hi", instructions=None, previous_response_id=None, provider_options={},
    )

    # No live sink -> non-streaming request path.
    assert provider.send(request).output_text == "blocking"
    assert client.used_request is True

    # Live sink active -> streaming path, deltas forwarded.
    deltas: list[str] = []
    _set_live_token_sink(deltas.append)
    try:
        assert provider.send(request).output_text == "live"
    finally:
        _set_live_token_sink(None)
    assert deltas == ["live"]


def test_provider_worker_process_provider_cancel_and_delete_response_commands():
    from services.core.main import _ProviderWorkerProcessProvider

    class _FakeClient:
        def __init__(self):
            self.commands = []

        def request(self, command, *, timeout_seconds=None):
            self.commands.append((command, timeout_seconds))
            return {
                "ok": True,
                "metadata": {
                    "response_control": {
                        "id": command["response_id"],
                        "action": command["command"],
                    }
                },
            }

    client = _FakeClient()
    provider = _ProviderWorkerProcessProvider(
        provider_name="lmstudio_responses",
        base_url="http://127.0.0.1:1234",
        timeout_seconds=9,
        provider_secret="secret-token",
        worker_client=client,
    )

    assert provider.cancel_response(" resp_cancel ") == {"id": "resp_cancel", "action": "cancel_response"}
    assert provider.delete_response("resp_delete") == {"id": "resp_delete", "action": "delete_response"}

    cancel_command, cancel_timeout = client.commands[0]
    delete_command, delete_timeout = client.commands[1]
    assert cancel_command["command"] == "cancel_response"
    assert cancel_command["response_id"] == "resp_cancel"
    assert cancel_command["base_url"] == "http://127.0.0.1:1234"
    assert cancel_command["lmstudio_responses_api_key"] == "secret-token"
    assert delete_command["command"] == "delete_response"
    assert delete_command["response_id"] == "resp_delete"
    assert cancel_timeout == 9
    assert delete_timeout == 9


def test_model_aware_idle_timeout_scales_and_respects_explicit_config():
    from services.core.main import _model_aware_idle_timeout, _model_param_billions

    assert _model_param_billions("google/gemma-4-e2b") == 2.0
    assert _model_param_billions("qwen2.5-7b-instruct") == 7.0
    assert _model_param_billions("no-size-here") is None

    # Explicit config always wins.
    assert _model_aware_idle_timeout(configured=45.0, model="google/gemma-4-e2b") == 45.0
    # Larger models get a larger idle window than small ones.
    small = _model_aware_idle_timeout(configured=None, model="google/gemma-4-e2b")
    large = _model_aware_idle_timeout(configured=None, model="llama-70b")
    assert large > small
    # Never below the floor.
    assert _model_aware_idle_timeout(configured=None, model=None) >= 30.0
