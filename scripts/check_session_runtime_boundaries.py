from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SESSION_RUNTIME_ROOT = ROOT / "packages" / "session_runtime"
NON_OWNER_ROOTS = (
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "telemetry",
)

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "collections",
    "packages.contracts",
    "packages.session_runtime",
    "pydantic",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.local_api_client",
    "packages.local_service_startup",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "services",
)
FORBIDDEN_SOURCE_TOKENS = (
    "input_text",
    "output_text",
    "raw_provider_output",
    "raw_prompt",
    "provider_payload",
    "provider_response_id",
    "api_key",
    "authorization",
    "bearer",
    "secret",
    "token",
    "vector",
    "embedding",
    "websocket",
    "daemon",
    "supervisor",
    "model_selection",
    "model selection",
    "provider routing",
    "retry",
    "fallback",
    "tool runtime",
    "voice",
    "desktop",
    "vision",
    "proactive",
)
SESSION_OWNER_TERMS = (
    "packages.session_runtime",
    "CurrentProcessSessionRegistry",
    "TurnLinkageMetadata",
    "SafeSessionProjection",
    "SafeConversationProjection",
    "build_turn_linkage_from_assistant_turn_input",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
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


def _scan_session_runtime(failures: list[str]) -> None:
    paths = _python_files(SESSION_RUNTIME_ROOT)
    if not paths:
        failures.append("packages/session_runtime is missing")
        return

    for path in paths:
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden session runtime token: {token}")

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


def _scan_non_owner_roots(failures: list[str]) -> None:
    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            rel = _rel(path)
            for term in SESSION_OWNER_TERMS:
                if term in text:
                    failures.append(f"{rel} mentions SessionRuntime-owned term: {term}")


def main() -> int:
    failures: list[str] = []
    _scan_session_runtime(failures)
    _scan_non_owner_roots(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS session runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
