# Overlay / Dynamic Island Refactor — Design

**Date:** 2026-06-01
**Status:** Approved for planning
**Scope:** The Marvex shell overlay surface (the always-on-top "Dynamic Island"). The
chat window is explicitly out of scope for this pass (handled separately, later).

## 1. Problem & intent

The current overlay (`apps/shell/src/surfaces/overlay.tsx` + `components/dynamic-island/index.tsx`
+ `lib/islandQueue.ts` + `lib/overlayHover.ts`) is to be fully replaced. The replacement
must:

- Be built on top of the **portable web subset** of the vendored library at
  `temp/react-native-pretty-toast-1.0.1/src` (copy the files, don't re-type them).
- Render as a **native-looking, free-floating pill** with no visible transparent window
  box — anchored **top-center** ("notch" position), always on top, correct on **any
  screen size / DPI**.
- Reflect the assistant's live **states** and a **waveform** (compact pill and expanded).
- Support **voice** (wake word, STT, TTS) the same way chat does — i.e. by *visualizing*
  the existing backend voice pipeline, not by capturing audio in the overlay.
- Show **approvals** inline in the expanded pill (Approve / Deny).
- **No click-through.** **No `approval-voice-decision`.** **Questions deferred.**

### Critical context (why the literal "copy all files" can't stand alone)

`react-native-pretty-toast` is a **React Native** library. Only its web path is usable in
Marvex's Tauri (DOM) webview, and that web path is a *transient top-center toast* — it has
no dynamic-island morph, no waveform, no voice, no approvals, no state wiring. So we copy
the DOM-portable subset as the **card/pill renderer**, and build the Marvex island and all
backend wiring **on top** of it.

Portability table:

| File | Action |
|------|--------|
| `WebToastView.tsx` | Copy verbatim — pure DOM (`createPortal`). The transient **card** renderer (info + approval), **not** the morph pill. |
| `toast.ts`, `useToast.ts`, `variants.ts`, `index.tsx` | Copy verbatim. |
| `ToastProvider.web.tsx` | Copy as `ToastProvider.tsx` (drop the `.web` suffix). |
| `types.ts` | Copy, but remove `import type { ColorValue, ImageSourcePropType } from 'react-native'` and alias both to `string`. |
| `ToastProvider.tsx` (native), `ToastViewNativeComponent.ts`, `ios/`, `android/` | **Do not copy** — React Native only, no Windows runtime. |

### Morph pill source (added 2026-06-01)

pretty-toast's `WebToastView` is a **toast** — fixed position, no expand/collapse. A Dynamic
Island needs the Framer-Motion `layout` **morph** (the black pill auto-resizing between
compact and expanded). Two local demos provide exactly that:

- **`UI_EXTERNAL_Helpers/components/dynamic-island.tsx`** — the original the current Marvex
  island was derived from. Rich morph: `motion/react` `layout` pill + spring `BOUNCE_VARIANTS`
  keyed per transition + enter blur/scale. **This is the vendored morph shell**, stripped of
  its demo views (weather/call/timer/notification/music) and the debug toolbar.
- **`temp/dynamic-island-web-main/src/components/DynanmicIsland/DynamicIsland.tsx`** — a
  Next.js web clone. Reference only: borrow its `transformOrigin: top` / `originY: 0` anchor
  so the pill grows downward from the top-center notch.

Division of labor: **morph pill shell** ← `UI_EXTERNAL_Helpers` (vendored, stripped);
**card/queue/swipe lifecycle** ← pretty-toast web subset. framer-motion + lucide + Tailwind
are already Marvex dependencies, so no new runtime deps.

## 2. Architecture

### 2.1 Module layout

```
apps/shell/src/components/pretty-toast/        ← VENDORED (copied)
  WebToastView.tsx, ToastProvider.tsx, toast.ts, useToast.ts,
  variants.ts, types.ts, index.tsx, NOTICE.md (MIT origin + diffs)

apps/shell/src/components/dynamic-island/      ← Marvex, built on top
  geometry.generated.ts    (emitted by Python; DO NOT hand-edit)
  DynamicIsland.tsx         (VENDORED morph shell from UI_EXTERNAL_Helpers, stripped of
                             demo views + toolbar; idle ⇄ expanded via framer-motion layout)
  IslandWaveform.tsx        (wraps existing MarvexWaveform; compact vs expanded dims)
  cards/ApprovalCard.tsx    (Approve / Deny, wired to control plane)
  cards/InfoCard.tsx        (welcome / transient info)

apps/shell/src/surfaces/overlay.tsx            ← rewritten surface

apps/shell/scripts/geometry/                   ← Python dev-time helpers (for the agent)
  pill_geometry.py, waveform_layout.py, emit_constants.py, tests/
```

**Deleted:** old `surfaces/overlay.tsx`, `components/dynamic-island/index.tsx`,
`lib/islandQueue.ts`, `lib/overlayHover.ts`, and their `.test` files. The vendored
`ToastProvider` queue replaces `islandQueue`; "no click-through" removes the need for
`overlayHover`.

### 2.2 Responsibilities (isolation boundaries)

- **pretty-toast/** — generic card/pill rendering + FIFO queue with `maxQueue` / `force` /
  auto-dismiss / swipe-up. Knows nothing about Marvex state. Input: `ToastConfig`. Output:
  rendered pill via portal.
- **dynamic-island/DynamicIsland.tsx** — the Marvex visual: idle compact pill vs expanded,
  hosts the waveform and (when present) a card. Pure presentational; props in, no IPC.
- **dynamic-island/geometry.generated.ts** — all hard-coded dimensions, radii, anchor
  margins, DPI scaling, waveform band layout. The single source of geometric truth, emitted
  by Python.
- **surfaces/overlay.tsx** — the only place with side effects: subscribes to
  `assistant-state`, maps state → view, fetches/decides approvals, sizes/anchors the native
  window, opens chat. Composes the above.
- **scripts/geometry/** — dev-time only. Computes geometry math and emits the generated TS
  (and a Rust constants snippet). Not shipped, not a runtime dependency.

## 3. Geometry & "native, no background" (top-center notch)

- The overlay Tauri window stays `transparent: true, alwaysOnTop: true, decorations: false,
  skipTaskbar: true`.
- On Windows the window is clipped by a **rounded region** (`SetWindowRgn`) to the **exact
  pill shape** using the generated corner radius, so there is **no transparent halo** — it
  reads as a free-floating object, not a box.
- **No click-through** (`set_ignore_cursor_events` is never enabled). The window stays
  interactive; the region clip is what lets desktop clicks outside the pill pass through.
  The Rust `set_overlay_click_through` command and all hover-edge logic are removed.
- **Anchor: top-center.** `set_overlay_size` is updated to center the window horizontally on
  the current monitor (`monitor.x + (monitor.width - win.width)/2`) at the generated top
  margin, replacing the current top-right math. Still clamped to the monitor and
  scale-factor aware, so it is correct on any resolution/DPI.

### Python helpers (run by the agent at dev time)

- `pill_geometry.py` — emits: idle size, expanded size, corner radius, padding, shadow
  insets, top-center top-margin, and DPI scaling table. Also emits the exact region rect.
- `waveform_layout.py` — emits: band count, spacing, and canvas dimensions for compact pill
  vs expanded width.
- `emit_constants.py` — writes `dynamic-island/geometry.generated.ts` and a Rust constants
  block consumed by `lib.rs`.
- `tests/` — pytest asserting the emitted constants (snapshot) and the scaling math.

## 4. States & waveform

- Source: `assistant-state` SSE (already wired end-to-end via `state_stream.rs` →
  `assistant-state` event → `normalizeAssistantState`). No change to that pipeline.
- View mapping:
  - `idle` → compact pill, slow dot pulse, flat/low waveform.
  - `listening` / `talking` → expanded; waveform follows real `audio_level`.
  - `thinking` / `working` / `using_tools` / `mcp` / `skills` / `searching_web` → expanded;
    animated waveform baseline + status label.
  - `needs_approval` → expanded; **ApprovalCard** takes over the pill body.
  - `asking` → (deferred) for now renders the same animated state + label; no question card.
- Waveform: reuse `components/waveform-shader/MarvexWaveform.tsx`, sized from
  `geometry.generated.ts` (compact vs expanded). Phase animation via the existing rAF driver.

## 5. Voice

No new audio code in the overlay. The `voice_worker_runtime` Python process already performs
wake-word detection, STT, TTS, and barge-in on the system microphone, independent of which
window is focused. "Voice works in overlay like chat" is therefore satisfied by the overlay
**visualizing** the same `assistant-state` (status + `audio_level`) stream the chat uses.
The shell never calls `getUserMedia`. Voice worker control (start/stop/model switching) stays
in the existing `VoiceMode` admin surface and is not duplicated in the overlay.

## 6. Approvals

- On transition into `needs_approval`, fetch `/control/approvals` (via `controlRequest`,
  existing path), take the first pending approval, and render an **ApprovalCard** inside the
  expanded pill.
- Buttons: **Approve / Deny** (Cancel omitted for the lean pass; can return later). Decision
  submitted via `decideApproval(id, decision, reason)` then `resumeApprovalTurn(...)` —
  exactly the existing control-plane contract (`runtime.py` routes
  `POST /control/approvals/{id}/{approve|deny}` are already implemented).
- The card is persistent (`autoDismiss: false`) until decided. If `trace_id`/`turn_id` are
  absent the resume step is skipped but the decision is still POSTed (so the buttons are
  never permanently dead — fixes a bug from the prior review).
- **No `approval-voice-decision` listener** (deferred).

## 7. Interaction

- Click the pill → expand in place. A small chevron affordance opens the full chat window
  (`showChat()` / `persistMode("chat")`). The chat window remains a separate surface.
- Swipe-up to dismiss transient info/approval cards comes from the vendored `WebToastView`
  (pointer drag), retained.

## 8. Out of scope (this pass)

- Questions/clarify rendering in the island (needs a pending-clarification backend endpoint).
- `approval-voice-decision` event channel.
- Backend-pushed `island-card` events.
- Any chat-window changes.

## 9. Testing

- **Vitest:**
  - vendored `WebToastView` smoke (renders title/message, swipe-dismiss threshold).
  - `DynamicIsland` view mapping (state → compact/expanded, card slot).
  - `ApprovalCard` decide flow with mocked `controlRequest` (approve → decide + resume;
    missing ids → decide only, buttons enabled).
  - overlay sizing/anchor: top-center math from `geometry.generated.ts`.
  - replace the currently-failing `dynamic-island/index.test.tsx`.
- **Python:** pytest for `scripts/geometry` (constant snapshot + scaling math).
- **Rust:** keep `state_stream` tests; update overlay-sizing test for top-center anchor and
  exact region; remove click-through test.
- **Manual:** verify in the running app (screenshot the pill idle + expanded + approval)
  after implementation.

## 10. Risks

- **DPI / multi-monitor correctness** is the highest-risk area; mitigated by the Python
  helper + scale-factor-aware Rust sizing and a clamp to the monitor.
- **Region clip on non-Windows** has no implementation; this app ships Windows-only (NSIS),
  so the `#[cfg(not(windows))]` no-op path is acceptable (documented).
- Vendoring a third-party file requires preserving its **MIT license** (NOTICE.md).
