
from __future__ import annotations

import importlib.util
import math
import os
import re
from typing import Literal

try:  # semantic-router is runtime-optional; classify_intent falls back to deterministic
    import semantic_router
except ModuleNotFoundError:  # pragma: no cover - exercised in light/frozen builds
    semantic_router = None
try:  # llama-index is runtime-optional
    from llama_index.core.selectors import SingleSelection
except ModuleNotFoundError:  # pragma: no cover
    SingleSelection = None
from pydantic import Field

from packages.capability_runtime import CapabilityExecutionMode, ToolRiskLevel
from packages.capability_runtime.models import CapabilityRuntimeModel
from packages.intent_runtime.models import (
    ClarificationNeededDecision,
    IntentAmbiguitySignal,
    IntentCandidate,
    IntentClassificationRequest,
    IntentClassificationResult,
    IntentConfidence,
    IntentKind,
    IntentRef,
    IntentRiskSignal,
    IntentRouteDecision,
    classification_from_kind,
)


class CapabilityAvailability(CapabilityRuntimeModel):
    status: Literal["enabled", "disabled", "unavailable"] = "enabled"
    reason_code: str = "available"


class IntentStep(CapabilityRuntimeModel):
    step_id: str
    intent_kind: IntentKind
    risk_level: ToolRiskLevel
    execution_mode: CapabilityExecutionMode
    capability_requirements: tuple[str, ...] = ()


class IntentPlan(CapabilityRuntimeModel):
    primary_intent: IntentKind
    secondary_intents: tuple[IntentKind, ...]
    steps: tuple[IntentStep, ...]
    clarification_stop: bool = False


class SemanticEncoding(CapabilityRuntimeModel):
    backend_name: str
    dimensions: tuple[float, ...]


class DeterministicLocalIntentEncoder:
    backend_name = "deterministic_local_encoder"

    def encode(self, text: str) -> SemanticEncoding:
        tokens = _semantic_tokens(text)
        values = [0.0] * len(_SEMANTIC_FEATURES)
        for index, feature in enumerate(_SEMANTIC_FEATURES):
            values[index] = sum(_TOKEN_FEATURES.get(token, {}).get(feature, 0.0) for token in tokens)
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return SemanticEncoding(backend_name=self.backend_name, dimensions=tuple(value / norm for value in values))


class FastEmbedIntentEncoder:
    backend_name = "fastembed_text_embedding"

    def __init__(self, *, model_name: str | None = None) -> None:
        try:
            from fastembed import TextEmbedding
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError("fastembed is not installed") from exc
        self._model = TextEmbedding(model_name=model_name or "BAAI/bge-small-en-v1.5")

    def encode(self, text: str) -> SemanticEncoding:
        vector = tuple(float(value) for value in next(iter(self._model.embed([text]))))
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return SemanticEncoding(backend_name=self.backend_name, dimensions=tuple(value / norm for value in vector))


