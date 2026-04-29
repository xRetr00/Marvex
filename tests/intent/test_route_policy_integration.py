from types import SimpleNamespace

from packages.adapters.intent.semantic_router_adapter import SemanticRouterAdapter
from packages.adapters.policy.pycasbin_policy_adapter import PyCasbinPolicyAdapter
from packages.contracts.intent_models import PolicyDecision, RouteFamily


class FakeRouteLayer:
    def __call__(self, input_text: str) -> SimpleNamespace:
        return SimpleNamespace(name="grounded_lookup", score=0.87)


class FakeEnforcer:
    def enforce(self, subject: str, obj: str, action: str) -> bool:
        return (subject, obj, action) == ("marvex", "grounded_lookup", "use")


def test_user_input_flows_through_route_family_and_policy_gate_only() -> None:
    router = SemanticRouterAdapter(route_layer=FakeRouteLayer())
    policy = PyCasbinPolicyAdapter(enforcer=FakeEnforcer())

    intent_decision = router.decide_route("what is current in the docs?")
    policy_decision = policy.decide(intent_decision)

    assert intent_decision.route_family == RouteFamily.GROUNDED_LOOKUP
    assert intent_decision.model_dump().keys() == {
        "route_family",
        "confidence",
        "ambiguity_flag",
    }
    assert policy_decision == PolicyDecision(
        allow=True,
        clarify=False,
        deny=False,
        reason_code="policy.allowed",
    )
