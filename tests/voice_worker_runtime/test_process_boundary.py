from __future__ import annotations

import subprocess
from io import StringIO

import pytest

from packages.voice_worker_runtime import VoiceWorkerCommand, VoiceWorkerController, VoiceWorkerLifecycleState, VoiceWorkerProcessAdapter, VoiceWorkerProcessSpec, VoiceWorkerProcessSupervisor
from packages.voice_worker_runtime.worker_main import run_worker_contract_loop, run_worker_loop


def test_process_spec_is_loopback_only_and_builds_module_argv() -> None:
    spec = VoiceWorkerProcessSpec(host="127.0.0.1", port=8767)

    assert spec.argv()[1:] == ("-m", "packages.voice_worker_runtime.worker_main", "--host", "127.0.0.1", "--port", "8767", "--jsonl")
    with pytest.raises(ValueError, match="loopback"):
        VoiceWorkerProcessSpec(host="0.0.0.0", port=8767)


def test_process_adapter_starts_once_and_stops_with_safe_shutdown(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []

    class _FakeProcess:
        def __init__(self, argv: tuple[str, ...], **kwargs: object) -> None:
            self.argv = argv
            self.kwargs = kwargs
            self.running = True

        def poll(self) -> int | None:
            return None if self.running else 0

        def terminate(self) -> None:
            calls.append(("terminate", True))
            self.running = False

        def wait(self, timeout: int) -> int:
            calls.append(("wait", timeout))
            return 0

    def _fake_popen(argv: tuple[str, ...], **kwargs: object) -> _FakeProcess:
        calls.append(("popen", argv))
        assert kwargs["stdin"] is subprocess.PIPE
        assert kwargs["stdout"] is subprocess.PIPE
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert kwargs["shell"] is False
        assert kwargs["text"] is True
        return _FakeProcess(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter = VoiceWorkerProcessAdapter(VoiceWorkerProcessSpec(host="127.0.0.1", port=8767))

    adapter.start()
    adapter.start()
    assert adapter.is_running() is True
    adapter.stop()

    assert [call[0] for call in calls] == ["popen", "terminate", "wait"]
    assert adapter.is_running() is False


def test_worker_contract_loop_reads_voice_worker_commands_and_writes_safe_jsonl() -> None:
    controller = VoiceWorkerController()
    input_stream = StringIO(
        VoiceWorkerCommand(command="start", command_id="cmd-start").model_dump_json()
        + "\n"
        + VoiceWorkerCommand(command="stop", command_id="cmd-stop").model_dump_json()
        + "\n"
    )
    output_stream = StringIO()

    final = run_worker_contract_loop(
        controller=controller,
        host="127.0.0.1",
        port=8767,
        input_stream=input_stream,
        output_stream=output_stream,
    )

    lines = [line for line in output_stream.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    assert '"command_id": "cmd-start"' in lines[0]
    assert '"lifecycle_state": "running"' in lines[0]
    assert '"command_id": "cmd-stop"' in lines[1]
    assert '"lifecycle_state": "stopped"' in lines[1]
    assert '"raw_audio": true' not in output_stream.getvalue().lower()
    assert final["status"]["lifecycle_state"] == "stopped"


def test_worker_main_once_mode_starts_and_stops_controller_without_remote_binding() -> None:
    controller = VoiceWorkerController()

    payload = run_worker_loop(controller=controller, host="127.0.0.1", port=8767, once=True)

    assert payload["host"] == "127.0.0.1"
    assert payload["status"]["lifecycle_state"] == "running"
    assert payload["status"]["local_only"] is True
    assert payload["status"]["hidden_recording_allowed"] is False
    assert controller.status().lifecycle_state == VoiceWorkerLifecycleState.STOPPED


class _FakeProcessAdapter:
    """Minimal fake for VoiceWorkerProcessSupervisor tests."""

    def __init__(self, *, starts_alive: bool = True) -> None:
        self._alive = starts_alive
        self.start_calls = 0
        self.stop_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        self._alive = True

    def stop(self) -> None:
        self.stop_calls += 1
        self._alive = False

    def is_running(self) -> bool:
        return self._alive

    def crash(self) -> None:
        self._alive = False

    def send_command(self, command: VoiceWorkerCommand) -> dict:
        return {}


def test_process_supervisor_start_stop_lifecycle() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter)

    status = supervisor.start()
    assert status["state"] == "running"
    assert adapter.start_calls == 1
    assert supervisor.is_running() is True

    status = supervisor.stop()
    assert status["state"] == "stopped"
    assert adapter.stop_calls == 1
    assert supervisor.is_running() is False


def test_process_supervisor_check_healthy_process_resets_restart_counter() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter)
    supervisor.start()

    status = supervisor.check()
    assert status["state"] == "running"
    assert status["consecutive_restarts"] == 0
    assert status["raw_audio_persisted"] is False


def test_process_supervisor_restarts_crashed_process_with_backoff() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter, initial_backoff_s=0.5, max_backoff_s=4.0)
    supervisor.start()
    adapter.crash()

    status = supervisor.check()
    assert status["state"] == "restarted"
    assert status["consecutive_restarts"] == 1
    assert status["current_backoff_s"] == 0.5
    assert adapter.start_calls == 2  # initial start + one restart

    adapter.crash()
    status = supervisor.check()
    assert status["consecutive_restarts"] == 2
    assert status["current_backoff_s"] == 1.0  # doubled


def test_process_supervisor_halts_after_max_restarts() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter, max_consecutive_restarts=2, initial_backoff_s=0.1)
    supervisor.start()

    for _ in range(3):
        adapter.crash()
        supervisor.check()

    assert supervisor._halted is True
    status = supervisor.safe_status()
    assert status["state"] == "halted"
    assert status["halted"] is True
    # A further start call should be blocked
    blocked = supervisor.start()
    assert blocked["state"] == "halted"


def test_process_supervisor_auto_restart_disabled_halts_immediately() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter, auto_restart=False)
    supervisor.start()
    adapter.crash()

    status = supervisor.check()
    assert status["state"] == "halted"
    assert status["reason_code"] == "process_exited_auto_restart_disabled"
    assert adapter.start_calls == 1  # no restart attempted


def test_process_supervisor_safe_status_never_persists_audio() -> None:
    adapter = _FakeProcessAdapter()
    supervisor = VoiceWorkerProcessSupervisor(adapter=adapter)
    status = supervisor.safe_status()
    assert status["raw_audio_persisted"] is False
