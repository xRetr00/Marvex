# Phase 1 — Shell UX, Performance, Presence & Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Marvex shell responsive (no main-thread blocking), turn the dynamic island into a live top-right presence that spawns cards, persist chat/sessions, and surface real failure states instead of "No displayable response returned."

**Architecture:** Replace the raw blocking `TcpStream` HTTP connector with async `reqwest` and make all I/O Tauri commands `async` so the UI/main thread never blocks. Make the overlay island the single presence surface (top-right, alive at idle, hover waveform) and convert Spotlight from a manually-summoned window into event-driven cards spawned from the island. Add a durable local session store with a real `session_ref`, and map turn outcomes to explicit, actionable chat + island states.

**Tech Stack:** Rust (Tauri 2.10, tokio via `tauri::async_runtime`, `reqwest`), TypeScript/React 19, Vitest, framer-motion, WebGL.

---

## File Structure

- `apps/shell/src-tauri/Cargo.toml` — add `reqwest` (rustls, json) dependency.
- `apps/shell/src-tauri/src/http.rs` — rewrite as async loopback HTTP client (`async fn http_get/http_post_json`).
- `apps/shell/src-tauri/src/lib.rs` — make I/O commands `async`; drop hardcoded `fake-model`; remove Spotlight tray item + global shortcut.
- `apps/shell/src-tauri/src/state_stream.rs` — unchanged (own thread already).
- `apps/shell/src-tauri/tauri.conf.json` — overlay anchored top-right; spotlight shrunk to content-sized top-right card.
- `apps/shell/src/lib/turnOutcome.ts` — NEW: map a raw turn result / thrown error into a discriminated `TurnOutcome`.
- `apps/shell/src/lib/turnOutcome.test.ts` — NEW: unit tests for outcome mapping.
- `apps/shell/src/lib/localTurn.ts` — keep parsing helpers; `finalTextFromTurnResult` reused by `turnOutcome`.
- `apps/shell/src/lib/sessionStore.ts` — NEW: durable local session id + message history.
- `apps/shell/src/lib/sessionStore.test.ts` — NEW: unit tests.
- `apps/shell/src/lib/overlayHover.ts` — NEW: pure edge-trigger helper for click-through.
- `apps/shell/src/lib/overlayHover.test.ts` — NEW: unit tests.
- `apps/shell/src/surfaces/overlay.tsx` — edge-triggered click-through; live idle island; waveform `active`.
- `apps/shell/src/components/waveform-shader/MarvexWaveform.tsx` — `active` prop + RAF pause/visibility.
- `apps/shell/src/surfaces/ChatApp.tsx` — remove Spotlight dock button; consume `TurnOutcome`; use session store; Sessions surface.
- `apps/shell/src/styles.css` — `.spotlight-shell`/`.spotlight-panel` content-sized, no scrollbars.

---

## Task 1: Add async HTTP client dependency

**Files:**
- Modify: `apps/shell/src-tauri/Cargo.toml`

- [ ] **Step 1: Add reqwest dependency**

In `apps/shell/src-tauri/Cargo.toml`, under `[dependencies]`, add:

```toml
reqwest = { version = "0.12", default-features = false, features = ["rustls-tls", "json"] }
```

- [ ] **Step 2: Verify it resolves and builds**

Run: `cd apps/shell/src-tauri && cargo build`
Expected: builds successfully (reqwest + rustls compiled).

- [ ] **Step 3: Commit**

```bash
git add apps/shell/src-tauri/Cargo.toml apps/shell/src-tauri/Cargo.lock
git commit -m "build(shell): add reqwest async http client"
```

---

## Task 2: Rewrite the HTTP connector as async (non-blocking)

**Files:**
- Modify: `apps/shell/src-tauri/src/http.rs`

- [ ] **Step 1: Replace the blocking TcpStream client with async reqwest**

Replace the entire body of `apps/shell/src-tauri/src/http.rs` with:

```rust
use std::time::Duration;

use serde_json::Value;

#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: String,
}

fn loopback_ok(host: &str) -> bool {
    matches!(host, "127.0.0.1" | "localhost" | "::1")
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(2))
        .timeout(Duration::from_secs(15))
        .build()
        .map_err(|err| format!("http client init failed: {err}"))
}

pub async fn http_get(host: &str, port: u16, path: &str, token: Option<&str>) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client()?.get(url).header("Accept", "application/json");
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await.map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let body = resp.text().await.map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body })
}

pub async fn http_post_json(host: &str, port: u16, path: &str, token: Option<&str>, body: &Value) -> Result<HttpResponse, String> {
    if !loopback_ok(host) {
        return Err("loopback host required".to_string());
    }
    let url = format!("http://{host}:{port}{path}");
    let mut req = client()?.post(url).header("Accept", "application/json").json(body);
    if let Some(token) = token {
        req = req.bearer_auth(token);
    }
    let resp = req.send().await.map_err(|err| format!("request failed: {err}"))?;
    let status = resp.status().as_u16();
    let text = resp.text().await.map_err(|err| format!("read failed: {err}"))?;
    Ok(HttpResponse { status, body: text })
}

#[cfg(test)]
mod tests {
    use super::loopback_ok;

    #[test]
    fn only_loopback_hosts_allowed() {
        assert!(loopback_ok("127.0.0.1"));
        assert!(loopback_ok("localhost"));
        assert!(!loopback_ok("example.com"));
    }
}
```

