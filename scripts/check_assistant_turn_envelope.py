from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_TURN_ENVELOPE = ROOT / "docs" / "ASSISTANT_TURN_ENVELOPE.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
TASK_SPEC_TEMPLATE = ROOT / "templates" / "TASK_SPEC.md"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"

REQUIRED_SECTIONS = [
    "## Purpose",
    "## Direct Rule",
    "## Current Provider Foundation Boundary",
    "## Rejected Option: Reuse Provider Turn Contracts",
    "## Accepted Option: New Assistant Envelope Above Provider Foundation",
    "## Planned Contract Responsibilities",
    "## Relationship To Existing Provider Contracts",
    "## Minimum Approval Path",
    "## Runtime Ownership Implications",
    "## Anti-Vaxil Contract Guardrails",
    "## Open Questions Before Schema Drafting",
]

REQUIRED_DOC_PHRASES = [
    "The provider turn is not the assistant turn",
    "The smallest assistant-level envelope is",
    "InputEvent",
    "AssistantTurnInput",
    "AssistantTurnResult",
    "AssistantFinalResponse",
    "TurnInput, TurnOutput, and FinalResponse must not be silently repurposed as assistant-turn contracts",
    "provider contracts remain provider-foundation scoped",
    "assistant-level contracts must wrap or reference provider-foundation contracts, not mutate them into assistant contracts",
    "Normalizes external input from CLI, future Shell, Voice, Desktop, and proactive triggers before assistant turn entry",
    "Assistant-level turn entry after input normalization",
    "Complete assistant-level turn result, independent of whether provider calls happened",
    "User-facing assistant response independent of provider response shape",
    "AssistantTurnInput may wrap or reference TurnInput only for provider-only compatibility",
    "AssistantTurnInput must not become an alias for TurnInput",
    "AssistantTurnResult may reference provider TurnOutput or provider-stage summaries",
    "AssistantTurnResult must not be shaped around provider_response_id",
    "AssistantFinalResponse may initially wrap current FinalResponse",
    "ProviderRequest and ProviderResponse remain provider-only",
    "TraceEvent and ErrorEnvelope may remain shared base contracts",
    "TraceEvent remains diagnostic unless persistent assistant event/history contracts are separately approved",
    "no assistant state hidden in TurnInput.metadata",
    "no memory/tool/session data hidden in ProviderRequest.provider_options",
    "no output-channel/TTS state hidden in ProviderResponse.raw_metadata",
    "no assistant history hidden in CLI args",
    "no persistent assistant history stored as raw TraceEvent.data",
]

REQUIRED_TEMPLATE_PHRASES = [
    "assistant_turn_envelope_gate",
    "touches_provider_foundation_contracts",
    "touches_assistant_envelope_contracts",
    "provider_contracts_not_repurposed",
    "assistant_contracts_wrap_or_reference_provider_contracts",
    "assistant_envelope_contracts_named",
]


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []

    envelope = _read(ASSISTANT_TURN_ENVELOPE, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    task_spec_template = _read(TASK_SPEC_TEMPLATE, failures)
    run_all_checks = _read(RUN_ALL_CHECKS, failures)

    for section in REQUIRED_SECTIONS:
        if section not in envelope:
            failures.append(f"docs/ASSISTANT_TURN_ENVELOPE.md missing section: {section}")

    envelope_lower = envelope.lower()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.lower() not in envelope_lower:
            failures.append(f"docs/ASSISTANT_TURN_ENVELOPE.md missing phrase: {phrase}")

    validation_lower = validation_gates.lower()
    if "assistant turn envelope gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Assistant Turn Envelope Gate")
    if "turninput, turnoutput, and finalresponse must not be silently repurposed" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must protect provider-foundation contracts")

    template_lower = task_spec_template.lower()
    for phrase in REQUIRED_TEMPLATE_PHRASES:
        if phrase not in template_lower:
            failures.append(f"templates/TASK_SPEC.md missing assistant envelope phrase: {phrase}")

    if "check_assistant_turn_envelope.py" not in run_all_checks:
        failures.append("scripts/run_all_checks.py must run check_assistant_turn_envelope.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant turn envelope gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
