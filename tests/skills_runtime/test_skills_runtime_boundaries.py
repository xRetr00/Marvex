from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_RUNTIME = ROOT / "packages" / "skills_runtime"
FORBIDDEN_IMPORTS = (
    "apps",
    "os",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "packages.core",
    "packages.local_api",
    "packages.local_service_startup",
    "packages.provider_runtime",
    "packages.runtime_composition",
    "packages.telemetry",
    "packages.assistant_runtime",
    "packages.memory_runtime",
    "packages.session_runtime",
    "packages.adapters.capabilities.mcp",
    "services",
)
FORBIDDEN_TEXT = (
    "exec(",
    "eval(",
    "subprocess",
    "pip install",
    "git clone",
    "http://",
    "https://",
    "raw_prompt_persisted=True",
    "raw_transcript_persisted=True",
    "arbitrary_script_execution_allowed: Literal[True]",
)


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


def test_skills_runtime_boundary_stays_isolated_from_execution_and_other_runtime_owners() -> None:
    assert SKILLS_RUNTIME.is_dir()
    for path in sorted(SKILLS_RUNTIME.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_TEXT:
            assert token not in text, f"{path.relative_to(ROOT)} contains {token}"
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module:
                message = f"{path.relative_to(ROOT)} imports {module}"
                assert not _matches_prefix(module, FORBIDDEN_IMPORTS), message
