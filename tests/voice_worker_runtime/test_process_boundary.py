from __future__ import annotations

import subprocess

import pytest

from packages.voice_worker_runtime import VoiceWorkerController, VoiceWorkerLifecycleState, VoiceWorkerProcessAdapter, VoiceWorkerProcessSpec
from packages.voice_worker_runtime.worker_main import run_worker_loop


def test_process_spec_is_loopback_only_and_builds_module_argv() -> None:
    spec = VoiceWorkerProcessSpec(host="127.0.0.1", port=8767)

    assert spec.argv()[1:] == ("-m", "packages.voice_worker_runtime.worker_main", "--host", "127.0.0.1", "--port", "8767")
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
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["stdout"] is subprocess.DEVNULL
        assert kwargs["stderr"] is subprocess.DEVNULL
        assert kwargs["shell"] is False
        return _FakeProcess(argv, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)
    adapter = VoiceWorkerProcessAdapter(VoiceWorkerProcessSpec(host="127.0.0.1", port=8767))

    adapter.start()
    adapter.start()
    assert adapter.is_running() is True
    adapter.stop()

    assert [call[0] for call in calls] == ["popen", "terminate", "wait"]
    assert adapter.is_running() is False


def test_worker_main_once_mode_starts_and_stops_controller_without_remote_binding() -> None:
    controller = VoiceWorkerController()

    payload = run_worker_loop(controller=controller, host="127.0.0.1", port=8767, once=True)

    assert payload["host"] == "127.0.0.1"
    assert payload["status"]["lifecycle_state"] == "running"
    assert payload["status"]["local_only"] is True
    assert payload["status"]["hidden_recording_allowed"] is False
    assert controller.status().lifecycle_state == VoiceWorkerLifecycleState.STOPPED
