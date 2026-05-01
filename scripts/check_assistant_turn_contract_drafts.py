from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSISTANT_TURN_CONTRACTS = ROOT / "docs" / "ASSISTANT_TURN_CONTRACTS.md"
CONTRACT_APPROVALS = ROOT / "docs" / "CONTRACT_APPROVALS.md"
VALIDATION_GATES = ROOT / "docs" / "VALIDATION_GATES.md"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"

CONTRACTS = [
    "InputEvent",
    "AssistantTurnInput",
    "AssistantTurnResult",
    "AssistantFinalResponse",
]

REQUIRED_SECTIONS = [
    "## Purpose",
    "## Direct Rules",
    "## Relationship To Provider Foundation",
    "## Draft Common Rules",
    "## InputEvent",
    "## AssistantTurnInput",
    "## AssistantTurnResult",
    "## AssistantFinalResponse",
    "## Implementation Block",
]

REQUIRED_DOC_PHRASES = [
    "These contracts are draft documentation only.",
    "Do not create Pydantic models from this document until contracts are approved.",
    "TurnInput and TurnOutput remain provider-foundation contracts.",
    "FinalResponse remains provider-foundation final response until explicitly migrated or wrapped.",
    "ProviderRequest and ProviderResponse remain provider-only.",
    "InputEvent and AssistantTurnInput sit above provider calls.",
    "AssistantTurnResult may reference provider TurnOutput or provider-stage summaries.",
    "AssistantFinalResponse owns assistant-level user-facing response.",
    "TraceEvent and ErrorEnvelope remain shared base contracts.",
    "Unknown fields are allowed only inside metadata.",
    "payload and payload_ref relationship",
    "Must not include provider request fields.",
    "Must not alias TurnInput.",
    "Must not carry provider-specific options.",
    "Must not contain memory/tool/session bodies directly.",
    "Must not be shaped around provider_response_id.",
    "Must be valid even if no provider call happened.",
    "Must not embed raw tool/memory outputs",
    "must not become an alias for FinalResponse",
]

REQUIRED_FIELDS = {
    "InputEvent": [
        "schema_version",
        "trace_id",
        "event_id",
        "source",
        "input_modality",
        "payload",
        "payload_ref",
        "session_ref",
        "privacy",
        "timestamp",
        "metadata",
    ],
    "AssistantTurnInput": [
        "schema_version",
        "trace_id",
        "turn_id",
        "input_event_id",
        "session_ref",
        "identity_ref",
        "user_visible_input",
        "assistant_mode",
        "policy_context",
        "metadata",
    ],
    "AssistantTurnResult": [
        "schema_version",
        "trace_id",
        "turn_id",
        "assistant_final_response",
        "output_events",
        "stage_summaries",
        "provider_turn_refs",
        "tool_result_refs",
        "memory_result_refs",
        "session_result_ref",
        "error",
        "metadata",
    ],
    "AssistantFinalResponse": [
        "schema_version",
        "response_type",
        "text",
        "payload_ref",
        "output_channel_intent",
        "safe_for_display",
        "safe_for_speech",
        "memory_write_eligible",
        "finish_reason",
        "metadata",
    ],
}


def _read(path: Path, failures: list[str]) -> str:
    if not path.is_file():
        failures.append(f"missing {path.relative_to(ROOT).as_posix()}")
        return ""
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start == -1:
        return ""
    next_heading = text.find("\n## ", start + len(marker))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def main() -> int:
    failures: list[str] = []

    contracts_doc = _read(ASSISTANT_TURN_CONTRACTS, failures)
    approvals = _read(CONTRACT_APPROVALS, failures)
    validation_gates = _read(VALIDATION_GATES, failures)
    run_all_checks = _read(RUN_ALL_CHECKS, failures)

    for section in REQUIRED_SECTIONS:
        if section not in contracts_doc:
            failures.append(f"docs/ASSISTANT_TURN_CONTRACTS.md missing section: {section}")

    doc_lower = contracts_doc.lower()
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase.lower() not in doc_lower:
            failures.append(f"docs/ASSISTANT_TURN_CONTRACTS.md missing phrase: {phrase}")

    for contract, fields in REQUIRED_FIELDS.items():
        section = _section(contracts_doc, contract)
        if not section:
            failures.append(f"docs/ASSISTANT_TURN_CONTRACTS.md missing contract section: {contract}")
            continue
        for field in fields:
            if f"`{field}`" not in section:
                failures.append(f"docs/ASSISTANT_TURN_CONTRACTS.md {contract} missing field: {field}")
        if "```json" not in section:
            failures.append(f"docs/ASSISTANT_TURN_CONTRACTS.md {contract} missing JSON example")

    for contract in CONTRACTS:
        expected_row = f"| {contract} | 0.1.1-draft | draft | none | none | no |"
        if expected_row not in approvals:
            failures.append(
                "docs/CONTRACT_APPROVALS.md must contain draft/no row: "
                f"{expected_row}"
            )
        forbidden_row = f"| {contract} | 0.1.1-draft | approved |"
        if forbidden_row in approvals:
            failures.append(f"{contract} must not be approved for implementation")

    validation_lower = validation_gates.lower()
    if "assistant turn contract drafts gate" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must document Assistant Turn Contract Drafts Gate")
    if "draft/no only" not in validation_lower:
        failures.append("docs/VALIDATION_GATES.md must state assistant draft rows are draft/no only")

    if "check_assistant_turn_contract_drafts.py" not in run_all_checks:
        failures.append("scripts/run_all_checks.py must run check_assistant_turn_contract_drafts.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS assistant turn contract drafts gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
