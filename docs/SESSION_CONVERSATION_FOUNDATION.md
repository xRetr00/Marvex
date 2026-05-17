# Session And Conversation Foundation

## Decision

Marvex uses both `session_ref` and `conversation_ref`.

A session is the current assistant interaction container used to group assistant
turns safely in this process. A conversation is the logical user-visible grouping
that can outlive one process or span sessions later, but in this foundation it is
only a safe reference.

The foundation is owned by `packages.session_runtime`. Contracts provide the
small reference shapes. AssistantRuntime may observe session-reference presence
for one-turn state. Telemetry may link safe references to `trace_id` and
`turn_id`. Core, Local API, RuntimeComposition, ProviderRuntime,
local_service_startup, and telemetry must not become session stores.

## Safe Linkage

Allowed persistent or projected fields:

- `schema_version`
- `trace_id`
- `turn_id`
- `session_ref` with `ref_type` and safe `ref_id`
- `conversation_ref` with `ref_type` and safe `ref_id`
- `previous_response_id_present` as a boolean only
- turn and trace id lists in safe projections
- `transcript_persisted: false`

Forbidden by default:

- raw prompts or user-visible input bodies
- provider payloads, provider outputs, raw metadata, or provider response ids
- full transcripts or hidden history
- tokens, credentials, environment values, or auth material
- memory records, embeddings, vector search, tool state, UI state, voice state,
  desktop context, vision state, proactive state, retry/fallback/model routing,
  daemon supervision, or WebSocket/event streams

## Relationship To Existing IDs

- `trace_id` links runtime and telemetry observations.
- `turn_id` identifies one assistant turn.
- `session_ref` groups turns within the session boundary.
- `conversation_ref` groups turns under the logical conversation boundary.
- `previous_response_id` is still explicit caller/provider continuity input. It
  is not a session id, not a conversation id, and not stored by SessionRuntime.

## Future Memory Dependency

Future memory may depend on this foundation only by reading safe references and
turn linkage metadata through an approved contract. Memory must remain a
separate owner and must not reinterpret SessionRuntime projections as recall,
semantic history, transcripts, embeddings, or profile storage.

