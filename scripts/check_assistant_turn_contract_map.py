from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_MAP = ROOT / "docs" / "ASSISTANT_TURN_CONTRACT_MAP.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"

REQUIRED_DOC_PHRASES = [
    "current approved contracts are provider-foundation contracts",
    "not assistant-turn contracts",
    "must not be silently repurposed",
    "TurnInput",
    "TurnOutput",
    "ProviderRequest",
    "ProviderResponse",
    "FinalResponse",
    "InputEvent",
    "AssistantTurnInput",
    "AssistantTurnPlan",
    "AssistantTurnResult",
    "SessionState",
    "ConversationState",
    "UserIdentity",
    "LocalProfile",
    "IntentResult",
    "GoalFrame",
    "PolicyDecision",
    "PermissionRequest",
    "ContextPlan",
    "MemoryQuery",
    "MemoryResult",
    "MemoryWriteCandidate",
    "MemoryWriteResult",
    "ToolPlan",
    "ToolCall",
    "ToolResult",
    "ReasoningRequest",
    "provider-stage bridge",
    "AssistantFinalResponse",
    "OutputEvent",
    "SpeechOutput",
    "UIEvent",
    "VoiceInput",
    "WorkerEnvelope",
    "ServiceLifecycle",
    "PersistentTraceRecord",
    "AssistantEventRecord",
]

REQUIRED_GUARDRAILS = [
    "No memory hidden in `provider_options`, `raw_metadata`, prompt metadata, or `TraceEvent.data`.",
    "No tool result hidden inside prompt text or provider response text.",
    "No policy decision embedded as a side effect of router output.",
    "No desktop context injected directly into `ProviderRequest`.",
    "No voice/TTS fields inside `ProviderResponse` or provider adapter metadata.",
    "No session history inside `ProviderRuntime`.",
    "No assistant turn state inside CLI arguments beyond client input.",
    "No assistant-level fields added to provider contracts as shortcuts.",
    "No memory writeback from provider output without `MemoryWriteCandidate` and policy approval.",
    "No persistent event/history storage using plain trace logs without an approved event record.",
]

REQUIRED_TEMPLATE_PHRASES = [
    "assistant_turn_contract_map_gate",
    "input_output_contracts_named",
    "contract_approval_status_identified",
    "provider_foundation_contracts_not_repurposed",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    contract_map = _read(CONTRACT_MAP, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    task_spec_template = _read(TASK_SPEC_TEMPLATE, failures)
    run_all_checks = _read(RUN_ALL_CHECKS, failures)

    contract_map_lower = contract_map.lower()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.lower() not in contract_map_lower:
            failures.append(f"docs/ASSISTANT_TURN_CONTRACT_MAP.md missing phrase: {phrase}")

    for guardrail in REQUIRED_GUARDRAILS:
        if guardrail not in contract_map:
            failures.append(
                "docs/ASSISTANT_TURN_CONTRACT_MAP.md missing guardrail: "
                f"{guardrail}"
            )

    validation_lower = validation_gates.lower()
    if "assistant turn contract map gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Assistant Turn Contract Map Gate")
    if "provider-foundation contracts, not assistant-turn contracts" not in validation_lower:
        failures.append(
            "docs/VALIDATION_GATES.md must protect provider-foundation contracts"
        )

    template_lower = task_spec_template.lower()
    for phrase in REQUIRED_TEMPLATE_PHRASES:
        if phrase not in template_lower:
            failures.append(f"templates/TASK_SPEC.md missing contract map gate phrase: {phrase}")

    if "check_assistant_turn_contract_map.py" not in run_all_checks:
        failures.append("scripts/run_all_checks.py must run check_assistant_turn_contract_map.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant turn contract map gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