- [ ] **Step 2: Run the http unit test**

Run: `cd apps/shell/src-tauri && cargo test --lib http`
Expected: `only_loopback_hosts_allowed` passes. (Compilation will fail in `lib.rs` until Task 3; if so, proceed to Task 3 then re-run.)

- [ ] **Step 3: Commit (after Task 3 compiles)**

Defer commit to Task 3 Step 4 since `lib.rs` callers must become async in the same compile unit.

---

## Task 3: Make I/O commands async; drop hardcoded fake-model

**Files:**
- Modify: `apps/shell/src-tauri/src/lib.rs`

- [ ] **Step 1: Make the network commands async and await the client**

In `apps/shell/src-tauri/src/lib.rs`, change these command functions. For each, add `async` and `.await` on the http calls. Because async commands cannot hold a `MutexGuard` across `.await`, clone the token in a tight non-async scope first.

Replace `backend_health`:

```rust
#[tauri::command]
async fn backend_health(state: tauri::State<'_, Mutex<ShellState>>) -> Result<Value, String> {
    let token = { state.lock().map_err(|_| "shell state unavailable".to_string())?.token.clone() };
    match http::http_get("127.0.0.1", 8765, "/health", Some(&token)).await {
        Ok(response) => {
            let body: Value = serde_json::from_str(&response.body).unwrap_or_else(|_| json!({"raw": false}));
            Ok(json!({"reachable": response.status == 200, "status_code": response.status, "health": body}))
        }
        Err(err) => Ok(json!({"reachable": false, "error": err})),
    }
}
```

Replace `submit_chat_turn` (note: `model` is now `null` so Core uses its configured default instead of the fake provider, and `execution_mode` is dropped to let Core decide):

```rust
#[tauri::command]
async fn submit_chat_turn(text: String, metadata: Option<Value>, state: tauri::State<'_, Mutex<ShellState>>) -> Result<Value, String> {
    let text = text.trim().to_string();
    if text.is_empty() {
        return Err("chat text must be non-empty".to_string());
    }
    let (token, session_id) = {
        let guard = state.lock().map_err(|_| "shell state unavailable".to_string())?;
        (guard.token.clone(), session_id_from_metadata(&metadata))
    };
    let now = monotonic_id();
    let trace_id = format!("trace-shell-chat-{now}");
    let turn_id = format!("turn-shell-chat-{now}");
    let body = json!({
        "schema_version": "0.1.1-draft",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": format!("event-shell-chat-{now}"),
            "session_ref": {"ref_type": "session", "ref_id": session_id},
            "identity_ref": null,
            "user_visible_input": text,
            "assistant_mode": "default",
            "policy_context": {"requested_capabilities": [], "sensitivity": "normal"},
            "metadata": safe_shell_turn_metadata(metadata)
        },
        "model": null,
        "instructions": null,
        "previous_response_id": null,
        "provider_options": {}
    });
    let response = http::http_post_json("127.0.0.1", 8765, "/v1/turns", Some(&token), &body).await?;
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Core response: {err}"))
}

fn session_id_from_metadata(metadata: &Option<Value>) -> String {
    if let Some(Value::Object(map)) = metadata {
        if let Some(Value::String(id)) = map.get("session_id") {
            let trimmed = id.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }
    "shell-session".to_string()
}
```

Replace `control_request`:

```rust
#[tauri::command]
async fn control_request(path: String, method: String, body: Option<Value>, state: tauri::State<'_, Mutex<ShellState>>) -> Result<Value, String> {
    if !path.starts_with('/') || path.contains("://") {
        return Err("control path must be local".to_string());
    }
    let token = { state.lock().map_err(|_| "shell state unavailable".to_string())?.token.clone() };
    let full_path = format!("/control{path}");
    let response = if method.eq_ignore_ascii_case("POST") {
        http::http_post_json("127.0.0.1", 8766, &full_path, Some(&token), &body.unwrap_or_else(|| json!({}))).await?
    } else {
        http::http_get("127.0.0.1", 8766, &full_path, Some(&token)).await?
    };
    serde_json::from_str(&response.body).map_err(|err| format!("invalid Control Plane response: {err}"))
}
```

