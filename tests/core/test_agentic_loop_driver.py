"""Tests for the agentic tool-loop driver (docs/TODO/02, P2.3)."""

from pathlib import Path

from packages.adapters.capabilities.tools import ToolRegistry, default_registry, file_tools_registry, memory_tools_registry
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
from packages.contracts import SessionRef
from packages.core.orchestration.agentic_tools import ProviderStep, run_tool_loop
from packages.memory_runtime import CurrentProcessMemoryStore


def _combined_registry() -> ToolRegistry:
    return ToolRegistry((*default_registry().tools(), *file_tools_registry().tools()))


def _memory_registry() -> ToolRegistry:
    return memory_tools_registry(
        memory_store=CurrentProcessMemoryStore(),
        session_ref=SessionRef(ref_type="session", ref_id="session-memory-driver"),
    )


def _builder(root: str | None = None):
    def build(tool_id: str, arguments: dict) -> CapabilityExecutionRequest:
        ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier=tool_id)
        args = dict(arguments)
        if root is not None and tool_id.startswith("file."):
            args.setdefault("root", root)
        proposal = CapabilityCallProposal(
            schema_version="1", proposal_id=f"p.{tool_id}", trace_id="t", turn_id="u",
            capability_ref=ref, proposed_action=tool_id, risk_level=ToolRiskLevel.SAFE,
            side_effect_level=ToolSideEffectLevel.READ_ONLY,
            execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY, arguments_schema={"type": "object"},
        )
        permission = CapabilityPermissionDecision(
            schema_version="1", decision_id="d", capability_ref=ref, decision="approved",
            reason_code="ok", human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
        )
        return CapabilityExecutionRequest(
            schema_version="1", request_id="r", trace_id="t", turn_id="u",
            proposal=proposal, permission_decision=permission, arguments=args,
        )

    return build


def _builder_with_query(root: str, natural_query: str):
    def build(tool_id: str, arguments: dict) -> CapabilityExecutionRequest:
        args = dict(arguments)
        if tool_id.startswith("file."):
            args.setdefault("root", root)
            args.setdefault("natural_query", natural_query)
        return _builder()(tool_id, args)

    return build


def _fc(name: str, arguments: str, call_id: str = "c1") -> dict:
    return {"id": call_id, "type": "function", "function": {"name": name, "arguments": arguments}}


def test_immediate_text_answer_finalizes():
    sends = []

    def send(input_text, tool_messages, prev):
        sends.append((input_text, tool_messages, prev))
        return ProviderStep(output_text="hello there", tool_calls=[], response_id="r1", error=False)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="hi")
    assert result.status == "final"
    assert result.text == "hello there"
    assert result.steps == 1
    assert len(sends) == 1


def test_reasoning_only_response_is_retried_for_a_user_facing_answer():
    steps = [
        ProviderStep(
            output_text="<think>I should answer the greeting.</think>",
            tool_calls=[],
            response_id="r1",
            error=False,
        ),
        ProviderStep(
            output_text="I'm doing well. How can I help?",
            tool_calls=[],
            response_id="r2",
            error=False,
        ),
    ]
    seen = []

    def send(input_text, tool_messages, prev):
        seen.append((input_text, tool_messages, prev))
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="How are you?")

    assert result.status == "final"
    assert result.text == "I'm doing well. How can I help?"
    assert result.response_id == "r2"
    assert seen[1][2] == "r1"
    assert "user-facing answer" in seen[1][0]


def test_single_tool_call_then_text():
    # Step 1: model calls calculator. Step 2: model answers with the result.
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("builtin.calculator", '{"expression": "6*7"}')], response_id="r1", error=False),
        ProviderStep(output_text="The answer is 42.", tool_calls=[], response_id="r2", error=False),
    ]
    seen = []

    def send(input_text, tool_messages, prev):
        seen.append((input_text, tool_messages, prev))
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="what is 6*7")
    assert result.status == "final"
    assert result.text == "The answer is 42."
    assert result.executed_tool_ids == ["builtin.calculator"]
    assert result.steps == 2
    # Second send carried the tool result messages and the chained response id.
    assert seen[1][1] is not None  # tool_messages threaded
    assert any(m.get("role") == "tool" and "42" in str(m.get("content")) for m in seen[1][1])
    assert seen[1][2] == "r1"  # previous_response_id chained


