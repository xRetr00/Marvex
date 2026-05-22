from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = ROOT / "services" / "voice_worker"
README_PATH = WORKER_ROOT / "README.md"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "argparse",
    "collections.abc",
    "dataclasses",
    "json",
    "packages.voice_worker_runtime",
    "pydantic",
    "services.voice_worker",
    "sys",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.capability_runtime",
    "packages.core",
    "packages.intent_runtime",
    "packages.local_api",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "services.core",
    "services.desktop_agent",
    "services.intent_worker",
    "services.provider_worker",
    "services.shell",
    "services.tool_worker",
)
# audio/STT/TTS library names that must NOT be imported directly from the service layer
FORBIDDEN_AUDIO_IMPORTS = (
    "sounddevice",
    "moonshine",
    "funasr",
    "kokoro",
    "piper",
)
EXPECTED_FILES = {"README.md", "__init__.py", "models.py", "controller.py", "main.py"}
CONTRACT_STATUS_PHRASE = "contract status: see docs/contract_approvals.md"


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return None
        return node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def main() -> int:
    failures: list[str] = []

    # --- structural checks ---
    if not WORKER_ROOT.is_dir():
        failures.append("services/voice_worker directory is missing")
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    entries = {path.name for path in WORKER_ROOT.iterdir() if path.name != "__pycache__"}
    missing = sorted(EXPECTED_FILES - entries)
    if missing:
        failures.append(f"services/voice_worker missing files: {missing}")

    # --- README contract-status governance gate ---
    if README_PATH.is_file():
        readme_text = README_PATH.read_text(encoding="utf-8")
        # Strip markdown backtick formatting before checking the phrase (case-insensitive)
        readme_normalized = readme_text.replace("`", "").lower()
        if CONTRACT_STATUS_PHRASE not in readme_normalized:
            failures.append(
                f"services/voice_worker/README.md missing governance phrase: 'Contract status: see docs/CONTRACT_APPROVALS.md'"
            )
    else:
        failures.append("services/voice_worker/README.md is missing")

    # --- entrypoint and JSONL loop checks (source level) ---
    main_path = WORKER_ROOT / "main.py"
    if main_path.is_file():
        main_text = main_path.read_text(encoding="utf-8")
        if "def main(" not in main_text:
            failures.append("services/voice_worker/main.py missing entrypoint main() function")
        if "--jsonl" not in main_text:
            failures.append("services/voice_worker/main.py missing --jsonl JSONL loop support")
        if "run_worker_contract_loop" not in main_text:
            failures.append("services/voice_worker/main.py does not delegate to run_worker_contract_loop")
        if "127.0.0.1" not in main_text:
            failures.append("services/voice_worker/main.py missing loopback default (127.0.0.1)")
    else:
        failures.append("services/voice_worker/main.py is missing")

    # --- controller wraps runtime, not re-implementation ---
    controller_path = WORKER_ROOT / "controller.py"
    if controller_path.is_file():
        controller_text = controller_path.read_text(encoding="utf-8")
        if "VoiceWorkerController" not in controller_text:
            failures.append(
                "services/voice_worker/controller.py must import and wrap VoiceWorkerController from packages.voice_worker_runtime"
            )
    else:
        failures.append("services/voice_worker/controller.py is missing")

    # --- import boundary checks across all Python files ---
    for path in sorted(WORKER_ROOT.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")

        # Forbidden audio/STT/TTS direct imports
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            failures.append(f"{rel} has a syntax error: {exc}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            root_module = module.split(".")[0]
            if root_module in FORBIDDEN_AUDIO_IMPORTS:
                failures.append(
                    f"{rel} directly imports audio/STT/TTS library '{root_module}' — must not re-implement audio/STT/TTS in the service layer"
                )
            if _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES):
                failures.append(f"{rel} imports forbidden dependency: {module}")
            if not _matches_prefix(module, ALLOWED_IMPORT_PREFIXES):
                failures.append(f"{rel} imports non-approved dependency: {module}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS voice worker service boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
