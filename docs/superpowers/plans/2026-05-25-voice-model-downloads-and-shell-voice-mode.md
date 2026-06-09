# Voice Model Downloads And Shell Voice Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make voice model setup recoverable from the shell, fix worker-side model installation/readiness, and add an isolated Voice Mode tab without changing normal chat or overlay behavior.

**Architecture:** The voice worker remains the owner of model assets, package readiness, STT/TTS switching, wake-word supervision, and safe projections. The shell adds a Voice Mode tab that calls existing Control Plane worker endpoints and a new safe model catalog endpoint; it never imports or runs voice engines directly. Downloads stay explicit and local-only under the worker asset root.

**Tech Stack:** Python voice worker runtime, Control Plane voice endpoints, React shell, Tauri control bridge, Vitest/pytest.

---

### Task 1: Root-Cause Regression Tests

**Files:**
- Modify: `tests/voice_worker_runtime/test_model_downloads.py`
- Modify: `tests/voice_worker_runtime/test_backend_runtime_refs.py`
- Modify: `tests/scripts/test_fetch_voice_models.py`

- [ ] Add a failing worker test showing archive downloads must be extracted into the requested asset directory before install registration.
- [ ] Superseded: the old paired TTS readiness path was replaced by the single Supertonic V2 asset.
- [ ] Add a failing manifest test showing the active Moonshine package backend uses the Moonshine CDN layout instead of a sherpa ASR archive.
- [ ] Run `.\.venv\Scripts\pytest tests\voice_worker_runtime\test_model_downloads.py tests\voice_worker_runtime\test_backend_runtime_refs.py tests\scripts\test_fetch_voice_models.py -q` and confirm the new tests fail before production changes.

### Task 2: Backend Asset Fix

**Files:**
- Modify: `packages/voice_worker_runtime/assets.py`
- Modify: `packages/voice_worker_runtime/backend_runtime.py`
- Modify: `packages/voice_worker_runtime/model_adapters.py`
- Modify: `packages/control_plane_api/voice.py`
- Modify: `voice_models.manifest.json`

- [ ] Add archive extraction support to `VoiceAssetManager.download` through an explicit `extract` request field.
- [ ] Add a safe voice model catalog endpoint for shell UI consumption.
- [ ] Treat Supertonic V2 as a single required installed TTS asset.
- [ ] Keep TTS model execution isolated behind the worker adapter boundary.
- [ ] Update manifest source URIs to current canonical sources researched on 2026-05-25.

### Task 3: Shell Voice Mode Tab

**Files:**
- Modify: `apps/shell/src/lib/shellCommands.ts`
- Create: `apps/shell/src/lib/voiceControlClient.ts`
- Create: `apps/shell/src/surfaces/VoiceMode.tsx`
- Create: `apps/shell/src/surfaces/VoiceMode.test.tsx`
- Modify: `apps/shell/src/surfaces/ChatApp.tsx`

- [ ] Add typed shell bridge helpers for voice worker status, assets, catalog, start/stop, STT/TTS/voice switches, and model downloads.
- [ ] Add a Voice Mode tab with STT backend, TTS backend, active voice combo boxes, model asset list, wake-word state, and explicit test/start/stop/download actions.
- [ ] Keep existing chat and overlay navigation unchanged except for routing the chat mic button through voice worker start/stop instead of local-only state.
- [ ] Run `npm --prefix apps/shell test -- VoiceMode.test.tsx shellCommands.test.ts` and confirm UI tests pass.

### Task 4: Verification

**Files:**
- All changed files above.

- [ ] Run focused pytest for voice worker/control plane download/readiness behavior.
- [ ] Run shell unit tests for Voice Mode and command bridge behavior.
- [ ] Run `npm --prefix apps/shell run build`.
- [ ] Start the shell dev server and inspect the Voice tab locally.
