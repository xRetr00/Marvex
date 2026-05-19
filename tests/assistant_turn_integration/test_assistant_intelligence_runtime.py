from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from packages.adapters.providers.tool_calls import ProviderToolCallSource
from packages.adapters.capabilities.mcp import McpAllowlist, McpServerRef, McpTransport
from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_turn_integration import EndToEndTurnStateStore, run_end_to_end_assistant_turn
from packages.capability_runtime import CapabilityExecutionMode
from packages.contracts import ConversationRef, SessionRef, TraceStage
from packages.intent_runtime import IntentKind
from packages.memory_runtime import MemoryRecord, MemoryRef, SQLiteMemoryStore
from packages.telemetry.search import TraceSearchQuery, search_traces


class FakeMcpSession:
    def __init__(self) -> None:
        self.initialized = 0
        self.called: list[tuple[str, dict[str, object]]] = []

    async def initialize(self) -> None:
        self.initialized += 1

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(name="safe_lookup", description="Read-only deterministic lookup.", inputSchema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}),
                Tool(name="run_shell", description="dangerous", inputSchema={"type": "object"}),
            ]
        )

    async def call_tool(self, name: str, arguments: dict[str, object]) -> CallToolResult:
        self.called.append((name, arguments))
        return CallToolResult(content=[TextContent(type="text", text="hidden raw result")], isError=False)


class FakeBrowserPage:
    def title(self) -> str:
        return "Public Example"

    def inner_text(self, selector: str) -> str:
        assert selector == "body"
        return "Public browser page text that remains outside persisted payloads."

def _turn_input(text: str):
    event = build_text_input_event(
        schema_version="1",
        trace_id="trace-intel-1",
        event_id="event-intel-1",
        text=text,
        timestamp="2026-05-18T12:00:00+00:00",
        session_id="session-intel-1",
    )
    return build_turn_input_from_event(schema_version="1", trace_id="trace-intel-1", turn_id="turn-intel-1", input_event=event)

def test_tool_using_turn_executes_allowlisted_mcp_tool_through_capability_policy() -> None:
    store = EndToEndTurnStateStore()
    session = FakeMcpSession()
    result = run_end_to_end_assistant_turn(
        _turn_input("Use the MCP safe lookup tool for a public weather summary"),
        model="fake-model",
        state_store=store,
        mcp_session=session,
        mcp_server_ref=McpServerRef(server_id="local-test", transport=McpTransport.STREAMABLE_HTTP, origin="manual_test_fixture"),
        mcp_allowlist=McpAllowlist(allowed_server_ids=("local-test",), allowed_tool_names=("safe_lookup", "run_shell")),
    )

    assert session.initialized == 1
    assert session.called == [("safe_lookup", {"query": "safe_lookup"})]
    assert result.intent_projection.selected_intent["intent_kind"] == "mcp_needed"
    assert result.tool_state_projection["result_status"] == "succeeded"
    assert result.tool_state_projection["provider_continuation_ready"] is True
    assert result.context_projection.included_sources == ({"kind": "user_input_summary", "identifier": "input.turn-intel-1"}, {"kind": "mcp_tool_schema", "identifier": "mcp.local-test.safe_lookup"})
    assert result.prompt_projection.section_kinds.count("capability_schema") == 1
    assert result.control_plane_summary["mcp_tool_count"] == 1
    assert result.telemetry_summary["mcp_execution_status"] == "succeeded"

    snapshot = store.control_plane_snapshot()
    assert snapshot.mcp_servers[0]["server_id"] == "local-test"
    assert snapshot.mcp_servers[0]["allowed_tool_count"] == 1
    serialized = snapshot.model_dump_json().lower()
    assert "hidden raw result" not in serialized
    assert "run_shell" not in serialized

    trace = store.trace_reader.read_trace("trace-intel-1")
    assert trace is not None
    stages = {event["stage"] for event in trace["events"]}
    assert TraceStage.TURN_RECEIVED.value in stages
    assert TraceStage.TURN_COMPLETED.value in stages

