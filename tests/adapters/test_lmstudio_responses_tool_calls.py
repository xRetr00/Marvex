"""Tests for LMStudio Responses adapter tool-calling support (docs/TODO/02)."""

from types import SimpleNamespace

from packages.adapters.providers.lmstudio_responses import (
    LMStudioResponsesProvider,
    LMStudioResponsesProviderConfig,
)
from packages.contracts import ProviderRequest


def _request(**overrides) -> ProviderRequest:
    base = dict(
        schema_version="0.1.1-draft",
        trace_id="t-1",
        turn_id="u-1",
        model="qwen3.5-2b",
        input_text="list desktop files",
        instructions=None,
        previous_response_id=None,
        provider_options={},
    )
    base.update(overrides)
    return ProviderRequest(**base)


class _FakeResponses:
    def __init__(self, sink, response):
        self._sink = sink
        self._response = response

    def create(self, **kwargs):
        self._sink.append(kwargs)
        return self._response


class _FakeClient:
    def __init__(self, sink, response):
        self.responses = _FakeResponses(sink, response)


def _provider(sink, response):
    return LMStudioResponsesProvider(
        config=LMStudioResponsesProviderConfig(),
        client_factory=lambda **_kw: _FakeClient(sink, response),
    )


def _text_response(text="ok"):
    return SimpleNamespace(
        id="resp-1",
        status="completed",
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text=text)])],
        usage=SimpleNamespace(total_tokens=1),
    )


def test_no_tools_means_no_tools_key():
    sink: list[dict] = []
    _provider(sink, _text_response()).send(_request())
    assert "tools" not in sink[0]
    assert sink[0]["input"] == "list desktop files"


def test_tools_converted_to_flat_responses_shape():
    sink: list[dict] = []
    chat_schema = [
        {"type": "function", "function": {"name": "file.list", "description": "list dir", "parameters": {"type": "object"}}}
    ]
    _provider(sink, _text_response()).send(_request(tools=chat_schema))
    sent_tools = sink[0]["tools"]
    assert sent_tools == [
        {"type": "function", "name": "file.list", "description": "list dir", "parameters": {"type": "object"}}
    ]


def test_function_call_output_items_parsed_into_tool_calls():
    response = SimpleNamespace(
        id="resp-2",
        status="completed",
        output=[
            SimpleNamespace(type="function_call", call_id="fc_1", name="file.list", arguments='{"path": "Desktop"}'),
        ],
        usage=SimpleNamespace(total_tokens=1),
    )
    sink: list[dict] = []
    result = _provider(sink, response).send(_request(tools=[{"type": "function", "function": {"name": "file.list"}}]))
    assert result.tool_calls is not None
    assert result.tool_calls[0]["function"]["name"] == "file.list"
    assert result.tool_calls[0]["function"]["arguments"] == '{"path": "Desktop"}'
    assert result.tool_calls[0]["id"] == "fc_1"


def test_tool_messages_become_function_call_outputs():
    sink: list[dict] = []
    tool_messages = [
        {"role": "assistant", "content": None, "tool_calls": [{"id": "fc_1", "function": {"name": "file.list", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "fc_1", "content": "Desktop: a.txt"},
    ]
    _provider(sink, _text_response("done")).send(
        _request(previous_response_id="resp-prev", tool_messages=tool_messages)
    )
    sent_input = sink[0]["input"]
    assert isinstance(sent_input, list)
    assert sent_input == [
        {"type": "function_call_output", "call_id": "fc_1", "output": "Desktop: a.txt"}
    ]
    assert sink[0]["previous_response_id"] == "resp-prev"


def test_plain_text_response_has_no_tool_calls():
    sink: list[dict] = []
    result = _provider(sink, _text_response("hello")).send(_request())
    assert result.tool_calls is None
    assert result.output_text == "hello"
