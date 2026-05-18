from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_RUNTIME = ROOT / "packages" / "capability_runtime"
ASSISTANT_RUNTIME = ROOT / "packages" / "assistant_runtime"
ADAPTERS = ROOT / "packages" / "adapters" / "capabilities"
TOOL_ORCHESTRATION = ASSISTANT_RUNTIME / "tool_orchestration.py"
BUILTINS_ADAPTER = ADAPTERS / "builtins.py"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

NON_OWNER_ROOTS = (
    ROOT / "packages" / "core",
    ROOT / "packages" / "local_api",
    ROOT / "packages" / "local_service_startup",
    ROOT / "packages" / "provider_runtime",
    ROOT / "packages" / "runtime_composition",
    ROOT / "packages" / "memory_runtime",
    ROOT / "packages" / "session_runtime",
    ROOT / "packages" / "telemetry",
)
ASSISTANT_RUNTIME_ALLOWED_LOOP_FILES = {
    "packages/assistant_runtime/lifecycle.py",
    "packages/assistant_runtime/tool_orchestration.py",
}
LOOP_OWNER_TERMS = (
    "AgentLoopState",
    "AgentLoopStep",
    "AgentLoopDecision",
    "AgentLoopStopReason",
    "AgentLoopGuardResult",
    "ToolOrchestrationState",
    "PendingApprovalState",
    "ToolContinuationState",
    "SafeAgentLoopProjection",
)
REQUIRED_CAPABILITY_TERMS = LOOP_OWNER_TERMS + (
    "evaluate_agent_loop_guard",
    "ToolingTelemetrySummary",
    "CapabilityExecutionRequest",
    "make_denial_result",
)
REQUIRED_ASSISTANT_TERMS = (
    "ToolOrchestratedTurnState",
    "build_tool_orchestrated_lifecycle_summary",
    "provider_continuation_ready",
    "final_response_ready",
    "raw_payload_persisted: Literal[False]",
)
FORBIDDEN_ASSISTANT_TERMS = (
    "packages.adapters",
    "CapabilityExecutionRequest",
    "execute_request(",
    "dispatch(",
)
REQUIRED_BUILTIN_TERMS = (
    "CapabilityExecutionRequest",
    "def execute_request",
    "_result_for_request",
    "raw_input_persisted=False",
    "raw_output_persisted=False",
)
FORBIDDEN_RAW_PERSISTENCE_TOKENS = (
    "raw_payload_persisted: Literal[True]",
    "raw_tool_output_persisted: Literal[True]",
    "raw_tool_payloads_persisted: Literal[True]",
    "raw_input_persisted=True",
    "raw_output_persisted=True",
    "raw_prompt_persisted=True",
)
REQUIRED_DOC_PHRASES = (
    "Agent Execution Loop and Tool-Orchestrated Turn Foundation",
    "CapabilityRuntime remains authoritative",
    "provider tool calls are proposals",
    "risky actions can pause for human approval",
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


def _scan_required_text(path: Path, terms: tuple[str, ...], failures: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    for term in terms:
        if term not in text:
            failures.append(f"{_rel(path)} missing required agent-loop term: {term}")


def _scan_non_owners(failures: list[str]) -> None:
    for root in NON_OWNER_ROOTS:
        for path in _python_files(root):
            text = path.read_text(encoding="utf-8")
            for term in LOOP_OWNER_TERMS:
                if term in text:
                    failures.append(f"{_rel(path)} mentions CapabilityRuntime-owned loop term: {term}")


def _scan_assistant_runtime(failures: list[str]) -> None:
    for path in _python_files(ASSISTANT_RUNTIME):
        rel = _rel(path)
        text = path.read_text(encoding="utf-8")
        for term in LOOP_OWNER_TERMS:
            if term in text and rel not in ASSISTANT_RUNTIME_ALLOWED_LOOP_FILES:
                failures.append(f"{rel} mentions agent-loop term outside approved coordination file: {term}")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            module = _module_from_import(node)
            if module and (module == "packages.adapters" or module.startswith("packages.adapters.")):
                failures.append(f"{rel} imports adapter boundary: {module}")

    orchestration_text = TOOL_ORCHESTRATION.read_text(encoding="utf-8") if TOOL_ORCHESTRATION.is_file() else ""
    for term in FORBIDDEN_ASSISTANT_TERMS:
        if term in orchestration_text:
            failures.append(f"packages/assistant_runtime/tool_orchestration.py contains forbidden executor term: {term}")


def main() -> int:
    failures: list[str] = []
    capability_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(CAPABILITY_RUNTIME))
    adapter_text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files(ADAPTERS))

    for term in REQUIRED_CAPABILITY_TERMS:
        if term not in capability_text:
            failures.append(f"CapabilityRuntime missing agent-loop term: {term}")
    _scan_required_text(TOOL_ORCHESTRATION, REQUIRED_ASSISTANT_TERMS, failures)
    _scan_required_text(BUILTINS_ADAPTER, REQUIRED_BUILTIN_TERMS, failures)
    _scan_non_owners(failures)
    _scan_assistant_runtime(failures)

    for token in FORBIDDEN_RAW_PERSISTENCE_TOKENS:
        if token in capability_text or token in adapter_text:
            failures.append(f"agent-loop foundation contains forbidden raw persistence token: {token}")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_agent_execution_loop_boundaries.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_agent_execution_loop_boundaries.py")

    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (VALIDATION_GATES, PROJECT_STATUS)
        if path.is_file()
    )
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in docs:
            failures.append(f"agent-loop docs/status missing phrase: {phrase}")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS agent execution loop boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())