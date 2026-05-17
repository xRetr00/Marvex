from __future__ import annotations

from packages.capability_runtime.execution import (
    CapabilityCallProposal,
    CapabilityExecutionRequest,
    CapabilityExecutionSummary,
    CapabilityResultEnvelope,
)
from packages.capability_runtime.models import (
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
)


class DeterministicFakeCapabilityAdapter:
    adapter_id = "deterministic_fake"

    def dispatch(
        self,
        *,
        proposal: CapabilityCallProposal,
        permission_decision: CapabilityPermissionDecision,
        arguments: dict[str, object],
    ) -> tuple[CapabilityResultEnvelope, CapabilityExecutionSummary]:
        request = CapabilityExecutionRequest(
            schema_version=proposal.schema_version,
            request_id=f"{proposal.proposal_id}:request",
            trace_id=proposal.trace_id,
            turn_id=proposal.turn_id,
            proposal=proposal,
            permission_decision=permission_decision,
            arguments=arguments,
            raw_arguments_persisted=False,
        )
        result = CapabilityResultEnvelope(
            schema_version=request.schema_version,
            result_id=f"{request.request_id}:result",
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_ref=request.proposal.capability_ref,
            status="succeeded",
            safe_result={"status": "ok", "adapter": self.adapter_id},
            raw_input_persisted=False,
            raw_output_persisted=False,
        )
        summary = CapabilityExecutionSummary.from_result(
            result,
            readiness_count=1,
            eligible_count=1,
            denied_count=0,
            executed_fake_count=1,
        )
        return result, summary


def fake_capability_ref() -> CapabilityRef:
    return CapabilityRef(kind=CapabilityKind.TOOL, identifier="fake.status")
