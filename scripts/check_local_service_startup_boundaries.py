from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTUP_ROOT = ROOT / "packages" / "local_service_startup"
FORBIDDEN_INTEGRATION_ROOTS = [
    ROOT / "packages" / "core",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "runtime_composition",
]
STARTUP_IMPORT_TOKEN = "packages.local_service_startup"

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "dataclasses",
    "datetime",
    "enum",
    "json",
    "os",
    "secrets",
    "types",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "services",
)
FORBIDDEN_SOURCE_TOKENS = (
    "open(",
    "write_text",
    "touch(",
    "unlink(",
    "os.environ",
    "getenv",
    "fastapi",
    "litestar",
    "uvicorn",
    "websocket",
    "requests",
    "httpx",
    "urllib",
    "providerrequest",
    "providerresponse",
    "create_provider",
    "run_lmstudio_responses_assistant_bridge",
    "run_fake_provider_assistant_bridge",
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


def _scan_startup_imports_and_tokens(failures: list[str]) -> None:
    paths = _python_files(STARTUP_ROOT)
    if not paths:
        failures.append("packages/local_service_startup is missing")
        return

    for path in paths:
        rel = _rel(path)
        text = _read(path)
        lowered = text.lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden startup behavior token: {token}")

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


def _scan_unapproved_integrations(failures: list[str]) -> None:
    for root in FORBIDDEN_INTEGRATION_ROOTS:
        for path in _python_files(root):
            text = _read(path)
            if STARTUP_IMPORT_TOKEN in text:
                failures.append(f"{_rel(path)} mentions {STARTUP_IMPORT_TOKEN}")


def main() -> int:
    failures: list[str] = []
    _scan_startup_imports_and_tokens(failures)
    _scan_unapproved_integrations(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS local service startup boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

