from __future__ import annotations

from datetime import UTC, datetime

from packages.assistant_runtime.input_normalization import build_text_input_event, build_turn_input_from_event
from packages.context_runtime import ContextCandidate, ContextSourceKind, ContextSourceRef, ContextSourceTrustLevel
from packages.intent_runtime import IntentKind, IntentRef
from packages.prompt_harness_runtime import PromptAssemblyRequest
from packages.prompt_harness_runtime.adaptive import AdaptivePromptRoute, adaptive_context_policy_for_route, assemble_adaptive_prompt_harness


def _turn_input(text: str = "Use a tool and remember the source.") -> object:
    event = build_text_input_event(
        schema_version="1",
        trace_id="trace-provider-compiler",
        event_id="event-provider-compiler",
        text=text,
        timestamp=datetime(2026, 5, 23, 12, 0, tzinfo=UTC),
    )
    return build_turn_input_from_event(
        schema_version="1",
        trace_id="trace-provider-compiler",
        turn_id="turn-provider-compiler",
        input_event=event,
    )


def _prompt_result():
    intent_ref = IntentRef(intent_id="intent.capability_tool", intent_kind=IntentKind.CAPABILITY_TOOL)
    policy = adaptive_context_policy_for_route(AdaptivePromptRoute.TOOL_USE)
    candidates = (
        ContextCandidate.from_safe_summary(
            ContextSourceRef(kind=ContextSourceKind.CAPABILITY_SCHEMA, identifier="builtin.calculator"),
            "tool=builtin.calculator; purpose=Safe arithmetic; risk=low; approval_required=False",
            token_estimate=24,
            intent_tags=(IntentKind.CAPABILITY_TOOL.value,),
        ),
        ContextCandidate.from_safe_summary(
            ContextSourceRef(kind=ContextSourceKind.MEMORY_PROJECTION, identifier="memory.user.preference"),
            "User prefers concise answers.",
            token_estimate=12,
            intent_tags=(IntentKind.CAPABILITY_TOOL.value,),
            trust_level=ContextSourceTrustLevel.UNTRUSTED_SUMMARY,
        ),
    )
    return assemble_adaptive_prompt_harness(
        PromptAssemblyRequest(
            schema_version="1",
            trace_id="trace-provider-compiler",
            turn_id="turn-provider-compiler",
            intent_ref=intent_ref,
            context_pack=policy.build_pack(
                schema_version="1",
                trace_id="trace-provider-compiler",
                turn_id="turn-provider-compiler",
                intent_ref=intent_ref,
                candidates=candidates,
            ),
        )
    )


def test_provider_prompt_compiler_is_single_marvex_identity_no_persona() -> None:
    from packages.agent_runtime import default_agent_catalog, default_persona_catalog
    from packages.prompt_harness_runtime.provider_compiler import compile_provider_prompt

    payload = compile_provider_prompt(
        turn_input=_turn_input(),
        prompt_result=_prompt_result(),
        agent_profile=default_agent_catalog().active_agent(),
        persona_profile=default_persona_catalog().active_persona(),
    )

    assert payload.instructions is not None
    # Marvex is Marvex: a single identity, with context-safety + policy.
    assert "You are Marvex" in payload.instructions
    assert "untrusted data" in payload.instructions
    assert "Marvex policy remains authoritative" in payload.instructions
    # No persona / agent-role / subagent / skill complexity in the prompt.
    assert "Active persona" not in payload.instructions
    assert "agent.main.marvex" not in payload.instructions
    assert "Selected agent" not in payload.instructions
    # It must not ADVERTISE subagents/personas it can't run (saying "no
    # subagents" is fine, claiming it "may propose bounded subagents" is not).
    assert "bounded subagents" not in payload.instructions
    assert "may propose" not in payload.instructions
    assert "female TTS voice profile" not in payload.instructions
    assert "skill.planning" not in payload.instructions
    # User context still flows through unchanged.
    assert "tool=builtin.calculator" in payload.input_text
    assert "User prefers concise answers" in payload.input_text
    assert payload.raw_prompt_persisted is False
    assert payload.safe_projection()["raw_prompt_persisted"] is False


def test_provider_stage_can_send_precompiled_prompt_payload() -> None:
    from packages.agent_runtime import default_agent_catalog, default_persona_catalog
    from packages.assistant_runtime.provider_stage import run_provider_stage_turn
    from packages.contracts import FinishReason, ProviderResponse
    from packages.prompt_harness_runtime.provider_compiler import compile_provider_prompt

    class RecordingProvider:
        def __init__(self) -> None:
            self.request = None

        def send(self, request):
            self.request = request
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="recording_provider",
                response_id="provider-response-compiled",
                output_text="ok",
                finish_reason=FinishReason.STOP,
                usage={},
                raw_metadata={},
                error=None,
            )

    provider = RecordingProvider()
    payload = compile_provider_prompt(
        turn_input=_turn_input(),
        prompt_result=_prompt_result(),
        agent_profile=default_agent_catalog().active_agent(),
        persona_profile=default_persona_catalog().active_persona(),
    )

    result = run_provider_stage_turn(_turn_input(), provider=provider, model="neutral-model", provider_prompt=payload)

    assert result.error is None
    assert provider.request.input_text == payload.input_text
    assert provider.request.instructions == payload.instructions


def test_provider_prompt_compiler_resolves_ids_for_telemetry_without_leaking_into_prompt() -> None:
    from packages.prompt_harness_runtime.provider_compiler import compile_provider_prompt

    selected_turn = _turn_input().model_copy(
        update={"metadata": {"agent_profile_id": "agent.deep_search", "persona_profile_id": "persona.marvex.female"}}
    )

    payload = compile_provider_prompt(turn_input=selected_turn, prompt_result=_prompt_result())

    # The ids still resolve for telemetry / control plane back-compat ...
    assert payload.agent_id == "agent.deep_search"
    assert payload.persona_id == "persona.marvex.female"
    # ... but they no longer shape the model prompt (Marvex is Marvex).
    assert "agent.deep_search" not in (payload.instructions or "")
    assert "Deep Search" not in (payload.instructions or "")
