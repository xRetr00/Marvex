from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "packages" / "voice_worker_runtime"
PYPROJECT = ROOT / "pyproject.toml"
CONTROL_VOICE = ROOT / "packages" / "control_plane_api" / "voice.py"
FRONTEND = ROOT / "apps" / "control_plane_web" / "src" / "views" / "ExpandedViews.tsx"
DOC = ROOT / "docs" / "VOICE_WORKER_RUNTIME.md"

FORBIDDEN_IMPORTS = (
    "packages.assistant_runtime",
    "packages.assistant_turn_integration",
    "packages.capability_runtime",
    "packages.intent_runtime",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "services",
)
REQUIRED_MARKERS = (
    "VoiceWorkerConfig",
    "VoiceWorkerStatus",
    "VoiceWorkerCommand",
    "VoiceWorkerEvent",
    "VoiceWorkerHealth",
    "VoiceWorkerLifecycleState",
    "VoiceWorkerErrorEnvelope",
    "SafeVoiceWorkerProjection",
    "hidden_auto_start_allowed: Literal[False]",
    "raw_audio_persistence_allowed: Literal[False]",
    "raw_transcript_persistence_allowed: Literal[False]",
    "phrase: str = \"Hey Marvex\"",
    "model_asset_checksum_mismatch",
    "wakeword_model_not_installed",
    "model_path_not_found_under_voice_asset_root",
    "durations_counts_only",
    "telemetry_summary",
    "loopback-only",
)
CONTROL_TERMS = (
    "/control/voice/worker",
    "test_mic",
    "test_playback",
    "test_wakeword",
    "reload_config",
    "switch_stt_backend",
    "switch_tts_backend",
    "switch_active_voice",
)


def _module(node: ast.AST) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    return None


def main() -> int:
    failures: list[str] = []
    if not WORKER.is_dir():
        failures.append("packages/voice_worker_runtime is missing")
    worker_text = "\n".join(path.read_text(encoding="utf-8") for path in WORKER.rglob("*.py")) if WORKER.is_dir() else ""
    for marker in REQUIRED_MARKERS:
        if marker not in worker_text:
            failures.append(f"voice worker runtime missing marker: {marker}")
    for path in WORKER.rglob("*.py") if WORKER.is_dir() else ():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module(node)
            if module and any(module == forbidden or module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_IMPORTS):
                failures.append(f"{path.relative_to(ROOT).as_posix()} imports forbidden owner: {module}")
    pyproject = PYPROJECT.read_text(encoding="utf-8") if PYPROJECT.is_file() else ""
    if "sounddevice==0.5.5" not in pyproject:
        failures.append("pyproject missing sounddevice==0.5.5")
    control_text = CONTROL_VOICE.read_text(encoding="utf-8") if CONTROL_VOICE.is_file() else ""
    for term in CONTROL_TERMS:
        if term not in control_text:
            failures.append(f"Control Plane voice worker API missing term: {term}")
    frontend = FRONTEND.read_text(encoding="utf-8") if FRONTEND.is_file() else ""
    if "Voice Worker Process" not in frontend or "Start Worker" not in frontend or "Test Mic Level" not in frontend or "Microphone device" not in frontend or "Playback device" not in frontend or "Apply Devices" not in frontend or "Test Wakeword" not in frontend:
        failures.append("Control Plane web missing voice worker status and controls")
    doc = DOC.read_text(encoding="utf-8") if DOC.is_file() else ""
    for phrase in ("no hidden recording", "local-only", "sounddevice==0.5.5", "not Orb", "checksum", "Loopback-only", "Worker-safe telemetry"):
        if phrase not in doc:
            failures.append(f"docs/VOICE_WORKER_RUNTIME.md missing phrase: {phrase}")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS voice worker runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
