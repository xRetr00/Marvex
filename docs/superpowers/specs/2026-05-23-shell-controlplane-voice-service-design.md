# Marvex Shell UX, Control Plane Window, and 24/7 Voice Service — Design

Date: 2026-05-23
Status: Approved (pending written-spec review)

## Problem

The Marvex Tauri shell (`apps/shell`) has three categories of defects reported by the project owner:

1. **Shell UI freezes / poor performance.** The in-app UI becomes unresponsive and feels slow. Root cause confirmed: the overlay surface registers a `mousemove` listener that calls the Tauri command `setOverlayClickThrough` on *every* pointer move (`apps/shell/src/surfaces/overlay.tsx`), flooding the IPC bridge. The WebGL waveform (`MarvexWaveform`) also runs an unconditional 60fps render loop even when idle/hidden.
2. **No real Control Plane.** The shell embeds a minimal in-shell "Control Plane" tab and a "Deps" tab that only show a fraction of settings. The full original Control Plane app (`apps/control_plane_web`, 26 views including Providers, Voice Runtime with selected model/provider/TTS voice/STT model + downloads, Agents/Personas) is built by the installer but never opened by the shell.
3. **Spotlight and island are wrong.** The `spotlight` window is a 780×420 box with scrollbars, summoned manually from the dock button + tray menu + global shortcut — i.e. it behaves like a mode/window, not event-driven cards. The dynamic island (`overlay` window) is pinned top-left, shows only a bare pulsing dot at idle, and feels "dead." The owner wants the island on the **right**, showing live state even at idle, expanding the voice waveform on hover, with Spotlight cards spawning *out of* the island.
4. **Voice/wake word not shipped as a guaranteed always-on capability.** The wake-word ("Hey Marvex") worker is treated as part of optional dependency handling. The owner wants it forced into the build, shipped with its models, and running 24/7 as a Windows service that starts at boot, so "Hey Marvex" fires instantly in real time.

## Decisions (from brainstorming)

- **Control Plane:** dedicated Tauri window loading the original `control_plane_web`; retire the shell's mini Control Plane + Deps tabs.
- **Voice runtime:** a true Windows Service. Scope = **full backend service** (supervises Core + control plane + intent/tool/provider/voice workers 24/7) because keeping Core warm is what makes "Hey Marvex" fire instantly with no cold-start. The shell becomes a thin client.
- **Structure:** one spec, phased implementation. Order: Phase 1 (Shell UX/perf) → Phase 2 (Control Plane window) → Phase 3 (build/installer/voice service).
- **Spotlight global shortcut (Ctrl+Shift+Space):** removed. Spotlight is fully event-driven.
- **Governance:** wake-word-enabled-by-default / always-on overrides the current documented "disabled by default" stance; `PROJECT_STATUS.md` and `docs/CONTRACT_APPROVALS.md` will be updated. No-raw-audio-persistence and safe-projection guarantees are preserved.

## Non-Goals

- No new assistant intelligence, provider routing, tool, memory, or cognition behavior.
- No change to the safe-projection / no-raw-payload-persistence guarantees.
- No redesign of `control_plane_web`'s internal views beyond wiring the model/voice/STT selection + download endpoints if a gap is found.
- No macOS/Linux service work (Windows-only service for this slice).

---

## Phase 1 — Shell UX & Performance

### 1a. Eliminate the IPC freeze (overlay click-through)
In `apps/shell/src/surfaces/overlay.tsx`, replace the per-mousemove invoke with edge-triggered logic:
- Keep `lastOverRef` (boolean). On `mousemove`, compute `over`; only call `setOverlayClickThrough(!over)` when `over !== lastOverRef.current`.
- Throttle the geometry check with a `requestAnimationFrame` guard so at most one check runs per frame.
- Result: one IPC call per actual enter/leave transition instead of hundreds per second.

