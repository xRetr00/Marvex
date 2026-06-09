from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VOICE = ROOT / "packages" / "voice_runtime"
CONTROL_APP = ROOT / "packages" / "control_plane_api" / "app.py"
CONTROL_VOICE = ROOT / "packages" / "control_plane_api" / "voice.py"
FRONTEND_APP = ROOT / "apps" / "control_plane_web" / "src" / "App.tsx"
PYPROJECT = ROOT / "pyproject.toml"
DECISION = ROOT / "docs" / "library-decisions" / "voice_runtime_backends.md"

FORBIDDEN_IMPORTS = (
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.assistant_turn_integration",
    "packages.capability_runtime",
    "packages.core",
    "packages.intent_runtime",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "services",
)
REQUIRED_VOICE_MARKERS = (
    "VoiceRuntimeConfig",
    "AudioRingBuffer",
    "TranscriptionResult",
    "SpeechSynthesisResult",
    "SherpaOnnxWakeWordAdapter",
    "SileroVadAdapter",
    "load_silero_vad",
    "WebRtcVadAdapter",
    "webrtcvad",
    "SentenceBoundaryDetector",
    "generate_sentences",
    "BargeInDetector",
    "VoicePersonalityProfile",
    "VoiceControlPlaneFacade",
)
REQUIRED_DEPENDENCIES = (
    "moonshine-voice==0.0.59",
    "funasr==1.3.1",
    "sherpa-onnx==1.13.2",
    "sherpa-onnx-core==1.13.2",
    "supertonic==1.3.1",
    "piper-tts==1.4.2",
    "stream2sentence==0.3.2",
    "silero-vad==6.2.1",
    "webrtcvad-wheels==2.0.14",
)
CONTROL_TERMS = (
    "/control/voice",
    "test_stt",
    "test_tts",
    "select_stt",
    "select_tts",
    "update_wakeword",
    "update_vad",
    "update_barge_in",
    "update_early_speech",
    "update_personality",
    "update_retention",
    "download",
    "remove",
)


def _module(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    return None


def main() -> int:
    failures: list[str] = []
    if not VOICE.is_dir():
        failures.append("packages/voice_runtime is missing")
    voice_text = "\n".join(path.read_text(encoding="utf-8") for path in VOICE.rglob("*.py")) if VOICE.is_dir() else ""
    for marker in REQUIRED_VOICE_MARKERS:
        if marker not in voice_text:
            failures.append(f"VoiceRuntime missing marker: {marker}")
    for path in VOICE.rglob("*.py") if VOICE.is_dir() else ():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module(node)
            if module and any(module == forbidden or module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_IMPORTS):
                failures.append(f"{path.relative_to(ROOT).as_posix()} imports forbidden owner: {module}")

    text_files = [path for root in ("packages", "tests", "docs", "scripts") for path in (ROOT / root).rglob("*") if path.is_file()]
    for path in text_files:
        if path.suffix.lower() in {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".pcm"}:
            failures.append(f"raw audio fixture committed: {path.relative_to(ROOT).as_posix()}")
    pyproject = PYPROJECT.read_text(encoding="utf-8") if PYPROJECT.is_file() else ""
    decision = DECISION.read_text(encoding="utf-8") if DECISION.is_file() else ""
    for dependency in REQUIRED_DEPENDENCIES:
        if dependency not in pyproject:
            failures.append(f"pyproject missing voice dependency: {dependency}")
        if dependency not in decision:
            failures.append(f"voice library decision missing dependency: {dependency}")
    control_text = (CONTROL_APP.read_text(encoding="utf-8") if CONTROL_APP.is_file() else "") + "\n" + (CONTROL_VOICE.read_text(encoding="utf-8") if CONTROL_VOICE.is_file() else "")
    for term in CONTROL_TERMS:
        if term not in control_text:
            failures.append(f"Control Plane voice API missing term: {term}")
    frontend = FRONTEND_APP.read_text(encoding="utf-8") if FRONTEND_APP.is_file() else ""
    if "Voice" not in frontend:
        failures.append("Control Plane web missing Voice view")
    if "claims_facts_without_evidence: Literal[False]" not in voice_text:
        failures.append("Early speech must encode no-fact-claims without evidence")
    if "queued_chunks_canceled" not in voice_text or "barge_in.user_speech_detected" not in voice_text:
        failures.append("Barge-in must interrupt queued/playback state")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS voice runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
