"""local-wake enrollment storage + DTW wake runner (docs: local_wake report)."""

from __future__ import annotations

import wave
from pathlib import Path

from packages.voice_runtime import AudioFrame
from packages.voice_worker_runtime import wake_enrollment
from packages.voice_worker_runtime.assets import VoiceModelInstallResult
from packages.voice_worker_runtime.local_wake_adapter import LocalWakeRunner


def _asset() -> VoiceModelInstallResult:
    return VoiceModelInstallResult(model_id="hey-marvex", backend_id="local-wake", model_kind="wakeword", status="installed")


def _frame(n_bytes: int = 3200) -> AudioFrame:
    return AudioFrame(frame_id="f", pcm=b"\x01\x02" * (n_bytes // 2), sample_rate=16_000, duration_ms=100, channel_count=1)


# --- enrollment storage -----------------------------------------------------

def test_reference_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.delenv("MARVEX_WAKE_REFERENCE_DIR", raising=False)
    assert wake_enrollment.wake_reference_dir(tmp_path).name == "wake-references"
    monkeypatch.setenv("MARVEX_WAKE_REFERENCE_DIR", str(tmp_path / "custom"))
    assert wake_enrollment.wake_reference_dir(tmp_path) == tmp_path / "custom"


def test_next_reference_path_increments(tmp_path):
    first = wake_enrollment.next_reference_path(tmp_path, phrase="Hey Marvex")
    assert first.name == "hey-marvex-01.wav"
    wake_enrollment.write_wake_reference_wav(first, [b"\x00\x00" * 100], sample_rate=16_000)
    second = wake_enrollment.next_reference_path(tmp_path, phrase="Hey Marvex")
    assert second.name == "hey-marvex-02.wav"


def test_write_and_list_references(tmp_path):
    path = wake_enrollment.next_reference_path(tmp_path, phrase="Hey Marvex")
    status = wake_enrollment.write_wake_reference_wav(path, [b"\x10\x20" * 800], sample_rate=16_000)
    assert status["bytes"] == 1600
    with wave.open(str(path), "rb") as handle:
        assert handle.getframerate() == 16_000
        assert handle.getnchannels() == 1
    assert wake_enrollment.list_wake_references(tmp_path, phrase="Hey Marvex") == [path]
    assert wake_enrollment.list_wake_references(tmp_path, phrase="other") == []


# --- LocalWakeRunner --------------------------------------------------------

def _runner_with_refs(tmp_path, compare_fn, *, window_seconds=0.4):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    wake_enrollment.write_wake_reference_wav(ref_dir / "hey-marvex-01.wav", [b"\x00\x00" * 100], sample_rate=16_000)
    return LocalWakeRunner(
        asset_manager=object(),
        reference_dir=ref_dir,
        compare_fn=compare_fn,
        window_seconds=window_seconds,
        cooldown_decodes=0,
    )


def test_no_references_is_not_ready(tmp_path):
    runner = LocalWakeRunner(asset_manager=object(), reference_dir=tmp_path / "empty", compare_fn=lambda a, b: 0.0)
    result = runner((_frame(),), _asset(), phrase="Hey Marvex", threshold=0.2)
    assert result.detected is False
    assert result.reason_code == "local_wake_no_references"


def test_unavailable_when_no_matcher(tmp_path):
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    wake_enrollment.write_wake_reference_wav(ref_dir / "hey-marvex-01.wav", [b"\x00\x00" * 100], sample_rate=16_000)
    # compare_fn=None and lwake not installed -> unavailable (not a crash).
    runner = LocalWakeRunner(asset_manager=object(), reference_dir=ref_dir, compare_fn=None)
    result = runner((_frame(),), _asset(), phrase="Hey Marvex", threshold=0.2)
    assert result.reason_code in {"local_wake_unavailable", "local_wake_buffering", "local_wake_no_references"}


def test_buffering_then_detect_below_threshold(tmp_path):
    runner = _runner_with_refs(tmp_path, compare_fn=lambda a, b: 0.05)  # very similar
    # First frame: not enough buffered -> buffering.
    first = runner((_frame(),), _asset(), phrase="Hey Marvex", threshold=0.2)
    assert first.reason_code == "local_wake_buffering"
    # Feed more frames to fill >= half the window, then it should detect.
    detected = None
    for _ in range(6):
        detected = runner((_frame(),), _asset(), phrase="Hey Marvex", threshold=0.2)
        if detected.detected:
            break
    assert detected is not None and detected.detected is True


def test_no_detection_when_distance_above_threshold(tmp_path):
    runner = _runner_with_refs(tmp_path, compare_fn=lambda a, b: 0.9)  # dissimilar
    result = None
    for _ in range(6):
        result = runner((_frame(),), _asset(), phrase="Hey Marvex", threshold=0.2)
    assert result is not None and result.detected is False
    assert result.reason_code == "local_wake_below_threshold"
