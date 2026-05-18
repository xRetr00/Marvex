from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from packages.contracts.intent_models import IntentDecision, RouteFamily


@dataclass(frozen=True)
class AdapterDependencyUnavailableError(RuntimeError):
    dependency_name: str
    adapter_name: str
    reason_code: str = "dependency_unavailable"

    def __str__(self) -> str:
        return f"{self.adapter_name} dependency unavailable: {self.dependency_name}"


class SemanticRouterAdapter:
    def __init__(
        self,
        route_layer: Callable[[str], Any],
        ambiguity_threshold: float = 0.45,
        library_routes: tuple[Any, ...] = (),
    ) -> None:
        self._route_layer = route_layer
        self._ambiguity_threshold = ambiguity_threshold
        self._library_routes = library_routes

    def decide_route(self, input_text: str) -> IntentDecision:
        result = self._route_layer(input_text)
        route_family = self._route_family_from(result)
        confidence = self._confidence_from(result)
        if confidence < self._ambiguity_threshold or route_family == RouteFamily.CLARIFY:
            return IntentDecision(
                route_family=RouteFamily.CLARIFY,
                confidence=confidence,
                ambiguity_flag=True,
            )
        return IntentDecision(
            route_family=route_family,
            confidence=confidence,
            ambiguity_flag=False,
        )

    @classmethod
    def from_library(
        cls,
        routes: dict[str, Iterable[str]] | None = None,
        encoder: Any | None = None,
        importer: Callable[[str], Any] = importlib.import_module,
        ambiguity_threshold: float = 0.45,
    ) -> "SemanticRouterAdapter":
        try:
            semantic_router = importer("semantic_router")
            layer_module = importer("semantic_router.layer")
        except ModuleNotFoundError as exc:
            raise AdapterDependencyUnavailableError(
                dependency_name="semantic_router",
                adapter_name="SemanticRouterAdapter",
            ) from exc

        if encoder is None:
            raise ValueError("SemanticRouterAdapter.from_library requires an encoder")

        route_objects = [
            semantic_router.Route(name=name, utterances=list(utterances))
            for name, utterances in (routes or {}).items()
        ]
        route_layer = layer_module.RouteLayer(encoder=encoder, routes=route_objects)
        return cls(route_layer=route_layer, ambiguity_threshold=ambiguity_threshold, library_routes=tuple(route_objects))

    @classmethod
    def from_local_library_routes(
        cls,
        *,
        routes: dict[str, Iterable[str]],
        importer: Callable[[str], Any] = importlib.import_module,
        ambiguity_threshold: float = 0.45,
    ) -> "SemanticRouterAdapter":
        try:
            semantic_router = importer("semantic_router")
        except ModuleNotFoundError as exc:
            raise AdapterDependencyUnavailableError(
                dependency_name="semantic_router",
                adapter_name="SemanticRouterAdapter",
            ) from exc

        route_objects = tuple(
            semantic_router.Route(name=name, utterances=list(utterances))
            for name, utterances in routes.items()
        )
        route_layer = _LocalSemanticRouteLayer(route_objects)
        return cls(route_layer=route_layer, ambiguity_threshold=ambiguity_threshold, library_routes=route_objects)

    def library_route_names(self) -> tuple[str, ...]:
        return tuple(str(getattr(route, "name")) for route in self._library_routes)

    @staticmethod
    def _route_family_from(result: Any) -> RouteFamily:
        name = result.get("name") if isinstance(result, dict) else getattr(result, "name", None)
        if name is None:
            raise ValueError("semantic route result missing name")
        return RouteFamily(name)

    @staticmethod
    def _confidence_from(result: Any) -> float:
        if isinstance(result, dict):
            raw = result.get("score", result.get("similarity_score", 0.0))
        else:
            raw = getattr(result, "score", getattr(result, "similarity_score", 0.0))
        return max(0.0, min(1.0, float(raw)))


class _LocalSemanticRouteLayer:
    def __init__(self, routes: tuple[Any, ...]) -> None:
        self._routes = routes

    def __call__(self, input_text: str) -> SimpleNamespace:
        input_tokens = _tokens(input_text)
        best_name = RouteFamily.CLARIFY.value
        best_score = 0.0
        for route in self._routes:
            utterances = tuple(getattr(route, "utterances", ()) or ())
            score = max((_overlap_score(input_tokens, _tokens(utterance)) for utterance in utterances), default=0.0)
            if score > best_score:
                best_name = str(getattr(route, "name"))
                best_score = score
        return SimpleNamespace(name=best_name, score=best_score)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _overlap_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))
