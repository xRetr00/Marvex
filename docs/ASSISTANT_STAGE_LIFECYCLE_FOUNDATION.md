# Assistant Stage Lifecycle Foundation

## Status

The Assistant Stage Lifecycle Foundation is complete as an AssistantRuntime-owned
one-turn lifecycle layer.

It defines safe lifecycle primitives and projections for coordinating existing
foundation references across assistant runtime state, session/conversation
linkage, memory readiness, provider-stage execution, final response assembly,
and telemetry trace linkage.

## Lifecycle Order

AssistantRuntime owns the ordered lifecycle names:

1. `input_normalization`
2. `session_conversation_linkage`
3. `runtime_state_snapshot`
4. `memory_read_policy`
5. `provider_stage_preparation`
6. `provider_result_consumption`
7. `final_response_assembly`
8. `memory_write_candidate`
9. `memory_policy_hooks`
10. `telemetry_trace_linkage`

`validate_lifecycle_transition(...)` allows same-stage and forward movement and
rejects backwards movement. It is a validation primitive only; it is not a stage
scheduler, retry engine, cancellation engine, daemon supervisor, router, or
provider selector.

## Safe Summary Shape

`AssistantTurnLifecycleSummary.safe_projection()` may expose only:

- `trace_id` and `turn_id`
- safe `session_ref` and `conversation_ref`
- stage names, stage statuses, and ref/error presence booleans
- final-response presence and safe error code
- provider turn ref count and provider response id presence
- previous response id presence
- memory read/write/forget readiness booleans and safe counts
- telemetry event count and persistent trace linkage readiness
- `transcript_persisted: false`
- `raw_payload_persisted: false`

It must not expose raw prompts, raw user-visible input, raw assistant outputs,
final response text, provider payloads, provider outputs, provider response ids,
previous response ids, transcripts, tokens, credentials, secrets, or environment
values.

## Ownership Boundaries

AssistantRuntime owns lifecycle primitive definitions, safe lifecycle projection,
and one-turn stage coordination summaries.

Core may call approved AssistantRuntime provider-stage helpers, but Core remains
orchestration-only and does not own lifecycle internals.

SessionRuntime remains the owner of session/conversation linkage helpers,
registries, and projections. AssistantRuntime carries only approved contract refs
or presence bits.

MemoryRuntime remains the owner of memory refs, records, read queries, write
candidates, policy decisions, forget requests, stores, and safe projections.
AssistantRuntime records readiness and counts only; it does not import
MemoryRuntime or perform memory read/write/forget dispatch.

Telemetry remains the owner of trace event safety, persistence, and reads.
AssistantRuntime records event counts and trace-link readiness only.

Local API remains HTTP/auth/JSON-only. It must receive lifecycle data only
through injected handlers and must not import or construct lifecycle primitives.

RuntimeComposition remains explicit approved-path composition. It must not become
the lifecycle brain, memory brain, session brain, provider router, or service
registry.

ProviderRuntime remains provider construction only. It must not own assistant
stage lifecycle state.

local_service_startup remains startup token/discovery/startup metadata only.

## Still Blocked

This foundation does not implement tools, UI, voice, desktop context, vision,
proactive behavior, generic provider routing, retry/fallback/model selection,
embeddings, vector search, automatic memory extraction, raw transcript
persistence, daemon supervision, WebSocket/events, cross-process trace lookup,
or dependency additions.
