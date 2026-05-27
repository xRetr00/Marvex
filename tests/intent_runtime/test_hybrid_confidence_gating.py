from __future__ import annotations

from packages.intent_runtime import IntentClassificationRequest, IntentKind
from packages.intent_runtime.hybrid import HybridIntentRuntime


def _classify(text: str):
    request = IntentClassificationRequest(
        schema_version="1",
        trace_id="trace-intent-confidence",
        turn_id="turn-intent-confidence",
        user_input_summary=text,
    )
    return HybridIntentRuntime.default().classify(request)


def test_conversational_inputs_default_to_provider_chat() -> None:
    for text in (
        "Hello through ProviderWorker",
        "Hello there friend",
        "Explain why the sky is blue",
        "Tell me a joke",
        "Can you help me think this through?",
    ):
        result = _classify(text)

        assert result.selected_intent.intent_kind == IntentKind.PROVIDER_SIMPLE_CHAT
        assert result.confidence.score >= 0.45
        assert result.hybrid_details["route_fallback_reason"] == "provider.default_unmatched_or_low_confidence"


def test_special_routes_require_clear_signal_and_surface_confidence_details() -> None:
    examples = {
        "search latest browser-use version": IntentKind.WEB_SEARCH,
        "What model did OpenAI release this month?": IntentKind.WEB_SEARCH,
        "What changed in OpenAI models during May 2026?": IntentKind.WEB_SEARCH,
        "list MCP tools": IntentKind.MCP_NEEDED,
        "list tools": IntentKind.CAPABILITY_TOOL,
        "show me the PDF names on my desktop": IntentKind.FILE_READ_LIST_SEARCH,
        "write test.txt on my desktop": IntentKind.RISKY_ACTION,
        "what changed in my memory tree about Marvex?": IntentKind.MEMORY_TREE_NEEDED,
        "Use the calculator tool for 2+2": IntentKind.CAPABILITY_TOOL,
        "Give a grounded answer with current web evidence": IntentKind.GROUNDED_ANSWER,
    }

    for text, expected in examples.items():
        result = _classify(text)

        assert result.selected_intent.intent_kind == expected
        assert result.hybrid_details["semantic_encoder_backend_name"]
        assert result.hybrid_details["semantic_confidence_threshold"] >= 0.5
        assert result.hybrid_details["selected_route_confidence"] >= 0.0
        assert "route_fallback_reason" in result.hybrid_details