def test_model_authored_text_before_tool_call_is_preserved_as_commentary():
    steps = [
        ProviderStep(
            output_text="<think>private plan</think>I'm locating MAR.txt on your Desktop.",
            tool_calls=[_fc("file.read", '{"path": "Desktop/MAR.txt"}')],
            response_id="r1",
            error=False,
            usage={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14},
        ),
        ProviderStep(
            output_text="MAR.txt contains test data.",
            tool_calls=[],
            response_id="r2",
            error=False,
            usage={
                "input_tokens": 20,
                "output_tokens": 6,
                "total_tokens": 26,
                "input_tokens_details": {"cached_tokens": 5},
            },
        ),
    ]

    def send(input_text, tool_messages, prev):
        return steps.pop(0)

    result = run_tool_loop(
        send=send,
        registry=_combined_registry(),
        request_builder=_builder(),
        max_steps=5,
        initial_input="read MAR.txt",
    )

    assert result.status == "final"
    assert result.text == "MAR.txt contains test data."
    assert result.commentary == ["I'm locating MAR.txt on your Desktop."]
    assert result.usage == {
        "input_tokens": 30,
        "output_tokens": 10,
        "total_tokens": 40,
        "input_tokens_details": {"cached_tokens": 5},
    }


def test_loop_can_resume_from_an_approved_tool_result():
    initial_messages = [
        {"role": "assistant", "content": None, "tool_calls": [_fc("file.write", '{"path":"note.txt","content":"done"}')]},
        {"role": "tool", "tool_call_id": "c1", "content": '{"status":"succeeded"}'},
    ]
    seen = []

    def send(input_text, tool_messages, prev):
        seen.append((input_text, tool_messages, prev))
        return ProviderStep(output_text="The file is written.", tool_calls=[], response_id="r2", error=False)

    result = run_tool_loop(
        send=send,
        registry=default_registry(),
        request_builder=_builder(),
        max_steps=5,
        initial_input="write the note",
        previous_response_id="r1",
        initial_tool_messages=initial_messages,
    )

    assert result.status == "final"
    assert result.text == "The file is written."
    assert seen == [("", initial_messages, "r1")]


def test_risky_tool_stops_for_approval(tmp_path: Path):
    def send(input_text, tool_messages, prev):
        return ProviderStep(
            output_text="", tool_calls=[_fc("file.write", '{"path": "x.txt", "content": "data"}')],
            response_id="r1", error=False,
        )

    result = run_tool_loop(send=send, registry=_combined_registry(), request_builder=_builder(root=str(tmp_path)), max_steps=5, initial_input="write a file")
    assert result.status == "needs_approval"
    assert result.needs_approval_tool_ids == ["file.write"]
    assert not (tmp_path / "x.txt").exists()  # never executed


def test_memory_write_search_and_forget_never_stop_for_approval():
    calls = [
        ProviderStep(output_text="", tool_calls=[_fc("memory.remember", '{"content": "User prefers concise answers.", "scope": "session"}', "remember")], response_id="r1", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("memory.search", '{"query": "concise", "scope": "session"}', "search")], response_id="r2", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("memory.forget", '{"memory_ref": "memory.missing"}', "forget")], response_id="r3", error=False),
        ProviderStep(output_text="Memory operations completed.", tool_calls=[], response_id="r4", error=False),
    ]

    def send(_input_text, _tool_messages, _prev):
        return calls.pop(0)

    result = run_tool_loop(
        send=send,
        registry=_memory_registry(),
        request_builder=_builder(),
        max_steps=5,
        initial_input="run memory operations",
    )

    assert result.status == "final"
    assert result.needs_approval_tool_ids == []
    assert result.executed_tool_ids == ["memory.remember", "memory.search", "memory.forget"]
    assert result.text == "Memory operations completed."


def test_provider_error_returns_error_status():
    def send(input_text, tool_messages, prev):
        return ProviderStep(output_text="", tool_calls=[], response_id=None, error=True)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=5, initial_input="hi")
    assert result.status == "error"


