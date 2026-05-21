from __future__ import annotations

"""
Boundary gate: connector auto-fetch scheduler.

Asserts:
  - auto-fetch is disabled by default (manifest + config + policy)
  - no raw account content / credentials / token persistence
  - no live network call paths reachable without explicit enable
  - errors swallowed (never crash the scheduler)
  - derived-safe ingest only (raw_payload_persisted / raw_credentials_persisted = False)
  - KVStore protocol exists for injectable persistence
  - FetchClient is injectable (no hard-coded network import in connector_runtime)
  - connector_runtime import boundary still clean (no forbidden stdlib I/O)
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONNECTOR_RUNTIME = ROOT / "packages" / "connector_runtime"
ADAPTERS_CONNECTORS = ROOT / "packages" / "adapters" / "connectors"
SCHEDULER_ADAPTER = ADAPTERS_CONNECTORS / "scheduler.py"
GITHUB_ADAPTER = ADAPTERS_CONNECTORS / "github_connector.py"
AUTO_FETCH_MODELS = CONNECTOR_RUNTIME / "auto_fetch_scheduler.py"
RUNTIME_PY = CONNECTOR_RUNTIME / "runtime.py"
RUN_ALL = ROOT / "scripts" / "run_all_checks.py"

# Imports that must NOT appear in packages/connector_runtime/*.py
FORBIDDEN_CONNECTOR_IMPORTS = (
    "json",
    "hashlib",
    "sqlite3",
    "pathlib",
    "logging",
    "os",
    "subprocess",
    "httpx",
    "requests",
    "urllib",
    "http",
    "socket",
    "asyncio",
    "threading",
)

# Terms that must appear in the scheduler models module
REQUIRED_SCHEDULER_TERMS = (
    "auto_fetch_enabled: bool = False",
    "KVStore",
    "FetchedPage",
    "ProviderSyncConfig",
    "ConnectionSyncState",
    "SchedulerTickStatus",
    "SchedulerTickResult",
    "raw_credentials_persisted: Literal[False]",
    "raw_payload_persisted: Literal[False]",
)

# Terms that must appear in the adapter scheduler
REQUIRED_ADAPTER_TERMS = (
    "AutoFetchScheduler",
    "SKIPPED_DISABLED",
    "ERROR_SWALLOWED",
    "except Exception",  # error-swallowing pattern
    "_save_state",
    "_load_state",
    "ingest_callback",
)

# Terms that must appear in the github connector
REQUIRED_GITHUB_TERMS = (
    "auto_fetch_enabled=False",
    "raw_credentials_persisted",
    "raw_token_persisted",
    "make_fake_fetch_client",
    "HttpGetFn",
)

# Forbidden text in any connector_runtime or adapter file
FORBIDDEN_TOKENS = (
    "raw_token_persisted: Literal[True]",
    "raw_credentials_persisted: Literal[True]",
    "raw_payload_persisted: Literal[True]",
    "auto_fetch_default_enabled: Literal[True]",
    "account_action_allowed: Literal[True]",
    "raw_content_persisted: Literal[True]",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file()) if root.exists() else []


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _scan_connector_runtime_imports(failures: list[str]) -> None:
    """Connector_runtime must not import any I/O or network stdlib."""
    for path in _python_files(CONNECTOR_RUNTIME):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module is None:
                continue
            for forbidden in FORBIDDEN_CONNECTOR_IMPORTS:
                if module == forbidden or module.startswith(f"{forbidden}."):
                    failures.append(
                        f"connector_runtime import boundary violated: {rel} imports {module}"
                    )


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _check_required_terms(text: str, terms: tuple[str, ...], label: str, failures: list[str]) -> None:
    for term in terms:
        if term not in text:
            failures.append(f"{label} missing required term: {repr(term)}")


def _check_disabled_by_default(
    auto_fetch_text: str,
    models_text: str,
    github_text: str,
    failures: list[str],
) -> None:
    if "auto_fetch_enabled: bool = False" not in auto_fetch_text:
        failures.append("ProviderSyncConfig must default auto_fetch_enabled=False")
    if "auto_fetch_default_enabled: Literal[False] = False" not in models_text:
        failures.append("ConnectorManifest must declare auto_fetch_default_enabled: Literal[False]")
    if github_text and "auto_fetch_enabled=False" not in github_text:
        failures.append("GitHub connector must set auto_fetch_enabled=False by default")


def _check_no_live_network_paths(
    github_text: str,
    scheduler_text: str,
    failures: list[str],
) -> None:
    _scan_connector_runtime_imports(failures)
    if github_text:
        if "HttpGetFn" not in github_text:
            failures.append("GitHub adapter must expose an injectable HttpGetFn fetch client")
        if "make_fake_fetch_client" not in github_text:
            failures.append("GitHub adapter must provide a make_fake_fetch_client for CI/tests")
    if scheduler_text and "FetchClient" not in scheduler_text:
        failures.append("Scheduler adapter must use an injectable FetchClient")


def _check_error_swallowing(scheduler_text: str, failures: list[str]) -> None:
    if not scheduler_text:
        failures.append(f"missing scheduler adapter: {SCHEDULER_ADAPTER.relative_to(ROOT).as_posix()}")
        return
    if "except Exception" not in scheduler_text:
        failures.append("Scheduler adapter must catch-and-swallow errors (except Exception)")
    if "ERROR_SWALLOWED" not in scheduler_text:
        failures.append("Scheduler adapter must emit ERROR_SWALLOWED status on errors")


def _check_derived_safe_ingest(
    combined: str,
    scheduler_text: str,
    failures: list[str],
) -> None:
    for token in FORBIDDEN_TOKENS:
        if token in combined:
            failures.append(f"connector autofetch files contain forbidden token: {token!r}")
    lower = scheduler_text.lower()
    for term in ("raw_token_persisted: literal[true]", "raw_credentials_persisted: literal[true]"):
        if term in lower:
            failures.append(f"Scheduler KV persistence must not store credentials: {term}")


def main() -> int:
    failures: list[str] = []

    # Cache file texts once to avoid redundant reads
    auto_fetch_text = _read_file(AUTO_FETCH_MODELS)
    scheduler_text = _read_file(SCHEDULER_ADAPTER)
    github_text = _read_file(GITHUB_ADAPTER)
    models_text = _read_file(CONNECTOR_RUNTIME / "models.py")
    combined = "\n".join([auto_fetch_text, scheduler_text, github_text, _read_file(RUNTIME_PY)])

    # 1. Required files exist
    for path, label in [
        (AUTO_FETCH_MODELS, "connector_runtime/auto_fetch_scheduler.py"),
        (SCHEDULER_ADAPTER, "adapters/connectors/scheduler.py"),
        (GITHUB_ADAPTER, "adapters/connectors/github_connector.py"),
    ]:
        if not path.is_file():
            failures.append(f"missing required autofetch file: {label}")

    # 2. Required terms in each file
    _check_required_terms(auto_fetch_text, REQUIRED_SCHEDULER_TERMS, "auto_fetch_scheduler.py", failures)
    _check_required_terms(scheduler_text, REQUIRED_ADAPTER_TERMS, "scheduler.py", failures)
    _check_required_terms(github_text, REQUIRED_GITHUB_TERMS, "github_connector.py", failures)

    # 3. Disabled by default
    _check_disabled_by_default(auto_fetch_text, models_text, github_text, failures)

    # 4. No live network paths without explicit enable
    _check_no_live_network_paths(github_text, scheduler_text, failures)

    # 5. Errors swallowed
    _check_error_swallowing(scheduler_text, failures)

    # 6. Derived-safe ingest only (no forbidden tokens)
    _check_derived_safe_ingest(combined, scheduler_text, failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS connector autofetch boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
