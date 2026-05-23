from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "packages" / "sandbox_runtime" / "sandbox.py"

# The sandbox is a POLICY sandbox on the real local FS — never a VM/container.
FORBIDDEN_IMPORT_PREFIXES = (
    "docker",
    "microsandbox",
    "exec_sandbox",
    "codejail",
    "vagrant",
    "qemu",
    "requests",
    "httpx",
    "urllib3",
    "aiohttp",
    "socket",
)
REQUIRED_TEXT = (
    "CapabilityExecutionRequest",  # approval-gated request type
    "CapabilityResultEnvelope",
    "SandboxPolicy",
    "is_path_allowed",
    "is_command_allowed",
    "denied_path_substrings",
    "denied_command_substrings",
    "timeout=",  # shell execution must be bounded
    "raw_content_persisted",
    "raw_command_persisted",
)
FORBIDDEN_TEXT = (
    "raw_content_persisted=True",
    "raw_command_persisted=True",
    "raw_input_persisted=True",
    "raw_output_persisted=True",
)
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches_prefix(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def main() -> int:
    failures: list[str] = []
    if not SANDBOX.is_file():
        print("FAIL packages/sandbox_runtime/sandbox.py is missing")
        return 1

    text = SANDBOX.read_text(encoding="utf-8")
    for phrase in REQUIRED_TEXT:
        if phrase not in text:
            failures.append(f"sandbox.py missing required phrase: {phrase}")
    for token in FORBIDDEN_TEXT:
        if token in text:
            failures.append(f"sandbox.py contains forbidden token: {token}")

    tree = ast.parse(text, filename=str(SANDBOX))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue
        module = _module_from_import(node)
        if module and _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES):
            failures.append(f"sandbox.py imports forbidden dependency (must be policy sandbox, not VM/network): {module}")

    if "check_sandbox_boundaries.py" not in RUN_ALL_CHECKS.read_text(encoding="utf-8"):
        failures.append("scripts/run_all_checks.py must run check_sandbox_boundaries.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS sandbox boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
