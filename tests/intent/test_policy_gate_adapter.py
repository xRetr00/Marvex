import pytest

from packages.adapters.policy.pycasbin_policy_adapter import (
    AdapterDependencyUnavailableError,
    PyCasbinPolicyAdapter,
)
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily


class FakeEnforcer:
    def __init__(self, allowed_routes: set[str]) -> None:
        self.allowed_routes = allowed_routes
        self.calls = []

    def enforce(self, subject: str, obj: str, action: str) -> bool:
        self.calls.append((subject, obj, action))
        return obj in self.allowed_routes and action == "use"


def intent(route_family: RouteFamily, confidence: float = 0.80, ambiguous: bool = False) -> IntentDecision:
    return IntentDecision(
        route_family=route_family,
        confidence=confidence,
        ambiguity_flag=ambiguous,
    )


def test_policy_allows_route_when_injected_enforcer_allows_capability() -> None:
    enforcer = FakeEnforcer({"direct_answer"})
    adapter = PyCasbinPolicyAdapter(enforcer=enforcer)

    decision = adapter.decide(intent(RouteFamily.DIRECT_ANSWER))

    assert decision == PolicyDecision(
        allow=True,
        clarify=False,
        deny=False,
        reason_code="policy.allowed",
    )
    assert enforcer.calls == [("marvex", "direct_answer", "use")]


def test_policy_does_not_own_route_ambiguity_decisions() -> None:
    enforcer = FakeEnforcer({"grounded_lookup"})
    adapter = PyCasbinPolicyAdapter(enforcer=enforcer)

    decision = adapter.decide(intent(RouteFamily.GROUNDED_LOOKUP, confidence=0.31, ambiguous=True))

    assert decision == PolicyDecision(
        allow=True,
        clarify=False,
        deny=False,
        reason_code="policy.allowed",
    )
    assert enforcer.calls == [("marvex", "grounded_lookup", "use")]


def test_policy_denies_route_when_enforcer_rejects_capability() -> None:
    adapter = PyCasbinPolicyAdapter(enforcer=FakeEnforcer({"direct_answer"}))

    decision = adapter.decide(intent(RouteFamily.LOCAL_STATE_INSPECTION))

    assert decision == PolicyDecision(
        allow=False,
        clarify=False,
        deny=True,
        reason_code="policy.denied",
    )


def test_policy_decision_requires_exactly_one_flag() -> None:
    with pytest.raises(ValueError):
        PolicyDecision(
            allow=True,
            clarify=True,
            deny=False,
            reason_code="policy.invalid",
        )


def test_optional_pycasbin_constructor_reports_structured_dependency_error() -> None:
    def missing_importer(module_name: str) -> object:
        raise ModuleNotFoundError(module_name)

    with pytest.raises(AdapterDependencyUnavailableError) as error:
        PyCasbinPolicyAdapter.from_library(importer=missing_importer)

    assert error.value.dependency_name == "casbin"
    assert error.value.adapter_name == "PyCasbinPolicyAdapter"
    assert error.value.reason_code == "dependency_unavailable"
