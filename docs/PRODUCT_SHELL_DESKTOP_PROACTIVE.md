# Marvex Product Surfaces — Shell, Desktop Agent, Proactive (Design)

Status: design/spec for the product surfaces that sit ON TOP of the bounded backend
(Core daemon, Provider/Intent/Tool/Voice workers, cognition loop, memory, web, learning).
This document defines the agreed product direction. Contract-registry flips
(`docs/CONTRACT_APPROVALS.md`) and governance reclassification
(`docs/GOVERNANCE_CLASSIFICATION.md`) are applied as their own slices when each
surface is implemented. Vision is OUT (no camera yet).

Everything here is a LOOPBACK CLIENT of the existing JSON contracts over HTTP/WebSocket —
the backend is unchanged; these are new front surfaces + new workers.

## 1. Model tiering (3 models, not 1)
Small local models are test-only. Production routing tiers via `provider_selection_runtime`:
- Tier 0 — tiny ~350M local: trivial/routing/classification, fillers, quick yes/no.
- Tier 1 — Qwen ~2B local: normal daily chat, short tasks.
- Tier 2 — large cloud LLM: complex thinking, multi-step agent/"body" reasoning, tool planning.
Selection is by intent confidence/complexity + risk + capability requirements (the existing
`ProviderSelectionRuntime` decision), with fallback. Tier escalation is a routing decision,
not new infrastructure.

## 2. Shell = one Windows app (Tauri), tray-only
- **Tauri v2** chosen (reuses the existing React control-plane web; tiny WebView2 binary).
- **Supervisor/launcher**: a single tray app boots and supervises the backend as WINDOWLESS
  child processes (`CREATE_NO_WINDOW`): Core daemon (`--serve`), Provider/Intent/Tool/Voice
  workers. Health-monitored, auto-restart, logs to files. Python backend runs as a Tauri
  **sidecar** (bundled, spawned) — NOT separate terminals.
- **Always minimized to tray**, **autostart on Windows login**, single-instance lock,
  graceful shutdown stops all children. Packaged as one installer (Tauri NSIS/MSI).
- No orb. (Removed by decision.)

## 3. Status pill + waveform (top-left, state-driven — NOT random)
A small always-on-top top-left indicator, shown only when Marvex is active (wake-triggered,
NOT proactive-popping):
- **Text status** (simple, one line): Talking / Listening / Thinking / Working / Using Tools /
  MCP / Skills / Searching Web / Asking / Needs Approval / Idle.
- **Waveform underneath**: driven by REAL state + audio:
  - Listening → reactive waveform from live mic amplitude (STT input level).
  - Speaking → flowing waveform from TTS output amplitude/tone.
  - Thinking/Working → calm pulse (no audio).
  Must read true VoiceWorker/turn state + audio level over the loopback event stream
  (WebSocket/`/control`), never random animation.
- Style: Siri-style "voice waves" glow (simpler/cleaner than a 3D orb), implemented as a
  transparent always-on-top Tauri window (web canvas/CSS/WebGL). Click-through via the Rust
  `setIgnoreCursorEvents` cursor-poll pattern (Tauri has no native per-region hit-test).

## 4. Spotlight surface (Marvex-invoked, controlled)
A macOS-Spotlight/Siri-style panel that Marvex shows when it needs to present something:
- approval prompts with buttons AND voice approval (waits for either button OR voice OR timeout);
- info, photos, search results, and the LLM's response when it's large.
- Invoked by Marvex (or a global hotkey), controlled/transient — NOT the chat history.

## 5. Chat UI (the normal window)
- Type chat + TTS playback + mic button for STT.
- Shows everything normally (the full surface): all of the above statuses, results, approvals,
  history. Spotlight is the lightweight controlled surface; Chat is the full one.

## 6. Desktop Agent — read window CONTENT (not just titles)
Goal: Marvex perceives what's actually on screen — VS Code editor text, the YouTube video
being watched, terminal output — not window titles.
Recommended local/free stack (all loopback/MCP, no cloud screen data by default):
- **Windows UI Automation tree** for live structured content of focused apps:
  `pywinauto` (win32 + uia backends) and `Python-UIAutomation-for-Windows` (yinkaisheng) —
  works for VS Code/Electron, terminals, WPF/WinForms, Chrome/Firefox, Qt(partial).
  Reads text, controls, selection — the "what's in this window" layer.
