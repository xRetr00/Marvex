from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_API_ROOT = ROOT / "packages" / "local_api"
SERVICE_ROOT = ROOT / "services"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "collections.abc",
    "dataclasses",
    "packages.contracts",
    "packages.process_runtime",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "services",
)
FORBIDDEN_TOKENS = (
    "/v1/turns",
    "websocket",
    "providerrequest",
    "providerresponse",
    "turnorchestrator",
    "run_assistant_provider_stage_turn",
    "run_provider_stage_turn",
    "run_lmstudio_responses_assistant_bridge",
    "run_fake_provider_assistant_bridge",
    "create_provider",
    "providerruntimeconfig",
    "retry",
    "fallback",
    "routing",
    "session",
    "history",
    "model selection",
    "model_selection",
    "api_key",
    "apikey",
    "memory",
    "tool",
    "voice",
    "desktop",
    "vision",
    "proactive",
    "0.0.0.0",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def _scan_local_api(failures: list[str]) -> None:
    paths = _python_files(LOCAL_API_ROOT)
    if not paths:
        failures.append("packages/local_api is missing")
        return

    combined_text = "\n".join(_read(path) for path in paths)
    if 'host: str = "127.0.0.1"' not in combined_text:
        failures.append("packages/local_api must default to host 127.0.0.1")

    for path in paths:
        rel = _rel(path)
        text = _read(path)
        lowered = text.lower()
        for token in FORBIDDEN_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden local API behavior token: {token}")

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


def _scan_service_placeholders(failures: list[str]) -> None:
    if not SERVICE_ROOT.exists():
        return
    for path in SERVICE_ROOT.rglob("*"):
        if path.is_file() and path.name != "README.md":
            failures.append(f"{_rel(path)} violates README-only service placeholder policy")


def main() -> int:
    failures: list[str] = []
    _scan_local_api(failures)
    _scan_service_placeholders(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS local API boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
