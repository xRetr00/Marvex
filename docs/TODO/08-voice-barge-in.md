# 08 — Voice barge-in (interrupt Marvex while it's speaking)

**Status:** TODO (not started)
**Area:** voice worker (`packages/voice_worker_runtime/controller.py`)

## Problem

In continuous voice mode you cannot interrupt Marvex mid-sentence. While TTS is
playing, the half-duplex echo gate (added with the STT/TTS self-echo fix)
deliberately **mutes** mic capture so the assistant's own voice is never
re-transcribed. That gate is correct for echo, but it also means a user who
starts talking over the reply is ignored until playback finishes.

There is already a `_speak_with_barge_in` path in the controller, but it is
**skipped while the continuous wake loop owns the mic** (`controller.py`, the
`if bool(command.payload.get("barge_in")) and not self._continuous_active:`
branch), so normal voice mode never uses it.

## Goal

Let the user interrupt playback: when the user clearly starts speaking during
TTS, stop playback (`BARGE_IN_DETECTED`) and start capturing their new
utterance — without re-introducing the self-echo bug.

## Approach sketch

- Re-enable barge-in monitoring inside the continuous loop instead of fully
  muting capture during playback. The current gate (`_capture_suppressed()`)
  drops frames wholesale; replace "drop everything" with "run a barge-in VAD on
  echo-cancelled capture only."
- Reuse `capture_echo_cancelled_frames` (the audio adapter exposes it; AEC
  removes Marvex's own far-end audio so its TTS doesn't self-trigger). Only treat
  residual, above-threshold speech as a real barge-in.
- Require a short sustained-speech window (e.g. ≥ 200–300 ms over the AEC'd
  signal) before interrupting, to avoid stopping on a cough or the echo tail.
- On barge-in: `interrupt_playback(reason_code="barge_in.user_speech_detected")`,
  set `_playback_status = "interrupted"`, clear `_queued_tts_count`, and hand the
  fresh frames to `_run_post_wake_capture` (no wake word needed — the user is
  already addressing Marvex).

## Risks / why it's deferred

- Without reliable AEC, barge-in detection will re-trigger on Marvex's own
  speakers (the exact echo loop we just fixed). The quality of barge-in is gated
  on the AEC path being solid. Needs on-device tuning and testing.
- Threshold tuning (sensitivity vs. false interrupts) is empirical and can't be
  validated without a microphone.

## Acceptance

- [ ] Speaking over TTS in continuous mode stops playback within ~300 ms.
- [ ] Marvex's own TTS never self-triggers a barge-in (no regression of the
      echo fix), verified on-device.
- [ ] A unit test drives a fake AEC capture that yields speech during playback
      and asserts `BARGE_IN_DETECTED` + capture handoff.
