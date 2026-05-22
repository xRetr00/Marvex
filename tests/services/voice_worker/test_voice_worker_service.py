from __future__ import annotations

import io
import json
from pathlib import Path

from packages.voice_worker_runtime.models import VoiceWorkerLifecycleState
from packages.voice_worker_runtime.worker_main import run_worker_contract_loop
from packages.voice_worker_runtime.controller import VoiceWorkerController
from services.voice_worker.controller import VoiceWorkerServiceController
from services.voice_worker.models import SERVICE_NAME, SERVICE_VERSION, VoiceWorkerServiceConfig


ROOT = Path(__file__).resolve().parents[3]


# ---- helpers ----

def _run_jsonl(commands: list[dict[str, object]]) -> list[dict[str, object]]:
    """Drive run_worker_contract_loop with a StringIO buffer and return parsed responses."""
    input_text = "".join(json.dumps(cmd) + "\n" for cmd in commands)
    output_buf = io.StringIO()
    controller = VoiceWorkerController()
    run_worker_contract_loop(
        controller=controller,
        host="127.0.0.1",
        port=8767,
        input_stream=io.StringIO(input_text),
        output_stream=output_buf,
    )
    output_buf.seek(0)
    return [json.loads(line) for line in output_buf if line.strip()]


# ---- service structure ----

def test_voice_worker_service_has_expected_files() -> None:
    service_root = ROOT / "services" / "voice_worker"
    entries = {p.name for p in service_root.iterdir() if p.name != "__pycache__"}

    assert {"README.md", "__init__.py", "models.py", "controller.py", "main.py"}.issubset(entries)


def test_voice_worker_readme_contains_contract_status_line() -> None:
    readme = (ROOT / "services" / "voice_worker" / "README.md").read_text(encoding="utf-8")
    # Strip backtick markdown formatting before checking (README uses `docs/CONTRACT_APPROVALS.md`)
    readme_normalized = readme.replace("`", "").lower()

    assert "contract status: see docs/contract_approvals.md" in readme_normalized


# ---- service controller ----

def test_service_controller_wraps_runtime_and_reports_lifecycle() -> None:
    controller = VoiceWorkerServiceController(config=VoiceWorkerServiceConfig())

    status_before = controller.status()
    assert status_before.state == VoiceWorkerLifecycleState.STOPPED.value

    start_result = controller.start(trace_id="trace-svc-start")
    assert start_result.ok is True
    assert start_result.command == "start"
    assert start_result.state == VoiceWorkerLifecycleState.RUNNING.value

    stop_result = controller.stop(trace_id="trace-svc-stop")
    assert stop_result.ok is True
    assert stop_result.state == VoiceWorkerLifecycleState.STOPPED.value


def test_service_controller_health_has_no_raw_audio_flag() -> None:
    controller = VoiceWorkerServiceController()
    health = controller.health()
    serialized = json.dumps(health.model_dump(mode="json")).lower()

    assert health.hidden_recording_allowed is False
    assert health.local_only is True
    assert "raw_audio_persisted\": true" not in serialized


def test_service_controller_version_returns_worker_id() -> None:
    controller = VoiceWorkerServiceController()
    version = controller.version()

    assert version.worker == "local-voice-worker"
    assert version.worker_version == SERVICE_VERSION


def test_service_controller_metadata_never_persists_audio_or_transcript() -> None:
    controller = VoiceWorkerServiceController()
    result = controller.start(trace_id="trace-svc-safety")
    serialized = json.dumps(result.model_dump(mode="json")).lower()

    assert result.metadata.get("raw_audio_persisted") is False
    assert result.metadata.get("raw_transcript_persisted") is False
    assert "raw_audio_persisted\": true" not in serialized
    assert "raw_transcript_persisted\": true" not in serialized


# ---- JSONL contract loop (via runtime) ----

def test_jsonl_start_stop_lifecycle() -> None:
    responses = _run_jsonl([
        {"command": "start", "command_id": "cmd-start", "trace_id": "trace-jsonl"},
        {"command": "pause", "command_id": "cmd-pause", "trace_id": "trace-jsonl"},
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-jsonl"},
    ])

    assert len(responses) == 3
    start_r, pause_r, stop_r = responses

    # start
    assert start_r["command_id"] == "cmd-start"
    assert start_r["status"]["lifecycle_state"] == "running"

    # pause (proves status snapshot in each result)
    assert pause_r["command_id"] == "cmd-pause"
    assert pause_r["status"]["lifecycle_state"] == "paused"

    # stop
    assert stop_r["command_id"] == "cmd-stop"
    assert stop_r["status"]["lifecycle_state"] == "stopped"


def test_jsonl_safe_projection_never_contains_raw_audio_or_transcript() -> None:
    responses = _run_jsonl([
        {"command": "start", "command_id": "cmd-start", "trace_id": "trace-safety"},
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-safety"},
    ])

    serialized = json.dumps(responses).lower()
    # No raw_audio_persisted or raw_transcript_persisted flag should ever be True
    assert '"raw_audio_persisted": true' not in serialized
    assert '"raw_transcript_persisted": true' not in serialized
    # Each response event should have the safe flags
    for response in responses:
        event = response.get("event") or {}
        assert event.get("raw_audio_persisted") is False
        assert event.get("raw_transcript_persisted") is False


def test_jsonl_health_command_reports_lifecycle() -> None:
    responses = _run_jsonl([
        {"command": "start", "command_id": "cmd-start", "trace_id": "trace-health"},
        {"command": "health", "command_id": "cmd-health", "trace_id": "trace-health"},
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-health"},
    ])

    health_r = responses[1]
    assert health_r["command_id"] == "cmd-health"
    assert health_r["status"]["lifecycle_state"] == "running"
    assert health_r["status"]["process_started"] is True


def test_jsonl_version_command_reports_worker_id() -> None:
    responses = _run_jsonl([
        {"command": "version", "command_id": "cmd-version", "trace_id": "trace-version"},
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-version"},
    ])

    version_r = responses[0]
    assert version_r["command_id"] == "cmd-version"
    assert "version" in version_r["event"]["summary"]
    assert version_r["event"]["summary"]["version"]["worker"] == "local-voice-worker"


def test_jsonl_invalid_command_returns_error_envelope() -> None:
    responses = _run_jsonl([
        {"command": "not_a_real_command", "command_id": "cmd-bad", "trace_id": "trace-bad"},
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-bad"},
    ])

    error_r = responses[0]
    assert "error" in error_r
    assert error_r["error"] is not None
    assert error_r["raw_audio_persisted"] is False
    assert error_r["raw_transcript_persisted"] is False


def test_jsonl_loop_terminates_on_stop() -> None:
    """The JSONL loop must stop reading after a stop command."""
    responses = _run_jsonl([
        {"command": "stop", "command_id": "cmd-stop", "trace_id": "trace-term"},
        # These lines should never be processed:
        {"command": "start", "command_id": "cmd-after-stop", "trace_id": "trace-term"},
    ])

    # Only the stop response should be present
    assert len(responses) == 1
    assert responses[0]["command_id"] == "cmd-stop"


def test_loopback_host_is_enforced() -> None:
    controller = VoiceWorkerController()
    try:
        run_worker_contract_loop(
            controller=controller,
            host="0.0.0.0",
            port=8767,
            input_stream=io.StringIO(""),
            output_stream=io.StringIO(),
        )
    except ValueError as exc:
        assert "loopback" in str(exc).lower()
    else:
        raise AssertionError("expected non-loopback host to be rejected")
