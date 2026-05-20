# Voice Worker Service

Status: approved local-only VoiceWorker service contract surface.

Contract status: approved in `docs/CONTRACT_APPROVALS.md`.

This service directory remains README-only until the implementation moves from
`packages.voice_worker_runtime` into a service-owned entrypoint. The approved
runtime implementation surface is the local-only worker boundary and its safe
command/status/event contract, not a remote service or product shell.

Intended ownership: local VoiceWorker process boundary for explicit lifecycle,
microphone capture, speaker playback, model asset readiness/downloads, backend
runner adapters, wakeword supervision, heartbeat/status, and safe telemetry
summaries.

Forbidden: hidden auto-start, hidden recording, remote exposure, raw audio or
transcript persistence by default, assistant policy ownership, Local API
internals, RuntimeComposition supervision, Orb/shell UI, desktop agent behavior,
vision, and proactive behavior.
