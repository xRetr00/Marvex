# 06 — Streaming responses (text + voice)

**Theme:** UX / Infra · **Size:** L · **Status:** in progress — foundation landed

## Progress

- **[done] Core streaming driver** (`packages/core/orchestration/streaming.py`,
  tested in `tests/core/test_streaming_driver.py`): a provider-agnostic
  `run_streaming_turn(events, on_delta=...)` that forwards text deltas to a sink,
  reconciles them with the terminal event's authoritative `output_text`, handles
  stream errors (caller falls back to non-streaming), and returns a `StreamedTurn`
  the caller converts to the usual `AssistantTurnResult`. Pure + unit-tested.

- **[remaining]** the integration layers (all additive, behind a flag; the
  default non-streaming path stays byte-for-byte unchanged):
  1. **Provider `stream_send`** on LMStudio Responses (`responses.create(stream=True)`)
     and LiteLLM (`completion(stream=True)`), yielding `StreamTextDelta` /
     `StreamCompleted` / `StreamError`. Share the event types via `packages/contracts`
     so adapters don't import core. Relax the forbidden-`stream` boundary test on
     the streaming path only.
  2. **Core SSE endpoint** in `packages/local_api` that drives `run_streaming_turn`
     and emits deltas + a terminal event carrying the full `AssistantTurnResult`.
  3. **Rust/Tauri** streaming command that consumes the SSE and re-emits Tauri
     events to the shell (keep `submit_chat_turn` as the non-streaming fallback).
  4. **Shell** incremental render: append deltas to the in-progress bubble; on the
     terminal event reconcile stages/refs/approval.
  5. **Voice** path: feed deltas through `SentenceBoundaryDetector` → `TTSQueue`
     (pairs with item 04) so the first sentence speaks before generation finishes.

These need the live app (fastapi/SSE/Tauri/vite) to wire and verify, so they were
not landed blind.

## Problem

Every response is computed fully before the user sees anything. In chat the
reply appears in one blocking chunk after a multi-second wait; in voice nothing
can be spoken until the entire answer is generated. This makes the assistant
feel sluggish even when the model is fine, and it blocks low-latency voice
(item 04) from speaking incrementally.

## Evidence (current state)

- The provider adapters call the model **non-streaming**: LiteLLM uses
  `litellm.completion(**call_args)` (not `litellm.completion(stream=True, …)`),
  and the boundary test
  `tests/adapters/test_litellm_provider.py::test_no_tools_mcp_or_streaming_fields_sent`
  explicitly forbids a `stream` field. LMStudio uses `responses.create(...)`
  without streaming.
- The turn API (`/v1/turns`) returns a single `AssistantTurnResult` JSON body;
  there is no token/event stream channel to the shell.
- The shell renders the whole assistant message at once
  (`apps/shell/src/surfaces/ChatApp.tsx` `send` awaits the full result).
- Voice TTS infrastructure (`TTSQueue`, `SentenceBoundaryDetector`,
  `stream2sentence` is even installed) is built to consume incremental text but
  is fed a finished string.

## Why this is large, not a patch

- It introduces a **streaming transport** end to end: provider stream → Core →
  shell (SSE/WebSocket/Tauri event) and a parallel provider stream → sentence
  segmentation → TTS for voice.
- It changes the turn contract from request/response to request/stream-of-events
  while preserving the final `AssistantTurnResult` for persistence and the
  approval/tool flows.
- It interacts with item 02 (tool calls mid-stream) and item 04 (speak
  sentences as they arrive) — the design must accommodate both.

## Proposed approach (incremental)

1. **Provider streaming opt-in:** add a streaming path to the adapters
   (`litellm.completion(stream=True)`, LMStudio streaming) behind a capability
   flag; relax the forbidden-`stream` boundary test on that path only.
2. **Core event stream:** add a streaming turn endpoint (SSE is simplest over
   the existing loopback HTTP) that emits deltas + a terminal event carrying the
   full `AssistantTurnResult` (so persistence/refs are unchanged).
3. **Shell incremental render:** consume deltas and append to the in-progress
   assistant bubble; on terminal event, reconcile with the final result
   (stages, refs, approval).
4. **Voice path:** feed provider deltas through `SentenceBoundaryDetector` →
   `TTSQueue` so the first sentence is spoken while the rest generates
   (depends on / pairs with item 04).
5. **Fallback:** non-streaming providers and clients keep the current
   request/response path unchanged.

## Affected files (anticipated)

- `packages/adapters/providers/litellm/`, `.../lmstudio_responses/` — streaming
  send + delta yield.
- `packages/local_api/` — streaming turn endpoint (SSE).
- `services/core/main.py` — stream provider deltas through the turn, still
  produce the final result.
- `apps/shell/src/surfaces/ChatApp.tsx` + commands — consume the stream.
- `packages/voice_runtime` TTS queue — already incremental; connect it.
- Boundary tests + governance for the `stream` field.

## Acceptance criteria

- Chat shows tokens as they arrive; final message matches today's content +
  stages + refs.
- Non-streaming providers/clients behave exactly as today.
- Voice speaks the first sentence before the full answer is done (with item 04).
- Cancellation mid-stream stops generation cleanly.

## Risks / notes

- Streaming + tool calls (item 02) + approval gating interact; design the event
  schema to carry tool-call and approval events, not just text deltas.
- SSE over the existing loopback HTTP is the least-disruptive transport; avoid a
  new WebSocket stack unless needed.
- Keep the final-result contract intact so persistence, session linkage, and the
  response-id chain are unaffected.
