from __future__ import annotations

from packages.capability_runtime import (
    CapabilityExecutionSummary,
    CapabilityKind,
    CapabilityRef,
    CapabilityResultEnvelope,
    SafeCapabilityProjection,
)


def test_result_and_summary_safe_projection_never_persist_raw_payloads() -> None:
    result = CapabilityResultEnvelope(
        schema_version="1",
        result_id="result-1",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="fake.status"),
        status="succeeded",
        safe_result={"status": "ok"},
        raw_input_persisted=False,
        raw_output_persisted=False,
    )
    summary = CapabilityExecutionSummary.from_result(
        result,
        readiness_count=3,
        eligible_count=1,
        denied_count=1,
        executed_fake_count=1,
    )
    projection = SafeCapabilityProjection.from_summary(summary).model_dump()

    assert projection["safe_result_status"] == "succeeded"
    assert projection["executed_fake_capability_count"] == 1
    assert "safe_result" not in projection