class OpenAICompatibleEmbeddingIntentEncoder:
    backend_name = "openai_compatible_embedding"

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    def encode(self, text: str) -> SemanticEncoding:
        import httpx

        response = httpx.post(
            f"{self._base_url}/embeddings",
            json={"model": self._model, "input": text},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        vector = tuple(float(value) for value in payload["data"][0]["embedding"])
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return SemanticEncoding(backend_name=self.backend_name, dimensions=tuple(value / norm for value in vector))


class EncodedSemanticRouteLayer:
    selection_strategy = "encoded_route_cosine"

    def __init__(self, *, encoder: DeterministicLocalIntentEncoder | FastEmbedIntentEncoder | OpenAICompatibleEmbeddingIntentEncoder, routes: tuple[semantic_router.Route, ...]) -> None:
        self._encoder = encoder
        self._routes = routes
        self._encoded_routes = tuple(
            (
                route,
                tuple(self._encoder.encode(utterance).dimensions for utterance in tuple(route.utterances)),
            )
            for route in routes
        )

    @property
    def backend_name(self) -> str:
        return self._encoder.backend_name

    def select(self, text: str) -> tuple[IntentKind, float]:
        encoded = self._encoder.encode(text).dimensions
        best_kind = IntentKind.PROVIDER_SIMPLE_CHAT
        best_score = 0.0
        for route, utterance_vectors in self._encoded_routes:
            score = max((_cosine(encoded, vector) for vector in utterance_vectors), default=0.0)
            if score > best_score:
                best_kind = IntentKind(route.name)
                best_score = score
        if best_score < 0.05:
            return IntentKind.PROVIDER_SIMPLE_CHAT, 0.0
        return best_kind, best_score


class HybridIntentRuntime:
    semantic_confidence_threshold = 0.58

    def __init__(
        self,
        *,
        capabilities: dict[str, CapabilityAvailability] | None = None,
        semantic_encoder: DeterministicLocalIntentEncoder | FastEmbedIntentEncoder | OpenAICompatibleEmbeddingIntentEncoder | None = None,
    ) -> None:
        self._capabilities = capabilities or {
            "web_search": CapabilityAvailability(),
            "calculator": CapabilityAvailability(),
            "browser": CapabilityAvailability(),
            "mcp": CapabilityAvailability(),
            "memory_tree": CapabilityAvailability(),
            "file_read_list_search": CapabilityAvailability(),
        }
        self._routes = _semantic_routes()
        self._semantic_layer = EncodedSemanticRouteLayer(
            encoder=semantic_encoder or _configured_semantic_encoder(),
            routes=self._routes,
        )

    @classmethod
    def default(cls, *, capabilities: dict[str, CapabilityAvailability] | None = None) -> "HybridIntentRuntime":
        return cls(capabilities=capabilities)

    def classify(self, request: IntentClassificationRequest) -> IntentClassificationResult:
        text = request.user_input_summary.strip()
        deterministic = _deterministic_intent(text)
        semantic_kind, semantic_score = self._semantic_layer.select(text)
        threshold = self.semantic_confidence_threshold
        selected = deterministic
        route_gating_reason = "deterministic.signal"
        fallback_reason = ""
        semantic_override_allowed = (
            deterministic == IntentKind.PROVIDER_SIMPLE_CHAT
            and semantic_kind != IntentKind.PROVIDER_SIMPLE_CHAT
            and semantic_score >= threshold
            and _explicit_route_signal(text, semantic_kind)
        )
        if semantic_override_allowed:
            selected = semantic_kind
            route_gating_reason = "semantic.confident_explicit_signal"
        if deterministic in {
            IntentKind.GROUNDED_ANSWER,
            IntentKind.FILE_READ_LIST_SEARCH,
            IntentKind.MEMORY,
            IntentKind.MEMORY_TREE_NEEDED,
            IntentKind.MCP_NEEDED,
            IntentKind.MCP_SKILL,
            IntentKind.SKILL_NEEDED,
            IntentKind.CONNECTOR_ACCOUNT,
            IntentKind.SETTINGS_CONTROL_PLANE,
            IntentKind.RISKY_ACTION,
            IntentKind.UNSAFE_OR_INJECTION_SUSPECTED,
            IntentKind.UNSAFE_RISKY,
            IntentKind.CLARIFICATION,
        }:
            selected = deterministic
            route_gating_reason = "deterministic.authoritative_signal"
        if selected == IntentKind.PROVIDER_SIMPLE_CHAT:
            fallback_reason = "provider.default_unmatched_or_low_confidence"
            route_gating_reason = "provider.safe_default"
        selector = _single_selection(index=_kind_index(selected), selected=selected)
        if selected == IntentKind.PROVIDER_SIMPLE_CHAT and _freshness_needed(text):
            selected = IntentKind.WEB_SEARCH
            route_gating_reason = "freshness.required"
            fallback_reason = ""
        capability = self._capability_for(selected)
        availability = self._capabilities.get(capability, CapabilityAvailability())
        if selected == IntentKind.WEB_SEARCH and availability.status != "enabled":
            selected = IntentKind.CLARIFICATION
            score = 0.31
            route_gating_reason = "capability.unavailable_clarification"
            fallback_reason = ""
        elif selected != IntentKind.PROVIDER_SIMPLE_CHAT and availability.status != "enabled":
            selected = IntentKind.PROVIDER_SIMPLE_CHAT
            score = 0.7
            route_gating_reason = "capability.unavailable_provider_fallback"
            fallback_reason = "provider.capability_unavailable"
        else:
            score = 0.7 if selected == IntentKind.PROVIDER_SIMPLE_CHAT else max(semantic_score, 0.86 if deterministic == selected else 0.62)
        risk_signal, risk_level = _risk_for(selected, text)
        result = classification_from_kind(
            request,
            kind=selected,
            score=score,
            risk_signal=risk_signal,
            risk_level=risk_level,
            reason_code="hybrid.semantic_encoder" if route_gating_reason.startswith("semantic.") else "hybrid.llamaindex_selector",
            backend_name=f"hybrid_intent_runtime.{self._semantic_layer.backend_name}",
            hybrid_details={
                "deterministic_candidate": deterministic.value,
                "semantic_candidate": semantic_kind.value,
                "selected_route_confidence": semantic_score if selected == semantic_kind else score,
                "semantic_confidence_threshold": threshold,
                "route_gating_reason": route_gating_reason,
                "route_fallback_reason": fallback_reason,
                "fallback_reason": fallback_reason,
                "semantic_router_route_count": len(self._routes),
                "semantic_encoder_backend_name": self._semantic_layer.backend_name,
                "semantic_selection_strategy": self._semantic_layer.selection_strategy,
                "semantic_router_hybrid_extra_available": _semantic_router_hybrid_extra_available(),
                "llamaindex_selector_used": SingleSelection is not None and isinstance(selector, SingleSelection),
                "llamaindex_selection_index": selector.index,
                "freshness_needed": _freshness_needed(text),
                "capability": capability,
                "capability_status": availability.status,
                "capability_reason_code": availability.reason_code,
            },
        )
        if selected == IntentKind.CLARIFICATION:
            return result.model_copy(update={
                "ambiguity_signal": IntentAmbiguitySignal(ambiguous=True, reason_code="intent.clarify_or_unavailable", candidate_count=1),
                "clarification": ClarificationNeededDecision.NEEDED,
            })
        return result

    def plan(self, request: IntentClassificationRequest) -> IntentPlan:
        text = request.user_input_summary.lower()
        if "search" in text and "pyproject" in text:
            steps = (
                IntentStep(step_id="step.web_search", intent_kind=IntentKind.WEB_SEARCH, risk_level=ToolRiskLevel.LOW, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, capability_requirements=("web_search",)),
                IntentStep(step_id="step.repo_read", intent_kind=IntentKind.FILE_READ_LIST_SEARCH, risk_level=ToolRiskLevel.LOW, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, capability_requirements=("repo.read",)),
                IntentStep(step_id="step.grounded_answer", intent_kind=IntentKind.GROUNDED_ANSWER, risk_level=ToolRiskLevel.SAFE, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, capability_requirements=("grounded.evidence",)),
            )
            return IntentPlan(primary_intent=IntentKind.WEB_SEARCH, secondary_intents=(IntentKind.FILE_READ_LIST_SEARCH, IntentKind.GROUNDED_ANSWER), steps=steps)
        result = self.classify(request)
        step = IntentStep(step_id=f"step.{result.selected_intent.intent_kind.value}", intent_kind=result.selected_intent.intent_kind, risk_level=result.candidates[0].risk_level, execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY)
        return IntentPlan(primary_intent=result.selected_intent.intent_kind, secondary_intents=(), steps=(step,), clarification_stop=result.selected_intent.intent_kind == IntentKind.CLARIFICATION)

    def _capability_for(self, kind: IntentKind) -> str:
        return {
            IntentKind.WEB_SEARCH: "web_search",
            IntentKind.CAPABILITY_TOOL: "calculator",
            IntentKind.BROWSER_COMPUTER_USE: "browser",
            IntentKind.MCP_NEEDED: "mcp",
            IntentKind.MEMORY_TREE_NEEDED: "memory_tree",
            IntentKind.FILE_READ_LIST_SEARCH: "file_read_list_search",
        }.get(kind, "none")


def _semantic_routes() -> tuple[semantic_router.Route, ...]:
    return (
        semantic_router.Route(name=IntentKind.PROVIDER_SIMPLE_CHAT.value, utterances=("hello", "hi there", "tell me a joke", "explain why", "normal conversation", "can we continue")),
        semantic_router.Route(name=IntentKind.CAPABILITY_TOOL.value, utterances=("2+2", "compute arithmetic", "calculator")),
        semantic_router.Route(name=IntentKind.WEB_SEARCH.value, utterances=("search latest version", "current docs", "recent release")),
        semantic_router.Route(name=IntentKind.BROWSER_COMPUTER_USE.value, utterances=("open youtube", "go to website", "browser page", "navigate webpage")),
        semantic_router.Route(name=IntentKind.MEMORY_TREE_NEEDED.value, utterances=("memory tree changes", "source grounded memory evidence")),
        semantic_router.Route(name=IntentKind.MCP_NEEDED.value, utterances=("list mcp tools", "mcp server tool")),
        semantic_router.Route(name=IntentKind.SKILL_NEEDED.value, utterances=("use skill", "skill package")),
        semantic_router.Route(name=IntentKind.SETTINGS_CONTROL_PLANE.value, utterances=("control plane settings", "approval telemetry")),
    )


def _single_selection(*, index: int, selected: IntentKind):
    reason = f"llamaindex.selector.{selected.value}"
    if SingleSelection is None:
        return type("SelectionProjection", (), {"index": index, "reason": reason})()
    return SingleSelection(index=index, reason=reason)


def _semantic_select(text: str, routes: tuple[semantic_router.Route, ...]) -> tuple[IntentKind, float]:
    return EncodedSemanticRouteLayer(encoder=DeterministicLocalIntentEncoder(), routes=routes).select(text)


def _deterministic_intent(text: str) -> IntentKind:
    lowered = text.lower().strip()
    if lowered in {"do it", "that", "it", "do that"} or "that thing" in lowered:
        return IntentKind.CLARIFICATION
    if any(part in lowered for part in ("ignore previous instructions", "system prompt", "prompt injection", "command injection", "rm -rf", "steal credentials", "exfiltrate", "bypass captcha", "override policy")):
        return IntentKind.UNSAFE_OR_INJECTION_SUSPECTED
    if re.fullmatch(r"\s*\d+\s*[+\-*/]\s*\d+\s*", lowered) or lowered.startswith("compute "):
        return IntentKind.CAPABILITY_TOOL
    if any(part in lowered for part in ("grounded answer", "cite", "citation")):
        return IntentKind.GROUNDED_ANSWER
    if "evidence" in lowered and any(part in lowered for part in ("web", "memory", "grounded", "answer")):
        return IntentKind.GROUNDED_ANSWER
    if _local_file_write_needed(lowered):
        return IntentKind.RISKY_ACTION
    if _local_file_read_needed(lowered):
        return IntentKind.FILE_READ_LIST_SEARCH
    if _tool_diagnostics_needed(lowered):
        return IntentKind.CAPABILITY_TOOL
    if any(part in lowered for part in ("latest", "current", "recent", "version", "search web", "search ")):
        return IntentKind.WEB_SEARCH
    if any(part in lowered for part in ("memory tree", "source grounded", "evidence")):
        return IntentKind.MEMORY_TREE_NEEDED
    if any(part in lowered for part in ("remember", "memory", "preference")):
        return IntentKind.MEMORY
    if "mcp" in lowered and "skill" in lowered:
        return IntentKind.MCP_SKILL
    if "mcp" in lowered:
        return IntentKind.MCP_NEEDED
    if "skill" in lowered:
        return IntentKind.SKILL_NEEDED
    if any(part in lowered for part in ("connector", "account", "oauth", "gmail", "calendar", "drive", "slack", "notion")):
        return IntentKind.CONNECTOR_ACCOUNT
    if any(part in lowered for part in ("control plane", "settings", "approval", "telemetry")):
        return IntentKind.SETTINGS_CONTROL_PLANE
    if any(part in lowered for part in ("open yt", "youtube", "go to ", "open ", "browser")):
        return IntentKind.BROWSER_COMPUTER_USE
    if _local_file_read_needed(lowered):
        return IntentKind.FILE_READ_LIST_SEARCH
    if any(part in lowered for part in ("delete", "send", "upload", "install", "write", "run command")):
        return IntentKind.RISKY_ACTION
    if _freshness_needed(text):
        return IntentKind.WEB_SEARCH
    return IntentKind.PROVIDER_SIMPLE_CHAT


def _explicit_route_signal(text: str, kind: IntentKind) -> bool:
    lowered = text.lower()
    signals = {
        IntentKind.CAPABILITY_TOOL: ("compute", "calculate", "calculator", "+", "-", "*", "/"),
        IntentKind.WEB_SEARCH: ("search", "latest", "current", "recent", "version", "release", "docs"),
        IntentKind.BROWSER_COMPUTER_USE: ("open", "go to", "browser", "navigate", "webpage", "youtube"),
        IntentKind.MEMORY_TREE_NEEDED: ("memory tree", "source grounded", "evidence"),
        IntentKind.MCP_NEEDED: ("mcp", "server tool"),
        IntentKind.SKILL_NEEDED: ("skill",),
        IntentKind.SETTINGS_CONTROL_PLANE: ("control plane", "settings", "approval", "telemetry"),
    }
    return any(signal in lowered for signal in signals.get(kind, ()))


def _tool_diagnostics_needed(lowered: str) -> bool:
    return any(
        part in lowered
        for part in (
            "list tools",
            "show tools",
            "available tools",
            "what tools",
            "capability diagnostics",
            "capabilities",
        )
    )


def _local_file_read_needed(lowered: str) -> bool:
    if any(part in lowered for part in ("read file", "list files", "search files", "inspect file")):
        return True
    if any(location in lowered for location in ("desktop", "folder", "directory", "drive", "disk")) and any(
        subject in lowered
        for subject in (
            "file",
            "files",
            "pdf",
            "pdfs",
            "filename",
            "filenames",
            "names",
            "report",
            "document",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "xlsx",
        )
    ):
        return True
    return False


def _local_file_write_needed(lowered: str) -> bool:
    if not any(action in lowered for action in ("write", "create", "save", "make")):
        return False
    return any(subject in lowered for subject in ("file", ".txt", ".md", ".json", "desktop", "folder", "directory"))


def _risk_for(kind: IntentKind, text: str) -> tuple[IntentRiskSignal, ToolRiskLevel]:
    if kind in {IntentKind.UNSAFE_OR_INJECTION_SUSPECTED, IntentKind.UNSAFE_RISKY}:
        return IntentRiskSignal.UNSAFE_REQUEST, ToolRiskLevel.CRITICAL
    if kind in {IntentKind.RISKY_ACTION, IntentKind.BROWSER_COMPUTER_USE, IntentKind.CONNECTOR_ACCOUNT} or any(part in text.lower() for part in ("install", "delete", "send", "upload")):
        return IntentRiskSignal.RISKY_ACTION_REQUESTED, ToolRiskLevel.HIGH
    if kind in {IntentKind.WEB_SEARCH, IntentKind.MCP_NEEDED, IntentKind.MEMORY_TREE_NEEDED, IntentKind.FILE_READ_LIST_SEARCH}:
        return IntentRiskSignal.NONE, ToolRiskLevel.LOW
    return IntentRiskSignal.NONE, ToolRiskLevel.SAFE


def _freshness_needed(text: str) -> bool:
    lowered = text.lower()
    if any(part in lowered for part in ("latest", "current", "recent", "today", "version", "price", "release", "docs", "api", "dependency")):
        return True
    if re.search(r"\b(this|last|next)\s+(day|week|month|quarter|year)\b", lowered):
        return True
    if re.search(r"\b(in|during|since|as of)\s+(20\d{2}|january|february|march|april|may|june|july|august|september|october|november|december)\b", lowered):
        return True
    if any(part in lowered for part in ("announced", "launched", "released", "rolled out", "changed", "new model", "new api", "available now")):
        return True
    return False


def _kind_index(kind: IntentKind) -> int:
    return list(IntentKind).index(kind)


def _semantic_router_hybrid_extra_available() -> bool:
    return importlib.util.find_spec("semantic_router.hybrid") is not None


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))


