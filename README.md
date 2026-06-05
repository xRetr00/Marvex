# Marvex

<p align="center">
  <img src="assets/Marvex_WordMark_NoBackground.png" alt="Marvex logo" width="960" />
</p>

<p align="center">
  <a href="version.toml"><img alt="Version" src="https://img.shields.io/badge/version-0.3.0-2563eb" /></a>
  <img alt="Assistant OS" src="https://img.shields.io/badge/Assistant%20OS-infrastructure%20first-111827" />
  <img alt="Local first" src="https://img.shields.io/badge/local--first-loopback%20default-0f766e" />
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white" />
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-0078d4?logo=windows&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white" />
  <img alt="Tauri" src="https://img.shields.io/badge/shell-Tauri%20v2-24c8db?logo=tauri&logoColor=white" />
</p>

<p align="center">
  <img alt="Pydantic contracts" src="https://img.shields.io/badge/contracts-Pydantic-e92063?logo=pydantic&logoColor=white" />
  <img alt="Provider adapters" src="https://img.shields.io/badge/providers-LM%20Studio%20%7C%20LiteLLM%20%7C%20Fake-7c3aed" />
  <img alt="MCP ready" src="https://img.shields.io/badge/MCP-adapter%20boundary-334155" />
  <a href="https://github.com/xRetr00/Marvex/issues"><img alt="Issues" src="https://img.shields.io/github/issues/xRetr00/Marvex" /></a>
  <a href="https://github.com/xRetr00/Marvex/discussions"><img alt="Discussions" src="https://img.shields.io/github/discussions/xRetr00/Marvex" /></a>
  <a href="https://github.com/xRetr00/Marvex/graphs/contributors"><img alt="Contributors" src="https://img.shields.io/github/contributors/xRetr00/Marvex" /></a>
</p>

Marvex is a local-first Assistant OS platform for Windows. It is built as
assistant infrastructure first: Core service, process-ready workers, typed
contracts, policy gates, telemetry, memory, voice, desktop automation seams,
Control Plane, and a Tauri shell.

Marvex is not an MVP, provider-chat wrapper, or CLI-first assistant. The current
provider and CLI paths are foundation/test paths for a larger assistant turn
model where Core, providers, intent, tools, memory, voice, desktop context,
policy, shell UI, and telemetry remain replaceable and independently governed.

## Strengths

- **Assistant OS architecture first** - provider turns are treated as one stage
  of a larger assistant lifecycle, not as the product model.
- **Process-ready boundaries** - Core, ProviderWorker, IntentWorker,
  ToolWorker, VoiceWorker, DesktopAgent, policy, telemetry, memory, and shell
  surfaces are designed around explicit contracts, health/version behavior,
  trace propagation, startup/shutdown rules, and safe projections.
- **Local-first security posture** - product services bind to loopback by
  default, protected routes use local bearer/cookie auth, shell token handoff
  avoids browser token storage, and raw tokens/audio/transcripts/provider
  payloads are not projected by default.
- **Ports/adapters discipline** - maintained libraries such as FastAPI,
  Pydantic, LiteLLM, OpenAI SDK, MCP SDK, Playwright, semantic-router, Authlib,
  FastEmbed, and voice SDKs live behind replaceable adapters instead of leaking
  into Core.
- **Policy-gated capabilities** - tool and computer-use paths run through
  CapabilityRuntime and approval/policy envelopes before execution.
- **Real desktop product surface** - a Windows Tauri v2 shell supervises or
  connects to the local backend, hosts chat/presence surfaces, opens the full
  Control Plane, and packages the Python runtime for installer builds.
- **Memory and cognition foundations** - derived memory, SQLite-backed recall,
  Obsidian-compatible vault projection, prompt harnessing, and context budgeting
  are bounded by persistence and provenance rules.
- **Voice worker foundation** - wakeword, VAD, STT, TTS, model asset readiness,
  device controls, barge-in, and safe worker telemetry are isolated from Core
  and exposed through protected Control Plane surfaces.

## Current Capability Map

| Surface | Current state |
| --- | --- |
| Core service | Native FastAPI/Uvicorn loopback API with `/health`, `/version`, turns, traces, auth, state publishing, and bounded agentic turn composition. |
| Assistant turn spine | Typed assistant envelope contracts, stage lifecycle foundations, recovery models, and provider-stage integration tests. |
| Provider runtime | Fake provider, LM Studio Responses adapter, LiteLLM adapter, structured output paths, streaming, and tool-call proposal normalization. |
| Intent worker | Local JSONL process boundary for classification and safe intent projections; does not execute tools or call providers. |
| Tool worker | Local JSONL process boundary around CapabilityRuntime policy, approvals, execution summaries, and blocked-result envelopes. |
| Control Plane | Local protected web/API surface for providers, approvals, runtime state, traces/logs, voice controls, memory, connectors, and settings. |
| Windows shell | Tauri v2 product shell with backend supervision/connection, chat, presence island, event-driven approval surface, dedicated Control Plane window, autostart, and installer path. |
| Voice worker | Local-only worker runtime with wakeword/STT/TTS controls, audio device tests, model readiness/downloads, VAD, playback, and barge-in. |
| Memory/cognition | Derived-memory loop, SQLite memory store, Memory Tree runtime, Obsidian-compatible vault projection, prompt harness, and safe recall. |
| Desktop/proactive | Approved bounded foundations for local perception, owner-mode automation contracts, visible proactive proposals, and policy-controlled execution. |
| Telemetry/governance | Trace events, safe sinks, architecture gates, contract approvals, boundary scripts, validation reports, and library decision records. |

## Architecture Posture

