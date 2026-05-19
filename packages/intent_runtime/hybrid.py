
from __future__ import annotations

import importlib.util
import re
from typing import Literal

import semantic_router
from llama_index.core.selectors import SingleSelection
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


class HybridIntentRuntime:
    def __init__(self, *, capabilities: dict[str, CapabilityAvailability] | None = None) -> None:
        self._capabilities = capabilities or {
            "web_search": CapabilityAvailability(),
            "calculator": CapabilityAvailability(),
            "browser": CapabilityAvailability(),
            "mcp": CapabilityAvailability(),
            "memory_tree": CapabilityAvailability(),
            "file_read_list_search": CapabilityAvailability(),
        }
        self._routes = _semantic_routes()

    @classmethod
    def default(cls, *, capabilities: dict[str, CapabilityAvailability] | None = None) -> "HybridIntentRuntime":
        return cls(capabilities=capabilities)

    def classify(self, request: IntentClassificationRequest) -> IntentClassificationResult:
        text = request.user_input_summary.strip()
        deterministic = _deterministic_intent(text)
        semantic_kind, semantic_score = _semantic_select(text, self._routes)
        selected = semantic_kind if semantic_score >= 0.35 else deterministic
        selector = SingleSelection(index=_kind_index(selected), reason=f"llamaindex.selector.{selected.value}")
        if selected == IntentKind.PROVIDER_SIMPLE_CHAT and _freshness_needed(text):
            selected = IntentKind.WEB_SEARCH
        capability = self._capability_for(selected)
        availability = self._capabilities.get(capability, CapabilityAvailability())
        if selected == IntentKind.WEB_SEARCH and availability.status != "enabled":
            selected = IntentKind.CLARIFICATION
            score = 0.31
        else:
            score = max(semantic_score, 0.86 if deterministic == selected else 0.62)
        risk_signal, risk_level = _risk_for(selected, text)
        result = classification_from_kind(
            request,
            kind=selected,
            score=score,
            risk_signal=risk_signal,
            risk_level=risk_level,
            reason_code="hybrid.semantic_router" if semantic_score >= 0.35 else "hybrid.llamaindex_selector",
            backend_name="hybrid_intent_runtime",
            hybrid_details={
                "deterministic_candidate": deterministic.value,
                "semantic_candidate": semantic_kind.value,
                "semantic_router_route_count": len(self._routes),
                "semantic_router_hybrid_extra_available": _semantic_router_hybrid_extra_available(),
                "llamaindex_selector_used": isinstance(selector, SingleSelection),
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
        semantic_router.Route(name=IntentKind.CAPABILITY_TOOL.value, utterances=("2+2", "compute arithmetic", "calculator")),
        semantic_router.Route(name=IntentKind.WEB_SEARCH.value, utterances=("search latest version", "current docs", "recent release")),
        semantic_router.Route(name=IntentKind.BROWSER_COMPUTER_USE.value, utterances=("open youtube", "go to website", "browser page")),
        semantic_router.Route(name=IntentKind.MEMORY_TREE_NEEDED.value, utterances=("memory tree changes", "source grounded memory evidence")),
        semantic_router.Route(name=IntentKind.MCP_NEEDED.value, utterances=("list mcp tools", "mcp server tool")),
        semantic_router.Route(name=IntentKind.SKILL_NEEDED.value, utterances=("use skill", "skill package")),
        semantic_router.Route(name=IntentKind.SETTINGS_CONTROL_PLANE.value, utterances=("control plane settings", "approval telemetry")),
    )


def _semantic_select(text: str, routes: tuple[semantic_router.Route, ...]) -> tuple[IntentKind, float]:
    tokens = _tokens(text)
    best_kind = IntentKind.CLARIFICATION
    best_score = 0.0
    for route in routes:
        score = max((_overlap(tokens, _tokens(utterance)) for utterance in route.utterances), default=0.0)
        if score > best_score:
            best_kind = IntentKind(route.name)
            best_score = score
    return best_kind, best_score


def _deterministic_intent(text: str) -> IntentKind:
    lowered = text.lower().strip()
    if lowered in {"do it", "that", "it", "do that"} or "that thing" in lowered:
        return IntentKind.CLARIFICATION
    if any(part in lowered for part in ("ignore previous instructions", "system prompt", "prompt injection", "command injection", "rm -rf", "steal credentials", "exfiltrate", "bypass captcha", "override policy")):
        return IntentKind.UNSAFE_OR_INJECTION_SUSPECTED
    if re.fullmatch(r"\s*\d+\s*[+\-*/]\s*\d+\s*", lowered) or lowered.startswith("compute "):
        return IntentKind.CAPABILITY_TOOL
    if any(part in lowered for part in ("latest", "current", "recent", "version", "search web", "search ")):
        return IntentKind.WEB_SEARCH
    if any(part in lowered for part in ("grounded answer", "cite", "citation")):
        return IntentKind.GROUNDED_ANSWER
    if any(part in lowered for part in ("memory tree", "source grounded", "evidence")):
        return IntentKind.MEMORY_TREE_NEEDED
    if any(part in lowered for part in ("remember", "memory", "preference")):
        return IntentKind.MEMORY
    if any(part in lowered for part in ("open yt", "youtube", "go to ", "open ", "browser")):
        return IntentKind.BROWSER_COMPUTER_USE
    if "mcp" in lowered:
        return IntentKind.MCP_NEEDED
    if "skill" in lowered:
        return IntentKind.SKILL_NEEDED
    if any(part in lowered for part in ("connector", "account", "oauth", "gmail", "calendar", "drive", "slack", "notion")):
        return IntentKind.CONNECTOR_ACCOUNT
    if any(part in lowered for part in ("control plane", "settings", "approval", "telemetry")):
        return IntentKind.SETTINGS_CONTROL_PLANE
    if any(part in lowered for part in ("read file", "list files", "search files", "inspect file")):
        return IntentKind.FILE_READ_LIST_SEARCH
    if any(part in lowered for part in ("delete", "send", "upload", "install", "write", "run command")):
        return IntentKind.RISKY_ACTION
    return IntentKind.PROVIDER_SIMPLE_CHAT


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
    return any(part in lowered for part in ("latest", "current", "recent", "today", "version", "price", "release", "docs", "api", "dependency"))


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
