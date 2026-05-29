"""Pin the provider-selection behaviour the Core executor relies on.

The Core service rebuilds its ProviderSelectionRuntime with a single
candidate whenever the user configures a provider (e.g. picking LM Studio in
the Control Plane). This test proves that a single-candidate runtime selects
exactly that candidate, which is what makes configure_provider's choice
actually stick instead of being reverted to the stale startup default.
"""

from packages.capability_runtime import AutonomyPolicy
from packages.provider_selection_runtime import (
    ModelCapabilityRequirement,
    ProviderCandidate,
    ProviderFallbackPolicy,
    ProviderRetryPolicy,
    ProviderSelectionRequest,
    ProviderSelectionRuntime,
)


def _request() -> ProviderSelectionRequest:
    return ProviderSelectionRequest(
        trace_id="trace-sel-1",
        requirement=ModelCapabilityRequirement(
            requested_capability="assistant_turn",
            tool_calling_required=False,
            min_context_length=0,
            local_preferred=True,
            cost_preference="balanced",
        ),
        autonomy_policy=AutonomyPolicy.for_mode("ask_before_risky"),
        fallback_policy=ProviderFallbackPolicy(
            provider_fallback_enabled=True,
            side_effect_retry_requires_policy=True,
        ),
        retry_policy=ProviderRetryPolicy(max_retries=1, retry_side_effect_tools=False),
    )


def _runtime_for(provider_id: str, model: str) -> ProviderSelectionRuntime:
    # Mirrors exactly what _CoreServiceProviderWorkerTurnExecutor.configure_provider
    # now builds when the user selects a provider/model.
    return ProviderSelectionRuntime(
        candidates=(
            ProviderCandidate(
                provider_id=provider_id,
                model=model,
                supports_tools=False,
                context_length=4096,
                locality="local",
                healthy=True,
                cost_tier="free",
            ),
        )
    )


def test_single_candidate_runtime_selects_that_candidate():
    runtime = _runtime_for("lmstudio_responses", "qwen3.5-2b-uncensored")
    decision = runtime.select(_request())
    assert decision.selected.provider_id == "lmstudio_responses"
    assert decision.selected.model == "qwen3.5-2b-uncensored"


def test_rebuild_changes_selection_from_litellm_to_lmstudio():
    # Startup default (what reverted the user's choice before the fix).
    default_runtime = _runtime_for("litellm", "openrouter/anthropic/claude-3.5-sonnet")
    assert default_runtime.select(_request()).selected.provider_id == "litellm"

    # After configure_provider rebuilds the runtime for LM Studio.
    rebuilt = _runtime_for("lmstudio_responses", "qwen3.5-2b-uncensored")
    decision = rebuilt.select(_request())
    assert decision.selected.provider_id == "lmstudio_responses"
    assert decision.selected.model == "qwen3.5-2b-uncensored"