Note: `get_setup_status`, `start_setup`, `start_backend`, `gui_health`, `supervisor_status` do not call the network and can stay sync. The `on_menu_event` handler calls `control_request` for pause/resume voice — wrap those in `tauri::async_runtime::spawn`:

```rust
"pause_voice" => {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let _ = control_request("/voice/worker/pause".into(), "POST".into(), Some(json!({})), app.state::<Mutex<ShellState>>()).await;
    });
}
"resume_voice" => {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let _ = control_request("/voice/worker/resume".into(), "POST".into(), Some(json!({})), app.state::<Mutex<ShellState>>()).await;
    });
}
```

- [ ] **Step 2: Build the Rust crate**

Run: `cd apps/shell/src-tauri && cargo build`
Expected: compiles. Fix any `State<'_, ...>` lifetime errors by ensuring async commands use `tauri::State<'_, Mutex<ShellState>>`.

- [ ] **Step 3: Run Rust tests**

Run: `cd apps/shell/src-tauri && cargo test --lib`
Expected: PASS (http loopback test + existing supervisor/state_stream tests).

- [ ] **Step 4: Commit**

```bash
git add apps/shell/src-tauri/src/http.rs apps/shell/src-tauri/src/lib.rs
git commit -m "fix(shell): async non-blocking backend bridge to unfreeze the UI"
```

---

## Task 4: Edge-triggered overlay click-through helper

**Files:**
- Create: `apps/shell/src/lib/overlayHover.ts`
- Test: `apps/shell/src/lib/overlayHover.test.ts`

- [ ] **Step 1: Write the failing test**

Create `apps/shell/src/lib/overlayHover.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { makeHoverEdgeTrigger } from "./overlayHover";

describe("makeHoverEdgeTrigger", () => {
  it("only fires when the over state changes", () => {
    const onChange = vi.fn();
    const trigger = makeHoverEdgeTrigger(onChange);
    trigger(false); // initial known state may emit once
    onChange.mockClear();
    trigger(false);
    trigger(false);
    expect(onChange).not.toHaveBeenCalled();
    trigger(true);
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(true);
    trigger(true);
    expect(onChange).toHaveBeenCalledTimes(1);
    trigger(false);
    expect(onChange).toHaveBeenCalledTimes(2);
    expect(onChange).toHaveBeenLastCalledWith(false);
  });
});
```

- [ ] **Step 2: Run it to confirm failure**

Run: `cd apps/shell && npx vitest run src/lib/overlayHover.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement the helper**

Create `apps/shell/src/lib/overlayHover.ts`:

```ts
/**
 * Edge-triggered hover tracker. Calls `onChange` only when the over/not-over
 * state actually transitions, so a high-frequency mousemove stream produces at
 * most one call per enter/leave instead of one IPC call per pixel of motion.
 */
export function makeHoverEdgeTrigger(onChange: (over: boolean) => void) {
  let last: boolean | undefined;
  return (over: boolean) => {
    if (over === last) return;
    last = over;
    onChange(over);
  };
}
```

- [ ] **Step 4: Run the test to confirm pass**

Run: `cd apps/shell && npx vitest run src/lib/overlayHover.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/shell/src/lib/overlayHover.ts apps/shell/src/lib/overlayHover.test.ts
git commit -m "feat(shell): edge-triggered overlay hover helper"
```

---

## Task 5: Throttle the WebGL waveform (active prop + visibility)

**Files:**
- Modify: `apps/shell/src/components/waveform-shader/MarvexWaveform.tsx`

- [ ] **Step 1: Add `active` prop and pause the RAF loop at rest**

In `MarvexWaveform.tsx`, extend the props interface and gate the loop. Change the interface to add:

```ts
interface MarvexWaveformProps {
  audioLevel: number;
  className?: string;
  width?: number;
  height?: number;
  /** When false, render a single frame then stop the RAF loop to idle the GPU. */
  active?: boolean;
}
```

Change the component signature to `export function MarvexWaveform({ audioLevel, className, width = 320, height = 80, active = true }: MarvexWaveformProps)`.

Inside the render `useEffect`, replace the `draw` loop tail and add a visibility guard. Replace the `const draw = () => { ... rafRef.current = requestAnimationFrame(draw); };` block with:

```ts
    let running = true;
    const renderFrame = () => {
      const elapsed = (performance.now() - startTimeRef.current) / 1000;
      smoothRef.current += (targetRef.current - smoothRef.current) * 0.09;
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.uniform1f(timeLoc, elapsed);
      gl.uniform2f(resLoc, canvas.width, canvas.height);
      gl.uniform1f(audioLoc, smoothRef.current);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    };
    const loop = () => {
      if (!running) return;
      renderFrame();
      if (active && !document.hidden) {
        rafRef.current = requestAnimationFrame(loop);
      }
    };
    loop();
    const onVisibility = () => {
      if (active && !document.hidden) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = requestAnimationFrame(loop);
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
```

And update the cleanup return to:

```ts
    return () => {
      running = false;
      cancelAnimationFrame(rafRef.current);
      document.removeEventListener("visibilitychange", onVisibility);
      gl.deleteProgram(program);
    };
```

Add `active` to the effect dependency array: change `}, []);` (the render effect) to `}, [active]);`.

- [ ] **Step 2: Build the frontend to typecheck**

Run: `cd apps/shell && npx tsc -b`
Expected: no type errors.

- [ ] **Step 3: Commit**

```bash
git add apps/shell/src/components/waveform-shader/MarvexWaveform.tsx
git commit -m "perf(shell): idle the waveform GPU loop when inactive or hidden"
```

---

## Task 6: Move the island top-right; live idle presence; edge-trigger + active waveform

**Files:**
- Modify: `apps/shell/src-tauri/tauri.conf.json`
- Modify: `apps/shell/src/surfaces/overlay.tsx`

- [ ] **Step 1: Anchor the overlay window top-right**

In `apps/shell/src-tauri/tauri.conf.json`, in the `overlay` window object, remove `"x": 16, "y": 16` and add a width and right-leaning position. Replace the overlay window block's geometry so it reads:

```json
      {
        "label": "overlay",
        "title": "Marvex Status",
        "url": "/overlay",
        "width": 360,
        "height": 120,
        "decorations": false,
        "transparent": true,
        "alwaysOnTop": true,
        "skipTaskbar": true,
        "resizable": false,
        "visible": true
      }
