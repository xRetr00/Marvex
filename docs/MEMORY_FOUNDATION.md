# Memory Foundation

## Decision

Memory in Marvex means policy-governed assistant recall material. The first
approved memory shapes are safe records, references, write candidates, read
results, forget results, and safe projections owned by `packages.memory_runtime`.

Memory is not a transcript store, telemetry store, session store, provider
state store, prompt cache, vector database, tool state, UI state, voice state,
desktop context, vision state, proactive state, router, model selector, daemon,
or WebSocket/event stream.

## Safe Stored Fields

Allowed in this foundation:

- `memory_ref` with `ref_type: "memory"` and safe `ref_id`
- `scope`: `session` or `conversation`
- `memory_kind`: `fact`, `preference`, `instruction`, or `summary`
- safe `session_ref` and `conversation_ref`
- `trace_id` and `turn_id` provenance
- safe normalized memory content only after `explicit_user` or `policy_approved`
  authorization
- safe tags
- `raw_transcript_persisted: false`

Forbidden by default:

- raw prompts or user-visible input bodies copied as transcripts
- raw assistant outputs or provider outputs
- provider payloads, provider response ids, raw metadata, or provider continuity
  ids
- full transcripts or hidden conversation history
- tokens, credentials, environment values, auth material, secrets, and private
  stack traces
- embeddings, vector indexes, semantic search stores, automatic extraction,
  tools, UI, voice, desktop, vision, proactive behavior, generic provider
  routing, retry/fallback/model selection, daemon supervision, or WebSocket
  streams

## Relation To Session And Telemetry

SessionRuntime owns `session_ref` and `conversation_ref` only. MemoryRuntime may
link records to those references, but SessionRuntime must not own memory storage
or recall.

Telemetry owns trace events and trace persistence only. MemoryRuntime may keep
`trace_id` and `turn_id` provenance, but telemetry must not become memory
storage.

AssistantRuntime may receive safe memory context in a future approved task, but
it must not own memory storage or recall. Core, Local API, RuntimeComposition,
ProviderRuntime, and local service startup remain memory-owner blind.

## Future Policy

Future memory reads and writes require an explicit policy decision before
runtime integration. Write candidates default to `pending`; provider-driven or
automatic transcript-derived writes remain blocked. Forget/delete behavior must
be addressable by `MemoryRef` and return a safe result without exposing stored
content.