def test_browser_approval_can_resume_safe_approved_readiness_without_frontend_execution() -> None:
    store = EndToEndTurnStateStore()
    paused = run_end_to_end_assistant_turn(_turn_input("Click the browser button"), model="fake-model", state_store=store)

    assert paused.tool_state_projection["pending_approval_count"] == 1
    approval = store.approval_store.approve("approval-turn-intel-1", reason="user approved bounded test action")
    assert approval is not None
    assert approval.execution_started is False

    resumed = run_end_to_end_assistant_turn(
        _turn_input("Click the browser button"),
        model="fake-model",
        state_store=store,
        resume_approval_request_id="approval-turn-intel-1",
    )

    assert resumed.tool_state_projection["approval_decision"] == "approved"
    assert resumed.tool_state_projection["execution_request_present"] is True
    assert resumed.tool_state_projection["result_status"] == "requires_human_approval"
    assert resumed.control_plane_summary["approved_count"] == 1
    assert resumed.control_plane_summary["pending_approval_count"] == 0
    assert resumed.raw_payload_persisted is False

def test_intent_context_prompt_selects_skill_and_memory_without_dumping_all_tools() -> None:
    store = EndToEndTurnStateStore()
    result = run_end_to_end_assistant_turn(
        _turn_input("Use the writing skill and remember my short answer preference"),
        model="fake-model",
        state_store=store,
    )

    assert result.intent_projection.selected_intent["intent_kind"] in {"skill_needed", "memory"}
    assert result.context_projection.raw_context_persisted is False
    assert result.prompt_projection.raw_prompt_persisted is False
    assert result.prompt_projection.budget_report["within_budget"] is True
    assert result.prompt_projection.section_kinds.count("capability_schema") <= 1
    assert result.telemetry_summary["selected_capability_schema_count"] <= 1

def test_provider_tool_call_mapping_flows_through_integrated_capability_execution() -> None:
    result = run_end_to_end_assistant_turn(
        _turn_input("Use the calculator tool"),
        model="fake-model",
        provider_tool_call={"id": "call_calc", "function": {"name": "calculator", "arguments": "{\"expression\": \"2 + 2\"}"}},
        provider_tool_call_source=ProviderToolCallSource.LMSTUDIO,
    )

    assert result.tool_state_projection["provider_tool_call_source"] == "lmstudio"
    assert result.tool_state_projection["provider_tool_proposal_id"] == "lmstudio.call_calc"
    assert result.tool_state_projection["result_status"] == "succeeded"
    assert result.tool_state_projection["provider_continuation_ready"] is True
    assert "2 + 2" not in result.model_dump_json()

def test_memory_backend_refs_participate_in_context_and_trace_search(tmp_path) -> None:
    memory_store = SQLiteMemoryStore(memory_db_path=tmp_path / "memory.sqlite", local_user_root=tmp_path)
    memory_store.write_record(MemoryRecord(
        schema_version="1",
        memory_ref=MemoryRef(ref_type="memory", ref_id="memory-short-answer"),
        scope="session",
        memory_kind="preference",
        session_ref=SessionRef(ref_type="session", ref_id="session-intel-1"),
        conversation_ref=ConversationRef(ref_type="conversation", ref_id="conversation.turn-intel-1"),
        trace_id="trace-memory-seed",
        turn_id="turn-memory-seed",
        content="User prefers concise implementation status updates.",
        write_authorization="explicit_user",
        created_at=datetime(2026, 5, 18, tzinfo=UTC),
        tags=("preference",),
    ))
    store = EndToEndTurnStateStore(memory_store=memory_store)

    result = run_end_to_end_assistant_turn(
        _turn_input("Remember my short answer preference"),
        model="fake-model",
        state_store=store,
    )

    assert result.context_projection.included_sources[-1] == {"kind": "memory_projection", "identifier": "memory.memory-short-answer"}
    assert result.telemetry_summary["memory_context_ref_count"] == 1
    assert result.control_plane_summary["memory_ref_count"] == 1
    assert store.control_plane_snapshot().memory[0]["memory_ref"] == "memory-short-answer"

    traces = search_traces(
        store.trace_reader,
        TraceSearchQuery(schema_version="1", session_ref_id="session-intel-1", tool_status="not_executed", status="completed"),
        trace_ids=("trace-intel-1",),
    )
    assert traces.match_count == 1
    assert "concise implementation" not in str(traces.safe_projection()).lower()