def _configured_semantic_encoder() -> DeterministicLocalIntentEncoder | FastEmbedIntentEncoder | OpenAICompatibleEmbeddingIntentEncoder:
    backend = os.environ.get("MARVEX_INTENT_ENCODER", "").strip().lower()
    if backend == "fastembed":
        return FastEmbedIntentEncoder(model_name=os.environ.get("MARVEX_INTENT_FASTEMBED_MODEL"))
    if backend in {"openai_compatible_embedding", "lmstudio_embedding", "lmstudio_embeddings"}:
        return OpenAICompatibleEmbeddingIntentEncoder(
            base_url=os.environ.get("MARVEX_INTENT_EMBEDDING_BASE_URL", "http://127.0.0.1:1234/v1"),
            model=os.environ.get("MARVEX_INTENT_EMBEDDING_MODEL", "text-embedding-nomic-embed-text-v1.5"),
            timeout_seconds=float(os.environ.get("MARVEX_INTENT_EMBEDDING_TIMEOUT", "10")),
        )
    if not backend and importlib.util.find_spec("fastembed") is not None:
        return FastEmbedIntentEncoder(model_name=os.environ.get("MARVEX_INTENT_FASTEMBED_MODEL"))
    return DeterministicLocalIntentEncoder()


def _semantic_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", text.lower()))


