"""Tests for LiteLLM adapter opt-in tool-calling support (docs/TODO/02)."""

from types import SimpleNamespace

from packages.adapters.providers.litellm import LiteLLMProvider
from packages.adapters.providers.litellm import litellm_provider
from packages.contracts import FinishReason, ProviderRequest


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


def _completion(*, content="", tool_calls=None, finish_reason="stop"):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(
        id="resp-1",
        choices=[SimpleNamespace(finish_reason=finish_reason, message=message)],
        usage=SimpleNamespace(total_tokens=1),
    )


def test_no_tools_means_no_tools_key_sent(monkeypatch):
    calls = []
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: (calls.append(kw), _completion(content="hi"))[1])
    LiteLLMProvider().send(_request())
    assert "tools" not in calls[0]


def test_tools_are_forwarded_when_present(monkeypatch):
    calls = []
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: (calls.append(kw), _completion(content="hi"))[1])
    schema = [{"type": "function", "function": {"name": "file.list", "description": "list", "parameters": {"type": "object"}}}]
    LiteLLMProvider().send(_request(tools=schema))
    assert calls[0]["tools"] == schema


def test_tool_calls_are_parsed_from_response(monkeypatch):
    tool_calls = [
        SimpleNamespace(
            id="call_abc",
            function=SimpleNamespace(name="file.list", arguments='{"path": "Desktop"}'),
        )
    ]
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: _completion(content="", tool_calls=tool_calls, finish_reason="tool_calls"))
    response = LiteLLMProvider().send(_request(tools=[{"type": "function", "function": {"name": "file.list"}}]))
    assert response.tool_calls is not None
    assert response.tool_calls[0]["function"]["name"] == "file.list"
    assert response.tool_calls[0]["function"]["arguments"] == '{"path": "Desktop"}'
    assert response.tool_calls[0]["id"] == "call_abc"


def test_plain_text_response_has_no_tool_calls(monkeypatch):
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: _completion(content="just text"))
    response = LiteLLMProvider().send(_request())
    assert response.tool_calls is None
    assert response.output_text == "just text"


def test_tool_messages_are_appended_for_continuation(monkeypatch):
    calls = []
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: (calls.append(kw), _completion(content="done"))[1])
    tool_messages = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "file.list", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "c1", "content": "Desktop: a.txt, b.txt"},
    ]
    LiteLLMProvider().send(_request(tool_messages=tool_messages))
    sent = calls[0]["messages"]
    assert sent[-2]["role"] == "assistant"
    assert sent[-1]["role"] == "tool"
    assert sent[-1]["tool_call_id"] == "c1"


def test_malformed_tool_calls_are_skipped(monkeypatch):
    tool_calls = [
        SimpleNamespace(id="c1", function=SimpleNamespace(name="", arguments="{}")),  # empty name -> skipped
        SimpleNamespace(id="c2", function=SimpleNamespace(name="file.read", arguments=None)),  # arguments None -> "{}"
    ]
    monkeypatch.setattr(litellm_provider.litellm, "completion", lambda **kw: _completion(tool_calls=tool_calls))
    response = LiteLLMProvider().send(_request(tools=[{"type": "function", "function": {"name": "file.read"}}]))
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["function"]["name"] == "file.read"
    assert response.tool_calls[0]["function"]["arguments"] == "{}"
