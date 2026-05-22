from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.adapters.capabilities.mcp import McpAllowlist, McpClientSession, McpSdkAdapter, McpServerRef
from packages.capability_runtime import CapabilityExecutionRequest, CapabilityPermissionDecision, HumanApprovalRequirement
from packages.desktop_agent_runtime.models import DesktopContentItem, DesktopRecallResult

_RECALL_TOOL_PRIORITY = ("screenpipe_recall", "screenpipe.search", "safe_lookup")
_MIN_LIMIT = 1
_MAX_LIMIT = 20


class ScreenpipeRecallProjection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    server_id: str
    transport: str
    status: Literal["succeeded", "failed", "denied", "not_available"]
    reason_code: str | None = None
    tool_name: str | None = None
    requested_limit: int = Field(ge=1)
    bounded_limit: int = Field(ge=1, le=20)
    result_content_count: int = 0
    result_content_types: tuple[str, ...] = ()
    structured_content_present: bool = False
    raw_screen_persisted: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False
    raw_mcp_payload_persisted: Literal[False] = False


ScreenpipeRecallProjection.model_rebuild()


async def recall_screenpipe_via_mcp(
    *,
    session: McpClientSession,
    server_ref: McpServerRef,
    allowlist: McpAllowlist,
    query: str,
    limit: int = 5,
) -> ScreenpipeRecallProjection:
    bounded_limit = max(_MIN_LIMIT, min(_MAX_LIMIT, limit))
    adapter = McpSdkAdapter(session=session, allowlist=allowlist)
    listings = await adapter.discover_tools(server_ref)
    listing = _pick_allowed_recall_listing(listings)
    if listing is None:
        return ScreenpipeRecallProjection(
            server_id=server_ref.server_id,
            transport=server_ref.transport.value,
            status="not_available",
            reason_code="no_allowlisted_recall_tool",
            requested_limit=limit,
            bounded_limit=bounded_limit,
        )

    proposal = adapter.create_call_proposal(
        listing,
        proposal_id=f"screenpipe.recall.{server_ref.server_id}",
        trace_id=f"trace.screenpipe.{server_ref.server_id}",
        turn_id=f"turn.screenpipe.{server_ref.server_id}",
    )
    decision = CapabilityPermissionDecision(
        schema_version="1",
        decision_id=f"decision.{proposal.proposal_id}",
        capability_ref=proposal.capability_ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    request = CapabilityExecutionRequest(
        schema_version="1",
        request_id=f"request.{proposal.proposal_id}",
        trace_id=proposal.trace_id,
        turn_id=proposal.turn_id,
        proposal=proposal,
        permission_decision=decision,
        arguments={"query": query, "limit": bounded_limit},
    )
    result = await adapter.call_approved_tool(server_ref, request)
    safe_result = result.safe_result
    return ScreenpipeRecallProjection(
        server_id=server_ref.server_id,
        transport=server_ref.transport.value,
        status=result.status if result.status in {"succeeded", "failed", "denied"} else "failed",
        reason_code=safe_result.get("reason_code") if isinstance(safe_result.get("reason_code"), str) else None,
        tool_name=listing.tool_ref.tool_name,
        requested_limit=limit,
        bounded_limit=bounded_limit,
        result_content_count=_as_int(safe_result.get("content_count")),
        result_content_types=_as_str_tuple(safe_result.get("content_types")),
        structured_content_present=bool(safe_result.get("structured_content_present")),
    )


def _pick_allowed_recall_listing(listings: tuple) -> object | None:
    allowed = [listing for listing in listings if getattr(listing, "allowed", False)]
    if not allowed:
        return None
    by_name = {listing.tool_ref.tool_name: listing for listing in allowed}
    for candidate in _RECALL_TOOL_PRIORITY:
        if candidate in by_name:
            return by_name[candidate]
    return allowed[0]


def _as_int(value: object) -> int:
    return value if isinstance(value, int) else 0


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def screenpipe_projection_to_desktop_recall(
    projection: ScreenpipeRecallProjection,
    *,
    trace_id: str,
    query_summary: str,
) -> DesktopRecallResult:
    text = (
        f"screenpipe recall status={projection.status}; "
        f"tool={projection.tool_name or 'none'}; "
        f"content_count={projection.result_content_count}; "
        f"content_types={','.join(projection.result_content_types) or 'none'}"
    )
    if projection.reason_code:
        text += f"; reason={projection.reason_code}"
    return DesktopRecallResult(
        trace_id=trace_id,
        query_summary=query_summary[:240] or "screenpipe recall",
        items=(
            DesktopContentItem.from_text(
                source_kind="screenpipe_recall",
                text=text,
                application="screenpipe",
            ),
        ),
    )
