from __future__ import annotations

from dataclasses import dataclass

import pytest


ROUTE_FAMILIES = {
    "direct_answer",
    "grounded_lookup",
    "local_state_inspection",
    "clarify",
}


@dataclass(frozen=True)
class SpikeRouteDecision:
    route_family: str
    score: float
    exposed_tools: tuple[str, ...] = ()
    selection_source: str = "spike_fixture"


def select_single_route_family(scores: dict[str, float]) -> SpikeRouteDecision:
    unknown = set(scores) - ROUTE_FAMILIES
    if unknown:
        raise ValueError(f"unknown route families: {sorted(unknown)}")
    route_family, score = max(scores.items(), key=lambda item: item[1])
    if score < 0.45:
        return SpikeRouteDecision(route_family="clarify", score=score)
    return SpikeRouteDecision(route_family=route_family, score=score)


def custom_deterministic_routing_status() -> dict[str, str]:
    return {
        "status": "rejected_for_architecture",
        "reason": "custom routing becomes phrase-list policy and is only acceptable as a test baseline",
    }


def test_toy_route_selection_returns_exactly_one_route_family_without_tools() -> None:
    decision = select_single_route_family(
        {
            "direct_answer": 0.20,
            "grounded_lookup": 0.88,
            "local_state_inspection": 0.41,
            "clarify": 0.10,
        }
    )

    assert decision.route_family == "grounded_lookup"
    assert decision.route_family in ROUTE_FAMILIES
    assert isinstance(decision.route_family, str)
    assert decision.exposed_tools == ()


def test_low_confidence_routes_to_clarify_without_broad_tool_exposure() -> None:
    decision = select_single_route_family(
        {
            "direct_answer": 0.22,
            "grounded_lookup": 0.32,
            "local_state_inspection": 0.35,
            "clarify": 0.21,
        }
    )

    assert decision.route_family == "clarify"
    assert decision.exposed_tools == ()


def test_custom_deterministic_routing_is_recorded_as_rejected_or_deferred() -> None:
    status = custom_deterministic_routing_status()

    assert status["status"] == "rejected_for_architecture"
    assert "phrase-list" in status["reason"]


def test_semantic_router_route_constructor_smoke_when_installed() -> None:
    semantic_router = pytest.importorskip("semantic_router")

    route_cls = getattr(semantic_router, "Route", None)
    if route_cls is None:
        pytest.fail("semantic_router is installed but does not expose Route")

    route = route_cls(name="direct_answer", utterances=["answer a stable question"])
    assert route.name == "direct_answer"
    assert route.utterances == ["answer a stable question"]
