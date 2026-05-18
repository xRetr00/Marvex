from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / "packages" / "marketplace_runtime"
CONTROL_API = ROOT / "packages" / "control_plane_api"
FRONTEND = ROOT / "apps" / "control_plane_web" / "src"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

ALLOWED_IMPORTS = (
    "__future__",
    "packages.skills_runtime",
    "pydantic",
    "typing",
)
FORBIDDEN_IMPORTS = (
    "os",
    "pathlib",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "packages.adapters",
    "packages.core",
    "packages.provider_runtime",
    "packages.runtime_composition",
)
FORBIDDEN_TEXT = (
    "subprocess",
    "os.system",
    "pip install",
    "git clone",
    "install_started: Literal[True]",
    "launch_started: Literal[True]",
    "auto_execution_allowed: Literal[True]",
    "script_execution_allowed: Literal[True]",
    "remote_loading_allowed: Literal[True]",
    "raw_registry_payload_persisted: Literal[True]",
)
REQUIRED_TERMS = (
    "McpMarketplaceEntry",
    "McpAllowlistProposal",
    "SkillMarketplaceEntry",
    "MarketplaceEnablementState",
    "validate_mcp_server_manifest",
    "read_only_browse: Literal[True]",
    "install_allowed: Literal[False]",
    "auto_execution_allowed: Literal[False]",
)
REQUIRED_CONTROL_TERMS = (
    "/marketplace/mcp",
    "/marketplace/skills",
    "/memory",
    "/traces/search",
    "/policies",
    "/diagnostics",
)
REQUIRED_FRONTEND_TERMS = (
    "MCP Marketplace",
    "Skills Marketplace",
    "Memory Inspect",
    "Trace Search",
    "Tool Risk Policy",
    "Runtime Diagnostics",
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


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def main() -> int:
    failures: list[str] = []
    if not MARKETPLACE.is_dir():
        failures.append("packages/marketplace_runtime is missing")
    marketplace_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(MARKETPLACE))
    for term in REQUIRED_TERMS:
        if term not in marketplace_text:
            failures.append(f"marketplace runtime missing required term: {term}")
    for token in FORBIDDEN_TEXT:
        if token in marketplace_text:
            failures.append(f"marketplace runtime contains forbidden token: {token}")
    for path in _python_files(MARKETPLACE):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module is None:
                continue
            if _matches(module, FORBIDDEN_IMPORTS):
                failures.append(f"{_rel(path)} imports forbidden marketplace dependency: {module}")
            if not _matches(module, ALLOWED_IMPORTS):
                failures.append(f"{_rel(path)} imports non-approved marketplace dependency: {module}")
    control_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CONTROL_API))
    for term in REQUIRED_CONTROL_TERMS:
        if term not in control_text:
            failures.append(f"control plane missing marketplace/control expansion endpoint term: {term}")
    frontend_text = "\n".join(path.read_text(encoding="utf-8") for path in FRONTEND.rglob("*.tsx") if "node_modules" not in path.parts)
    for term in REQUIRED_FRONTEND_TERMS:
        if term not in frontend_text:
            failures.append(f"frontend missing expanded control-plane view term: {term}")
    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_marketplace_memory_control_plane_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_marketplace_memory_control_plane_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    if "Marketplace, Memory Backend, and Control Plane Expansion" not in docs:
        failures.append("docs/status missing Marketplace, Memory Backend, and Control Plane Expansion")
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS marketplace memory control plane boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
