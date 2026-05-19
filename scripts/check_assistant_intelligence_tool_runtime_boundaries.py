from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "packages" / "assistant_turn_integration"
BROWSER_ADAPTER = ROOT / "packages" / "adapters" / "capabilities" / "browser.py"
PROVIDER_TOOL_CALLS = ROOT / "packages" / "adapters" / "providers" / "tool_calls.py"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "assistant_runtime",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "telemetry",
)
FORBIDDEN_NON_OWNER_IMPORTS = (
    "packages.adapters.capabilities.browser",
    "packages.adapters.capabilities.mcp",
    "packages.adapters.providers.tool_calls",
)
REQUIRED_INTEGRATION_TERMS = (
    "IntentKind.MCP_NEEDED",
    "IntentKind.SKILL_NEEDED",
    "McpSdkAdapter",
    "mcp_allowlist",
    "resume_approval_request_id",
    "store.approval_store.read_decision",
    "ProviderToolCallMapper",
    "PlaywrightBrowserWorkflow",
    "MemoryReadQuery",
    "IntentKind.MEMORY_TREE_NEEDED",
    "intent_classifier",
    "_memory_tree_evidence_ref_count",
    "_memory_ref_count",
    "raw_payload_persisted: Literal[False]",
)
REQUIRED_ADAPTER_TERMS = (
    "PlaywrightBrowserWorkflow",
    "raw_page_text_persisted",
    "ProviderToolCallMapper",
    "ProviderToolCallSource",
    "raw_provider_payload_persisted: Literal[False]",
)
FORBIDDEN_TEXT = (
    "from playwright",
    "import playwright",
    "raw_payload_persisted=True",
    "raw_prompt_persisted=True",
    "raw_provider_payload_persisted=True",
    "shell",
    "subprocess",
    "0.0.0.0",
)
PROVIDER_TOOL_FORBIDDEN = (
    "CapabilityExecutionRequest",
    "CapabilityResultEnvelope",
    "call_tool(",
    "execute(",
)
REQUIRED_DOC_PHRASES = (
    "Assistant Intelligence and Tool-Using Runtime Integration",
    "Provider tool calls remain proposals",
    "allowlisted MCP live proof",
    "safe browser workflow",
    "Memory Tree evidence refs",
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


def main() -> int:
    failures: list[str] = []
    integration_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(INTEGRATION))
    adapter_text = "\n".join(path.read_text(encoding="utf-8") for path in (BROWSER_ADAPTER, PROVIDER_TOOL_CALLS) if path.is_file())

    for term in REQUIRED_INTEGRATION_TERMS:
        if term not in integration_text:
            failures.append(f"assistant intelligence integration missing term: {term}")
    for term in REQUIRED_ADAPTER_TERMS:
        if term not in adapter_text:
            failures.append(f"assistant intelligence adapters missing term: {term}")
    for token in FORBIDDEN_TEXT:
        if token in integration_text:
            failures.append(f"assistant intelligence integration contains forbidden token: {token}")
    provider_text = PROVIDER_TOOL_CALLS.read_text(encoding="utf-8") if PROVIDER_TOOL_CALLS.is_file() else ""
    for token in PROVIDER_TOOL_FORBIDDEN:
        if token in provider_text:
            failures.append(f"provider tool-call mapper must not execute tools or own result envelopes: {token}")

    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and _matches_prefix(module, FORBIDDEN_NON_OWNER_IMPORTS):
                    failures.append(f"{_rel(path)} imports adapter/tool-call owner directly: {module}")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_assistant_intelligence_tool_runtime_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_assistant_intelligence_tool_runtime_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"assistant intelligence docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS assistant intelligence tool runtime boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
