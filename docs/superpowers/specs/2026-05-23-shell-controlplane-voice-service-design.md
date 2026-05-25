# Marvex Shell UX, Presence Layer, Control Plane Window, and 24/7 Voice Service — Design

Date: 2026-05-23
Status: Approved-in-principle (pending written-spec review after feedback round)

## Problem

The Marvex Tauri shell (`apps/shell`) has several defects reported by the project owner:

1. **The whole app freezes / "Not Responding."** Not just the overlay — the chat window, app startup, and even the tray context menu freeze. Confirmed root cause: **every networking Tauri command is synchronous and performs blocking socket I/O on the main/UI thread.** `apps/shell/src-tauri/src/http.rs` uses a raw `TcpStream` with `read_to_string` and a 20-second read timeout; commands like `submit_chat_turn`, `control_request`, `backend_health`, `gui_health`, and `get_setup_status` are declared `fn` (not `async fn`), so in Tauri v2 they run on the main thread that also paints windows and renders the tray menu. Any slow/blocking call freezes the entire app. A secondary contributor: `overlay.tsx` calls the `setOverlayClickThrough` command on **every** `mousemove`, flooding the IPC bridge. The WebGL waveform also runs an unconditional 60fps loop even at rest.

2. **No real Control Plane.** The shell embeds a minimal in-shell "Control Plane" tab and a "Deps" tab showing a fraction of settings. The full original Control Plane (`apps/control_plane_web`, 26 views incl. Providers, Voice Runtime with selected model/provider/TTS voice/STT model + downloads, Agents/Personas) is built by the installer but never opened by the shell.

3. **The presence layer (the "soul") is wrong and feels dead.** The dynamic island (the always-present, Siri-like presence — "Siri is part of macOS") and the cards/spotlights it spawns are the soul of the assistant OS, but today: the island (`overlay` window) is pinned top-left, shows only a bare pulsing dot at idle, and feels dead; Spotlight is a 780×420 scrollbar window summoned manually from the dock button + tray menu + global shortcut (i.e. a mode/window, not event-driven cards). The owner wants the island on the **right**, alive and showing live state even at idle, expanding the voice waveform on hover, with cards (approvals, results, agenda, info) spawning *out of* the island.

4. **Chat/sessions are ephemeral and the session ref is hardcoded.** Shell chat history lives only in React state and is lost on close. `submit_chat_turn` hardcodes `session_ref.ref_id = "shell-session"`. There is no way to see prior chats/sessions or resume where you left off.

5. **Failure states collapse into one meaningless message.** When the chat UI is open but the backend isn't running, no LLM/provider is configured, or the provider errors, sending "Hi" just shows **"No displayable response returned."** (`localTurn.ts:8`). `submit_chat_turn` also **hardcodes `"model":"fake-model"` / `execution_mode: "assistant_runtime_fake_provider"`** (`lib.rs`), so the shell never exercises a real configured provider. All failure cases need distinct, actionable messaging surfaced in chat and reflected in the island presence.

6. **Voice/wake word is not a guaranteed always-on capability.** The wake-word ("Hey Marvex") worker is treated as part of optional dependency handling. The owner wants it forced into the build, shipped with its models, and running 24/7 as a Windows service that starts at boot, so "Hey Marvex" fires instantly in real time.

## Decisions (from brainstorming + feedback)

