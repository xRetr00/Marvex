from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_NON_ADAPTER_IMPORTS = (
    "playwright",
    "browser_use",
    "agents",
)
NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "telemetry",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "local_service_startup",
)
OWNER_MODE_RAW_PERSISTENCE_MARKERS = (
    "raw_screenshot_persisted=True",
    "raw_dom_persisted=True",
    "raw_screen_persisted=True",
    "raw_browser_payload_persisted=True",
)


def _python_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.py") if path.is_file()) if root.exists() else []


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


def test_only_tooling_adapters_can_import_browser_or_agent_sdks() -> None:
    adapter_allowlist = {
        ROOT / "packages" / "adapters" / "capabilities" / "browser.py",
        ROOT / "packages" / "adapters" / "capabilities" / "browser_use.py",
        ROOT / "packages" / "adapters" / "capabilities" / "openai_agents.py",
    }
    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and _matches_prefix(module, FORBIDDEN_NON_ADAPTER_IMPORTS):
                    assert path in adapter_allowlist, f"{path.relative_to(ROOT)} imports {module}"


def test_raw_automation_persistence_is_only_enabled_in_approved_owner_mode_modules() -> None:
    allowed = {
        ROOT / "packages" / "adapters" / "capabilities" / "browser_use.py",
        ROOT / "packages" / "adapters" / "capabilities" / "computer_use.py",
        ROOT / "packages" / "automation_runtime" / "artifacts.py",
    }
    for root in (ROOT / "packages" / "capability_runtime", ROOT / "packages" / "adapters" / "capabilities"):
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            for token in OWNER_MODE_RAW_PERSISTENCE_MARKERS:
                if token in text:
                    assert path in allowed, f"{path.relative_to(ROOT)} contains {token} outside owner-mode modules"