```

(The window is positioned to the right at runtime by overlay.tsx via the existing positioner; see Step 2 — we right-align content within the window and rely on a right anchor command. If no positioner is wired, add `"center": false` and a Rust right-anchor as in `position_spotlight_top_right`. For Phase 1 we right-align via CSS inside a right-edge window.)

To guarantee the window itself sits at the right edge, set the position from Rust at setup. In `apps/shell/src-tauri/src/lib.rs` `setup`, after getting the overlay window (the existing `if let Some(window) = app.get_webview_window("overlay")` block), add before `set_ignore_cursor_events`:

```rust
                if let (Ok(Some(monitor)), Ok(size)) = (window.current_monitor(), window.outer_size()) {
                    let m = monitor.size();
                    let x = (m.width as i32) - (size.width as i32) - 16;
                    let _ = window.set_position(tauri::PhysicalPosition::new(x.max(0), 16));
                }
```

- [ ] **Step 2: Rework overlay.tsx for edge-trigger + live idle + active waveform**

Replace the body of `OverlaySurface` in `apps/shell/src/surfaces/overlay.tsx`. Import the edge-trigger helper at the top:

```ts
import { makeHoverEdgeTrigger } from "../lib/overlayHover";
```

Replace the click-through `useEffect` with an edge-triggered, rAF-throttled version:

```tsx
  useEffect(() => {
    const trigger = makeHoverEdgeTrigger((over) => void setOverlayClickThrough(!over));
    let frame = 0;
    const onMove = (event: MouseEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const rect = islandRef.current?.getBoundingClientRect();
        const over = Boolean(
          rect &&
            event.clientX >= rect.left && event.clientX <= rect.right &&
            event.clientY >= rect.top && event.clientY <= rect.bottom,
        );
        setHovered(over);
        trigger(over);
      });
    };
    window.addEventListener("mousemove", onMove);
    void setOverlayClickThrough(true);
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
```

Change the idle island content so it shows live state (status label) instead of a bare dot, and pass `active` to the waveform. Replace the `idleContent` prop value with:

```tsx
          idleContent={
            <div style={{ padding: "7px 12px", display: "flex", alignItems: "center", gap: 8 }}>
              <MarvexWaveform audioLevel={0.12} width={40} height={18} active={false} />
              <TextShimmer text={isActive ? statusText : "Marvex"} />
            </div>
          }
```

And in `ringContent`, pass `active`:

```tsx
              <MarvexWaveform audioLevel={isActive ? audioLevel : 0.18} width={isActive ? 120 : 64} height={22} active={isActive || hovered} />
