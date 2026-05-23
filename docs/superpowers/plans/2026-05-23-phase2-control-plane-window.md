# Phase 2 — Control Plane Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Open the full original `control_plane_web` (26 views incl. Providers, Voice Runtime with model/voice/STT selection + downloads) in a dedicated Tauri window, authenticated with the shell's local token, and retire the shell's mini Control Plane + Deps tabs.

**Architecture:** Serve the built `control_plane_web` SPA from the existing Control Plane WSGI server (port 8766) at non-`/control` paths, so the SPA's relative `/control` fetch is same-origin. The shell opens a `control` Tauri window pointed at `http://127.0.0.1:8766/` and injects the shell bearer token into `sessionStorage` via an initialization script (matching `control_plane_web`'s existing `authHeaders()` which reads `sessionStorage["marvex_control_plane_token"]`). No `control_plane_web` source changes; no CORS needed.

**Tech Stack:** Python WSGI (wsgiref), Rust (Tauri 2.10 WebviewWindowBuilder + initialization_script), TypeScript/React.

---

## File Structure
- `packages/control_plane_api/static_web.py` — NEW: static SPA file resolver + WSGI response helper.
- `packages/control_plane_api/static_web_test`... → `tests/control_plane_api/test_static_web.py` — NEW test.
- `packages/control_plane_api/app.py` — accept `web_dist`, serve static for non-`/control` GET before auth.
- `services/core/main.py` — resolve web dist (env `MARVEX_CONTROL_WEB_DIST`) and pass to the control app.
- `apps/shell/src-tauri/src/lib.rs` — `open_control_plane` command (external window + token init script).
- `apps/shell/src-tauri/src/supervisor.rs` — set `MARVEX_CONTROL_WEB_DIST` on the core child in dev.
- `apps/shell/src/lib/shellCommands.ts` — `openControlPlane()` wrapper.
- `apps/shell/src/surfaces/ChatApp.tsx` — dock "Control Plane" opens the window; remove mini control + deps tabs.

---

## Task 1: Static SPA serving in the control plane WSGI app

**Files:**
- Create: `packages/control_plane_api/static_web.py`
- Test: `tests/control_plane_api/test_static_web.py`
- Modify: `packages/control_plane_api/app.py`

- [ ] **Step 1: Write the failing test**

Create `tests/control_plane_api/test_static_web.py`:

```python
from pathlib import Path

from packages.control_plane_api.static_web import resolve_static_file


def test_resolves_index_for_root(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html>marvex</html>", encoding="utf-8")
    resolved, content_type = resolve_static_file(tmp_path, "/")
    assert resolved == tmp_path / "index.html"
    assert content_type == "text/html; charset=utf-8"


def test_resolves_asset(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("//", encoding="utf-8")
    resolved, content_type = resolve_static_file(tmp_path, "/assets/app.js")
    assert resolved == assets / "app.js"
    assert content_type == "application/javascript"


def test_spa_fallback_to_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    resolved, _ = resolve_static_file(tmp_path, "/some/spa/route")
    assert resolved == tmp_path / "index.html"


def test_blocks_path_traversal(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("x", encoding="utf-8")
    resolved, _ = resolve_static_file(tmp_path, "/../secret")
    # Traversal must never escape the dist root; falls back to index.
    assert resolved == tmp_path / "index.html"
```

- [ ] **Step 2: Run, expect failure** — `uv run python -m pytest tests/control_plane_api/test_static_web.py -q` → FAIL (no module).

- [ ] **Step 3: Implement `static_web.py`**

```python
from __future__ import annotations

from pathlib import Path

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
    ".txt": "text/plain; charset=utf-8",
}


def content_type_for(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def resolve_static_file(dist_root: Path, request_path: str) -> tuple[Path | None, str]:
    """Resolve a request path to a file inside dist_root.

    Returns (path, content_type). Unknown SPA routes fall back to index.html.
    Path traversal outside dist_root is rejected (falls back to index.html).
    """
    root = dist_root.resolve()
    index = root / "index.html"
    rel = request_path.lstrip("/")
    if not rel:
        return (index if index.is_file() else None, content_type_for(index))
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return (index if index.is_file() else None, content_type_for(index))
    if candidate.is_file():
        return candidate, content_type_for(candidate)
    return (index if index.is_file() else None, content_type_for(index))
```

