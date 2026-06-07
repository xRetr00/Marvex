from __future__ import annotations

from packages.adapters.capabilities.tools import ToolRegistry, WebFetchTool, default_registry
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
from packages.web_search_runtime import WebFetchResult


class _FakeFetcher:
    def __init__(self, *, result: WebFetchResult | None = None, raise_exc: bool = False) -> None:
        self.result = result or WebFetchResult(
            url="https://example.test/article",
            final_url="https://example.test/article",
            domain="example.test",
            title="Example article",
            text_preview="Readable article body",
            text_character_count=21,
        )
        self.raise_exc = raise_exc
        self.urls: list[str] = []

    def fetch(self, url: str, *, max_chars: int) -> WebFetchResult:
        self.urls.append(url)
        if self.raise_exc:
            raise RuntimeError("network down")
        return self.result.model_copy(update={"text_preview": self.result.text_preview[:max_chars]})


def _request(arguments: dict) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="web.fetch")
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id="p",
        trace_id="t",
        turn_id="u",
        capability_ref=ref,
        proposed_action="web.fetch",
        risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.NETWORK,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="d",
        capability_ref=ref,
        decision="approved",
        reason_code="ok",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id="r",
        trace_id="t",
        turn_id="u",
        proposal=proposal,
        permission_decision=permission,
        arguments=arguments,
    )


def test_web_fetch_returns_safe_page_projection() -> None:
    fetcher = _FakeFetcher()
    result = WebFetchTool(fetcher=fetcher).execute(_request({"url": "https://example.test/article", "max_chars": 12}))

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "web_fetch"
    assert result.safe_result["url"] == "https://example.test/article"
    assert result.safe_result["domain"] == "example.test"
    assert result.safe_result["text_preview"] == "Readable art"
    assert result.safe_result["raw_html_persisted"] is False
    assert fetcher.urls == ["https://example.test/article"]


def test_web_fetch_failure_is_graceful() -> None:
    result = WebFetchTool(fetcher=_FakeFetcher(raise_exc=True)).execute(_request({"url": "https://example.test"}))

    assert result.status == "succeeded"
    assert result.safe_result["operation"] == "web_fetch"
    assert result.safe_result["text_character_count"] == 0
    assert "error" in result.safe_result


def test_web_fetch_tool_schema_in_registry_when_added() -> None:
    registry = ToolRegistry((*default_registry().tools(), WebFetchTool(fetcher=_FakeFetcher())))
    ids = {schema["function"]["name"] for schema in registry.tool_schemas()}

    assert "web.fetch" in ids
