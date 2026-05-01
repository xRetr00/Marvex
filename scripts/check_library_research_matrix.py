from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY_RESEARCH_MATRIX = ROOT / "docs" / "LIBRARY_RESEARCH_MATRIX.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"

REQUIRED_SECTIONS = [
    "## Purpose",
    "## Current Approved Library Posture",
    "## Discovery Sources",
    "## Ecosystem Matrix By Subsystem",
    "## Strong Future Decision Candidates",
    "## Adapter-Only / Pattern-Only Candidates",
    "## Avoid As Central Runtime",
    "## Not Relevant Or Rejected Candidates",
    "## Risk Matrix Summary",
    "## Gaps Requiring Deeper Research",
    "## Required Future Library Decision Records",
    "## No Framework Takeover Rule",
]

REQUIRED_MATRIX_PHRASES = [
    "LiteLLM for provider adapter behavior",
    "OpenAI SDK for LM Studio/OpenAI-compatible provider adapter behavior",
    "Pydantic for contracts",
    "Task 045A expanded discovery beyond the first shortlist",
    "awesome-python",
    "best-of-python",
    "awesome-llm-apps",
    "awesome agent-framework",
    "MCP ecosystem",
    "future subsystem implementation requires a library decision record before custom code or new dependency",
    "no framework or library may own Core or AssistantTurnRuntime",
    "libraries must stay behind ports/adapters/runtimes",
    "FastAPI / Litestar / possibly Connexion",
    "Authlib",
    "OpenTelemetry / structlog / CloudEvents / eventsourcing",
    "Qdrant local / LanceDB / Milvus Lite / SQLite FTS5",
    "mem0 / Letta",
    "official MCP SDK/ecosystem",
    "PyCasbin / Cedar / OPA",
    "Pydantic Settings / Dynaconf",
    "Phoenix / Braintrust / OpenTelemetry GenAI-style tooling",
    "OpenAI Structured Outputs / Instructor / Guardrails-style validation",
    "OpenAI Audio / faster-whisper / Piper successor",
    "PyAutoGUI / Playwright / OS accessibility / MCP desktop servers",
    "LangGraph",
    "CrewAI",
    "Agno",
    "Microsoft Agent Framework",
    "AutoGen",
    "OpenAI Agents SDK",
    "Pydantic AI",
    "LlamaIndex Workflows",
    "Haystack",
    "smolagents",
    "MCP SDK",
    "LiteLLM",
    "Phoenix/Braintrust",
    "translating Marvex contracts into adapter calls",
    "runtime factory wiring after approval",
    "trace/cancellation propagation glue",
    "error envelope normalization",
]

REQUIRED_DECISION_AREAS = [
    "local API/server runtime",
    "IPC / JSON-RPC / WebSocket / local auth",
    "provider routing/fallback",
    "telemetry/logging/event persistence",
    "memory runtime and vector/search backend",
    "MCP/tool execution/sandboxing",
    "process supervision and Windows service lifecycle",
    "config management",
    "policy engine",
    "intent routing",
    "structured outputs/constrained generation",
    "voice STT/TTS",
    "desktop automation",
    "agent observability/evals",
]

REQUIRED_TEMPLATE_PHRASES = [
    "library_research_matrix_gate",
    "library_research_or_decision_record",
    "new_dependency_or_custom_infrastructure_proposed",
    "subsystem_specific_library_decision_record_required",
    "avoid_framework_library_owning_core_or_assistantturnruntime",
    "libraries_stay_behind_ports_adapters_runtimes",
    "thin_glue_only",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    matrix = _read(LIBRARY_RESEARCH_MATRIX, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    task_spec_template = _read(TASK_SPEC_TEMPLATE, failures)
    run_all_checks = _read(RUN_ALL_CHECKS, failures)

    matrix_lower = matrix.lower()
    for section in REQUIRED_SECTIONS:
        if section not in matrix:
            failures.append(f"docs/LIBRARY_RESEARCH_MATRIX.md missing section: {section}")

    for phrase in REQUIRED_MATRIX_PHRASES:
        if phrase.lower() not in matrix_lower:
            failures.append(f"docs/LIBRARY_RESEARCH_MATRIX.md missing phrase: {phrase}")

    for area in REQUIRED_DECISION_AREAS:
        if area.lower() not in matrix_lower:
            failures.append(f"docs/LIBRARY_RESEARCH_MATRIX.md missing decision area: {area}")

    validation_lower = validation_gates.lower()
    if "library research matrix gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Library Research Matrix Gate")
    if "future subsystem implementation requires a library decision record" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must require library decision records")

    template_lower = task_spec_template.lower()
    for phrase in REQUIRED_TEMPLATE_PHRASES:
        if phrase not in template_lower:
            failures.append(f"templates/TASK_SPEC.md missing library research phrase: {phrase}")

    if "check_library_research_matrix.py" not in run_all_checks:
        failures.append("scripts/run_all_checks.py must run check_library_research_matrix.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS library research matrix gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
