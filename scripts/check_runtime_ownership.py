from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_OWNERSHIP = ROOT / "docs" / "RUNTIME_OWNERSHIP.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"

REQUIRED_DOC_PHRASES = [
    "Core owns the assistant lifecycle envelope",
    "Core must not own assistant stage internals",
    "AssistantTurnRuntime owns assistant stage dispatch",
    "AssistantTurnRuntime must not own subsystem internals",
    "Subsystem runtimes own domain selection, dispatch, lifecycle, and execution",
    "ProviderRuntime must not own sessions, history, fallback policy, tools, memory, context, or policy",
    "ContextRuntime / ContextBuilder must not retrieve memory, expose tools, decide policy, or call providers",
    "Ports remain minimal contracts only",
    "Adapters own external protocols and library-specific code",
]

REQUIRED_SECTIONS = [
    "## Purpose",
    "## Accepted Ownership Decision",
    "## Core Boundary",
    "## AssistantTurnRuntime Boundary",
    "## Subsystem Runtime Boundaries",
    "## Dispatch and Selection Ownership",
    "## Failure and Cancellation Ownership",
    "## Trace and Event Ownership",
    "## Anti-God-Object Guardrails",
    "## Dangerous Runtime Work",
    "## Future Runtime Task Gate",
    "## Open Questions Before Runtime Implementation",
]

REQUIRED_TEMPLATE_PHRASES = [
    "runtime_ownership_gate",
    "which_runtime_owns_this_work",
    "which_layer_owns_dispatch",
    "which_layer_owns_selection",
    "which_layer_owns_lifecycle",
    "which_layer_owns_failure_cancellation_behavior",
    "avoid_expanding_core_into_god_object",
    "avoid_expanding_assistantturnruntime_into_subsystem_internals",
    "avoid_expanding_providerruntime_into_routing_session_history_fallback",
    "avoid_putting_memory_tool_policy_behavior_into_contextbuilder",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    runtime_ownership = _read(RUNTIME_OWNERSHIP, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    task_spec_template = _read(TASK_SPEC_TEMPLATE, failures)
    run_all_checks = _read(RUN_ALL_CHECKS, failures)

    for section in REQUIRED_SECTIONS:
        if section not in runtime_ownership:
            failures.append(f"docs/RUNTIME_OWNERSHIP.md missing section: {section}")

    runtime_lower = runtime_ownership.lower()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.lower() not in runtime_lower:
            failures.append(f"docs/RUNTIME_OWNERSHIP.md missing phrase: {phrase}")

    validation_lower = validation_gates.lower()
    if "runtime ownership gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Runtime Ownership Gate")
    if "core owns the assistant lifecycle envelope" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must state Core runtime ownership")

    template_lower = task_spec_template.lower()
    for phrase in REQUIRED_TEMPLATE_PHRASES:
        if phrase not in template_lower:
            failures.append(f"templates/TASK_SPEC.md missing runtime ownership phrase: {phrase}")

    if "check_runtime_ownership.py" not in run_all_checks:
        failures.append("scripts/run_all_checks.py must run check_runtime_ownership.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS runtime ownership gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