```

- [ ] **Step 3: Build + run existing overlay tests**

Run: `cd apps/shell && npx tsc -b && npx vitest run src/surfaces/overlay.test.tsx`
Expected: typechecks; tests pass (update assertions in `overlay.test.tsx` if they asserted the old dot-only idle content — make them assert the island renders and the waveform canvas is present).

- [ ] **Step 4: Commit**

```bash
git add apps/shell/src-tauri/tauri.conf.json apps/shell/src-tauri/src/lib.rs apps/shell/src/surfaces/overlay.tsx apps/shell/src/surfaces/overlay.test.tsx
git commit -m "feat(shell): island moves top-right, alive at idle, edge-triggered hover"
```

---

## Task 7: Spotlight as content-sized card; remove window/mode entry points

**Files:**
- Modify: `apps/shell/src-tauri/tauri.conf.json`
- Modify: `apps/shell/src-tauri/src/lib.rs`
- Modify: `apps/shell/src/styles.css`
- Modify: `apps/shell/src/surfaces/ChatApp.tsx`

- [ ] **Step 1: Shrink the spotlight window to a content card**

In `apps/shell/src-tauri/tauri.conf.json`, change the `spotlight` window: remove `"center": true`, set a smaller size, keep transparent. Replace its geometry fields:

```json
      {
        "label": "spotlight",
        "title": "Marvex Spotlight",
        "url": "/spotlight",
        "width": 420,
        "height": 240,
        "decorations": false,
        "transparent": true,
        "alwaysOnTop": true,
        "skipTaskbar": true,
        "resizable": false,
        "visible": false
      }
```

- [ ] **Step 2: Anchor spotlight under the island (top-right) and remove the shortcut + tray item**

In `apps/shell/src-tauri/src/lib.rs`:
- `position_spotlight_top_right` already anchors top-right; keep it (it is called by `show_spotlight`).
- Remove the global shortcut: delete the `.plugin(tauri_plugin_global_shortcut::Builder::new()...)` block from the builder chain, delete `app.global_shortcut().register(...)` in `setup`, and remove the now-unused `use tauri_plugin_global_shortcut::...` import. (Leave `tauri-plugin-global-shortcut` in Cargo.toml; harmless.)
- In `build_tray`, remove the Spotlight menu line. The menu becomes:

```rust
    let menu = MenuBuilder::new(app)
        .text("open_chat", "Open Marvex")
        .separator()
        .text("pause_voice", "Pause voice")
        .text("resume_voice", "Resume voice")
        .separator()
        .text("quit", "Quit")
        .build()?;
```

- In `on_menu_event`, remove the `"open_spotlight"` arm.

- [ ] **Step 3: Make the spotlight panel content-sized with no scrollbars**

In `apps/shell/src/styles.css`, find `.spotlight-shell` and `.spotlight-panel` and ensure no overflow/scroll and content sizing. Set:

```css
html, body, #root { background: transparent; }
.spotlight-shell {
  width: 100vw;
  height: 100vh;
  display: flex;
  justify-content: flex-end;
  align-items: flex-start;
  padding: 8px;
  overflow: hidden;
  background: transparent;
}
.spotlight-panel {
  max-width: 100%;
  max-height: 100%;
  overflow: hidden;
  border-radius: 16px;
}
```

(If `.spotlight-shell`/`.spotlight-panel` already exist, update their `overflow`/sizing rather than duplicating.)

- [ ] **Step 4: Remove the Spotlight button from the dock**

In `apps/shell/src/surfaces/ChatApp.tsx`, in the footer, delete the `<button onClick={() => void showSpotlight()} ...>` block (the one with `<Sparkles />` and title "Spotlight (Ctrl+Shift+Space)") and the adjacent `<div style={{ width: 1, height: 28, ... }} />` separator if it only separated that button. Remove the now-unused `showSpotlight` and `Sparkles` imports if no longer referenced.

- [ ] **Step 5: Build + typecheck + Rust build**

Run: `cd apps/shell && npx tsc -b` and `cd apps/shell/src-tauri && cargo build`
Expected: both succeed.

- [ ] **Step 6: Commit**

```bash
git add apps/shell/src-tauri/tauri.conf.json apps/shell/src-tauri/src/lib.rs apps/shell/src/styles.css apps/shell/src/surfaces/ChatApp.tsx
git commit -m "feat(shell): spotlight becomes a content-sized card; remove window/mode entry points"
```

---

## Task 8: Turn-outcome mapping (failure states)

**Files:**
- Create: `apps/shell/src/lib/turnOutcome.ts`
- Test: `apps/shell/src/lib/turnOutcome.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `apps/shell/src/lib/turnOutcome.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { outcomeFromTurnResult, outcomeFromError } from "./turnOutcome";

describe("outcomeFromError", () => {
  it("classifies a backend-unreachable error", () => {
    const o = outcomeFromError(new Error("request failed: connection refused"));
    expect(o.kind).toBe("backend_offline");
    expect(o.text.length).toBeGreaterThan(0);
  });
  it("classifies a generic error as error", () => {
    const o = outcomeFromError(new Error("invalid Core response: boom"));
    expect(o.kind).toBe("error");
  });
});

describe("outcomeFromTurnResult", () => {
  it("returns ok with the final text", () => {
    const o = outcomeFromTurnResult({ assistant_final_response: { text: "Hello there" } });
    expect(o.kind).toBe("ok");
    expect(o.text).toBe("Hello there");
  });
  it("maps a no-provider error", () => {
    const o = outcomeFromTurnResult({ error: { message: "no provider configured" } });
    expect(o.kind).toBe("no_provider");
  });
  it("maps a provider error", () => {
    const o = outcomeFromTurnResult({ error: { message: "provider upstream 500" } });
    expect(o.kind).toBe("provider_error");
  });
  it("maps an empty result distinctly", () => {
    const o = outcomeFromTurnResult({ assistant_final_response: { text: "" } });
    expect(o.kind).toBe("empty");
  });
});
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd apps/shell && npx vitest run src/lib/turnOutcome.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement turnOutcome**

Create `apps/shell/src/lib/turnOutcome.ts`:

```ts
import { stagesFromTurnResult, uiDirectivesFromTurnResult, type TurnStage, type UiDirective } from "./localTurn";