### 1b. WebGL waveform throttling
In `apps/shell/src/components/waveform-shader/MarvexWaveform.tsx`:
- Add an `active` prop (derived from `expanded`/state). When inactive, render a single frame and stop the RAF loop; resume when active.
- Stop the loop on `document.visibilitychange` → hidden; resume on visible.
- Goal: GPU usage ≈ 0 at rest.

### 1c. Island on the right, live state at idle
- `tauri.conf.json`: change the `overlay` window anchor from top-left (`x:16`) to top-right. Use a deterministic right anchor; if dynamic positioning is needed, a Rust helper mirrors `position_spotlight_top_right`.
- `overlay.tsx`: the idle island content shows a compact live status (status label + small ambient waveform reflecting `assistant-state`) rather than a bare dot. Hover/active expands to the full ring with the live waveform.

### 1d. Spotlight = island-spawned cards (not a window/mode)
- `tauri.conf.json`: shrink the `spotlight` window to a content-sized card, anchored directly beneath the island at top-right (not centered), `transparent`, no scrollbars.
- `apps/shell/src/styles.css`: fix `.spotlight-shell` / `.spotlight-panel` to size to content and remove the body/window overflow that produces scrollbars.
- Spotlight animates "out of" the island (origin top-right).
- Remove the Spotlight button from the `ChatApp` footer dock.
- Remove the "Spotlight" item from the tray menu (`lib.rs` `build_tray`).
- Remove the Ctrl+Shift+Space global shortcut registration + handler (`lib.rs`).
- Keep the `show_spotlight`/`hide_spotlight` commands for internal event-driven use (approval/result/agenda payloads), invoked by the state stream / approval flow, not by the user.

### Phase 1 testing
- Unit: edge-trigger logic for click-through (no call when state unchanged).
- Existing `overlay.test.tsx` and `Spotlight.test.tsx` updated for new behavior.
- Manual smoke: move mouse rapidly over/off island — UI stays responsive; island sits top-right and shows state at idle; hover animates the waveform; an injected approval payload shows a card spawning from the island with no scrollbars; no Spotlight button in dock; no Spotlight tray item; shortcut no longer summons Spotlight.

---

## Phase 2 — Control Plane Window

### 2a. Dedicated control plane window
- Add a `control` window definition (or create-on-demand `WebviewWindow`) that loads the bundled `control_plane_web` build output.
  - Dev: load its Vite dev URL. Production: load the bundled control plane `index.html` from Tauri resources.
  - Update the build (Phase 3 build script already builds `control_plane_web`) to copy its `dist` into the shell bundle resources so the window can load it offline.
- **Token injection:** the shell mints a local bearer token (`token.rs`). Expose it to the control plane window so `control_plane_web/src/lib/api.ts` can authorize `/control/*` calls — via an injected global (`window.__MARVEX_CP_TOKEN__`) read by `api.ts`, or a Tauri command the control plane page calls on load. Token is never logged or persisted by shell code.
- A new shell command `open_control_plane` shows/focuses (and lazily creates) the window. The dock's "Control Plane" entry calls it.

