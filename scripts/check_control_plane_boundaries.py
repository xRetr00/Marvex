from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROL_API = ROOT / "packages" / "control_plane_api"
FRONTEND = ROOT / "apps" / "control_plane_web"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

CONTROL_API_ALLOWED_IMPORTS = (
    "__future__",
    "collections",
    "json",
    "packages.capability_runtime",
    "packages.contracts",
    "packages.control_plane_api",
    "packages.local_api.auth_policy",
    "pydantic",
    "typing",
)
CONTROL_API_FORBIDDEN_IMPORTS = (
    "apps",
    "os",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "packages.adapters",
    "packages.assistant_runtime",
    "packages.core",
    "packages.memory_runtime",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.session_runtime",
    "packages.skills_runtime",
    "packages.telemetry",
    "services",
)
CONTROL_API_FORBIDDEN_TEXT = (
    "execute_request(",
    "dispatch(",
    "ToolExecutionPolicy",
    "raw_payload_persisted: Literal[True]",
    "raw_input_persisted=True",
    "raw_output_persisted=True",
    "authorization_token",
    "0.0.0.0",
)
FRONTEND_FORBIDDEN_TEXT = (
    "packages/",
    "packages.",
    "from packages",
    "import packages",
    "api_key",
    "authorization_token",
    "raw_payload: true",
    "rawPayload: true",
    "executeTool",
    "directToolExecution",
)
REQUIRED_CONTROL_API_TERMS = (
    "create_control_plane_api_app",
    "InMemoryApprovalStore",
    "ApprovalSummary",
    "ControlPlaneSnapshot",
    "validate_local_bearer_token",
    "execution_started: Literal[False]",
)
REQUIRED_DOC_PHRASES = (
    "Control Plane Foundation",
    "Control Plane API must not own policy",
    "Web frontend must never import Python internals",
    "CapabilityRuntime remains authoritative",
)


def _python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def _frontend_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    suffixes = {".ts", ".tsx", ".js", ".jsx", ".json", ".html"}
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)


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


def main() -> int:
    failures: list[str] = []
    if not CONTROL_API.is_dir():
        failures.append("packages/control_plane_api is missing")
    control_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CONTROL_API))
    for term in REQUIRED_CONTROL_API_TERMS:
        if term not in control_text:
            failures.append(f"Control Plane API missing required term: {term}")
    for token in CONTROL_API_FORBIDDEN_TEXT:
        if token in control_text:
            failures.append(f"Control Plane API contains forbidden token: {token}")
    for path in _python_files(CONTROL_API):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches_prefix(module, CONTROL_API_FORBIDDEN_IMPORTS):
                failures.append(f"{_rel(path)} imports forbidden boundary: {module}")
            if not _matches_prefix(module, CONTROL_API_ALLOWED_IMPORTS):
                failures.append(f"{_rel(path)} imports non-approved dependency: {module}")

    for path in _frontend_files(FRONTEND):
        text = path.read_text(encoding="utf-8")
        for token in FRONTEND_FORBIDDEN_TEXT:
            if token in text:
                failures.append(f"{_rel(path)} contains forbidden frontend token: {token}")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_control_plane_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_control_plane_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"control plane docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS control plane boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
