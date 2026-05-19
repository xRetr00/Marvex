from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORY_TREE = ROOT / "packages" / "memory_tree_runtime"
CONNECTOR_RUNTIME = ROOT / "packages" / "connector_runtime"
CONTROL_API = ROOT / "packages" / "control_plane_api"
FRONTEND = ROOT / "apps" / "control_plane_web" / "src"
RUN_ALL = ROOT / "scripts" / "run_all_checks.py"
VALIDATION = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
GOVERNANCE = ROOT / "docs" / "GOVERNANCE_CLASSIFICATION.md"

ALLOWED_MEMORY_IMPORTS = (
    "__future__",
    "dataclasses",
    "datetime",
    "enum",
    "hashlib",
    "json",
    "math",
    "pathlib",
    "packages.connector_runtime",
    "packages.memory_tree_runtime",
    "pydantic",
    "re",
    "sqlite3",
    "typing",
)
ALLOWED_CONNECTOR_IMPORTS = (
    "__future__",
    "datetime",
    "enum",
    "pydantic",
    "typing",
)
FORBIDDEN_IMPORTS = (
    "apps",
    "httpx",
    "requests",
    "os",
    "subprocess",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "services",
)
REQUIRED_MEMORY_TERMS = (
    "CanonicalMemoryDocument",
    "MemoryChunk",
    "SQLiteMemoryTreeIndex",
    "MemoryImportanceScore",
    "SourceMemoryTree",
    "TopicMemoryTree",
    "GlobalMemoryTree",
    "EvidenceLink",
    "MemoryTreeRuntime",
)
REQUIRED_CONNECTOR_TERMS = (
    "ConnectorManifest",
    "OAuthConnectionRef",
    "AutoFetchPolicy",
    "SourceSyncMode",
    "ConnectorSyncRequest",
    "raw_token_persisted: Literal[False]",
)
REQUIRED_CONTROL_TERMS = (
    "/connectors",
    "/sources",
    "/autofetch",
    "/memory/tree/search",
    "/memory/tree/source/",
    "/memory/tree/topic/",
    "/memory/tree/daily/",
    "/memory/tree/scoring",
)
REQUIRED_FRONTEND_TERMS = (
    "Connectors",
    "Memory Sources",
    "Auto-Fetch",
    "Memory Trees",
)
FORBIDDEN_TEXT = (
    "send_email",
    "post_message",
    "chat.postMessage",
    "messages.send",
    "raw_token_persisted: Literal[True]",
    "raw_credentials_persisted: Literal[True]",
    "auto_fetch_default_enabled: Literal[True]",
    "account_action_allowed: Literal[True]",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file()) if root.exists() else []


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _scan_imports(root: Path, allowed: tuple[str, ...], failures: list[str]) -> None:
    for path in _python_files(root):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches(module, FORBIDDEN_IMPORTS):
                failures.append(f"{rel} imports forbidden dependency: {module}")
            if not _matches(module, allowed):
                failures.append(f"{rel} imports non-approved dependency: {module}")


def main() -> int:
    failures: list[str] = []
    memory_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(MEMORY_TREE))
    connector_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CONNECTOR_RUNTIME))
    control_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CONTROL_API))
    frontend_text = "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND.rglob("*.tsx") if path.is_file())

    for term in REQUIRED_MEMORY_TERMS:
        if term not in memory_text:
            failures.append(f"memory tree runtime missing required term: {term}")
    for term in REQUIRED_CONNECTOR_TERMS:
        if term not in connector_text:
            failures.append(f"connector runtime missing required term: {term}")
    for term in REQUIRED_CONTROL_TERMS:
        if term not in control_text:
            failures.append(f"control plane missing memory tree connector endpoint term: {term}")
    for term in REQUIRED_FRONTEND_TERMS:
        if term not in frontend_text:
            failures.append(f"frontend missing memory tree connector view term: {term}")
    for token in FORBIDDEN_TEXT:
        if token in memory_text or token in connector_text or token in control_text:
            failures.append(f"memory tree connector foundation contains forbidden token: {token}")

    _scan_imports(MEMORY_TREE, ALLOWED_MEMORY_IMPORTS, failures)
    _scan_imports(CONNECTOR_RUNTIME, ALLOWED_CONNECTOR_IMPORTS, failures)

    checks = RUN_ALL.read_text(encoding="utf-8")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION, PROJECT_STATUS, GOVERNANCE) if path.is_file())
    if "check_memory_tree_connector_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_memory_tree_connector_boundaries.py")
    if "OpenHuman-Style Memory Tree and Connectors Foundation" not in docs:
        failures.append("docs/status missing OpenHuman-Style Memory Tree and Connectors Foundation")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS memory tree connector boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
