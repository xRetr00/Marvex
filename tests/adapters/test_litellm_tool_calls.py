"""Tests for LiteLLM adapter opt-in tool-calling support (docs/TODO/02)."""

from types import SimpleNamespace

from packages.adapters.providers.litellm import LiteLLMProvider
from packages.adapters.providers.litellm import litellm_provider
from packages.contracts import ProviderRequest


def _request(**overrides) -> ProviderRequest:
    base = dict(
        schema_version="0.1.1-draft",
        trace_id="trace-1",
        turn_id="turn-1",
        model="openrouter/test-model",
        input_text="list my desktop files",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )
    base.update(overrides)
    return ProviderRequest(**base)


def _responses(*, content="", output=None, status="completed"):
    return SimpleNamespace(
        id="resp-1",
        status=status,
        output_text=content,
        output=output or [],
        usage=SimpleNamespace(total_tokens=1),
    )


def test_no_tools_means_no_tools_key_sent(monkeypatch):
    calls = []
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: (calls.append(kw), _responses(content="hi"))[1],
    )
    LiteLLMProvider().send(_request())
    assert "tools" not in calls[0]


def test_tools_are_converted_to_responses_function_tools(monkeypatch):
    calls = []
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: (calls.append(kw), _responses(content="hi"))[1],
    )
    schema = [
        {
            "type": "function",
            "function": {
                "name": "file.list",
                "description": "list",
                "parameters": {"type": "object"},
            },
        }
    ]
    LiteLLMProvider().send(_request(tools=schema))
    assert calls[0]["tools"] == [
        {
            "type": "function",
            "name": "file.list",
            "description": "list",
            "parameters": {"type": "object"},
        }
    ]


def test_tool_calls_are_parsed_from_responses_output(monkeypatch):
    output = [
        SimpleNamespace(
            type="function_call",
            id="item_abc",
            call_id="call_abc",
            name="file.list",
            arguments='{"path": "Desktop"}',
        )
    ]
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: _responses(output=output),
    )
    response = LiteLLMProvider().send(
        _request(tools=[{"type": "function", "function": {"name": "file.list"}}])
    )
    assert response.tool_calls is not None
    assert response.tool_calls[0]["function"]["name"] == "file.list"
    assert response.tool_calls[0]["function"]["arguments"] == '{"path": "Desktop"}'
    assert response.tool_calls[0]["id"] == "call_abc"


def test_plain_text_response_has_no_tool_calls(monkeypatch):
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: _responses(content="just text"),
    )
    response = LiteLLMProvider().send(_request())
    assert response.tool_calls is None
    assert response.output_text == "just text"


def test_tool_messages_become_function_call_output_items(monkeypatch):
    calls = []
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: (calls.append(kw), _responses(content="done"))[1],
    )
    tool_messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "file.list", "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": "Desktop: a.txt, b.txt"},
    ]
    LiteLLMProvider().send(_request(tool_messages=tool_messages))
    assert calls[0]["input"] == [
        {
            "type": "function_call_output",
            "call_id": "c1",
            "output": "Desktop: a.txt, b.txt",
        }
    ]


def test_malformed_tool_calls_are_skipped(monkeypatch):
    output = [
        SimpleNamespace(type="function_call", id="c1", name="", arguments="{}"),
        SimpleNamespace(
            type="function_call",
            id="c2",
            name="file.read",
            arguments=None,
        ),
    ]
    monkeypatch.setattr(
        litellm_provider.litellm,
        "responses",
        lambda **kw: _responses(output=output),
    )
    response = LiteLLMProvider().send(
        _request(tools=[{"type": "function", "function": {"name": "file.read"}}])
    )
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["function"]["name"] == "file.read"
    assert response.tool_calls[0]["function"]["arguments"] == "{}"
