from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.intent_runtime import (
    IntentAmbiguitySignal,
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentKind,
    IntentRiskSignal,
    classification_from_kind,
)


class RouteExample(CapabilityRuntimeModel):
    text: str = Field(..., min_length=1, max_length=300)
    raw_example_persisted: Literal[False] = False


class RouteDefinition(CapabilityRuntimeModel):
    route_id: str = Field(..., min_length=1)
    intent_kind: IntentKind
    examples: tuple[RouteExample, ...]
    policy_owner: Literal["packages.capability_runtime"] = "packages.capability_runtime"


class SemanticRouteScore(CapabilityRuntimeModel):
    route_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    reason_code: str = "semantic_router.score"


class SemanticRouterThresholdPolicy(CapabilityRuntimeModel):
    min_confidence: float = Field(..., ge=0.0, le=1.0)
    clarification_confidence: float = Field(..., ge=0.0, le=1.0)


class SemanticRouterAdapterConfig(CapabilityRuntimeModel):
    schema_version: str
    backend_enabled: bool
    threshold_policy: SemanticRouterThresholdPolicy
    routes: tuple[RouteDefinition, ...]
    backend_name: Literal["semantic_router"] = "semantic_router"
    library_owns_policy: Literal[False] = False


class DisabledSemanticRouterBackend:
    def __init__(self, *, reason_code: str) -> None:
        self.reason_code = reason_code

    def score(self, _text: str, _routes: tuple[RouteDefinition, ...]) -> SemanticRouteScore:
        return SemanticRouteScore(route_id="disabled", score=0.0, reason_code=self.reason_code)


class SemanticRouterHarnessDecision(IntentClassificationResult):
    backend_name: str
    library_owns_policy: Literal[False] = False


class SemanticRouterHarnessAdapter:
    def __init__(self, *, config: SemanticRouterAdapterConfig, score_backend: Callable[[str, tuple[RouteDefinition, ...]], tuple[SemanticRouteScore, ...]] | None = None) -> None:
        self.config = config
        self._score_backend = score_backend

    def route(self, input_text: str) -> SemanticRouterHarnessDecision:
        request = IntentClassificationRequest(schema_version=self.config.schema_version, trace_id="trace-semantic-router", turn_id="turn-semantic-router", user_input_summary=input_text[:600])
        if not self.config.backend_enabled or self._score_backend is None:
            base = classification_from_kind(request, kind=IntentKind.CLARIFICATION, score=0.0, reason_code="semantic_router.backend_disabled")
        else:
            scores = self._score_backend(input_text, self.config.routes)
            top = max(scores, key=lambda item: item.score) if scores else SemanticRouteScore(route_id="missing", score=0.0)
            matched = next((route for route in self.config.routes if route.route_id == top.route_id), None)
            kind = matched.intent_kind if matched and top.score >= self.config.threshold_policy.min_confidence else IntentKind.CLARIFICATION
            base = classification_from_kind(request, kind=kind, score=top.score, reason_code=top.reason_code)
        return SemanticRouterHarnessDecision(**base.model_dump(), backend_name=self.config.backend_name, library_owns_policy=False)
