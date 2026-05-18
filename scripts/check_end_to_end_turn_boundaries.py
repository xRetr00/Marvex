from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "packages" / "assistant_turn_integration"
LOCAL_API = ROOT / "packages" / "local_api"
RUNTIME_COMPOSITION = ROOT / "packages" / "runtime_composition"
CORE = ROOT / "packages" / "core"
PROVIDER_RUNTIME = ROOT / "packages" / "provider_runtime"
CONTROL_API = ROOT / "packages" / "control_plane_api"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

REQUIRED_TERMS = (
    "run_end_to_end_assistant_turn",
    "create_end_to_end_local_turn_handler",
    "EndToEndTurnStateStore",
    "classify_intent",
    "build_context_pack",
    "assemble_prompt_harness",
    "run_provider_stage_turn",
    "CapabilityExecutionRequest",
    "BuiltinToolCatalog",
    "InMemoryTraceReader",
    "ControlPlaneSnapshot",
    "raw_prompt_persisted: Literal[False]",
    "raw_context_persisted: Literal[False]",
    "raw_payload_persisted: Literal[False]",
)
ALLOWED_IMPORT_PREFIXES = (
    "__future__",
    "asyncio",
    "dataclasses",
    "json",
    "typing",
    "pydantic",
    "packages.assistant_turn_integration",
    "packages.adapters.capabilities.browser",
    "packages.adapters.capabilities.builtins",
    "packages.adapters.capabilities.mcp",
    "packages.adapters.providers.fake.fake_provider",
    "packages.adapters.providers.tool_calls",
    "packages.assistant_runtime",
    "packages.assistant_runtime.provider_stage",
    "packages.assistant_runtime.tool_orchestration",
    "packages.capability_runtime",
    "packages.capability_runtime.models",
    "packages.context_runtime",
    "packages.contracts",
    "packages.control_plane_api",
    "packages.intent_runtime",
    "packages.memory_runtime",
    "packages.prompt_harness_runtime",
    "packages.session_runtime",
    "packages.telemetry",
)
FORBIDDEN_INTEGRATION_TEXT = (
    "raw_prompt_persisted=True",
    "raw_context_persisted=True",
    "raw_payload_persisted=True",
    "raw_input_persisted=True",
    "raw_output_persisted=True",
    "subprocess",
    "os.system",
    "Path.write_text",
    "open(",
    "model router",
    "model_selection",
    "generic provider routing",
    "0.0.0.0",
)
FORBIDDEN_OWNER_IMPORTS = (
    "packages.assistant_turn_integration",
    "packages.assistant_turn_integration",
    "packages.adapters.capabilities.browser",
    "packages.adapters.capabilities.builtins",
    "packages.adapters.capabilities.mcp",
    "packages.intent_runtime",
    "packages.context_runtime",
    "packages.prompt_harness_runtime",
)
REQUIRED_DOC_PHRASES = (
    "End-to-End Assistant Turn Integration Foundation",
    "Local API owns HTTP/auth/JSON only",
    "CapabilityRuntime owns policy/approval/dispatch",
    "IntentRuntime owns intent/route decisions",
    "PromptHarnessRuntime owns prompt plan construction",
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


def _scan_non_owners(failures: list[str]) -> None:
    for root in (LOCAL_API, RUNTIME_COMPOSITION, CORE, PROVIDER_RUNTIME, CONTROL_API):
        for path in _python_files(root):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module = _module_from_import(node)
                if module and _matches_prefix(module, FORBIDDEN_OWNER_IMPORTS):
                    failures.append(f"{_rel(path)} imports end-to-end integration/runtime owner: {module}")


def main() -> int:
    failures: list[str] = []
    if not INTEGRATION.is_dir():
        failures.append("packages/assistant_turn_integration is missing")
    integration_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(INTEGRATION))
    for term in REQUIRED_TERMS:
        if term not in integration_text:
            failures.append(f"assistant turn integration missing required term: {term}")
    for token in FORBIDDEN_INTEGRATION_TEXT:
        if token in integration_text:
            failures.append(f"assistant turn integration contains forbidden token: {token}")
    for path in _python_files(INTEGRATION):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module and not _matches_prefix(module, ALLOWED_IMPORT_PREFIXES):
                failures.append(f"{_rel(path)} imports non-approved dependency: {module}")
    _scan_non_owners(failures)

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_end_to_end_turn_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_end_to_end_turn_boundaries.py")
    docs = "\n".join(path.read_text(encoding="utf-8") for path in (VALIDATION_GATES, PROJECT_STATUS) if path.is_file())
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"end-to-end docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS end-to-end assistant turn boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