def test_safe_browser_read_workflow_executes_live_adapter_without_approval() -> None:
    result = run_end_to_end_assistant_turn(
        _turn_input("Read the browser page text"),
        model="fake-model",
        browser_page=FakeBrowserPage(),
    )

    assert result.tool_state_projection["browser_action_kind"] == "extract_text"
    assert result.tool_state_projection["result_status"] == "succeeded"
    assert result.tool_state_projection["pending_approval_count"] == 0
    assert result.telemetry_summary["browser_execution_status"] == "succeeded"
    assert "Public browser page text" not in result.model_dump_json()

def test_semantic_router_classifier_can_drive_integrated_intent_without_policy_ownership() -> None:
    from packages.adapters.intent.harness_semantic_router import (
        RouteDefinition,
        RouteExample,
        SemanticRouteScore,
        SemanticRouterAdapterConfig,
        SemanticRouterHarnessAdapter,
        SemanticRouterThresholdPolicy,
    )

    config = SemanticRouterAdapterConfig(
        schema_version="1",
        backend_enabled=True,
        threshold_policy=SemanticRouterThresholdPolicy(min_confidence=0.6, clarification_confidence=0.45),
        routes=(
            RouteDefinition(route_id="route.mcp", intent_kind=IntentKind.MCP_NEEDED, examples=(RouteExample(text="use mcp safe lookup"),)),
            RouteDefinition(route_id="route.browser", intent_kind=IntentKind.BROWSER_COMPUTER_USE, examples=(RouteExample(text="read browser page"),)),
        ),
    )
    adapter = SemanticRouterHarnessAdapter(
        config=config,
        score_backend=lambda text, routes: (SemanticRouteScore(route_id="route.mcp", score=0.93),),
    )

    result = run_end_to_end_assistant_turn(
        _turn_input("Use the external protocol tool for a public lookup"),
        model="fake-model",
        intent_classifier=adapter.route_request,
    )

    assert result.intent_projection.selected_intent["intent_kind"] == "mcp_needed"
    assert result.intent_projection.route_reason_code == "semantic_router.score"
    assert result.tool_state_projection["result_status"] == "not_executed"
    assert result.control_plane_summary["intent_backend"] == "semantic_router"
    assert result.control_plane_summary["library_owns_policy"] is False

def test_memory_tree_evidence_participates_in_context_prompt_telemetry_and_control_plane() -> None:
    from packages.connector_runtime import ConnectorCategory, ConnectorRef
    from packages.memory_tree_runtime import CanonicalSourceMetadata, MemoryTreeRuntime, canonicalize_source_document, chunk_document

    metadata = CanonicalSourceMetadata(
        source_id="source-memory-tree",
        external_id="doc-1",
        uri="local://memory/doc-1",
        title="Memory Tree Plan",
        connector_ref=ConnectorRef(connector_id="local-memory", category=ConnectorCategory.GENERIC_OAUTH),
        captured_at=datetime(2026, 5, 18, tzinfo=UTC),
    )
    document = canonicalize_source_document(
        metadata=metadata,
        markdown_body="Memory tree evidence supports source grounded assistant context.",
        ingested_at=datetime(2026, 5, 18, tzinfo=UTC),
    )
    chunks = chunk_document(document, max_chars=120)
    memory_tree = MemoryTreeRuntime.with_documents(documents=(document,), chunks=chunks)
    store = EndToEndTurnStateStore()

    result = run_end_to_end_assistant_turn(
        _turn_input("Use memory tree evidence for this answer"),
        model="fake-model",
        state_store=store,
        memory_tree_runtime=memory_tree,
    )

    assert result.intent_projection.selected_intent["intent_kind"] == "memory_tree_needed"
    assert {source["identifier"] for source in result.context_projection.included_sources} >= {
        f"memory_tree.node.{chunks[0].chunk_id}",
        "memory_tree.digest.current",
    }
    assert "memory_context" in result.prompt_projection.section_kinds
    assert result.telemetry_summary["memory_tree_evidence_ref_count"] >= 2
    assert result.telemetry_summary["memory_tree_context_included"] is True
    assert result.control_plane_summary["memory_tree_evidence_ref_count"] >= 2
    serialized = result.model_dump_json().lower()
    assert "source grounded assistant context" not in serialized
    assert "quote_preview" not in serialized