export type TurnOutcomeKind =
  | "ok"
  | "empty"
  | "no_provider"
  | "provider_error"
  | "backend_offline"
  | "error";

export interface TurnOutcome {
  kind: TurnOutcomeKind;
  text: string;
  stages?: TurnStage[];
  directives?: UiDirective[];
}

function lower(value: unknown): string {
  return typeof value === "string" ? value.toLowerCase() : "";
}

export function outcomeFromError(error: unknown): TurnOutcome {
  const message = error instanceof Error ? error.message : String(error);
  const m = message.toLowerCase();
  if (
    m.includes("connection refused") ||
    m.includes("connect") ||
    m.includes("request failed") ||
    m.includes("tauri bridge unavailable") ||
    m.includes("error sending request")
  ) {
    return { kind: "backend_offline", text: "Backend isn't running yet. Starting it — try again in a moment." };
  }
  return { kind: "error", text: message || "Request failed." };
}

export function outcomeFromTurnResult(payload: unknown): TurnOutcome {
  if (!payload || typeof payload !== "object") {
    return { kind: "error", text: "No response payload returned." };
  }
  const result = payload as {
    assistant_final_response?: { text?: unknown };
    error?: { message?: unknown };
  };
  const text = result.assistant_final_response?.text;
  if (typeof text === "string" && text.trim()) {
    return {
      kind: "ok",
      text,
      stages: stagesFromTurnResult(payload),
      directives: uiDirectivesFromTurnResult(payload),
    };
  }
  const errMsg = result.error?.message;
  if (typeof errMsg === "string" && errMsg.trim()) {
    const e = lower(errMsg);
    if (e.includes("no provider") || e.includes("not configured") || e.includes("no model")) {
      return { kind: "no_provider", text: "No model or provider is configured. Open Control Plane → Providers to set one up." };
    }
    if (e.includes("provider") || e.includes("upstream") || e.includes("llm")) {
      return { kind: "provider_error", text: `Provider error: ${errMsg}` };
    }
    return { kind: "error", text: errMsg };
  }
  // Turn completed but produced no text.
  if (result.assistant_final_response && (text === "" || text === undefined)) {
    return { kind: "empty", text: "The assistant returned no response text." };
  }
  return { kind: "error", text: "No displayable response returned." };
}
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd apps/shell && npx vitest run src/lib/turnOutcome.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/shell/src/lib/turnOutcome.ts apps/shell/src/lib/turnOutcome.test.ts
git commit -m "feat(shell): explicit turn-outcome mapping for failure states"
```

---

## Task 9: Durable session store

**Files:**
- Create: `apps/shell/src/lib/sessionStore.ts`
- Test: `apps/shell/src/lib/sessionStore.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `apps/shell/src/lib/sessionStore.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { getActiveSessionId, newSession, loadMessages, saveMessages, listSessions } from "./sessionStore";

beforeEach(() => localStorage.clear());

describe("sessionStore", () => {
  it("creates and persists a stable active session id", () => {
    const id = getActiveSessionId();
    expect(id).toMatch(/^session-/);
    expect(getActiveSessionId()).toBe(id); // stable across calls
  });

  it("round-trips messages for a session", () => {
    const id = getActiveSessionId();
    saveMessages(id, [{ role: "user", text: "hi" }]);
    expect(loadMessages(id)).toEqual([{ role: "user", text: "hi" }]);
  });

  it("newSession switches the active id and lists prior sessions", () => {
    const first = getActiveSessionId();
    saveMessages(first, [{ role: "user", text: "one" }]);
    const second = newSession();
    expect(second).not.toBe(first);
    expect(getActiveSessionId()).toBe(second);
    const ids = listSessions().map((s) => s.id);
    expect(ids).toContain(first);
  });
});
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd apps/shell && npx vitest run src/lib/sessionStore.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement sessionStore**

Create `apps/shell/src/lib/sessionStore.ts`:

```ts
export interface StoredMessage {
  role: "user" | "assistant" | "system";
  text: string;
  stages?: unknown;
  directives?: unknown;
}

