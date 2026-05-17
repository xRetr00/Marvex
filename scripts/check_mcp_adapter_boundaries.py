from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MCP_ADAPTER = ROOT / "packages" / "adapters" / "capabilities" / "mcp.py"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

REQUIRED_IMPORTS = (
    "mcp",
    "mcp.types",
    "packages.capability_runtime",
)
FORBIDDEN_IMPORTS = (
    "os",
    "pathlib",
    "subprocess",
    "requests",
    "httpx",
    "socket",
    "webbrowser",
    "mcp.client.stdio",
    "mcp.client.sse",
    "mcp.client.streamable_http",
)
REQUIRED_PHRASES = (
    "ClientSession",
    "CapabilityExecutionRequest",
    "CapabilityManifest",
    "CapabilityResultEnvelope",
    "McpAllowlist",
    "arbitrary_server_execution_allowed: Literal[False]",
    "auto_call_allowed: Literal[False]",
    "raw_schema_persisted: Literal[False]",
    "raw_input_persisted=False",
    "raw_output_persisted=False",
    "blocked_dangerous_tool_name",
)
REQUIRED_DOC_PHRASES = (
    "MCP Adapter Foundation",
    "official MCP Python SDK",
    "CapabilityRuntime remains authoritative",
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


def main() -> int:
    failures: list[str] = []
    if not MCP_ADAPTER.is_file():
        failures.append("packages/adapters/capabilities/mcp.py is missing")
    else:
        text = MCP_ADAPTER.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(MCP_ADAPTER))
        imports = {module for node in ast.walk(tree) if (module := _module_from_import(node))}
        for required in REQUIRED_IMPORTS:
            if not any(module == required or module.startswith(f"{required}.") for module in imports):
                failures.append(f"MCP adapter missing required import: {required}")
        for module in imports:
            if _matches_prefix(module, FORBIDDEN_IMPORTS):
                failures.append(f"MCP adapter imports forbidden boundary dependency: {module}")
        for phrase in REQUIRED_PHRASES:
            if phrase not in text:
                failures.append(f"MCP adapter missing boundary phrase: {phrase}")
        if "create_subprocess" in text or "stdio_client" in text:
            failures.append("MCP adapter must not launch stdio servers")
        if "call_tool(" not in text:
            failures.append("MCP adapter must call tools only through the official SDK session boundary")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_mcp_adapter_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_mcp_adapter_boundaries.py")

    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (VALIDATION_GATES, PROJECT_STATUS)
        if path.is_file()
    )
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"MCP adapter docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS mcp adapter boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
