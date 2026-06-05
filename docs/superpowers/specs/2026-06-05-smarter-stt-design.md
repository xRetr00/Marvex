# Smarter STT — design spec (2026-06-05)

## Goal

Three independent improvements to the local voice STT, plus two documented TODOs.

1. **Ignore non-English (A).** Marvex stays English-only, but uses a small spoken
   language-ID model to detect when an utterance is *not* English and drop it
   with a brief one-time notice instead of feeding gibberish to the model.
2. **Streaming partials (B).** Moonshine v2 streams the transcript word/phrase by
   phrase while the user talks, instead of staying silent until the whole
   utterance is captured and transcribed in one shot.
3. **SenseVoice as a selectable STT backend (C).** SenseVoice already works
   (multilingual, single-shot, `language="auto"`). Expose it in the UI as an
   alternative STT backend. No streaming for SenseVoice — that's fine.

Out of scope, documented as TODOs:
- **Barge-in** (interrupt Marvex while it speaks).
- **Addressing detection** — method 1: wakeword gating (exists); method 2 (future):
  optional speaker-ID via sherpa-onnx reusing wake enrollment.

## Why this shape

- Moonshine `medium-streaming-en` is English-only but streams; SenseVoice is
  multilingual but single-shot. You cannot get both "stream word-by-word" and
  "reliably detect non-English" from one model.
- Rather than run two full ASR models, a **tiny language-ID model**
  (`speechbrain/lang-id-voxlingua107-ecapa`, VoxLingua107 ECAPA-TDNN) runs **once
  at endpoint** purely to classify the spoken language. SpeechBrain rides on
  PyTorch, which is **already a dependency** (`funasr`/SenseVoice pulls
  `torch`/`torchaudio`), so this adds only the `speechbrain` package + a ~25 MB
  model, not a torch-sized footprint.

## Architecture (all in the voice worker)

### A. Language-ID gate
- New `LanguageIdRunner` (in `model_adapters.py`), constructed like the other
  runners, with an injectable `classifier_factory` for tests. It resolves the
  installed `speechbrain-langid` model, runs the ECAPA classifier once on the
  final utterance frames, and returns `(language_code, confidence)`.
- `VoiceWorkerBackendRuntime.detect_language(frames)` wraps it and is **fail-open**:
  any missing model / import error / low confidence → returns `None` (no verdict),
  so the turn is allowed. It only returns a verdict when it is *confident* the
  language is non-English.
- Controller: in `_run_post_wake_capture`, **only when the active STT backend is
  the English-only Moonshine**, after a successful transcription, call
  `detect_language`. If it confidently says non-English, reject the transcript
  with reason_code `non_english_ignored` and surface a one-time brief notice; the
  transcript is not dispatched.
- Model is a **runtime download** via the manifest (`bundled: false`), added as
  individual Hugging Face file entries (like Moonshine's multi-file layout).

### B. Moonshine streaming
- `MoonshineSttRunner` gains a streaming session API: `open_stream()` returns a
  small session object wrapping moonshine's `create_stream()` /
  `add_audio()` / `update_transcription()`. `feed(frames) -> partial_text` and
  `finish() -> TranscriptionResult`.
- `VoiceWorkerBackendRuntime.open_stt_stream(backend_id)` returns a session for
  streaming-capable backends (Moonshine), else `None`.
- `_capture_utterance` gains an optional `on_frame` hook called per captured
  speech frame. `_run_post_wake_capture` opens a stream (when available), feeds
  frames through `on_frame`, and emits a `TRANSCRIPTION_PARTIAL` worker event
  whenever the partial text changes; on endpoint it finalizes via `finish()`.
- **Fallback:** if no streaming session (backend unsupported) or any streaming
  error, fall back to the existing one-shot `test_stt` path. Existing behavior is
  never broken.

### C. SenseVoice selectable
- The worker already supports `switch_stt_backend` and the control endpoint
  `/control/voice/worker/stt/switch`. Add a frontend client call + a small STT
  picker (Moonshine / SenseVoice) in the voice settings UI, and make sure
  SenseVoice is reachable from the model-download UI (it is `bundled: false` in
  the manifest). When SenseVoice is active it transcribes any language and the
  LID gate is bypassed.

## Error handling
- LID: fail-open (missing/error/low-confidence → allow).
- Streaming: fall back to one-shot on any error.
- Non-English drop: emit the brief notice at most once per session so silence is
  never confusing, but never spam it.

## Testing
- `LanguageIdRunner` / `detect_language`: fake classifier — English → allow;
  confident non-English → verdict; low confidence → allow; model missing → allow.
- Gate bypassed when active backend is SenseVoice.
- Streaming session: fake transcriber emits changing partials then a final;
  assert partials emitted in order and final returned; assert fallback when no
  session.
- SenseVoice picker: client call hits the switch endpoint; UI renders the choice.

## TODOs (written to `docs/TODO/`)
- **Barge-in:** re-enable interrupting TTS in continuous mode, coexisting with the
  half-duplex echo gate.
- **Addressing detection:** method 1 = wakeword gating (already present); method 2
  (future) = optional speaker-ID via sherpa-onnx speaker embeddings, reusing the
  existing wake-reference enrollment to only accept the enrolled user's voice.