- [ ] **Step 4: Wire into `app.py`** — add `web_dist: str | None = None` to `create_control_plane_api_app` params. Inside `app(environ, start_response)`, BEFORE the auth gate (before line ~70 `auth_error = ...`), insert:

```python
        if method == "GET" and not path.startswith(CONTROL_PREFIX) and web_dist:
            from pathlib import Path as _Path
            from .static_web import resolve_static_file
            resolved, content_type = resolve_static_file(_Path(web_dist), path)
            if resolved is not None and resolved.is_file():
                data = resolved.read_bytes()
                start_response("200 OK", [("Content-Type", content_type), ("Content-Length", str(len(data)))])
                return [data]
```

- [ ] **Step 5: Run tests** — `uv run python -m pytest tests/control_plane_api/test_static_web.py -q` → PASS (4).

- [ ] **Step 6: Commit** — `git add packages/control_plane_api/static_web.py packages/control_plane_api/app.py tests/control_plane_api/test_static_web.py && git commit -m "feat(control-plane): serve the SPA from the control plane server"`

---

## Task 2: Resolve web dist in Core service

**Files:** Modify `services/core/main.py`

- [ ] **Step 1: Pass web_dist from env**

In `create_control_plane_service_app`, add resolution and pass-through:

```python
def create_control_plane_service_app(*, config, trace_reader=None, state_bus=None):
    import os
    web_dist = os.environ.get("MARVEX_CONTROL_WEB_DIST") or None
    return create_control_plane_api_app(
        approval_store=InMemoryApprovalStore(),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token=config.local_auth_token or "",
        trace_reader=trace_reader,
        state_bus=state_bus or get_default_bus(),
        web_dist=web_dist,
    )
```

- [ ] **Step 2: Build check** — `uv run python -c "import services.core.main"` → no error.
- [ ] **Step 3: Commit** — `git add services/core/main.py && git commit -m "feat(core): point control plane app at the bundled SPA dist via env"`

---

## Task 3: Supervisor sets the dev web dist

**Files:** Modify `apps/shell/src-tauri/src/supervisor.rs`

- [ ] **Step 1: Set MARVEX_CONTROL_WEB_DIST on spawned services in dev**

In `spawn_service`, after the `MARVEX_UV_PATH` env block, add (dev path = repo `apps/control_plane_web/dist`; prod path resolved from resource_dir if a `control_plane_web` dir is bundled):

```rust
    // Point the control plane server at the built control_plane_web SPA so the
    // shell's Control Plane window can load it same-origin.
    let web_dist = resource_dir
        .map(|dir| dir.join("control_plane_web"))
        .filter(|p| p.is_dir())
        .unwrap_or_else(|| project_root().join("apps").join("control_plane_web").join("dist"));
    if web_dist.is_dir() {
        command.env("MARVEX_CONTROL_WEB_DIST", web_dist);
    }
```

- [ ] **Step 2: cargo build** → compiles.
- [ ] **Step 3: Commit** — `git add apps/shell/src-tauri/src/supervisor.rs && git commit -m "feat(shell): expose control_plane_web dist to the core service"`

---

## Task 4: `open_control_plane` shell command

**Files:** Modify `apps/shell/src-tauri/src/lib.rs`, `apps/shell/src/lib/shellCommands.ts`

- [ ] **Step 1: Add the command in lib.rs**

```rust
#[tauri::command]
fn open_control_plane(app: AppHandle, state: tauri::State<Mutex<ShellState>>) -> Result<(), String> {
    let token = state.lock().map_err(|_| "shell state unavailable".to_string())?.token.clone();
    if let Some(window) = app.get_webview_window("control") {
        window.show().map_err(|e| e.to_string())?;
        return window.set_focus().map_err(|e| e.to_string());
    }
    let init = format!("window.sessionStorage.setItem('marvex_control_plane_token', '{}');", token.replace('\\', "\\\\').replace('\'', "\\'"));
    let url = tauri::WebviewUrl::External("http://127.0.0.1:8766/".parse().map_err(|_| "bad url".to_string())?);
    tauri::WebviewWindowBuilder::new(&app, "control", url)
        .title("Marvex Control Plane")
        .inner_size(1280.0, 860.0)
        .initialization_script(&init)
        .build()
        .map_err(|e| e.to_string())?;
    Ok(())
}
```

