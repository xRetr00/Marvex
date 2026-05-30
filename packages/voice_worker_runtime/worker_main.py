from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from collections.abc import Callable
from typing import Any, TextIO

from .controller import VoiceWorkerController
from .models import VoiceWorkerCommand, VoiceWorkerErrorEnvelope


def run_worker_loop(
    *,
    controller: VoiceWorkerController,
    host: str,
    port: int,
    once: bool = False,
    should_stop: Callable[[], bool] | None = None,
    sleep_seconds: float = 1.0,
) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("voice worker host must be loopback-only")
    result = controller.handle(VoiceWorkerCommand(command="start", command_id="voice-worker-main-start"))
    payload = {"host": host, "port": port, "status": result.status.safe_projection()}
    if once:
        controller.handle(VoiceWorkerCommand(command="stop", command_id="voice-worker-main-stop"))
        return payload
    stop = should_stop or (lambda: False)
    try:
        while not stop():
            time.sleep(sleep_seconds)
            _tick_wakeword_if_active(controller)
    except KeyboardInterrupt:
        pass
    finally:
        controller.handle(VoiceWorkerCommand(command="stop", command_id="voice-worker-main-stop"))
    return payload


def run_worker_contract_loop(
    *,
    controller: VoiceWorkerController,
    host: str,
    port: int,
    input_stream: TextIO,
    output_stream: TextIO,
) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("voice worker host must be loopback-only")
    lock = threading.RLock()
    stop_event = threading.Event()

    def wake_loop() -> None:
        # Continuous wake-word listening over ONE persistent mic stream. The
        # streaming zipformer needs gap-free audio; the old per-tick sd.rec
        # windows (with gaps + device reopening) corrupted its chunked state so
        # "Hey Marvex" never matched. We wait until the worker is started, then
        # run a single continuous capture+detect+command loop. Audio reads are
        # lock-free; the lock is taken only briefly around detection/capture.
        while not stop_event.wait(0.2):
            if _supervisor_started(controller):
                break
        if stop_event.is_set():
            return
        capture = _build_continuous_capture(controller)
        if capture is None:
            _write_tick_telemetry({"event": "wake_listen", "detected": False, "reason_code": "no_real_microphone"})
            return
        _write_tick_telemetry({"event": "wake_listen", "detected": False, "reason_code": "continuous_capture_started"})
        try:
            controller.run_wake_listen_loop(
                capture=capture,
                should_stop=stop_event.is_set,
                lock=lock,
                on_diagnostic=_write_loop_diagnostic,
            )
        except Exception as exc:  # never let the wake loop kill the worker
            _write_tick_telemetry({"event": "wake_listen_error", "detected": False, "reason_code": type(exc).__name__})

    tick_thread = threading.Thread(target=wake_loop, name="marvex-voice-wake-listen", daemon=True)
    tick_thread.start()
    try:
        with lock:
            final_status: dict[str, Any] = controller.status().safe_projection()
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line:
                continue
            command_name = ""
            try:
                payload = json.loads(line)
                command_name = str(payload.get("command", "")) if isinstance(payload, dict) else ""
                command = VoiceWorkerCommand.model_validate(payload)
                with lock:
                    result = controller.handle(command)
                    response = result.safe_projection()
                    final_status = result.status.safe_projection()
            except Exception:
                trace_id = _safe_payload_text(payload, "trace_id", fallback="trace-voice-worker-invalid") if isinstance(payload, dict) else "trace-voice-worker-invalid"
                command_id = _safe_payload_text(payload, "command_id", fallback="voice-worker-command-invalid") if isinstance(payload, dict) else "voice-worker-command-invalid"
                response = {
                    "schema_version": "1",
                    "trace_id": trace_id,
                    "command_id": command_id,
                    "error": VoiceWorkerErrorEnvelope.safe_error(
                        trace_id=trace_id,
                        reason_code="voice_worker_command_invalid",
                        message="Voice worker command validation failed.",
                    ).model_dump(mode="json"),
                    "raw_audio_persisted": False,
                    "raw_transcript_persisted": False,
                }
            output_stream.write(json.dumps(response, sort_keys=True) + "\n")
            output_stream.flush()
            if isinstance(response, dict) and response.get("command_id") and command_name == "stop":
                break
    finally:
        stop_event.set()
        tick_thread.join(timeout=2.0)
    return {"host": host, "port": port, "status": final_status}


