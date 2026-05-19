# Voice Worker Runtime

Marvex now has the first dedicated local voice worker process boundary after the in-process VoiceRuntime foundation. This is the live local voice runtime worker direction; it is not Orb, not Face UI, not desktop overlay, not vision, and not the final visual assistant shell.

## Ownership

`packages.voice_worker_runtime` owns the local worker boundary, lifecycle state, safe worker commands/events, microphone and playback adapters, model asset root validation, heartbeat/status projection, and the worker-managed path that can hand captured speech into `VoiceRuntime` through injected assistant-turn and policy callbacks.

It does not own assistant policy, AutonomyPolicy, CapabilityRuntime approval, intent routing, tools, memory, provider routing, RuntimeComposition supervision, or Local API internals. Control Plane remains a protected HTTP/auth/JSON surface that delegates to a worker facade.

## Runtime Behavior Added

- Explicit `VoiceWorkerConfig`, `VoiceWorkerStatus`, `VoiceWorkerCommand`, `VoiceWorkerEvent`, `VoiceWorkerHealth`, `VoiceWorkerLifecycleState`, `VoiceWorkerErrorEnvelope`, and `SafeVoiceWorkerProjection` models.
- User-visible start, stop, pause, resume, reload-config, test-mic, test-wakeword, test-STT, test-TTS, test-playback, install-model, switch-STT, switch-TTS, and switch-active-voice command paths.
- Local-only worker defaults with no hidden auto-start and no hidden recording.
- Heartbeat and lifecycle status for worker supervision.
- Loopback-only subprocess launch path with safe shutdown; `0.0.0.0` and remote bindings are rejected.
- Microphone device listing/test/capture adapter path, device selection through worker config reload, and playback device/test/interrupt path.
- Ring-buffer compatible PCM frame capture path for runtime integration without raw audio persistence.
- Manual voice turn path that assembles mockable captured frames, emits VAD/STT/assistant/TTS/playback worker events, delegates STT/TTS/policy to existing runtime seams, and records safe summaries only.
- Barge-in test path that interrupts playback and clears queued TTS state.
- Worker-safe telemetry summaries expose event counts and durations/counts only; they do not include raw audio, raw transcripts, generated audio, secrets, or provider/tool payloads.

## Dependency Decision

`sounddevice==0.5.5` is adopted as the local/free audio device library because it is cross-platform, PortAudio-backed, already resolved in `uv.lock`, and can be isolated behind `SoundDeviceAudioAdapter`. Runtime tests use `FakeLocalAudioAdapter` because CI cannot validate physical microphone or speaker hardware.

The sounddevice adapter is intentionally thin. It can list real local input/output devices when available, while heavy live capture/playback behavior remains adapter-owned and mockable. If sounddevice fails on a host because PortAudio or device permissions are unavailable, the exact blocker should be surfaced through worker test/status responses rather than faked as success.

## Asset Policy

Voice model and voice assets must live under the configured local voice asset root. Path traversal is blocked. Installs are explicit user-triggered operations. Missing local assets report `not_installed`, file checksum mismatches report `blocked`, and no fake readiness is returned. No arbitrary path writes, hidden downloads, secrets, raw model internals, raw audio, generated audio, or raw transcripts are persisted by default.

Current model assets are still not downloaded by this checkpoint. Moonshine v2, SenseVoice-Small, sherpa-onnx KWS/ASR/TTS/VAD, Kokoro, and Piper runtime execution remains ready only when the corresponding local model or voice asset is installed/configured. `Hey Marvex` wakeword tests require both enabled wakeword policy and the installed sherpa-onnx KWS asset; otherwise Control Plane reports the exact blocker.

## Control Plane

Protected Control Plane endpoints expose `/control/voice/worker` status, devices, start/stop/pause/resume, config reload, mic test, playback test, wakeword test, STT/TTS test, model install/remove, STT/TTS backend switching, and active voice switching. The web page shows worker status, microphone and playback selectors, backend/model readiness, wakeword/STT/TTS tests, telemetry summaries, and explicit worker controls. It does not render raw audio or raw transcripts.

## Safety Defaults

- local-only worker
- no hidden auto-start
- no hidden recording
- wakeword disabled by default and visible when enabled
- no raw audio persistence by default
- no raw transcript persistence by default
- no generated audio persistence by default
- no bypass of policy or approval
- high-risk voice actions must still flow through injected policy/approval owners

## Still Not Implemented

Always-running 24/7 wakeword supervision, real physical microphone validation in CI, real model downloads, live heavy STT/TTS inference against installed model files, echo suppression, Orb, Face UI, desktop overlay, final visual assistant shell, vision, proactive non-voice behavior, and remote worker exposure remain not implemented unless a later explicit goal widens scope.
