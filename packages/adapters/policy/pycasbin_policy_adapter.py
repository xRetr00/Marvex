from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily


@dataclass(frozen=True)
class AdapterDependencyUnavailableError(RuntimeError):
    dependency_name: str
    adapter_name: str
    reason_code: str = "dependency_unavailable"

    def __str__(self) -> str:
        return f"{self.adapter_name} dependency unavailable: {self.dependency_name}"


class PyCasbinPolicyAdapter:
    def __init__(
        self,
        enforcer: Any,
        subject: str = "marvex",
        action: str = "use",
    ) -> None:
        self._enforcer = enforcer
        self._subject = subject
        self._action = action

    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        if intent_decision.ambiguity_flag or intent_decision.route_family == RouteFamily.CLARIFY:
            return PolicyDecision(
                allow=False,
                clarify=True,
                deny=False,
                reason_code="policy.clarify_ambiguous_route",
            )

        allowed = bool(
            self._enforcer.enforce(
                self._subject,
                intent_decision.route_family.value,
                self._action,
            )
        )
        if allowed:
            return PolicyDecision(
                allow=True,
                clarify=False,
                deny=False,
                reason_code="policy.allowed",
            )
        return PolicyDecision(
            allow=False,
            clarify=False,
            deny=True,
            reason_code="policy.denied",
        )

    @classmethod
    def from_library(
        cls,
        model_path: str | None = None,
        policy_path: str | None = None,
        importer: Callable[[str], Any] = importlib.import_module,
    ) -> "PyCasbinPolicyAdapter":
        try:
            casbin = importer("casbin")
        except ModuleNotFoundError as exc:
            raise AdapterDependencyUnavailableError(
                dependency_name="casbin",
                adapter_name="PyCasbinPolicyAdapter",
            ) from exc

        if model_path is None or policy_path is None:
            raise ValueError("PyCasbinPolicyAdapter.from_library requires model_path and policy_path")
        return cls(enforcer=casbin.Enforcer(model_path, policy_path))
