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
    "These are assistant-envelope enums, not provider-foundation enums.",
    "source: `cli`, `shell`, `voice`, `desktop`, `proactive`, `system`.",
    "input_modality: `text`, `speech`, `desktop_event`, `system_event`.",
    "assistant_mode: `default`, `diagnostic`.",
    "response_type: `text`, `error`, `payload_ref`.",
    "output_channel_intent: `default`, `display`, `speech`, `both`.",
    "finish_reason: `stop`, `length`, `cancelled`, `error`, `unknown`.",
    "payload and payload_ref relationship",
    "Exactly one of `payload` or `payload_ref` must be non-null.",
    "Both null is invalid.",
    "Both present is invalid for first approval.",
    '"kind": "text"',
    "Raw UI trees, raw audio, screenshots, desktop captures, binary blobs, provider requests, provider responses, and encoded JSON strings are forbidden in `payload`.",
    "`payload_ref` must not point to arbitrary provider content.",
    "`privacy` is local classification metadata only.",
    "Policy decisions, access grants, permission results, identity/profile data, and redaction results are forbidden in `privacy`.",
    "Must not include provider request fields.",
    "Must not alias TurnInput.",
    "`policy_context` is seed-only.",
    "Policy allow/deny results, permission grants, tool scopes, memory write approval, policy engine output, and identity/session bodies are forbidden in `policy_context`.",
    "For text modality, `user_visible_input` must be a non-null string.",
    "For non-text modalities, `user_visible_input` may be null only when a future approved payload/reference contract supplies a user-visible representation.",
    "Must not carry provider-specific options.",
    "Must not contain memory/tool/session bodies directly.",
    "Hybrid reference strategy",
    "Cross-runtime references must be constrained strings or minimal typed references/summaries.",
    "References must not embed subsystem bodies.",
    '"stage_name": "provider_reasoning"',
    '"status": "completed"',
    '"error_ref": null',
    "No raw subsystem state, raw provider responses, tool outputs, memory content, prompt text, or hidden context blocks may appear in `stage_summaries`.",
    '"turn_ref": "provider-turn-001"',
    "No embedded `ProviderRequest`.",
    "No embedded `ProviderResponse`.",
    "No central `provider_response_id`.",
    "No provider routing/fallback/session state.",
    "`tool_result_refs` are references only until `ToolResult` is approved.",
    "`memory_result_refs` are references only until `MemoryResult` is approved.",
    "`output_events` are empty or reference/summary only until `OutputEvent` is approved.",
    "No raw tool output, memory content, UI render payload, TTS data, speech audio, or channel dispatch instruction may be embedded.",
    "Must not be shaped around provider_response_id.",
    "Must be valid even if no provider call happened.",
    "Must not embed raw tool/memory outputs",
    "`assistant_final_response` may be null only on hard failure when no user-facing response can be assembled.",
    "Degraded turns may contain both `assistant_final_response` and `error`.",
    "Stage-level failures belong in `stage_summaries` via `status` and `error_ref`.",
    "must not become an alias for FinalResponse",
    "For `response_type=text`, `text` must be non-null and `payload_ref` must be null.",
    "For `response_type=payload_ref`, `payload_ref` must be non-null.",
    "For `response_type=error`, `text` should contain user-safe error text unless explicitly suppressed by a future approved contract.",
    "Non-error responses require at least one content carrier.",
    "`output_channel_intent` is intent only, not dispatch.",
    "OutputRuntime owns actual dispatch later.",
    "`safe_for_display` means eligible for display, not required to display.",
    "`safe_for_speech` means eligible for speech, not required to speak.",
    "`memory_write_candidate_hint` is a candidate hint only.",
    "`memory_write_candidate_hint` is not memory write approval.",
    "`memory_write_candidate_hint` cannot cause writeback without a future `MemoryWriteCandidate` and PolicyRuntime approval.",
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
        "memory_write_candidate_hint",
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
