from __future__ import annotations


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
