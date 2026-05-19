# Voice Runtime Foundation

Marvex now has a bounded in-process VoiceRuntime foundation. This is not Orb, Face UI, desktop overlay, visual assistant shell, vision, or proactive non-voice behavior.

## Ownership

`packages.voice_runtime` owns voice I/O orchestration only: wakeword, VAD, audio buffering, chunk aggregation, STT/TTS backend selection, model and voice registries, sentence clamping, queued speech, barge-in state, early speech, voice personality settings, safe voice turn envelopes, and safe Control Plane projections.

VoiceRuntime does not own intent routing, tools, memory, provider routing, capability policy, autonomy policy, visual UI, desktop overlay, or service daemon behavior. Voice turns accept injected assistant-turn and policy callbacks so existing governance remains authoritative; the integration proof runs a voice transcript through `packages.assistant_turn_integration` and an `AutonomyPolicy` decision without importing those owners into VoiceRuntime.

## Backend Stack

- STT main: Moonshine v2 via `moonshine-voice==0.0.59`.
- STT fallback: SenseVoice-Small path via `funasr==1.3.1`.
- Secondary ASR/wakeword/TTS/VAD seam: `sherpa-onnx==1.13.2` plus `sherpa-onnx-core==1.13.2`.
- TTS main: `kokoro-onnx==0.5.0`.
- TTS fallback: `piper-tts==1.4.2`.
- Sentence chunking: `stream2sentence==0.3.2` behind a conservative sentence clamp seam.
- VAD main/fallback: `silero-vad==6.2.1` and `webrtcvad-wheels==2.0.14`.

`uv` resolution succeeded for the stack. `pip check` initially found that `sherpa-onnx-core` was required but missing; adding `sherpa-onnx-core==1.13.2` fixed the dependency check.

## Safety Defaults

- Wakeword always-listening is disabled by default and requires an explicit visible Control Plane toggle.
- Push-to-talk/manual trigger remains available as fallback.
- Raw audio, generated audio, and transcripts are not persisted by default.
- Safe projections expose counts, durations, backend ids, status, and reason codes only.
- Early speech uses safe filler and cannot claim facts without evidence.
- Barge-in interrupts playback and queued speech state.
- Model and voice downloads are explicit user-triggered operations and do not render raw model internals.

## Control Plane

Protected Control Plane APIs and web views expose status, backend health, STT/TTS selectors, wakeword settings, VAD/barge-in/early speech/personality settings, model or voice download/remove requests, STT/TTS tests, audio retention policy, and telemetry summaries. The frontend does not run audio engines directly.

## Voice Worker Follow-Up

The next phase now starts in `packages.voice_worker_runtime`. VoiceRuntime remains the in-process speech I/O orchestration foundation; VoiceWorkerRuntime owns the local worker lifecycle, microphone/playback adapters, process boundary, heartbeat/status, and Control Plane worker commands. VoiceWorkerRuntime delegates assistant policy and assistant turns through injected callbacks and must not make RuntimeComposition or Local API a worker supervisor.

## Still Outside This Foundation

Separate always-running voice worker processes, OS microphone service supervision, Orb/Face UI, desktop overlay, final visual assistant shell, vision, and proactive non-voice behavior require later explicit goals.