Register `open_control_plane` in `tauri::generate_handler![...]`.

- [ ] **Step 2: Add the JS wrapper** in `shellCommands.ts`:

```ts
export async function openControlPlane(): Promise<void> {
  await invoke("open_control_plane");
}
```

- [ ] **Step 3: cargo build + tsc** → both compile.
- [ ] **Step 4: Commit** — `git add apps/shell/src-tauri/src/lib.rs apps/shell/src/lib/shellCommands.ts && git commit -m "feat(shell): open the original Control Plane in a dedicated token-authed window"`

---

## Task 5: Dock opens the window; retire mini control + deps tabs

**Files:** Modify `apps/shell/src/surfaces/ChatApp.tsx`

- [ ] **Step 1: Repoint the dock**

Replace the `navItems` so Control Plane opens the window and Deps is removed:

```tsx
  const navItems = useMemo(() => [
    { id: "chat", icon: <MessageSquare />, label: "Chat", onClick: () => setActiveTab("chat") },
    { id: "sessions", icon: <History />, label: "Sessions", onClick: () => setActiveTab("sessions") },
    { id: "control", icon: <SlidersHorizontal />, label: "Control Plane", onClick: () => void openControlPlane() },
  ], []);
```

Add `import { openControlPlane } from "@/lib/shellCommands";` (merge into the existing import). Keep `activeTab` typed as `"chat" | "sessions"` only after removing the in-shell control/deps render branches.

- [ ] **Step 2: Remove the in-shell `control` and `deps` render branches** (the two large `activeTab === "control"` and `activeTab === "deps"` motion.div blocks) and the now-unused state/effects/helpers they used: `deps`, `features`, `depsState`, `depsReload`, `installingDep`, `depProgress`, the deps fetch effect, the control-plane snapshot effect, `handleInstallDep`, `RuntimeSelect`, `VOICES`, voice selector usage, `controlPlane`, `agentCatalog`, `personaCatalog`, `runtimeCatalogState`, etc. Update `TabId` to `"chat" | "sessions"`, `TAB_TITLES` to those two. Remove now-unused imports (Package, SlidersHorizontal can stay only if used; remove deps/control-only imports: depsClient, controlPlaneClient agent/persona fetchers, VoiceSelector*, SystemMonitor, RuntimeStatus, AnimatedProgressBar, RuntimeSelect, etc. if unreferenced).

- [ ] **Step 3: tsc + vitest** — `node_modules/.bin/tsc -b` (clean) and `npx vitest run` (update/remove ChatApp tests asserting the removed tabs).

- [ ] **Step 4: Commit** — `git add apps/shell/src/surfaces/ChatApp.tsx && git commit -m "feat(shell): retire in-shell control/deps tabs in favor of the Control Plane window"`

---

## Task 6: Verification
- [ ] `uv run python -m pytest tests/control_plane_api -q` → pass.
- [ ] `cd apps/shell && npx vitest run` → pass; `node_modules/.bin/tsc -b` → clean; `cargo build` → clean.
- [ ] Manual smoke (`npm run tauri dev`, after `cd apps/control_plane_web && npm run build`): dock "Control Plane" opens a window showing the full original control plane authenticated with live data; Providers + Voice Runtime show selected model/provider/TTS voice/STT model and download actions.

## Self-Review Notes
- Spec §2a→Tasks 1–4 (server static + window + token); §2b→Task 5 (retire tabs).
- control_plane_web is unmodified — same-origin relative fetch + sessionStorage token preserved.
- Prod bundling of control_plane_web/dist into the installer + setting MARVEX_CONTROL_WEB_DIST from the service is handled in Phase 3.