export interface SessionMeta {
  id: string;
  createdAt: number;
  updatedAt: number;
  title: string;
}

const ACTIVE_KEY = "marvex.session.active";
const INDEX_KEY = "marvex.session.index";
const MSG_PREFIX = "marvex.session.messages.";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable — degrade to in-memory only for this session */
  }
}

function makeId(): string {
  const rand = Math.random().toString(36).slice(2, 10);
  return `session-${Date.now()}-${rand}`;
}

function index(): SessionMeta[] {
  return readJson<SessionMeta[]>(INDEX_KEY, []);
}

function upsertMeta(id: string, patch: Partial<SessionMeta>): void {
  const list = index();
  const now = Date.now();
  const existing = list.find((m) => m.id === id);
  if (existing) {
    Object.assign(existing, patch, { updatedAt: now });
  } else {
    list.push({ id, createdAt: now, updatedAt: now, title: "New chat", ...patch });
  }
  writeJson(INDEX_KEY, list);
}

export function getActiveSessionId(): string {
  let id = localStorage.getItem(ACTIVE_KEY);
  if (!id) {
    id = makeId();
    localStorage.setItem(ACTIVE_KEY, id);
    upsertMeta(id, { title: "New chat" });
  }
  return id;
}

export function newSession(): string {
  const id = makeId();
  localStorage.setItem(ACTIVE_KEY, id);
  upsertMeta(id, { title: "New chat" });
  return id;
}

export function setActiveSession(id: string): void {
  localStorage.setItem(ACTIVE_KEY, id);
}

export function loadMessages(id: string): StoredMessage[] {
  return readJson<StoredMessage[]>(MSG_PREFIX + id, []);
}

export function saveMessages(id: string, messages: StoredMessage[]): void {
  writeJson(MSG_PREFIX + id, messages);
  const firstUser = messages.find((m) => m.role === "user");
  upsertMeta(id, firstUser ? { title: firstUser.text.slice(0, 48) } : {});
}

export function listSessions(): SessionMeta[] {
  return index().sort((a, b) => b.updatedAt - a.updatedAt);
}
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd apps/shell && npx vitest run src/lib/sessionStore.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add apps/shell/src/lib/sessionStore.ts apps/shell/src/lib/sessionStore.test.ts
git commit -m "feat(shell): durable local session store"
```

---

## Task 10: Wire ChatApp to outcomes + session persistence + Sessions surface

**Files:**
- Modify: `apps/shell/src/surfaces/ChatApp.tsx`

- [ ] **Step 1: Use the session store and outcome mapping in `send`**

In `apps/shell/src/surfaces/ChatApp.tsx`:

Add imports:

```ts
import { outcomeFromTurnResult, outcomeFromError } from "@/lib/turnOutcome";
import { getActiveSessionId, loadMessages, saveMessages, newSession, listSessions, type SessionMeta } from "@/lib/sessionStore";
```

Initialize the active session and restore messages. Replace the `messages` initial state and add a session id ref:

```tsx
  const sessionIdRef = useRef<string>(getActiveSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const restored = loadMessages(sessionIdRef.current);
    return restored.length ? (restored as ChatMessage[]) : [{ role: "system", text: "Marvex is ready. How can I help?" }];
  });
```

Persist on every change — add an effect:

```tsx
  useEffect(() => {
    saveMessages(sessionIdRef.current, messages as never);
  }, [messages]);
```

Rewrite `send` to pass `session_id` and map outcomes:

```tsx
  const send = useCallback(async (text: string) => {
    if (!text.trim() || pending) return;
    setPending(true);
    setMessages((prev) => [...prev, { role: "user", text }]);
    try {
      const result = await submitChatTurn(text, {
        agent_profile_id: selectedAgentId,
        persona_profile_id: selectedPersonaId,
        selected_voice_id: selectedVoice,
        session_id: sessionIdRef.current,
      } as never);
      const outcome = outcomeFromTurnResult(result);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text, stages: outcome.stages as never, directives: outcome.directives as never }]);
    } catch (error) {
      const outcome = outcomeFromError(error);
      setMessages((prev) => [...prev, { role: "assistant", text: outcome.text }]);
    } finally {
      setPending(false);
    }
  }, [pending, selectedAgentId, selectedPersonaId, selectedVoice]);