- **screenpipe** (MIT, open-source, fully local) as the 24/7 perception+memory layer:
  captures screen on meaningful events, pairs each screenshot with the OS **accessibility tree**
  (structured text) and falls back to **OCR**; local Whisper for system+mic audio; exposes an
  **MCP server**. Marvex consumes it via the EXISTING MCP path → Desktop Agent gets "what did I
  see/hear" recall + current context without leaving the machine.
- **OmniParser V2** (Microsoft, open) for pure-vision UI element parsing when accessibility
  data is missing (games/remote/canvas apps) — turns a screenshot into structured elements.
- Browser specifics (current tab URL / current YouTube video): via the UI Automation
  accessibility value of the address bar / page, or a future lightweight browser-extension
  bridge; treat as best-effort.
Safety: perception is local-only; safe bounded projections to the turn (no raw screen frames
persisted by Marvex beyond screenpipe's own user-owned local store); approval-gated before any
content leaves the machine to a cloud model.

## 7. computer-use — act on the PC (the "hands")
All execution behind CapabilityRuntime policy + approval (existing). Recommended free/open:
- **browser-use** (already a Marvex dep) — mature web automation (navigate/click/type/extract).
- **UFO** (Microsoft) — purpose-built Windows desktop automation via the UI Automation tree +
  vision planning; production-quality for Windows.
- **OmniParser V2** + UI Automation — vision+a11y hybrid grounding for clicks.
- **Open Interpreter** / **UI-TARS** — local-model-capable fallbacks for code/computer actions.
Marvex owns the loop/policy; these are adapters behind the Tool/Capability boundary, gated by
AutonomyPolicy + approval. Computer-use overlaps the (currently excluded) Desktop scope —
implement as approval-required, off-by-default.

## 8. Proactive (24/7, Desktop-Agent-driven, Learning-controlled)
- A bounded Proactive worker watches the Desktop Agent perception stream (screenpipe events +
  UI Automation) 24/7 and proposes initiative at the right moment (e.g. "you've been stuck on
  this error 10 min — want me to look?").
- **Wired to learning_runtime preference control**: "don't ask that again", "say that less",
  "only when important/critical", "say that more" become durable learned preferences that gate
  proactive frequency/triggers per topic. Explicit, visible, local-only, policy-controlled,
  never hidden background actions; user can mute globally/per-topic.

## 9. Contract / governance changes these surfaces require (apply per-slice)
When each surface is built, the implementing slice updates the registries:
- `Shell` contract → approved (Tauri tray supervisor + status pill/waveform + spotlight + chat;
  loopback client of Core/Control-Plane/Voice contracts; defines overlay/voice-STATE events).
- `DesktopAgent` contract → approved (window-content perception via UI Automation + screenpipe-MCP;
  safe bounded content projections; local-only; no raw frame persistence by default).
- New `Proactive` contract (initiative proposals + learning-preference gating; explicit/visible).
- Voice/overlay STATE contract: the status enum (Talking/Listening/Thinking/Working/Using
  Tools/MCP/Skills/Searching/Asking/Needs Approval/Idle) + audio-amplitude event stream the
  pill/waveform subscribes to.
- Provider tier config: tier-0/1/2 model selection in `provider_selection_runtime`.
- New dependencies (optional extras, library-decision-gated): `pywinauto`, `uiautomation`;
  screenpipe/OmniParser/UFO consumed as external processes/MCP (not Python deps).

## 10. Excluded (for now)
Vision (no camera yet). Anything beyond the surfaces above stays out until explicitly added.

## Sources (research, May 2026)
- Microsoft OmniParser V2 — https://github.com/microsoft/OmniParser ; https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
- Microsoft UFO / Windows Agent Arena — https://www.microsoft.com/applied-sciences/projects/windows-agent-arena
- Open computer-use roundups — https://fazm.ai/blog/best-open-source-computer-use-agent-windows-2026
- pywinauto — https://github.com/pywinauto/pywinauto
- Python-UIAutomation-for-Windows — https://github.com/yinkaisheng/Python-UIAutomation-for-Windows
- screenpipe (24/7 local screen+audio, a11y+OCR, MCP) — https://github.com/screenpipe/screenpipe ; https://docs.screenpi.pe/home
- Tauri v2 overlay/click-through — https://v2.tauri.app/learn/window-customization/ ; https://github.com/tauri-apps/tauri/issues/13070
