# 09 — Voice addressing detection (is this speech *for* Marvex?)

**Status:** TODO
**Area:** voice worker (`packages/voice_worker_runtime/`)

Goal: avoid Marvex acting on speech that isn't directed at it — side
conversations, other people in the room, etc. Two methods, in priority order.

---

## Method 1 — Wakeword gating (primary; mostly already present)

**Status:** Largely implemented — formalize and make it the default contract.

The strongest "is this for me?" signal we have is the wakeword ("Hey Marvex").
The continuous loop already requires a wake detection before it captures a
command (`run_wake_listen_loop` → `_run_post_wake_capture`), and there's a
local-wake enrollment path. Addressing via wakeword means: **only act on an
utterance that was preceded by the wake word** (or that arrives inside a short,
explicit follow-up window after Marvex just replied).

Work to finalize:
- [ ] Make "wake required per turn" the explicit, documented default (no hidden
      always-on command capture).
- [ ] Define the follow-up window: after Marvex answers, allow one wake-free
      reply for N seconds (configurable), then require the wake word again.
- [ ] The non-English language gate (already shipped) complements this: a
      wake-free side conversation in another language is dropped for free.

This method is cheap, reliable, and fully in-codebase.

---

## Method 2 — Speaker-ID gating (future; optional)

**Status:** Future / optional.

Only respond to the **enrolled user's voice** and ignore everyone else, even if
they say the wake word. Reuse what already exists:

- **Enrollment infra exists:** the wake-reference recorder
  (`wake_enrollment.py`, `WakeEnrollment.tsx`) already captures reference WAVs of
  the user's voice for local-wake.
- **Embeddings:** `sherpa-onnx` ships speaker-embedding models. Compute an
  embedding for the captured utterance and compare (cosine) against the enrolled
  reference embedding(s); reject below a similarity threshold.
- Integrate as an optional gate at endpoint (like the language gate): when
  speaker-ID is enabled and the utterance doesn't match the enrolled speaker,
  drop it (`reason_code = "unrecognized_speaker_ignored"`), fail-open when the
  model/enrollment is absent.

Why deferred:
- Adds a model + threshold tuning; short utterances make speaker-ID less
  reliable, so it needs on-device evaluation before it's trustworthy.
- Should be **opt-in** — a hard speaker gate that misfires would lock the user
  out of their own assistant.

Out of scope (both methods): semantic "directed-at-me" detection (same language,
same room, no wake word). That's research-grade and not worth it locally.

## Acceptance

- [ ] Method 1: documented wake-required contract + follow-up window, with tests.
- [ ] Method 2 (when built): optional speaker-ID gate reusing wake enrollment,
      fail-open, opt-in, with a fake-embedder unit test.