- **Async backend bridge:** replace the raw blocking `TcpStream` HTTP connector with a non-blocking async client; make all I/O-bound Tauri commands `async` and run network/file I/O off the main thread. This is the primary fix for the global freeze.
- **Control Plane:** dedicated Tauri window loading the original `control_plane_web`; retire the shell's mini Control Plane + Deps tabs.
- **Presence layer is first-class:** the dynamic island + its spawned cards are designed as one cohesive presence system driven by a single assistant-state source of truth.
- **Voice runtime:** a true Windows Service, scope = **full backend service** (supervises Core + control plane + intent/tool/provider/voice workers 24/7) so Core stays warm and "Hey Marvex" fires instantly with no cold start. The shell becomes a thin client.
- **Persistence:** durable chat/sessions with a real `session_ref`; prior chats/sessions are listable and resumable.
- **Structure:** one spec, phased. Order: Phase 1 (Shell UX/perf/presence/persistence/failure-states) → Phase 2 (Control Plane window) → Phase 3 (build/installer/voice service).
- **Spotlight global shortcut (Ctrl+Shift+Space):** removed; Spotlight is fully event-driven cards.
- **Governance:** wake-word-enabled-by-default / always-on overrides the current documented "disabled by default" stance; `PROJECT_STATUS.md` and `docs/CONTRACT_APPROVALS.md` updated. No-raw-audio-persistence and safe-projection guarantees preserved.

## Non-Goals

- No new assistant intelligence, tool, memory-cognition, or routing behavior beyond wiring provider/model selection through existing endpoints.
- No change to no-raw-payload-persistence / safe-projection guarantees.
- No redesign of `control_plane_web`'s internal views beyond wiring model/voice/STT selection + downloads if a gap is found.
- No macOS/Linux service work (Windows-only service for this slice).

---

## Phase 1 — Shell UX, Performance, Presence & Persistence (first)

### 1a. Async, non-blocking backend bridge (PRIMARY freeze fix)
- Replace the raw `TcpStream` connector in `http.rs` with an async HTTP client (`reqwest` async over loopback; Tauri already pulls in tokio via `tauri::async_runtime`). Keep the loopback-only host guard and bearer-token handling.
- Convert all I/O-bound commands to `async fn`: `submit_chat_turn`, `control_request`, `backend_health`, `gui_health`, `get_setup_status`, `start_setup`, `start_backend`. They must `await` the async client (or use `tauri::async_runtime::spawn_blocking` for any unavoidable blocking call) so the **main thread is never blocked**.
- Tighten timeouts (connect + per-request) to small, sane values with proper error mapping instead of a 20s read timeout.
- Acceptance: while a chat turn is in flight, the tray menu opens instantly and windows repaint smoothly.

### 1b. Overlay click-through: edge-triggered (secondary freeze fix)
- In `overlay.tsx`, track `lastOverRef`; call `setOverlayClickThrough(!over)` only when `over` changes, guarded by a `requestAnimationFrame` throttle. One IPC call per enter/leave instead of hundreds per second.

### 1c. WebGL waveform throttling
- `MarvexWaveform` gets an `active` prop; when inactive it renders a single frame and stops its RAF loop, resuming on active/hover. Stop on `document.visibilitychange → hidden`. GPU ≈ 0 at rest.

### 1d. Presence layer: the dynamic island as the soul
The island is the always-present, Siri-like presence and the anchor everything spawns from. Driven by a single assistant-state source (the `/control/state` stream).
- **Position:** move the `overlay` window anchor from top-left to top-right (`tauri.conf.json`; Rust right-anchor helper mirroring `position_spotlight_top_right`).
- **State→visual mapping (alive at idle):** idle = ambient "alive" pill showing current status (e.g. "Ready"/"Listening") with a subtle ambient waveform, not a bare dot; listening/talking = reactive waveform bound to `audio_level`; thinking/working/using-tools/searching = animated working motion; needs-approval = alert pulse. Hover always expands and animates the waveform.
- **Single state hook:** extract the assistant-state subscription + status→visual derivation into one shared module used by the island, cards, and chat header, so all surfaces agree.

### 1e. Spotlight = island-spawned cards (not a window/mode)
- Shrink the `spotlight` window to a content-sized, transparent, scrollbar-free card anchored directly beneath the island at top-right; fix `.spotlight-shell`/`.spotlight-panel` overflow + auto-size in `styles.css`.
- Cards animate "out of" the island (transform origin = island corner).
- Card kinds: approval, result, agenda, info — plus failure/notice cards (see 1g/1h) and a "session resumed" card.
- **Remove** the Spotlight dock button (`ChatApp` footer), the "Spotlight" tray item (`lib.rs build_tray`), and the Ctrl+Shift+Space shortcut registration/handler (`lib.rs`). Keep `show_spotlight`/`hide_spotlight` commands for internal event-driven use only.

