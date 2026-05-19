from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime import AutonomyAction, AutonomyPolicy, PolicyDecisionAuditRecord, ToolRiskLevel, evaluate_autonomy_action
from packages.capability_runtime.models import CapabilityRuntimeModel


class ProviderCandidate(CapabilityRuntimeModel):
    provider_id: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    supports_tools: bool = False
    context_length: int = Field(..., ge=1)
    locality: Literal["local", "cloud"]
    healthy: bool
    cost_tier: Literal["free", "low", "medium", "high"] = "medium"


class ModelCapabilityRequirement(CapabilityRuntimeModel):
    requested_capability: str
    tool_calling_required: bool = False
    min_context_length: int = Field(default=0, ge=0)
    local_preferred: bool = False
    cost_preference: Literal["lowest", "balanced"] = "balanced"


class ProviderFallbackPolicy(CapabilityRuntimeModel):
    provider_fallback_enabled: bool
    side_effect_retry_requires_policy: Literal[True] = True


class ProviderRetryPolicy(CapabilityRuntimeModel):
    max_retries: int = Field(..., ge=0, le=5)
    retry_side_effect_tools: Literal[False] = False


class ProviderSelectionRequest(CapabilityRuntimeModel):
    trace_id: str
    requirement: ModelCapabilityRequirement
    autonomy_policy: AutonomyPolicy
    fallback_policy: ProviderFallbackPolicy
    retry_policy: ProviderRetryPolicy


class SafeProviderSelectionProjection(CapabilityRuntimeModel):
    selected_provider_id: str
    fallback_provider_ids: tuple[str, ...]
    rejected_provider_ids: tuple[str, ...]
    fallback_allowed: bool
    retry_allowed: bool
    raw_provider_payload_persisted: Literal[False] = False


class ProviderSelectionDecision(CapabilityRuntimeModel):
    selected: ProviderCandidate
    fallback_candidates: tuple[ProviderCandidate, ...]
    rejected_candidates: tuple[ProviderCandidate, ...]
    fallback_allowed: bool
    retry_allowed: bool
    policy_audit: PolicyDecisionAuditRecord

    def safe_projection(self) -> SafeProviderSelectionProjection:
        return SafeProviderSelectionProjection(
            selected_provider_id=self.selected.provider_id,
            fallback_provider_ids=tuple(candidate.provider_id for candidate in self.fallback_candidates),
            rejected_provider_ids=tuple(candidate.provider_id for candidate in self.rejected_candidates),
            fallback_allowed=self.fallback_allowed,
            retry_allowed=self.retry_allowed,
        )


class ProviderSelectionRuntime:
    def __init__(self, *, candidates: tuple[ProviderCandidate, ...]) -> None:
        self._candidates = candidates

    def select(self, request: ProviderSelectionRequest) -> ProviderSelectionDecision:
        eligible, rejected = _partition_candidates(self._candidates, request.requirement)
        if not eligible:
            raise RuntimeError("provider_selection.no_eligible_provider")
        ranked = sorted(eligible, key=lambda candidate: _rank(candidate, request.requirement))
        audit = evaluate_autonomy_action(
            request.autonomy_policy,
            AutonomyAction(action="provider retry fallback", resource_type="provider", capability="retry_fallback", risk_level=ToolRiskLevel.MEDIUM, safe_trace_ref=request.trace_id),
        )
        fallback_allowed = request.fallback_policy.provider_fallback_enabled and audit.decision.value == "allow"
        retry_allowed = request.retry_policy.max_retries > 0 and audit.decision.value == "allow"
        return ProviderSelectionDecision(
            selected=ranked[0],
            fallback_candidates=tuple(ranked[1:]) if fallback_allowed else (),
            rejected_candidates=tuple(rejected),
            fallback_allowed=fallback_allowed,
            retry_allowed=retry_allowed,
            policy_audit=audit,
        )


def _partition_candidates(candidates: tuple[ProviderCandidate, ...], requirement: ModelCapabilityRequirement) -> tuple[list[ProviderCandidate], list[ProviderCandidate]]:
    eligible: list[ProviderCandidate] = []
    rejected: list[ProviderCandidate] = []
    for candidate in candidates:
        if not candidate.healthy or candidate.context_length < requirement.min_context_length or (requirement.tool_calling_required and not candidate.supports_tools):
            rejected.append(candidate)
        else:
            eligible.append(candidate)
    return eligible, rejected


def _rank(candidate: ProviderCandidate, requirement: ModelCapabilityRequirement) -> tuple[int, int, int]:
    locality = 0 if requirement.local_preferred and candidate.locality == "local" else 1
    cost = {"free": 0, "low": 1, "medium": 2, "high": 3}[candidate.cost_tier]
    context_slack = candidate.context_length - requirement.min_context_length
    return (locality, cost, context_slack)
