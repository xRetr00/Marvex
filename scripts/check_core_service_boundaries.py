from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "packages" / "core"
CORE_SERVICE = CORE_ROOT / "service.py"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "collections.abc",
    "dataclasses",
    "datetime",
    "enum",
    "packages.assistant_runtime.provider_stage",
    "packages.contracts",
    "packages.ports",
    "packages.telemetry",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.local_api",
    "packages.process_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.voice_runtime",
    "packages.voice_worker_runtime",
    "services",
)
FORBIDDEN_CORE_SERVICE_TOKENS = (
    "packages.adapters",
    "packages.local_api",
    "packages.process_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "voice_worker",
    "voice_runtime",
    "desktop",
    "proactive",
    "memory_runtime",
    "tool_orchestration",
    "create_provider",
    "lmstudio",
    "litellm",
    "openai",
    "anthropic",
    "gemini",
    "requests",
    "httpx",
    "urllib",
    "socket",
    "subprocess",
    "0.0.0.0",
    "global ",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    if not CORE_SERVICE.exists():
        failures.append("packages/core/service.py is missing")

    for path in _python_files(CORE_ROOT):
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
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

    if CORE_SERVICE.exists():
        lowered = CORE_SERVICE.read_text(encoding="utf-8").lower()
        for token in FORBIDDEN_CORE_SERVICE_TOKENS:
            if token in lowered:
                failures.append(
                    f"packages/core/service.py contains forbidden CoreService token: {token}"
                )

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS core service boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