### 2b. Retire shell mini surfaces
- Remove the "control" and "deps" tabs from `apps/shell/src/surfaces/ChatApp.tsx`. The chat window becomes Chat-only.
- The dock (`navItems`) keeps **Chat** and replaces Control/Deps with a single **Control Plane** entry that opens the window.
- Model/provider/TTS-voice/STT-model selection and model/voice downloads are owned by `control_plane_web`'s existing `VoiceRuntimeView` / Providers / Agents-Personas views, backed by the existing protected `/control` endpoints. If any of those selection/download controls are missing in `control_plane_web`, add them there (not in the shell).
- Delete now-unused shell-only modules if fully orphaned (`depsClient.ts`, deps UI, the shell's RuntimeSelect/voice-selector usage) — verified before deletion.

### Phase 2 testing
- Unit: `open_control_plane` command (window create/show idempotence) where testable; token-injection accessor.
- Manual smoke: dock "Control Plane" opens the full original control plane; it authenticates and renders live data; selected model/provider, TTS voice id, STT model are visible; model/voice download actions are present and callable.

---

## Phase 3 — Build, Installer & 24/7 Voice Windows Service

### 3a. Wake-word worker is a required, model-complete build artifact
- The voice worker (`services/voice_worker`) and its deps already exist in `pyproject.toml`. Harden the build so:
  - The wake-word KWS model + STT + TTS model assets required for "Hey Marvex" are bundled into the installer under the safe voice asset root.
  - The build **fails** if those required model assets are absent (no silent optional skip).
- `build-installer.ps1` / `.bat`: add a model-asset acquisition + verification step; include assets in Tauri `bundle.resources`.

### 3b. Marvex backend Windows Service (full backend, always warm)
- Introduce a service entrypoint that supervises the backend stack 24/7: Core (`8765`), Control Plane (`8766`), and intent/tool/provider/voice workers — reusing the existing supervisor logic (`apps/shell/src-tauri/src/supervisor.rs`) extracted/shared as appropriate, or a Python/Rust service host.
  - Always-on voice worker with wake word enabled → Core already running → instant "Hey Marvex" dispatch (no cold start).
  - Auto-restart on crash; starts at boot (before login).
  - Generates the local bearer token and writes it to a protected local file readable by the shell.
- **Shell becomes a thin client:** the shell's setup stops spawning its own Core/workers; instead it reads the shared token and connects to the already-running service. If the service is not present (dev / non-installed), the shell falls back to its current self-supervising behavior so `npm run tauri dev` still works.
- NSIS installer (`installMode: perMachine`, already set) registers and starts the service; uninstall removes it.

### 3c. Governance documentation
- Update `PROJECT_STATUS.md` and `docs/CONTRACT_APPROVALS.md`:
  - Wake word is now enabled-by-default and runs as an always-on Windows service.
  - Document the backend-service architecture and the thin-client shell.
  - Preserve and restate the no-raw-audio/transcript/generated-audio-persistence and safe-projection guarantees.

### Phase 3 testing
- Build smoke: `build-installer.ps1` fails when wake-word models are missing; succeeds with them bundled.
- Service smoke (manual, host-dependent): install → service runs at boot → "Hey Marvex" detected with shell closed → shell launches and connects to the running service via shared token. WebView2/audio/installer smokes remain manual per existing project practice.

---

## Architecture After This Work

```
                ┌─────────────────────────── Windows Service (24/7, boot start) ──────────────────────────┐
                │  Supervisor → Core(8765) + Control Plane(8766) + intent/tool/provider/voice workers      │
                │  Voice worker: always-on wake word "Hey Marvex" → instant dispatch to warm Core           │
                │  Mints local bearer token → protected token file                                          │
                └───────────────▲───────────────────────────────────────────────▲──────────────────────────┘
                                │ reads token, loopback HTTP                       │ loopback HTTP + token
                ┌───────────────┴──────────────┐                  ┌──────────────┴──────────────┐
                │  Shell (thin client, Tauri)   │                  │  Control Plane window         │
                │  - main: Chat-only            │                  │  (control_plane_web, 26 views)│
                │  - overlay: island (top-right,│                  │  Providers / Voice Runtime /  │
                │    live state, hover waveform)│                  │  Agents-Personas / downloads  │
                │  - spotlight: event cards from│                  └───────────────────────────────┘
                │    island (no window/mode)    │
                └───────────────────────────────┘
```

## Risks / Open Items
- The thin-client refactor must preserve a working `npm run tauri dev` (no installed service) via fallback to self-supervision.
- Token sharing between a perMachine service and a per-user shell needs a file location both can access with least privilege; define exact path during implementation.
- Wake-word model licensing/size for bundling into the installer must be confirmed during Phase 3.
