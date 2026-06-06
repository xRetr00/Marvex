# 06 — Streaming responses (text + voice)

**Theme:** UX / Infra · **Size:** L · **Status:** transport landed end-to-end —
true provider-token streaming is the remaining low-latency follow-up

## Progress

- **[done] Core streaming driver** (`packages/core/orchestration/streaming.py`,
  tested in `tests/core/test_streaming_driver.py`): a provider-agnostic
  `run_streaming_turn(events, on_delta=...)` that forwards text deltas to a sink,
  reconciles them with the terminal event's authoritative `output_text`, handles
  stream errors (caller falls back to non-streaming), and returns a `StreamedTurn`
  the caller converts to the usual `AssistantTurnResult`. Pure + unit-tested.

- **[done] Provider `stream_send`** on both adapters, yielding `StreamTextDelta` /
  `StreamCompleted` / `StreamError` shared via `packages/contracts.streaming_models`:
  LMStudio Responses (`responses.create(stream=True)`,
  `tests/adapters/test_lmstudio_responses_streaming.py`) and LiteLLM
  (`completion(stream=True)`, `tests/adapters/test_litellm_streaming.py`). The
  non-streaming `send` stays byte-for-byte unchanged; the source `stream` boundary
  token was relaxed (raw-HTTP / cross-package boundaries still enforced).

- **[done] Core SSE endpoint** `POST /v1/turns/stream` in `packages/local_api`
  (`tests/local_api/test_turns_stream_api.py`): driven by an additive
  `stream_turn_handler`, emits `data: {"type":"delta"|"final"|"error"}` SSE frames;
  auth/validation failures return JSON before the stream opens. Non-streaming
  `/v1/turns` is unchanged. `services/core/main._stream_turn_events` runs the full
  unchanged `submit_turn` pipeline (tools/approval/clarify/refs/persistence
  identical), then streams the reconciled final text via a lossless whitespace
  chunker and a terminal `final` event carrying the complete `AssistantTurnResult`.

- **[done] Tauri streaming command** `submit_chat_turn_stream`
  (`apps/shell/src-tauri/src/lib.rs`, `http::open_post_stream`): reads the SSE body
  via `Response::chunk()`, emits a `chat-stream` Tauri event per frame (tagged with
  `turn_id`), and resolves with the terminal result. `submit_chat_turn` remains the
  non-streaming fallback.

- **[done] Shell incremental render** (`apps/shell/src/surfaces/ChatApp.tsx`,
  `submitChatTurnStream` in `shellCommands.ts`): appends an in-progress assistant
  bubble, grows it from `chat-stream` deltas, and on the terminal event reconciles
  text + stages + refs + approval/clarification with the authoritative result.

- **[remaining] True provider-token streaming for low latency.** The Core handler
  currently streams the *reconciled final text* (computed by the unchanged
  `submit_turn`), so the UI animates progressively but model latency is unchanged.
  Real token-by-token latency reduction requires plumbing `stream_send` through the
  ProviderWorker JSONL subprocess (a new streaming command + multi-frame read in
  `_ProviderWorkerProcessProvider`) and a streaming turn path in the executor for
  the no-tool case. This was deliberately not landed blind because it crosses the
  process boundary and can't be verified without the live app.

- **[remaining] Voice early-sentence TTS** (item 5; pairs with item 04). The
  `chat-stream` deltas are now available shell-side as the integration point, but
  speaking the first sentence *before generation finishes* only helps once the
  above true-token streaming lands (under post-compute streaming the full answer is
  already computed before deltas emit). The voice path currently speaks the full
  reply, which is correct and unregressed.

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
