"""Tests for the web.search agentic tool (docs/TODO/05)."""

from packages.adapters.capabilities.tools import ToolRegistry, WebSearchTool, default_registry
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.web_search_runtime import (
    WebSearchEvidenceRef,
    WebSearchGroundingBundle,
    WebSearchQuery,
    WebSearchResult,
)


class _FakeProvider:
    provider_name = "fake"

    def __init__(self, *, raise_exc: bool = False):
        self._raise = raise_exc
        self.queries: list[str] = []

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        self.queries.append(query.query)
        if self._raise:
            raise RuntimeError("network down")
        result = WebSearchResult(
            title="Open source - Wikipedia",
            url="https://en.wikipedia.org/wiki/Open_source",
            domain="en.wikipedia.org",
            snippet="Open source software is released under a license...",
        )
        evidence = WebSearchEvidenceRef(
            evidence_id="web.evidence.1",
            source_url="https://en.wikipedia.org/wiki/Open_source",
            domain="en.wikipedia.org",
            title="Open source - Wikipedia",
            snippet="Open source software...",
        )
        return WebSearchGroundingBundle(query=query, provider="fake", results=(result,), evidence_refs=(evidence,))


def _request(arguments: dict) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="web.search")
    proposal = CapabilityCallProposal(
        schema_version="1", proposal_id="p", trace_id="t", turn_id="u",
        capability_ref=ref, proposed_action="web.search", risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.NETWORK,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1", decision_id="d", capability_ref=ref, decision="approved",
        reason_code="ok", human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    return CapabilityExecutionRequest(
        schema_version="1", request_id="r", trace_id="t", turn_id="u",
        proposal=proposal, permission_decision=permission, arguments=arguments,
    )


def test_web_search_returns_results():
    provider = _FakeProvider()
    result = WebSearchTool(provider=provider).execute(_request({"query": "what is open source"}))
    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "web_search"
    assert result.safe_result["result_count"] == 1
    assert result.safe_result["results"][0]["domain"] == "en.wikipedia.org"
    assert result.safe_result["evidence_refs"][0]["evidence_id"] == "web.evidence.1"
    assert provider.queries == ["what is open source"]


def test_web_search_failure_is_graceful():
    result = WebSearchTool(provider=_FakeProvider(raise_exc=True)).execute(_request({"query": "x"}))
    # Failures degrade to an empty result with an error note, never crash.
    assert result.status == "succeeded"
    assert result.safe_result["result_count"] == 0
    assert "error" in result.safe_result


def test_web_search_is_safe_risk_so_it_auto_executes_in_loop():
    # SAFE risk => the agentic engine auto-runs it (no approval gate).
    assert WebSearchTool(provider=_FakeProvider()).risk_level is ToolRiskLevel.SAFE


def test_web_tool_schema_in_registry_when_added():
    registry = ToolRegistry((*default_registry().tools(), WebSearchTool(provider=_FakeProvider())))
    ids = {s["function"]["name"] for s in registry.tool_schemas()}
    assert "web.search" in ids
