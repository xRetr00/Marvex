"""Guard the wake-word default threshold (docs/TODO/04 — wake reliability).

sherpa-onnx KeywordSpotter uses a low probability-style threshold (~0.25).
The old 0.72 default made "Hey Marvex" effectively never fire. This test
pins the default low so it can't silently regress to a strict value.
"""

from packages.voice_worker_runtime import VoiceWorkerConfig


def test_default_wakeword_threshold_is_sensitive():
    cfg = VoiceWorkerConfig.default()
    assert cfg.wakeword.threshold <= 0.3, (
        "wake-word threshold default too strict; sherpa-onnx KWS expects ~0.25"
    )


def test_default_phrase_is_hey_marvex():
    cfg = VoiceWorkerConfig.default()
    assert cfg.wakeword.phrase == "Hey Marvex"