def _tick_wakeword_if_active(controller: VoiceWorkerController) -> dict[str, object] | None:
    status = controller.status()
    if status.process_started and status.wakeword_supervisor_status.get("started") is True:
        return controller.tick_wakeword_supervisor().safe_projection()
    return None


def _supervisor_started(controller: VoiceWorkerController) -> bool:
    try:
        status = controller.status()
        return bool(status.process_started) and status.wakeword_supervisor_status.get("started") is True
    except Exception:
        return False


def _build_continuous_capture(controller: VoiceWorkerController):
    """Build a continuous mic capture from the controller's real audio device.

    Returns None when the worker is on the FakeLocalAudioAdapter (no real mic),
    in which case wake word can't work and we say so via telemetry instead of
    silently never detecting.
    """

    from packages.voice_worker_runtime.audio import SoundDeviceAudioAdapter
    from packages.voice_worker_runtime.continuous_capture import SoundDeviceContinuousCapture

    if not isinstance(getattr(controller, "audio", None), SoundDeviceAudioAdapter):
        return None
    cfg = controller.config
    device = cfg.audio.input_device_id
    resolved_device = int(device) if isinstance(device, str) and device.isdigit() else device
    return SoundDeviceContinuousCapture(
        sample_rate=cfg.audio.sample_rate,
        channels=cfg.audio.channel_count,
        frame_ms=cfg.audio.frame_duration_ms,
        device=resolved_device,
    )


def _write_tick_telemetry(tick: dict[str, object]) -> None:
    # Preserve the caller's event name and reason_code: forcing every line to
    # "wakeword_supervisor_tick" and dropping reason_code made the field logs
    # useless for triaging "wake word never triggers". Only raw audio/transcript
    # content is withheld (privacy); diagnostic metadata is kept.
    safe = {
        "event": tick.get("event", "wakeword_supervisor_tick"),
        "tick_count": tick.get("tick_count"),
        "lifecycle_state": tick.get("lifecycle_state"),
        "detected": tick.get("detected"),
        "exact_blocker": tick.get("exact_blocker"),
        "reason_code": tick.get("reason_code"),
        "raw_audio_persisted": False,
        "raw_transcript_persisted": False,
    }
    try:
        sys.stderr.write(json.dumps(safe, sort_keys=True) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _write_loop_diagnostic(payload: dict[str, object]) -> None:
    # Diagnostic sink for the continuous wake/listen loop. The loop is in the
    # runtime package (which must not touch stderr directly); the worker owns
    # process I/O, so it injects this callback. We never emit raw audio or
    # transcript text - only counts, confidences and reason codes.
    safe: dict[str, object] = {"raw_audio_persisted": False, "raw_transcript_persisted": False}
    for key in (
        "event",
        "reason_code",
        "phrase",
        "threshold",
        "frames_per_decode",
        "frames_read",
        "decodes",
        "detections",
        "confidence",
        "last_confidence",
        "last_reason_code",
        "audio_rms",
        "audio_rms_peak",
        "keywords_file_loaded",
        "keywords_source",
        "keywords_preview",
        "raw_keywords_preview",
        "reason",
    ):
        if key in payload:
            safe[key] = payload[key]
    try:
        sys.stderr.write(json.dumps(safe, sort_keys=True) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _safe_payload_text(payload: dict[str, Any], key: str, *, fallback: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        return fallback
    if not all(character.isalnum() or character in ".:-_" for character in value):
        return fallback
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Marvex local voice worker runtime")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--jsonl", action="store_true")
    args = parser.parse_args()
    controller = VoiceWorkerController()
    if args.jsonl:
        payload = run_worker_contract_loop(controller=controller, host=args.host, port=args.port, input_stream=__import__("sys").stdin, output_stream=__import__("sys").stdout)
    else:
        payload = run_worker_loop(controller=controller, host=args.host, port=args.port, once=args.once)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