Marvex keeps Core small. Core owns assistant lifecycle orchestration through
contracts and ports. It must not own provider SDK behavior, tool execution,
memory storage, voice capture, UI behavior, desktop control, or future policy
services.

Every external system belongs behind an adapter. Every future service boundary
must be able to grow into a separate process without rewriting Core. Every
capability surface must define what it owns, what it refuses to own, what it can
persist, and what it may expose to UI or telemetry.

```text
Windows Shell / Control Plane / CLI
  -> Local API / Core Service
    -> Assistant Runtime / Turn Spine
      -> Provider Runtime -> Provider Adapters
      -> Intent Worker
      -> Tool Worker / Capability Runtime
      -> Memory / Cognition Runtime
      -> Voice Worker
      -> Telemetry / State Bus
```

## Quick Start (Windows)

Prerequisites: Node.js, Rust/Cargo, Python 3.12+ for installer builds
(3.11+ for source package compatibility), and
[uv](https://github.com/astral-sh/uv).

```powershell
# Full build and installer path
.\build-installer.ps1

# Faster development build without final installer creation
.\build-installer.ps1 -SkipInstaller
```

The build script reads the application version from `version.toml`, builds the
Python wheel, prepares runtime resources, builds the React/Tauri shell, and can
produce NSIS/MSI installer artifacts.

For details, see [`docs/BUILD_GUIDE.md`](docs/BUILD_GUIDE.md) and
[`docs/MARVEX_INSTALLER_PACKAGING.md`](docs/MARVEX_INSTALLER_PACKAGING.md).

## Development

Run the Core service from source:

```powershell
uv run python -m services.core.main --help
$env:MARVEX_LOCAL_AUTH_TOKEN="local-dev"; uv run python -m services.core.main --serve
```

Build the web surfaces:

```powershell
npm --prefix apps\control_plane_web install
npm --prefix apps\control_plane_web run build

npm --prefix apps\shell install
npm --prefix apps\shell run build
```

Run validation:

```powershell
uv run python -m pytest -q
uv run python scripts/run_all_checks.py
```

Some smokes are intentionally local/manual because they require Windows shell
integration, WebView2, physical audio devices, installed voice model assets, or
external provider endpoints.

## Repository Layout

- `apps/` - Tauri shell, Control Plane web UI, CLI, and future shell notes.
- `services/` - runnable local entrypoints for Core and approved workers.
- `packages/` - contracts, ports, adapters, runtime packages, and shared
  assistant infrastructure.
- `docs/` - architecture, governance, contracts, validation, roadmap, and
  library decisions.
- `scripts/` - validation gates, smoke checks, packaging helpers, and boundary
  enforcement.
- `tests/` - contract, runtime, adapter, worker, API, shell, and governance
  coverage.
- `assets/` - Marvex brand and application assets.

## Key Stack

| Area | Libraries and tools |
| --- | --- |
| Core/API | FastAPI, Uvicorn, Pydantic, uv, pytest |
| Providers | LiteLLM, OpenAI SDK, LM Studio Responses-compatible adapter, fake provider |
| Assistant/tooling | MCP SDK, Playwright, browser-use seam, OpenAI Agents compatibility seam, semantic-router |
| Memory/context | SQLite, FastEmbed, LlamaIndex Core seam, Memory Tree runtime, Obsidian-compatible Markdown vault |
| Voice/audio | Sherpa-ONNX, local-wake, Moonshine Voice, SpeechBrain, Kokoro-ONNX, Piper TTS, Silero VAD, WebRTC VAD, SoundDevice |
| Frontend/shell | React, Vite, Tauri v2, Rust, Framer Motion |
| Governance | Contract approvals, validation gates, library decision records, runtime ownership docs |

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) - core ownership, future process boundaries, and provider path.
- [`docs/SYSTEM_MAP.md`](docs/SYSTEM_MAP.md) - first-pass map of major surfaces and forbidden dependencies.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) - governance-first roadmap and current reality.
- [`docs/CONTRACT_APPROVALS.md`](docs/CONTRACT_APPROVALS.md) - approved, draft, and blocked contract surfaces.
- [`docs/GOVERNANCE_CLASSIFICATION.md`](docs/GOVERNANCE_CLASSIFICATION.md) - implemented, bounded, future, and forbidden surface classifications.
- [`docs/ASSISTANT_TURN_SPINE.md`](docs/ASSISTANT_TURN_SPINE.md) - assistant-level turn model.
- [`docs/PROCESS_MODEL.md`](docs/PROCESS_MODEL.md) - process readiness expectations.
- [`docs/CONTROL_PLANE_FOUNDATION.md`](docs/CONTROL_PLANE_FOUNDATION.md) - Control Plane boundary.
- [`docs/VOICE_WORKER_RUNTIME.md`](docs/VOICE_WORKER_RUNTIME.md) - voice worker runtime.
- [`docs/MEMORY_FOUNDATION.md`](docs/MEMORY_FOUNDATION.md) - memory foundation.
- [`docs/VALIDATION_GATES.md`](docs/VALIDATION_GATES.md) - architecture and safety gates.

## Status

Marvex is in active development and Windows-first. The default runtime is local
and does not expose public network services by default. Several surfaces are
bounded foundations, not unrestricted product permission. Future expansion is
controlled by task specs, contract approvals, architecture docs, validation
gates, [`docs/GOVERNANCE_CLASSIFICATION.md`](docs/GOVERNANCE_CLASSIFICATION.md),
and explicit user approval.

## Community

[Contributors](https://github.com/xRetr00/Marvex/graphs/contributors) -
[Discussions](https://github.com/xRetr00/Marvex/discussions) -
[Issues](https://github.com/xRetr00/Marvex/issues)
