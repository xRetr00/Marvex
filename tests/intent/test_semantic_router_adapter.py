from types import SimpleNamespace

import pytest

from packages.adapters.intent.semantic_router_adapter import (
    AdapterDependencyUnavailableError,
    SemanticRouterAdapter,
)
from packages.contracts.intent_models import RouteFamily


class FakeRouteLayer:
    def __init__(self, route_name: str, score: float) -> None:
        self._route_name = route_name
        self._score = score
        self.called_with = None

    def __call__(self, input_text: str) -> SimpleNamespace:
        self.called_with = input_text
        return SimpleNamespace(name=self._route_name, score=self._score)


def test_selects_route_family_from_injected_semantic_router_layer() -> None:
    route_layer = FakeRouteLayer("grounded_lookup", 0.84)
    adapter = SemanticRouterAdapter(route_layer=route_layer)

    decision = adapter.decide_route("what changed in the latest release?")

    assert route_layer.called_with == "what changed in the latest release?"
    assert decision.route_family == RouteFamily.GROUNDED_LOOKUP
    assert decision.confidence == 0.84
    assert decision.ambiguity_flag is False


def test_low_confidence_route_becomes_clarify_without_custom_fallback_routing() -> None:
    adapter = SemanticRouterAdapter(
        route_layer=FakeRouteLayer("direct_answer", 0.32),
        ambiguity_threshold=0.45,
    )

    decision = adapter.decide_route("that one")

    assert decision.route_family == RouteFamily.CLARIFY
    assert decision.confidence == 0.32
    assert decision.ambiguity_flag is True


def test_intent_decision_exposes_no_tools_or_prompt_payload() -> None:
    adapter = SemanticRouterAdapter(route_layer=FakeRouteLayer("local_state_inspection", 0.91))

    decision = adapter.decide_route("read the local status file")

    assert decision.model_dump() == {
        "route_family": RouteFamily.LOCAL_STATE_INSPECTION,
        "confidence": 0.91,
        "ambiguity_flag": False,
    }


def test_optional_semantic_router_constructor_reports_structured_dependency_error() -> None:
    def missing_importer(module_name: str) -> object:
        raise ModuleNotFoundError(module_name)

    with pytest.raises(AdapterDependencyUnavailableError) as error:
        SemanticRouterAdapter.from_library(importer=missing_importer)

    assert error.value.dependency_name == "semantic_router"
    assert error.value.adapter_name == "SemanticRouterAdapter"
    assert error.value.reason_code == "dependency_unavailable"
