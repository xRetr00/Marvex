from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MEMORY_RUNTIME_ROOT = ROOT / "packages" / "memory_runtime"
NON_OWNER_ROOTS = (
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "telemetry",
)

ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "collections",
    "datetime",
    "packages.contracts",
    "packages.memory_runtime",
    "pydantic",
    "typing",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "apps",
    "json",
    "os",
    "pathlib",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.local_api_client",
    "packages.local_service_startup",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.session_runtime",
    "packages.telemetry",
    "services",
    "sqlite3",
)
FORBIDDEN_SOURCE_TOKENS = (
    "embedding",
    "vector",
    "faiss",
    "chroma",
    "annoy",
    "sqlite",
    "websocket",
    "daemon",
    "supervisor",
    "provider routing",
    "model selection",
    "retry",
    "fallback",
    "tool runtime",
    "voice",
    "desktop",
    "vision",
    "proactive",
)
MEMORY_OWNER_TERMS = (
    "packages.memory_runtime",
    "CurrentProcessMemoryStore",
    "MemoryRecord",
    "MemoryWriteCandidate",
    "MemoryReadResult",
    "MemoryForgetResult",
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


def _scan_memory_runtime(failures: list[str]) -> None:
    paths = _python_files(MEMORY_RUNTIME_ROOT)
    if not paths:
        failures.append("packages/memory_runtime is missing")
        return

    for path in paths:
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in lowered:
                failures.append(f"{rel} contains forbidden memory runtime token: {token}")

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
            for term in MEMORY_OWNER_TERMS:
                if term in text:
                    failures.append(f"{rel} mentions MemoryRuntime-owned term: {term}")


def main() -> int:
    failures: list[str] = []
    _scan_memory_runtime(failures)
    _scan_non_owner_roots(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS memory runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

