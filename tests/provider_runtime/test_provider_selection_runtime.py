from packages.capability_runtime import AutonomyMode, AutonomyPolicy, PolicyDecision
from packages.provider_selection_runtime import (
    ModelCapabilityRequirement,
    ProviderCandidate,
    ProviderFallbackPolicy,
    ProviderRetryPolicy,
    ProviderSelectionRequest,
    ProviderSelectionRuntime,
)


def test_provider_selection_prefers_healthy_capable_local_provider_and_safe_projection() -> None:
    runtime = ProviderSelectionRuntime(
        candidates=(
            ProviderCandidate(provider_id="cloud-small", model="cloud-mini", supports_tools=True, context_length=128000, locality="cloud", healthy=True, cost_tier="low"),
            ProviderCandidate(provider_id="local-lmstudio", model="qwen-local", supports_tools=True, context_length=64000, locality="local", healthy=True, cost_tier="free"),
        )
    )

    decision = runtime.select(
        ProviderSelectionRequest(
            trace_id="trace-provider-select",
            requirement=ModelCapabilityRequirement(requested_capability="tool_calling", tool_calling_required=True, min_context_length=32000, local_preferred=True),
            autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.ASK_BEFORE_RISKY),
            fallback_policy=ProviderFallbackPolicy(provider_fallback_enabled=True),
            retry_policy=ProviderRetryPolicy(max_retries=1),
        )
    )

    assert decision.selected.provider_id == "local-lmstudio"
    assert decision.fallback_candidates[0].provider_id == "cloud-small"
    projection = decision.safe_projection()
    assert projection.selected_provider_id == "local-lmstudio"
    assert projection.raw_provider_payload_persisted is False
    assert "qwen-local" not in projection.model_dump_json()


def test_provider_selection_fallback_is_policy_controlled_and_filters_unhealthy_or_incapable() -> None:
    runtime = ProviderSelectionRuntime(
        candidates=(
            ProviderCandidate(provider_id="no-tools", model="basic", supports_tools=False, context_length=128000, locality="cloud", healthy=True, cost_tier="low"),
            ProviderCandidate(provider_id="unhealthy-tools", model="broken", supports_tools=True, context_length=128000, locality="cloud", healthy=False, cost_tier="low"),
            ProviderCandidate(provider_id="cloud-tools", model="capable", supports_tools=True, context_length=128000, locality="cloud", healthy=True, cost_tier="medium"),
        )
    )

    blocked = runtime.select(
        ProviderSelectionRequest(
            trace_id="trace-provider-blocked",
            requirement=ModelCapabilityRequirement(requested_capability="tool_calling", tool_calling_required=True, min_context_length=64000),
            autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.LOCKED_DOWN),
            fallback_policy=ProviderFallbackPolicy(provider_fallback_enabled=False),
            retry_policy=ProviderRetryPolicy(max_retries=0),
        )
    )
    allowed = runtime.select(
        ProviderSelectionRequest(
            trace_id="trace-provider-allowed",
            requirement=ModelCapabilityRequirement(requested_capability="tool_calling", tool_calling_required=True, min_context_length=64000),
            autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX),
            fallback_policy=ProviderFallbackPolicy(provider_fallback_enabled=True),
            retry_policy=ProviderRetryPolicy(max_retries=2),
        )
    )

    assert blocked.selected.provider_id == "cloud-tools"
    assert blocked.fallback_allowed is False
    assert blocked.policy_audit.decision in {PolicyDecision.DENY, PolicyDecision.APPROVAL_REQUIRED}
    assert allowed.fallback_allowed is True
    assert allowed.retry_allowed is True
    assert {item.provider_id for item in allowed.rejected_candidates} == {"no-tools", "unhealthy-tools"}
