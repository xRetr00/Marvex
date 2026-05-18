from packages.intent_runtime import IntentKind
from packages.adapters.intent.harness_semantic_router import (
    DisabledSemanticRouterBackend,
    RouteDefinition,
    RouteExample,
    SemanticRouteScore,
    SemanticRouterAdapterConfig,
    SemanticRouterHarnessAdapter,
    SemanticRouterThresholdPolicy,
)


def test_semantic_router_adapter_maps_scores_to_marvex_intent_without_owning_policy() -> None:
    config = SemanticRouterAdapterConfig(
        schema_version="1",
        backend_enabled=True,
        threshold_policy=SemanticRouterThresholdPolicy(min_confidence=0.6, clarification_confidence=0.45),
        routes=(
            RouteDefinition(route_id="route.tool", intent_kind=IntentKind.CAPABILITY_TOOL, examples=(RouteExample(text="use calculator"),)),
        ),
    )
    adapter = SemanticRouterHarnessAdapter(config=config, score_backend=lambda text, routes: (SemanticRouteScore(route_id="route.tool", score=0.91),))

    decision = adapter.route("use calculator now")

    assert decision.selected_intent.intent_kind == IntentKind.CAPABILITY_TOOL
    assert decision.route_decision.policy_owner == "packages.capability_runtime"
    assert decision.route_decision.execution_allowed is False
    assert decision.backend_name == "semantic_router"


def test_semantic_router_adapter_low_score_falls_back_to_clarification() -> None:
    config = SemanticRouterAdapterConfig(
        schema_version="1",
        backend_enabled=True,
        threshold_policy=SemanticRouterThresholdPolicy(min_confidence=0.8, clarification_confidence=0.5),
        routes=(RouteDefinition(route_id="route.memory", intent_kind=IntentKind.MEMORY, examples=(RouteExample(text="remember"),)),),
    )
    adapter = SemanticRouterHarnessAdapter(config=config, score_backend=lambda text, routes: (SemanticRouteScore(route_id="route.memory", score=0.41),))

    decision = adapter.route("maybe")

    assert decision.selected_intent.intent_kind == IntentKind.CLARIFICATION
    assert decision.ambiguity_signal.ambiguous is True
    assert decision.route_decision.execution_allowed is False


def test_disabled_semantic_router_backend_is_explicit_safe_seam() -> None:
    backend = DisabledSemanticRouterBackend(reason_code="dependency_deferred")

    score = backend.score("anything", ())

    assert score.route_id == "disabled"
    assert score.score == 0.0
    assert score.reason_code == "dependency_deferred"
