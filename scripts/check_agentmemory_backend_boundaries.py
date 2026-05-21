"""Boundary gate for the agentmemory external-daemon memory backend.

Asserts:
1. Backend is disabled by default (MemoryBackendConfig.backend == "local").
2. No raw secret/token is persisted by the config layer.
3. agentmemory_backend.py uses urllib for HTTP — no requests/httpx imports.
4. agentmemory_backend.py does not import packages.memory_tree_runtime
   (Memory Tree pipeline is not coupled to the agentmemory backend).
5. The adapter lives in packages/adapters/memory/ — not inside
   packages/memory_runtime (preserving the original local store boundary).
6. Only stdlib http is used for tests (no real network calls in test files).
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_DIR = ROOT / "packages" / "adapters" / "memory"
CONFIG_FILE = ADAPTER_DIR / "config.py"
BACKEND_FILE = ADAPTER_DIR / "agentmemory_backend.py"
MEMORY_RUNTIME_DIR = ROOT / "packages" / "memory_runtime"
MEMORY_TREE_DIR = ROOT / "packages" / "memory_tree_runtime"
TESTS_DIR = ROOT / "tests" / "adapters" / "memory"

# Imports that must NOT appear in the backend (would add a hard dependency).
FORBIDDEN_HTTP_IMPORTS = ("requests", "httpx", "aiohttp")
# The Memory Tree pipeline must not be coupled to the agentmemory backend.
FORBIDDEN_BACKEND_IMPORTS = ("packages.memory_tree_runtime",)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _collect_imports(path: Path) -> list[str]:
    """Return all top-level module names imported by a Python file."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
    return modules


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(
        module == prefix or module.startswith(f"{prefix}.")
        for prefix in prefixes
    )


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_files_exist(failures: list[str]) -> None:
    for required in (CONFIG_FILE, BACKEND_FILE):
        if not required.exists():
            failures.append(f"required file missing: {_rel(required)}")


def _check_default_backend_is_local(failures: list[str]) -> None:
    if not CONFIG_FILE.exists():
        return
    text = CONFIG_FILE.read_text(encoding="utf-8")
    if '_DEFAULT_BACKEND: MemoryBackendKind = "local"' not in text and \
            "_DEFAULT_BACKEND = \"local\"" not in text:
        failures.append(
            "config.py must declare _DEFAULT_BACKEND = 'local' "
            "(agentmemory backend must be disabled by default)"
        )
    if "is_agentmemory_enabled" not in text:
        failures.append(
            "config.py must expose is_agentmemory_enabled property "
            "so callers can guard agentmemory code paths"
        )


def _check_no_forbidden_http_libs(failures: list[str]) -> None:
    if not BACKEND_FILE.exists():
        return
    imports = _collect_imports(BACKEND_FILE)
    for module in imports:
        for forbidden in FORBIDDEN_HTTP_IMPORTS:
            if _matches(module, (forbidden,)):
                failures.append(
                    f"{_rel(BACKEND_FILE)} must use stdlib urllib, "
                    f"not {forbidden!r} (found import: {module!r})"
                )


def _check_stdlib_urllib_used(failures: list[str]) -> None:
    if not BACKEND_FILE.exists():
        return
    text = BACKEND_FILE.read_text(encoding="utf-8")
    if "urllib" not in text:
        failures.append(
            f"{_rel(BACKEND_FILE)} must use stdlib urllib for HTTP requests"
        )


def _check_memory_tree_not_coupled(failures: list[str]) -> None:
    if not BACKEND_FILE.exists():
        return
    imports = _collect_imports(BACKEND_FILE)
    for module in imports:
        if _matches(module, FORBIDDEN_BACKEND_IMPORTS):
            failures.append(
                f"{_rel(BACKEND_FILE)} must not import packages.memory_tree_runtime "
                f"(Memory Tree pipeline must remain decoupled from agentmemory backend)"
            )


def _check_no_raw_secret_persistence(failures: list[str]) -> None:
    for path in _python_files(ADAPTER_DIR):
        text = path.read_text(encoding="utf-8")
        rel = _rel(path)
        if "raw_transcript_persisted: Literal[True]" in text:
            failures.append(f"{rel} sets raw_transcript_persisted to True")
        if "raw_token_persisted: Literal[True]" in text:
            failures.append(f"{rel} sets raw_token_persisted to True")
        if "raw_credentials_persisted: Literal[True]" in text:
            failures.append(f"{rel} sets raw_credentials_persisted to True")


def _check_memory_runtime_not_modified(failures: list[str]) -> None:
    """The original memory_runtime package must not import the agentmemory adapter."""
    for path in _python_files(MEMORY_RUNTIME_DIR):
        imports = _collect_imports(path)
        for module in imports:
            if _matches(module, ("packages.adapters.memory",)):
                failures.append(
                    f"{_rel(path)} imports packages.adapters.memory — "
                    "the local memory_runtime must not depend on the agentmemory adapter"
                )


def _check_loopback_warn_present(failures: list[str]) -> None:
    if not BACKEND_FILE.exists():
        return
    text = BACKEND_FILE.read_text(encoding="utf-8")
    if "_is_loopback_url" not in text and "loopback" not in text.lower():
        failures.append(
            f"{_rel(BACKEND_FILE)} must include loopback detection and "
            "warn on plaintext non-loopback HTTP"
        )


def _check_tests_use_stub_not_real_network(failures: list[str]) -> None:
    for path in _python_files(TESTS_DIR):
        imports = _collect_imports(path)
        for module in imports:
            if _matches(module, FORBIDDEN_HTTP_IMPORTS):
                failures.append(
                    f"{_rel(path)} test file imports {module!r}; "
                    "tests must use the in-process stub server, not real HTTP clients"
                )


def _check_default_config_function_exists(failures: list[str]) -> None:
    if not CONFIG_FILE.exists():
        return
    text = CONFIG_FILE.read_text(encoding="utf-8")
    if "def default_memory_backend_config" not in text:
        failures.append(
            "config.py must expose default_memory_backend_config() "
            "returning a local-backend config"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    failures: list[str] = []

    _check_files_exist(failures)
    _check_default_backend_is_local(failures)
    _check_no_forbidden_http_libs(failures)
    _check_stdlib_urllib_used(failures)
    _check_memory_tree_not_coupled(failures)
    _check_no_raw_secret_persistence(failures)
    _check_memory_runtime_not_modified(failures)
    _check_loopback_warn_present(failures)
    _check_tests_use_stub_not_real_network(failures)
    _check_default_config_function_exists(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS agentmemory backend boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
