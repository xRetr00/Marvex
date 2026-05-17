# SessionRuntime

`packages.session_runtime` owns the narrow Session and Conversation Foundation.
It is a reference and projection boundary only.

## Owned Surface

- safe `SessionRef` and `ConversationRef` usage
- turn linkage metadata: `trace_id`, `turn_id`, optional safe references, and
  `previous_response_id` presence only
- safe current-process session and conversation projections
- an optional instance-owned `CurrentProcessSessionRegistry` for grouping turns
  inside the current Python process

## Boundary Rules

- A session is the current assistant interaction container used to group turns
  by safe reference.
- A conversation is the logical user-visible grouping that may span one or more
  sessions later, but today is only a safe reference.
- `trace_id` identifies telemetry for a turn or run.
- `turn_id` identifies one assistant turn.
- `previous_response_id` remains provider continuity input supplied explicitly by
  the caller; SessionRuntime stores only whether it was present.
- No raw prompts, provider payloads, provider outputs, tokens, environment
  values, or full transcripts may be stored by default.

## Non-Goals

SessionRuntime is not memory, a transcript database, a provider router, a tool
runtime, a UI state store, a voice/Desktop/Vision runtime, a daemon supervisor,
or a WebSocket/event stream owner.