```

(Note: `ChatTurnMetadata` in `shellCommands.ts` should accept `session_id?: string`; add it there. Edit `apps/shell/src/lib/shellCommands.ts` `ChatTurnMetadata` to add `session_id?: string;`.)

- [ ] **Step 2: Add a Sessions tab to the dock**

In the `navItems` memo, the tabs are currently chat/control/deps. After Phase 2 removes control/deps, the Sessions tab is added here. For Phase 1, add a "sessions" tab id to `TabId`, `TAB_TITLES`, `navItems`, and render a simple sessions list in the content area that lists `listSessions()`, lets the user click one to `setActiveSession` + reload messages, and a "New chat" button calling `newSession()`. Concretely:

Extend types: `type TabId = "chat" | "control" | "deps" | "sessions";` and add `sessions: "Sessions"` to `TAB_TITLES`.

Add to `navItems` (before control): `{ id: "sessions", icon: <History />, label: "Sessions", onClick: () => setActiveTab("sessions") },` and import `History` from lucide-react.

Add a render branch in the `<AnimatePresence>` content for `activeTab === "sessions"`:

```tsx
          {activeTab === "sessions" && (
            <motion.div key="sessions" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} style={{ flex: 1, overflow: "auto", padding: 20 }}>
              <div style={{ maxWidth: 640, display: "flex", flexDirection: "column", gap: 10 }}>
                <Button size="sm" variant="outline" onClick={() => { const id = newSession(); sessionIdRef.current = id; setMessages([{ role: "system", text: "New chat started." }]); setActiveTab("chat"); }}>New chat</Button>
                {listSessions().map((s: SessionMeta) => (
                  <button key={s.id} onClick={() => { setActiveSession(s.id); sessionIdRef.current = s.id; setMessages(loadMessages(s.id) as never); setActiveTab("chat"); }}
                    style={{ textAlign: "left", padding: "10px 12px", borderRadius: 10, background: "var(--secondary)", border: "1px solid var(--border)", cursor: "pointer", color: "var(--foreground)" }}>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{s.title}</div>
                    <div style={{ fontSize: 11, color: "var(--muted-foreground)" }}>{new Date(s.updatedAt).toLocaleString()}</div>
                  </button>
                ))}
              </div>
            </motion.div>
          )}
```

Add `setActiveSession` to the import from sessionStore.

- [ ] **Step 3: Typecheck**

Run: `cd apps/shell && npx tsc -b`
Expected: no errors.

- [ ] **Step 4: Run the full shell test suite**

Run: `cd apps/shell && npx vitest run`
Expected: PASS (existing + new tests; update any ChatApp test that asserted the removed Spotlight button or old error string).

- [ ] **Step 5: Commit**

```bash
git add apps/shell/src/surfaces/ChatApp.tsx apps/shell/src/lib/shellCommands.ts
git commit -m "feat(shell): persist chats per session and surface real failure states"
```

---

## Task 11: Phase 1 verification

**Files:** none (verification only)

- [ ] **Step 1: Run all automated checks**

Run: `cd apps/shell && npx vitest run` then `cd apps/shell/src-tauri && cargo test --lib`
Expected: all green.

- [ ] **Step 2: Manual smoke (dev)**

Run: `cd apps/shell && npm run tauri dev`
Verify (per spec Phase 1 acceptance):
- Moving the mouse rapidly over/off the island keeps the UI responsive.
- The tray menu opens instantly while a chat turn is in flight.
- The island sits top-right and shows live state at idle; hover animates the waveform.
- An approval/result event spawns a scrollbar-free card from the island.
- No Spotlight dock button, no Spotlight tray item, Ctrl+Shift+Space does nothing.
- Send messages, close + reopen → conversation restored under the same session; Sessions tab lists prior chats.
- With the backend down, "Hi" shows a backend-offline message (not "No displayable response returned"); with no provider configured, it points to Control Plane → Providers.

- [ ] **Step 3: Final Phase 1 commit (if any fixups)**

```bash
git add -A
git commit -m "test(shell): phase 1 verification fixups"
```

---

## Self-Review Notes
- Spec §1a→Tasks 1–3; §1b→Tasks 4,6; §1c→Tasks 5,6; §1d→Task 6; §1e→Task 7; §1f→Tasks 9,10; §1g→Tasks 8,10 (+ fake-model drop in Task 3). All Phase 1 spec sections covered.
- Type consistency: `TurnOutcome.kind` values reused in ChatApp; `sessionStore` exports (`getActiveSessionId`, `newSession`, `setActiveSession`, `loadMessages`, `saveMessages`, `listSessions`, `SessionMeta`) all used in Task 10.
- Provider/model selection UI is Phase 2; Task 3 sets `model: null` so Core uses its configured default and reports when none — matching the spec's Phase 1/2 boundary note.
