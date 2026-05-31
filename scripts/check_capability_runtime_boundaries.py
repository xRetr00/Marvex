from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_RUNTIME_ROOT = ROOT / "packages" / "capability_runtime"
CAPABILITY_ADAPTER_ROOT = ROOT / "packages" / "adapters" / "capabilities"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "telemetry",
)
ASSISTANT_RUNTIME_ROOT = ROOT / "packages" / "assistant_runtime"

CAPABILITY_RUNTIME_ALLOWED_IMPORTS = (
    "__future__",
    "enum",
    "packages.capability_runtime",
    "pydantic",
    "typing",
)
CAPABILITY_RUNTIME_FORBIDDEN_IMPORTS = (
    "apps",
    "os",
    "pathlib",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.local_api",
    "packages.local_service_startup",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.session_runtime",
    "packages.telemetry",
    "services",
)
ADAPTER_FORBIDDEN_IMPORTS = (
    "apps",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "openai",
    "litellm",
)
ADAPTER_REQUIRED_IMPORT = "packages.capability_runtime"
FORBIDDEN_EXECUTION_TOKENS = (
    "subprocess",
    "auto-call",
    "auto_call_allowed: Literal[True]",
    "arbitrary_server_execution_allowed: Literal[True]",
    "arbitrary_script_execution_allowed: Literal[True]",
)
LEGACY_TOKEN_EXEMPT_FILES = {
    CAPABILITY_ADAPTER_ROOT / "builtins.py": ("shell",),
    CAPABILITY_ADAPTER_ROOT / "browser.py": ("browser",),
    CAPABILITY_ADAPTER_ROOT / "browser_use.py": ("browser",),
    CAPABILITY_ADAPTER_ROOT / "playwright_mcp.py": ("browser",),
    CAPABILITY_ADAPTER_ROOT / "computer_use.py": ("shell", "browser"),
    CAPABILITY_ADAPTER_ROOT / "files.py": ("subprocess",),
    CAPABILITY_ADAPTER_ROOT / "tools" / "base.py": ("shell",),
}
ADAPTER_REAL_BACKEND_IMPORT_EXEMPT_FILES = {
    CAPABILITY_ADAPTER_ROOT / "browser_use.py": ("os", "pathlib"),
    CAPABILITY_ADAPTER_ROOT / "playwright_mcp.py": ("os",),
    CAPABILITY_ADAPTER_ROOT / "computer_use.py": ("os",),
    CAPABILITY_ADAPTER_ROOT / "files.py": ("pathlib", "subprocess"),
    CAPABILITY_ADAPTER_ROOT / "tools" / "_write_support.py": ("pathlib",),
    CAPABILITY_ADAPTER_ROOT / "tools" / "read.py": ("pathlib",),
}
ADAPTER_REQUIRED_IMPORT_EXEMPT_FILES = {
    CAPABILITY_ADAPTER_ROOT / "tools" / "_write_support.py",
}
NON_OWNER_TERMS = (
    "packages.capability_runtime",
    "packages.adapters.capabilities",
    "DeterministicFakeCapabilityAdapter",
    "CapabilityExecutionRequest",
)
ASSISTANT_FORBIDDEN_TERMS = (
    "DeterministicFakeCapabilityAdapter",
    "CapabilityExecutionRequest",
    "packages.adapters.capabilities",
    "dispatch(",
)
NON_OWNER_TERM_EXEMPT_FILES = {
    ROOT / "packages" / "core" / "orchestration" / "agentic_tools.py",
    ROOT / "packages" / "core" / "orchestration" / "tool_grounding.py",
}
REQUIRED_DOC_PHRASES = (
    "Capability Platform Foundation",
    "CapabilityRuntime owns manifests",
    "adapters cannot bypass CapabilityRuntime policy",
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


def _scan_capability_runtime(failures: list[str]) -> None:
    if not CAPABILITY_RUNTIME_ROOT.is_dir():
        failures.append("packages/capability_runtime is missing")
        return
    for path in _python_files(CAPABILITY_RUNTIME_ROOT):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, CAPABILITY_RUNTIME_FORBIDDEN_IMPORTS):
                failures.append(f"{_rel(path)} imports forbidden dependency: {module}")
            if not _matches_prefix(module, CAPABILITY_RUNTIME_ALLOWED_IMPORTS):
                failures.append(f"{_rel(path)} imports non-approved dependency: {module}")


def _scan_adapters(failures: list[str]) -> None:
    if not CAPABILITY_ADAPTER_ROOT.is_dir():
        failures.append("packages/adapters/capabilities is missing")
        return
    mcp_adapter = CAPABILITY_ADAPTER_ROOT / "mcp.py"
    for path in _python_files(CAPABILITY_ADAPTER_ROOT):
        text = path.read_text(encoding="utf-8")
        lowered = text.lower()
        if path.name != "__init__.py" and path not in ADAPTER_REQUIRED_IMPORT_EXEMPT_FILES and ADAPTER_REQUIRED_IMPORT not in text:
            failures.append(f"{_rel(path)} must import CapabilityRuntime boundary models")
        if path != mcp_adapter:
            for token in FORBIDDEN_EXECUTION_TOKENS:
                if token in LEGACY_TOKEN_EXEMPT_FILES.get(path, ()):
                    continue
                if token.lower() in lowered:
                    failures.append(f"{_rel(path)} contains forbidden execution token: {token}")
            for token in ("shell", "browser", "filesystem write"):
                if token.lower() not in lowered:
                    continue
                if token in LEGACY_TOKEN_EXEMPT_FILES.get(path, ()):
                    continue
                failures.append(f"{_rel(path)} contains forbidden execution token: {token}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module and _matches_prefix(module, ADAPTER_FORBIDDEN_IMPORTS):
                failures.append(f"{_rel(path)} imports disabled real backend dependency: {module}")
            if module in {"os", "pathlib", "subprocess"} and module not in ADAPTER_REAL_BACKEND_IMPORT_EXEMPT_FILES.get(path, ()):
                failures.append(f"{_rel(path)} imports disabled real backend dependency: {module}")


def _scan_non_owners(failures: list[str]) -> None:
    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            for term in NON_OWNER_TERMS:
                if term in text and path not in NON_OWNER_TERM_EXEMPT_FILES:
                    failures.append(f"{_rel(path)} mentions CapabilityRuntime-owned term: {term}")
    for path in _python_files(ASSISTANT_RUNTIME_ROOT):
        text = path.read_text(encoding="utf-8")
        for term in ASSISTANT_FORBIDDEN_TERMS:
            if term in text:
                failures.append(f"{_rel(path)} contains forbidden capability execution term: {term}")


def _scan_docs(failures: list[str]) -> None:
    validation = VALIDATION_GATES.read_text(encoding="utf-8") if VALIDATION_GATES.is_file() else ""
    status = PROJECT_STATUS.read_text(encoding="utf-8") if PROJECT_STATUS.is_file() else ""
    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in validation and phrase not in status:
            failures.append(f"capability docs/status missing phrase: {phrase}")
    if "check_capability_runtime_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_capability_runtime_boundaries.py")


def main() -> int:
    failures: list[str] = []
    _scan_capability_runtime(failures)
    _scan_adapters(failures)
    _scan_non_owners(failures)
    _scan_docs(failures)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS capability runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