def test_max_steps_exhausted_when_model_keeps_calling_tools():
    def send(input_text, tool_messages, prev):
        # Always asks for a tool again -> never finalizes.
        return ProviderStep(output_text="", tool_calls=[_fc("builtin.time_date", "{}")], response_id="r", error=False)

    result = run_tool_loop(send=send, registry=default_registry(), request_builder=_builder(), max_steps=3, initial_input="time?")
    assert result.status == "max_steps"
    assert result.steps == 3
    assert result.executed_tool_ids == ["builtin.time_date", "builtin.time_date", "builtin.time_date"]


def test_long_dependent_tool_chain_can_continue_past_six_steps(tmp_path: Path):
    (tmp_path / "Desktop").mkdir()
    (tmp_path / "Desktop" / "MAR.txt").write_text("chain evidence", encoding="utf-8")
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("file.rg", '{"path": ".", "query": "MAR"}', "c1")], response_id="r1", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.read", '{"path": "Desktop/MAR.txt"}', "c2")], response_id="r2", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.list", '{"path": "Desktop"}', "c3")], response_id="r3", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("builtin.time_date", "{}", "c4")], response_id="r4", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.rg", '{"path": ".", "query": "chain"}', "c5")], response_id="r5", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.read", '{"path": "Desktop/MAR.txt"}', "c6")], response_id="r6", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.list", '{"path": "."}', "c7")], response_id="r7", error=False),
        ProviderStep(output_text="Completed the dependent chain.", tool_calls=[], response_id="r8", error=False),
    ]
    seen_previous_ids = []

    def send(input_text, tool_messages, prev):
        seen_previous_ids.append(prev)
        return steps.pop(0)

    result = run_tool_loop(
        send=send,
        registry=_combined_registry(),
        request_builder=_builder(root=str(tmp_path)),
        max_steps=12,
        initial_input="rg then read then list then continue",
    )

    assert result.status == "final"
    assert result.steps == 8
    assert result.executed_tool_ids == [
        "file.rg",
        "file.read",
        "file.list",
        "builtin.time_date",
        "file.rg",
        "file.read",
        "file.list",
    ]
    assert seen_previous_ids[1:] == ["r1", "r2", "r3", "r4", "r5", "r6", "r7"]


def test_web_search_through_loop_answers_latest_question():
    """Item 05 end-to-end: a 'latest model by Anthropic' style question -> the
    model calls web.search, gets fresh results, then answers with them, instead
    of confidently stating a stale fact from memory."""
    from packages.adapters.capabilities.tools import WebSearchTool
    from packages.web_search_runtime import (
        WebSearchEvidenceRef,
        WebSearchGroundingBundle,
        WebSearchResult,
    )

    class _FakeWeb:
        provider_name = "fake"

        def search(self, query):
            result = WebSearchResult(
                title="Anthropic launches Claude Opus 4.6",
                url="https://www.anthropic.com/news/claude-opus-4-6",
                domain="anthropic.com",
                snippet="Anthropic's latest model is Claude Opus 4.6.",
            )
            evidence = WebSearchEvidenceRef(
                evidence_id="web.evidence.1", source_url="https://www.anthropic.com/news/claude-opus-4-6",
                domain="anthropic.com", title="Claude Opus 4.6", snippet="latest model",
            )
            return WebSearchGroundingBundle(query=query, provider="fake", results=(result,), evidence_refs=(evidence,))

    registry = ToolRegistry((*default_registry().tools(), WebSearchTool(provider=_FakeWeb())))

    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("web.search", '{"query": "latest model by Anthropic"}')], response_id="r1", error=False),
        ProviderStep(output_text="Anthropic's latest model is Claude Opus 4.6 [web.evidence.1].", tool_calls=[], response_id="r2", error=False),
    ]

    def send(input_text, tool_messages, prev):
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=registry, request_builder=_builder(), max_steps=5, initial_input="what is the latest model by anthropic")
    assert result.status == "final"
    assert result.executed_tool_ids == ["web.search"]
    assert "4.6" in result.text


