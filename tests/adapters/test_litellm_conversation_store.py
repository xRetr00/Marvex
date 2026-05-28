"""Tests for the LiteLLM client-side conversation store and multi-turn wiring."""

from types import SimpleNamespace

from packages.adapters.providers.litellm import (
    LiteLLMConversationStore,
    LiteLLMProvider,
)
from packages.adapters.providers.litellm import litellm_provider
from packages.contracts import ProviderRequest


def _make_request(
    *,
    input_text: str = "Hello",
    previous_response_id: str | None = None,
    instructions: str | None = "Follow system guidance.",
) -> ProviderRequest:
    return ProviderRequest(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        model="openrouter/test-model",
        input_text=input_text,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options={},
    )


def _make_completion(*, response_id: str, content: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content=content),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )


def test_store_recall_returns_empty_for_unknown_ids():
    store = LiteLLMConversationStore()
    assert store.recall(None) == []
    assert store.recall("") == []
    assert store.recall("unknown") == []


def test_store_remember_and_recall_roundtrip():
    store = LiteLLMConversationStore()
    payload = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    store.remember("resp-1", payload)
    recalled = store.recall("resp-1")
    assert recalled == payload
    # Returned list is an independent copy.
    recalled.append({"role": "user", "content": "mutate"})
    assert store.recall("resp-1") == payload


def test_store_evicts_oldest_when_capacity_exceeded():
    store = LiteLLMConversationStore(max_entries=2)
    store.remember("a", [{"role": "user", "content": "1"}])
    store.remember("b", [{"role": "user", "content": "2"}])
    store.remember("c", [{"role": "user", "content": "3"}])
    assert store.recall("a") == []
    assert store.recall("b") == [{"role": "user", "content": "2"}]
    assert store.recall("c") == [{"role": "user", "content": "3"}]


def test_provider_without_store_preserves_single_message_behaviour(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _make_completion(response_id="r1", content="ok")

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    LiteLLMProvider().send(
        _make_request(previous_response_id="ignored-when-no-store")
    )

    assert calls[0]["messages"] == [
        {"role": "system", "content": "Follow system guidance."},
        {"role": "user", "content": "Hello"},
    ]


def test_provider_with_store_threads_prior_messages_into_next_turn(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _make_completion(response_id=f"resp-{len(calls)}", content=f"reply-{len(calls)}")

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    store = LiteLLMConversationStore()
    provider = LiteLLMProvider(conversation_store=store)

    first = provider.send(_make_request(input_text="hi", previous_response_id=None))
    assert first.response_id == "resp-1"
    assert calls[0]["messages"] == [
        {"role": "system", "content": "Follow system guidance."},
        {"role": "user", "content": "hi"},
    ]

    provider.send(
        _make_request(
            input_text="and again",
            previous_response_id="resp-1",
            instructions=None,
        )
    )

    assert calls[1]["messages"] == [
        {"role": "system", "content": "Follow system guidance."},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "reply-1"},
        {"role": "user", "content": "and again"},
    ]


def test_provider_with_store_replaces_system_when_instructions_change(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs):
        calls.append(kwargs)
        return _make_completion(response_id=f"resp-{len(calls)}", content="ok")

    monkeypatch.setattr(litellm_provider.litellm, "completion", fake_completion)

    store = LiteLLMConversationStore()
    provider = LiteLLMProvider(conversation_store=store)

    provider.send(_make_request(input_text="hi", previous_response_id=None))
    provider.send(
        _make_request(
            input_text="next",
            previous_response_id="resp-1",
            instructions="Use a stricter tone.",
        )
    )

    assert calls[1]["messages"][0] == {
        "role": "system",
        "content": "Use a stricter tone.",
    }
    # Old system message is dropped; prior user/assistant pair survives.
    system_count = sum(1 for m in calls[1]["messages"] if m["role"] == "system")
    assert system_count == 1


def test_provider_with_store_skips_recording_on_error(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("upstream blew up")

    monkeypatch.setattr(litellm_provider.litellm, "completion", boom)

    store = LiteLLMConversationStore()
    provider = LiteLLMProvider(conversation_store=store)

    response = provider.send(_make_request(input_text="hi"))
    assert response.error is not None
    assert len(store) == 0
