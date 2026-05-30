"""Model-driven clarification via the clarify tool in the agentic loop."""

from packages.adapters.capabilities.tools import ToolRegistry, default_registry
from packages.adapters.capabilities.tools.clarify import (
    ClarifyTool,
    clarification_payload_from_arguments,
)
from packages.core.orchestration.agentic_tools import ProviderStep, execute_tool_calls, run_tool_loop


def _registry() -> ToolRegistry:
    return ToolRegistry((*default_registry().tools(), ClarifyTool()))


def _clarify_call(question: str, options: list[str]) -> dict:
    import json

    return {
        "id": "call-clarify",
        "function": {"name": "clarify", "arguments": json.dumps({"question": question, "options": options})},
    }


def test_clarify_call_is_intercepted_not_executed():
    outcome = execute_tool_calls(
        [_clarify_call("OpenAI or open-weight?", ["OpenAI", "open-weight"])],
        registry=_registry(),
        request_builder=lambda name, args: None,
    )
    assert len(outcome.needs_clarification) == 1
    result = outcome.needs_clarification[0]
    assert result.status == "needs_clarification"
    assert result.clarification is not None
    assert result.clarification["title"] == "OpenAI or open-weight?"
    # Nothing was "executed".
    assert outcome.executed_tool_ids == []


def test_loop_pauses_on_clarify_with_payload_and_response_id():
    def send(input_text, tool_messages, prev):
        if tool_messages is None:
            return ProviderStep(output_text="", tool_calls=[_clarify_call("Which one?", ["A", "B"])], response_id="resp-1", error=False)
        return ProviderStep(output_text="answered", tool_calls=[], response_id="resp-2", error=False)

    result = run_tool_loop(
        send=send,
        registry=_registry(),
        request_builder=lambda name, args: None,
        max_steps=4,
        initial_input="ambiguous request",
    )
    assert result.status == "needs_clarification"
    assert result.response_id == "resp-1"
    assert result.clarification is not None
    assert [option["label"] for option in result.clarification["options"]] == ["A", "B"]


def test_payload_has_text_kind_when_no_options():
    payload = clarification_payload_from_arguments({"question": "What do you mean?"})
    assert payload["kind"] == "text"
    assert payload["allow_custom"] is True
    assert payload["options"] == []


def test_payload_always_allows_custom_with_options():
    payload = clarification_payload_from_arguments({"question": "Pick one", "options": ["x", "y"]})
    assert payload["kind"] == "single"
    assert payload["allow_custom"] is True
    assert len(payload["options"]) == 2
