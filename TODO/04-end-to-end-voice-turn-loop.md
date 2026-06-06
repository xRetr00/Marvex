# 04 — End-to-end voice turn loop

**Theme:** Voice · **Size:** XL · **Status:** partially wired

## Problem

Saying "Hey Marvex" and then a command does not produce a spoken answer. The
voice pipeline has all the *parts* installed and "ready" (wake word, STT, TTS,
VAD models all present per the Voice Mode screen), but they are not connected
into a continuous, real loop:

```
wake word ─?→ capture (with endpointing) ─?→ STT ─?→ chat turn ─?→ TTS ─?→ playback
              ▲ barge-in / interrupt ──────────────────────────────────────┘
```

Today only the first arrow is partly real, and even that uses a blind fixed-
length grab rather than VAD endpointing.

## Evidence (current state)

- The **live** worker loop only ticks wake word; it never runs a capture cycle:
  `packages/voice_worker_runtime/worker_main.py` → `_tick_wakeword_if_active`
  calls `controller.tick_wakeword_supervisor()` on a 1s timer. That's it.
- The wake→STT bridge we added (`VoiceWorkerController._run_post_wake_capture`)
  captures a **fixed 30 frames (~3s)** with no VAD endpointing, then emits a
  `TRANSCRIPTION_COMPLETED` event with the transcript — but **nothing consumes
  that event** to run a chat turn or speak a reply.
- `run_live_capture_cycle` exists in `controller.py` and *does* use a
  `vad_decider` + `ChunkAggregator` for endpointing and even calls
  `voice_runtime.run_voice_turn`, but it is **not invoked by the live worker**;
  it's reachable only from tests/manual paths.
- VAD adapters are real (`packages/voice_runtime/adapters.py`
  `SileroVadAdapter`, `WebRtcVadAdapter`) but the live wake path doesn't use
  them for endpointing.
- Barge-in (`BargeInDetector`), TTS queue, playback interrupt all exist as
  models but aren't wired into a running conversation loop.
- Earlier crashes fixed along the way: `GetFrames` buffer underrun (frame count
  raised to 12), then `stream.result` AttributeError (now uses
  `kws.get_result`). With those fixed, wake-word detection should fire — but the
  *post-detection* loop is the missing half.

## Why this is large, not a patch

- It is a **stateful realtime loop** spanning the voice worker process, the
  Core turn API, and audio playback, with interrupt/barge-in semantics.
- Endpointing (knowing when the user stopped talking) must use streaming VAD,
  not a fixed window — otherwise it either cuts people off or records silence.
- It must dispatch the recognized transcript as a real Core chat turn (reusing
  everything: provider, tools, memory) and then **stream the reply to TTS** and
  play it, while listening for barge-in to interrupt playback.
- Privacy invariants (no raw audio/transcript persistence) must hold throughout.

## Proposed approach

1. **Promote `run_live_capture_cycle` to the live loop:** on wake-word
   detection, the worker runs a VAD-endpointed capture (silero primary,
   webrtc fallback — both already adapters) instead of the fixed 30-frame grab.
   Retire/replace `_run_post_wake_capture`'s blind capture.
2. **Dispatch to Core:** the worker (or shell) sends the final transcript to the
   Core `/v1/turns` API as a normal chat turn, carrying the session id so memory
   (item 01) and provider selection apply.
3. **Speak the reply:** stream/segment the assistant text into the TTS queue
   (`TTSQueue`, `SentenceBoundaryDetector` already exist), synthesize via the
   active TTS backend (kokoro), and play through the audio adapter.
4. **Barge-in:** while playing, keep a light VAD running; on user speech, fire
   `BargeInDetector` → interrupt playback → start a new capture.
5. **State machine:** model the loop explicitly (idle → listening → capturing →
   transcribing → thinking → speaking → idle) with the existing
   `AssistantStatusKind` published to the shell so the orb reflects reality.

## Affected files (anticipated)

- `packages/voice_worker_runtime/worker_main.py` — live loop becomes a state
  machine, not just a wakeword ticker.
- `packages/voice_worker_runtime/controller.py` — use VAD-endpointed capture;
  wire transcript → turn dispatch → TTS → playback; barge-in.
- `packages/voice_runtime/` — reuse VAD adapters, TTS queue, barge-in, sentence
  boundary (mostly already present).
- Core turn dispatch client from the worker (or a shell-mediated bridge).
- `apps/shell` Voice Mode surface — reflect the live state machine.

## Acceptance criteria

- "Hey Marvex, what's 2+2?" → spoken "four" (or the model's answer) end to end.
- Endpointing stops capture when the user stops talking (not a fixed 3s).
- Speaking can be interrupted by the user (barge-in) and the loop recovers.
- No raw audio or raw transcript written to disk at any stage.
- Telemetry counters (`mic_capture_events`, `vad_speech_segments`, `stt_events`,
  `tts_events`, `wakeword_detections`) all move off zero in a real session.

## Risks / notes

- Realtime audio + interrupt is timing-sensitive and hard to unit-test; build a
  deterministic fake-audio harness (the `FakeLocalAudioAdapter` is a start).
- Depends on the chat turn actually answering — so the provider (now LM Studio)
  and ideally item 02 should be solid first.
- sherpa-onnx / kokoro / moonshine are all CPU ONNX; watch latency on the full
  loop and consider partial/streaming STT for responsiveness.