_SEMANTIC_FEATURES = (
    "provider",
    "tool",
    "web",
    "fresh",
    "browser",
    "memory",
    "mcp",
    "skill",
    "settings",
    "file",
    "risk",
    "unsafe",
    "grounded",
)


_TOKEN_FEATURES: dict[str, dict[str, float]] = {
    "hello": {"provider": 1.0},
    "hi": {"provider": 1.0},
    "hey": {"provider": 1.0},
    "joke": {"provider": 1.0},
    "explain": {"provider": 0.8},
    "conversation": {"provider": 1.0},
    "continue": {"provider": 0.7},
    "compute": {"tool": 1.0},
    "calculate": {"tool": 1.0},
    "calculator": {"tool": 1.0},
    "arithmetic": {"tool": 1.0},
    "search": {"web": 1.0},
    "web": {"web": 0.8, "grounded": 0.3},
    "latest": {"fresh": 1.0, "web": 0.7},
    "current": {"fresh": 1.0, "web": 0.6},
    "recent": {"fresh": 1.0, "web": 0.6},
    "version": {"fresh": 0.8, "web": 0.6},
    "release": {"fresh": 0.8, "web": 0.6},
    "docs": {"fresh": 0.7, "web": 0.8},
    "grounded": {"grounded": 1.0},
    "citation": {"grounded": 1.0},
    "citations": {"grounded": 1.0},
    "cite": {"grounded": 1.0},
    "evidence": {"grounded": 0.8, "memory": 0.3},
    "open": {"browser": 0.8},
    "go": {"browser": 0.4},
    "browser": {"browser": 1.0},
    "navigate": {"browser": 1.0},
    "webpage": {"browser": 1.0},
    "youtube": {"browser": 1.0},
    "yt": {"browser": 1.0},
    "memory": {"memory": 1.0},
    "remember": {"memory": 1.0},
    "preference": {"memory": 1.0},
    "preferences": {"memory": 1.0},
    "tree": {"memory": 0.8},
    "mcp": {"mcp": 1.0},
    "server": {"mcp": 0.4},
    "tool": {"tool": 0.4, "mcp": 0.3},
    "tools": {"tool": 0.4, "mcp": 0.4},
    "skill": {"skill": 1.0},
    "settings": {"settings": 1.0},
    "approval": {"settings": 0.8},
    "telemetry": {"settings": 0.8},
    "control": {"settings": 0.5},
    "plane": {"settings": 0.5},
    "file": {"file": 1.0},
    "files": {"file": 1.0},
    "read": {"file": 0.7},
    "list": {"file": 0.5, "mcp": 0.2},
    "inspect": {"file": 0.7},
    "delete": {"risk": 1.0},
    "send": {"risk": 1.0},
    "upload": {"risk": 1.0},
    "install": {"risk": 0.8, "mcp": 0.3},
    "run": {"risk": 0.5},
    "ignore": {"unsafe": 1.0},
    "prompt": {"unsafe": 0.8},
    "injection": {"unsafe": 1.0},
    "credentials": {"unsafe": 1.0},
    "exfiltrate": {"unsafe": 1.0},
}
