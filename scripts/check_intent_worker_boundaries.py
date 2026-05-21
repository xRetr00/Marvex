from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER_ROOT = ROOT / "services" / "intent_worker"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "argparse",
    "collections.abc",
    "contextlib",
    "dataclasses",
    "datetime",
    "enum",
    "io",
    "json",
    "os",
    "packages.contracts",
    "packages.intent_runtime.models",
    "pydantic",
    "sys",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.capability_runtime",
    "packages.core",
    "packages.local_api",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.voice_runtime",
    "services.core",
    "services.desktop_agent",
    "services.provider_worker",
    "services.shell",
    "services.tool_worker",
    "services.voice_worker",
)
FORBIDDEN_TOKENS = (
    "dispatch(",
    "ProviderRequest",
    "ProviderResponse",
    "CapabilityExecutionRequest",
    "ApprovalDecision",
    "create_provider",
    "raw_input_persisted=True",
    "raw prompt",
    "0.0.0.0",
    "desktop",
    "memory_runtime",
    "proactive",
    "provider_worker",
    "tool_worker",
    "voice_worker",
)
EXPECTED_FILES = {"README.md", "__init__.py", "models.py", "controller.py", "main.py"}


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
    if not WORKER_ROOT.is_dir():
        failures.append("services/intent_worker is missing")
    else:
        entries = {path.name for path in WORKER_ROOT.iterdir() if path.name != "__pycache__"}
        missing = sorted(EXPECTED_FILES - entries)
        unexpected = sorted(entries - EXPECTED_FILES)
        if missing:
            failures.append(f"services/intent_worker missing files: {missing}")
        if unexpected:
            failures.append(f"services/intent_worker has unexpected files: {unexpected}")

        for path in sorted(WORKER_ROOT.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TOKENS:
                if token in text:
                    failures.append(f"{rel} contains forbidden token: {token}")
            tree = ast.parse(text, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Import | ast.ImportFrom):
                    continue
                module = _module_from_import(node)
                if module is None:
                    continue
                if _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES):
                    failures.append(f"{rel} imports forbidden dependency: {module}")
                if not _matches_prefix(module, ALLOWED_IMPORT_PREFIXES):
                    failures.append(f"{rel} imports non-approved dependency: {module}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS intent worker boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
