from __future__ import annotations

from packages.capability_runtime import ApprovalDecision, CapabilityApprovalRequest

from .models import ApprovalDecisionResponse, ApprovalListResponse, ApprovalSummary


class InMemoryApprovalStore:
    def __init__(self, requests: tuple[CapabilityApprovalRequest, ...] = ()) -> None:
        self._pending = {request.approval_request_id: request for request in requests}
        self._decisions: dict[str, ApprovalDecisionResponse] = {}

    @classmethod
    def from_requests(cls, requests: tuple[CapabilityApprovalRequest, ...]) -> InMemoryApprovalStore:
        return cls(requests)

    def add_pending(self, request: CapabilityApprovalRequest) -> None:
        self._pending[request.approval_request_id] = request

    def list_pending(self) -> ApprovalListResponse:
        approvals = tuple(ApprovalSummary.from_request(request) for request in self._pending.values())
        return ApprovalListResponse(schema_version="1", approvals=approvals, pending_count=len(approvals))

    def read_pending(self, approval_request_id: str) -> ApprovalSummary | None:
        request = self._pending.get(approval_request_id)
        return ApprovalSummary.from_request(request) if request is not None else None

    def approve(self, approval_request_id: str, *, reason: str) -> ApprovalDecisionResponse | None:
        return self._decide(approval_request_id, decision="approved", reason=reason)

    def deny(self, approval_request_id: str, *, reason: str) -> ApprovalDecisionResponse | None:
        return self._decide(approval_request_id, decision="denied", reason=reason)

    def _decide(
        self,
        approval_request_id: str,
        *,
        decision: str,
        reason: str,
    ) -> ApprovalDecisionResponse | None:
        request = self._pending.pop(approval_request_id, None)
        if request is None:
            return None
        approval_decision = ApprovalDecision(
            schema_version=request.schema_version,
            decision_id=f"{approval_request_id}:{decision}",
            approval_request_id=approval_request_id,
            capability_ref=request.capability_ref,
            decision=decision,
            decided_by="user",
        )
        response = ApprovalDecisionResponse.from_decision(
            request=request,
            decision=approval_decision,
            reason=reason,
        )
        self._decisions[approval_request_id] = response
        return response