def test_web_search_then_file_write_requires_source_in_written_content(tmp_path: Path):
    from packages.adapters.capabilities.tools import WebSearchTool
    from packages.web_search_runtime import (
        WebSearchEvidenceRef,
        WebSearchGroundingBundle,
        WebSearchResult,
    )

    class _FakeWeb:
        provider_name = "fake"

        def search(self, query):
            result = WebSearchResult(
                title="OpenAI API models",
                url="https://developers.openai.com/api/docs/models/gpt-5.5",
                domain="developers.openai.com",
                snippet="GPT-5.5 is OpenAI's newest frontier model.",
            )
            evidence = WebSearchEvidenceRef(
                evidence_id="web.evidence.1",
                source_url="https://developers.openai.com/api/docs/models/gpt-5.5",
                domain="developers.openai.com",
                title="GPT-5.5 Model",
                snippet="newest frontier model",
            )
            return WebSearchGroundingBundle(query=query, provider="fake", results=(result,), evidence_refs=(evidence,))

    registry = ToolRegistry((*default_registry().tools(), *file_tools_registry().tools(), WebSearchTool(provider=_FakeWeb())))
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("web.search", '{"query": "latest OpenAI model"}', "c-search")], response_id="r1", error=False),
        ProviderStep(output_text="", tool_calls=[_fc("file.write", '{"path": "latest.md", "content": "The latest OpenAI model is GPT-5.5."}', "c-write-bad")], response_id="r2", error=False),
        ProviderStep(
            output_text="",
            tool_calls=[
                _fc(
                    "file.write",
                    '{"path": "latest.md", "content": "The latest OpenAI model is GPT-5.5. Source: https://developers.openai.com/api/docs/models/gpt-5.5"}',
                    "c-write-good",
                )
            ],
            response_id="r3",
            error=False,
        ),
    ]
    seen_tool_messages = []

    def send(input_text, tool_messages, prev):
        if tool_messages:
            seen_tool_messages.append(tool_messages)
        return steps.pop(0)

    result = run_tool_loop(
        send=send,
        registry=registry,
        request_builder=_builder(root=str(tmp_path)),
        max_steps=5,
        initial_input="search web for the latest OpenAI model and write the result to a file",
    )

    assert result.status == "needs_approval"
    assert result.needs_approval_tool_ids == ["file.write"]
    assert result.pending_tool is not None
    assert result.pending_tool["arguments"]["content"].endswith("/gpt-5.5")
    assert "include at least one source URL" in str(seen_tool_messages)


def test_real_file_read_through_loop(tmp_path: Path):
    (tmp_path / "note.txt").write_text("project alpha status: green", encoding="utf-8")
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("file.read", '{"path": "note.txt"}')], response_id="r1", error=False),
        ProviderStep(output_text="The note says project alpha is green.", tool_calls=[], response_id="r2", error=False),
    ]

    def send(input_text, tool_messages, prev):
        return steps.pop(0)

    result = run_tool_loop(send=send, registry=_combined_registry(), request_builder=_builder(root=str(tmp_path)), max_steps=5, initial_input="read note.txt and summarize")
    assert result.status == "final"
    assert result.executed_tool_ids == ["file.read"]
    assert "green" in result.text


def test_file_read_directory_call_can_resolve_from_original_user_query(tmp_path: Path):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    (desktop / "MAR.txt").write_text("Marvex desktop note", encoding="utf-8")
    steps = [
        ProviderStep(output_text="", tool_calls=[_fc("file.read", '{"path": "Desktop"}')], response_id="r1", error=False),
        ProviderStep(output_text="The desktop file says Marvex desktop note.", tool_calls=[], response_id="r2", error=False),
    ]
    seen_tool_messages = []

    def send(input_text, tool_messages, prev):
        if tool_messages:
            seen_tool_messages.append(tool_messages)
        return steps.pop(0)

    result = run_tool_loop(
        send=send,
        registry=_combined_registry(),
        request_builder=_builder_with_query(str(tmp_path), "read MAR.txt from Desktop"),
        max_steps=5,
        initial_input="read MAR.txt from Desktop",
    )

    assert result.status == "final"
    assert result.executed_tool_ids == ["file.read"]
    assert "Marvex desktop note" in str(seen_tool_messages)
