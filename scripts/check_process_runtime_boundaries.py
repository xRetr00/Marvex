from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESS_RUNTIME_ROOT = ROOT / "packages" / "process_runtime"
PROCESS_RUNTIME_FILE = PROCESS_RUNTIME_ROOT / "process_runtime.py"
CORE_ROOT = ROOT / "packages" / "core"
CLI_ROOT = ROOT / "apps" / "cli"
PROVIDER_RUNTIME_ROOT = ROOT / "packages" / "provider_runtime"

PROCESS_RUNTIME_MAX_LINES = 250
PROCESS_RUNTIME_SIZE_EXEMPTION = "process runtime size justification"

ALLOWED_IMPORTS = {
    "__future__",
    "copy",
    "dataclasses",
    "datetime",
    "packages.contracts",
    "types",
    "typing",
}

FORBIDDEN_IMPORTS = [
    "packages.core",
    "packages.adapters",
    "packages.provider_runtime",
    "packages.telemetry",
    "apps",
    "services",
]

FORBIDDEN_TOKENS = [
    "http",
    "server",
    "daemon",
    "subprocess",
    "supervisor",
    "thread",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "open(",
    "Path(",
    "os.environ",
    "getenv",
    "cli",
    "provider runtime",
    "tool",
    "memory",
    "intent",
    "voice",
    "desktop",
]

PROCESS_RUNTIME_IMPORT_TOKEN = "packages.process_runtime"
CLI_PROCESS_RUNTIME_ALLOWED = {"apps/cli/main.py"}


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _is_allowed_import(module: str) -> bool:
    return module in ALLOWED_IMPORTS or any(
        module.startswith(f"{allowed}.") for allowed in ALLOWED_IMPORTS
    )


def _is_forbidden_import(module: str) -> bool:
    return module in FORBIDDEN_IMPORTS or any(
        module.startswith(f"{forbidden}.") for forbidden in FORBIDDEN_IMPORTS
    )


def _scan_process_runtime_imports(failures: list[str]) -> None:
    for path in _python_files(PROCESS_RUNTIME_ROOT):
        text = _read_text(path)
        if text is None:
            continue

        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            failures.append(f"{_rel(path)}:{exc.lineno or 1} cannot be parsed")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if _is_forbidden_import(module):
                        failures.append(f"{_rel(path)}:{node.lineno} imports forbidden module: {module}")
                    elif not _is_allowed_import(module):
                        failures.append(f"{_rel(path)}:{node.lineno} imports unapproved module: {module}")

            if isinstance(node, ast.ImportFrom):
                if node.level == 1:
                    continue

                module = node.module or ""
                if _is_forbidden_import(module):
                    failures.append(f"{_rel(path)}:{node.lineno} imports forbidden module: {module}")
                elif not _is_allowed_import(module):
                    failures.append(f"{_rel(path)}:{node.lineno} imports unapproved module: {module}")


def _scan_process_runtime_tokens(failures: list[str]) -> None:
    for path in _python_files(PROCESS_RUNTIME_ROOT):
        text = _read_text(path)
        if text is None:
            continue

        lowered = text.lower()
        for token in FORBIDDEN_TOKENS:
            if token.lower() in lowered:
                failures.append(f"{_rel(path)} contains forbidden runtime token: {token}")


def _scan_process_runtime_size(failures: list[str]) -> None:
    if not PROCESS_RUNTIME_FILE.is_file():
        return

    text = _read_text(PROCESS_RUNTIME_FILE)
    if text is None:
        return

    line_count = len(text.splitlines())
    if (
        line_count > PROCESS_RUNTIME_MAX_LINES
        and PROCESS_RUNTIME_SIZE_EXEMPTION not in text.lower()
    ):
        failures.append(
            f"{_rel(PROCESS_RUNTIME_FILE)} has {line_count} lines and exceeds process runtime max {PROCESS_RUNTIME_MAX_LINES}"
        )


def _scan_unapproved_integrations(failures: list[str]) -> None:
    for root in [CORE_ROOT, CLI_ROOT, PROVIDER_RUNTIME_ROOT]:
        for path in _python_files(root):
            text = _read_text(path)
            if text is None:
                continue
            if PROCESS_RUNTIME_IMPORT_TOKEN in text:
                rel = _rel(path)
                if root == CLI_ROOT and rel in CLI_PROCESS_RUNTIME_ALLOWED:
                    continue
                failures.append(f"{rel} mentions {PROCESS_RUNTIME_IMPORT_TOKEN}")


def main() -> int:
    failures: list[str] = []

    _scan_process_runtime_imports(failures)
    _scan_process_runtime_tokens(failures)
    _scan_process_runtime_size(failures)
    _scan_unapproved_integrations(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS process runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