### 1f. Chat/session continuity (persistence)
- Replace the hardcoded `session_ref.ref_id = "shell-session"` with a real, stable per-conversation `session_ref` (generated, persisted locally, sent with each turn).
- Persist chat history durably (backed by the existing backend `SessionRuntime`/session endpoints where available; local fallback otherwise). On launch the shell restores the active conversation instead of starting blank.
- Add a sessions list / history surface so prior chats are viewable and resumable. (Reuses the control plane's session safe-projections where appropriate.)
- Acceptance: send messages, close and reopen the shell → conversation is still there and continues under the same session.

### 1g. Robust failure-state surfacing
- Replace the generic `finalTextFromTurnResult` fallback with explicit mapping of distinct cases, each with an actionable message + a presence/island reflection (e.g. island shows "Backend offline"):
  - **Backend unreachable** (command/connect error) → "Backend isn't running yet — starting it…" with a retry affordance, and reflect via `backend_health`.
  - **No provider/LLM configured** → "No model/provider is configured. Open Control Plane → Providers." (links to Phase 2 window).
  - **Provider error** (upstream returned error) → surface the safe provider error reason.
  - **Empty/edge result** (turn ok but no text) → a clear "no response text" notice distinct from errors.
- Stop hardcoding `fake-model`: `submit_chat_turn` sends the selected/configured provider+model (from control-plane selection) or lets Core use the configured default; the fake provider path becomes an explicit dev/test mode, not the shipped default. (Selection UI is owned by Phase 2; Phase 1 wires the turn to honor it and to report when nothing is configured.)
- Acceptance: with the backend down, "Hi" shows a backend-offline message (not "No displayable response returned"); with no provider configured, it points the user to Providers; the island reflects the failure state.

### Phase 1 testing
- Rust: async command compiles and returns without blocking; loopback guard + token handling preserved; right-anchor helper math.
- TS unit: edge-trigger click-through (no call when unchanged); `finalTextFromTurnResult` replacement returns the correct branch per case; session_ref generation/persistence; updated `overlay.test.tsx` / `Spotlight.test.tsx`.
- Manual smoke: rapid mouse over/off island stays responsive; tray menu opens during an in-flight turn; island sits top-right and shows state at idle; hover animates waveform; injected approval/result spawns a scrollbar-free card from the island; no Spotlight dock button/tray item/shortcut; close+reopen restores the conversation; backend-down and no-provider cases show actionable messages.

---

## Phase 2 — Control Plane Window

### 2a. Dedicated control plane window
- Add a `control` WebviewWindow (created on demand) that loads the bundled `control_plane_web` build (dev: its Vite URL; prod: bundled `index.html` from Tauri resources — the build script already builds `control_plane_web`; copy its `dist` into shell bundle resources).
- **Token injection:** expose the shell's local bearer token to the control plane page so `control_plane_web/src/lib/api.ts` can authorize `/control/*` (injected global `window.__MARVEX_CP_TOKEN__` read by `api.ts`, or a Tauri command the page calls on load). Token never logged/persisted by shell code.
- New `open_control_plane` command shows/focuses (lazily creates) the window; the dock's "Control Plane" entry calls it.

### 2b. Retire shell mini surfaces
- Remove the "control" and "deps" tabs from `ChatApp`; chat window becomes Chat-only (plus the sessions/history surface from 1f). Dock keeps **Chat** + **Sessions** + **Control Plane**.
- Model/provider/TTS-voice/STT-model selection + downloads live in `control_plane_web` (its `VoiceRuntimeView`/Providers/Agents-Personas, backed by existing `/control` endpoints). Add any missing selection/download controls there, not in the shell.
- Delete orphaned shell-only modules after verification (`depsClient.ts`, deps UI, shell `RuntimeSelect`, in-shell voice selector if unused).

### Phase 2 testing
- Unit: `open_control_plane` idempotence (create/show); token-injection accessor.
- Manual smoke: dock "Control Plane" opens the full original control plane authenticated with live data; selected model/provider, TTS voice id, STT model visible; model/voice download actions present and callable.

---

## Phase 3 — Build, Installer & 24/7 Voice Windows Service

### 3a. Wake-word worker is a required, model-complete build artifact
- Harden the build so the wake-word KWS + STT + TTS model assets required for "Hey Marvex" are bundled into the installer under the safe voice asset root, and the build **fails** if they are absent (no silent optional skip).
- `build-installer.ps1` / `.bat`: add model-asset acquisition + verification; include assets in Tauri `bundle.resources`.

### 3b. Marvex backend Windows Service (full backend, always warm)
- Introduce a service host that supervises the backend stack 24/7 (Core 8765, Control Plane 8766, intent/tool/provider/voice workers), reusing/extracting the existing supervisor logic (`supervisor.rs`). Always-on voice worker + warm Core → instant "Hey Marvex". Auto-restart on crash; starts at boot before login. Generates the local bearer token and writes it to a protected local file readable by the shell.
- **Shell becomes a thin client:** stops spawning its own Core/workers; requests a local token lease from the backend service and connects to the running service. If no service is present (dev / `npm run tauri dev`), it falls back to current self-supervision so dev still works.
- NSIS installer (`installMode: perMachine`, already set) registers + starts the service; uninstall removes it.

### 3c. Governance documentation
- Update `PROJECT_STATUS.md` and `docs/CONTRACT_APPROVALS.md`: wake word enabled-by-default + always-on Windows service; backend-service + thin-client architecture; restate no-raw-audio/transcript/generated-audio persistence + safe-projection guarantees.

### Phase 3 testing
- Build smoke: build fails when wake-word models missing; succeeds when bundled.
- Service smoke (manual, host-dependent): install → service runs at boot → "Hey Marvex" detected with shell closed → shell launches and connects via local token lease. WebView2/audio/installer smokes remain manual.

---

## Architecture After This Work

```
                ┌─────────────────────────── Windows Service (24/7, boot start) ──────────────────────────┐
                │  Supervisor → Core(8765) + Control Plane(8766) + intent/tool/provider/voice workers      │
                │  Voice worker: always-on wake word "Hey Marvex" → instant dispatch to warm Core           │
                │  Mints local bearer token → protected token file                                          │
                └───────────────▲───────────────────────────────────────────────▲──────────────────────────┘
                                │ reads token, async loopback HTTP                 │ async loopback HTTP + token
                ┌───────────────┴──────────────┐                  ┌──────────────┴──────────────┐
                │  Shell (thin client, Tauri)   │                  │  Control Plane window         │
                │  - main: Chat + Sessions      │                  │  (control_plane_web, 26 views)│
                │  - overlay: PRESENCE island   │                  │  Providers / Voice Runtime /  │
                │    (top-right, live idle state,│                 │  Agents-Personas / downloads  │
                │     hover waveform)            │                  └───────────────────────────────┘
                │  - spotlight: event cards      │
                │    spawned from the island     │
                │  Async non-blocking bridge     │
                │  Durable session_ref           │
                └───────────────────────────────┘
```

## Risks / Open Items
- Adopting `reqwest` adds a Rust dependency to the shell; confirm it builds with the existing Tauri toolchain (it shares tokio).
- Honoring provider/model selection in the chat turn depends on Phase 2 selection + the existing `/control` provider endpoints; Phase 1 wires "use configured default / report when none" and full selection lands with Phase 2.
- Thin-client refactor must preserve a working `npm run tauri dev` via self-supervision fallback.
- Shared-token file location between a perMachine service and per-user shell needs a least-privilege path (defined in implementation).
- Wake-word model licensing/size for installer bundling confirmed in Phase 3.
