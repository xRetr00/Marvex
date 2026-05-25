# Marvex Windows Installer — Packaging Documentation

file size justification: This packaging contract intentionally keeps installer, runtime, and sidecar validation details together until the app packaging boundary is split into owned specs.

## Overview

Marvex uses **Tier 1: Production (Setuptools Console Scripts)** for runtime service execution. This document describes the complete packaging architecture, build flow, and runtime behavior.

**Key principle**: Services are NOT frozen (PyInstaller). They use setuptools-generated console scripts for dynamic Python execution with runtime package installation support.

---

## Architecture: Three-Tier Resolution

### Tier 1: Production ✅ (Active)

**When**: Installer deployment with bundled resources

**What happens**:
1. Tauri installer packages `uv.exe` and `marvex-0.1.0-py3-none-any.whl`
2. On first app launch, supervisor detects missing venv
3. Creates `~/.marvex/runtime/venv/` via `uv venv --python 3.11`
4. Installs wheel: `uv pip install marvex-0.1.0-py3-none-any.whl`
5. Setuptools generates console script entry points:
   - `~/.marvex/runtime/venv/Scripts/marvex-core.exe`
   - `~/.marvex/runtime/venv/Scripts/marvex-voice-worker.exe`
   - Provider, intent, and tool worker entry points are still installed, but
     Core owns those persistent JSONL workers internally instead of Tauri
     supervising them as top-level service children.

**Service invocation**:
```
Supervisor → MARVEX_LOCAL_AUTH_TOKEN=<TOKEN> ~/.marvex/runtime/venv/Scripts/marvex-core.exe --serve --host 127.0.0.1 --port 8765 --provider provider_worker --worker-provider fake
```

**Advantages**:
- ✅ Real Python (not frozen bytecode)
- ✅ Supports runtime `uv pip install` (Deps tab works!)
- ✅ Debuggable, profiler-friendly, code reloadable
- ✅ Significantly smaller than PyInstaller (no frozen bytecode)
- ✅ Dynamic module loading

### Tier 3: Development Fallback 🔧

**When**: Source checkout, no bundled resources

**Service invocation**:
```
Supervisor → MARVEX_LOCAL_AUTH_TOKEN=<TOKEN> uv run python -m services.core.main --serve --port 8765
```

Runs services directly from source code. Perfect for active development.

---

## Console Script Entry Points

From `pyproject.toml`:
```toml
[project.scripts]
marvex-core = "services.core.main:main"
marvex-provider-worker = "services.provider_worker.main:main"
marvex-intent-worker = "services.intent_worker.main:main"
marvex-tool-worker = "services.tool_worker.main:main"
marvex-voice-worker = "services.voice_worker.main:main"
```

When setuptools installs the wheel, it generates Windows `.exe` wrappers at:
```
~/.marvex/runtime/venv/Scripts/marvex-*.exe
```

These wrappers are NOT frozen executables—they're entry-point shims that invoke Python and import the module:
```python
#!/path/to/venv/python.exe
import sys
from services.core.main import main
sys.exit(main())
```

---

## Build Process

### Full Build Command

From workspace root (`D:\Marvex`):
```powershell
.\build-installer.ps1
```

### Build Steps

**Step 1: Python Wheel**
```powershell
uv build --wheel
# Output: dist/marvex-0.1.0-py3-none-any.whl
```

**Step 2: Runtime Resources**
- Copy wheel to `apps/shell/runtime/`
- Copy `uv.exe` to `apps/shell/runtime/`

**Step 3: Frontend (React/Vite)**
```powershell
npm --prefix apps/control_plane_web run build
npm --prefix apps/shell run build
# Output: apps/shell/dist/ with index.html, assets/
# Control Plane output remains apps/control_plane_web/dist/ and is bundled as control_plane_web/
```

**Step 4: Tauri Build**
```powershell
npm --prefix apps/shell run tauri build
# Output: apps/shell/src-tauri/target/release/bundle/
#   - Marvex_0.1.0_x64-setup.exe (NSIS)
#   - Marvex_0.1.0_x64_en-US.msi (WiX)
```

### Tauri Configuration

**File**: `apps/shell/src-tauri/tauri.conf.json`

**Bundled resources**:
```json
"resources": {
  "../runtime/uv.exe": "uv.exe",
  "../runtime/marvex-0.1.0-py3-none-any.whl": "marvex-0.1.0-py3-none-any.whl",
  "../../control_plane_web/dist": "control_plane_web",
  "../voice-assets": "voice-assets"
}
```

**Windows installer**:
```json
"windows": {
  "nsis": {
    "installerIcon": "../../assets/icon.ico",
    "installMode": "perMachine",
    "displayLanguageSelector": false
  }
}
```

---

## Runtime Bootstrap (First Launch)

### Sequence

```
User launches app.exe
  ↓
Tauri supervisor starts
  ↓
Check: ~/.marvex/runtime/venv/Scripts/marvex-core.exe exists?
  ├─ YES → Jump to "Services Running"
  └─ NO → Continue
  ↓
Look for bundled resources?
  ├─ NOT FOUND → Dev mode: use `uv run python -m`
  └─ FOUND → Continue
  ↓
Generate bearer token
  ↓
Create venv:
  uv venv ~/.marvex/runtime/venv --python 3.11
  ↓
Install wheel into venv:
  uv pip install marvex-0.1.0-py3-none-any.whl --python ~/.marvex/runtime/venv/Scripts/python.exe
  ↓
Setuptools generates console scripts:
  ~/.marvex/runtime/venv/Scripts/marvex-*.exe
  ↓
Services Running:
  Launch Core via console script with the token in `MARVEX_LOCAL_AUTH_TOKEN`
  ↓
Write manifest to ~/.marvex/runtime/manifest.json
```

### Runtime Manifest

**File**: `~/.marvex/runtime/manifest.json`

```json
{
  "schema_version": "1",
  "marvex_version": "0.1.0",
  "runtime_phase": "ready",
  "runtime_architecture": "tier1_setuptools_console_scripts",
  "created_at_unix_ms": 1234567890000,
  "venv": "C:\\Users\\username\\.marvex\\runtime\\venv",
  "python": "C:\\Users\\username\\.marvex\\runtime\\venv\\Scripts\\python.exe",
  "uv": "C:\\Users\\username\\AppData\\Local\\Programs\\Python\\Lib\\site-packages\\...",
  "endpoints": {
    "core": "http://127.0.0.1:8765",
    "control": "http://127.0.0.1:8766/control"
  },
  "services": [
    {
      "name": "core",
      "module": "services.core.main",
      "console_script": "marvex-core",
      "exe": "C:\\Users\\username\\.marvex\\runtime\\venv\\Scripts\\marvex-core.exe",
      "runtime_tier": "tier1_setuptools",
      "kind": "http",
      "port": 8765
    },
    {
      "name": "voice_worker",
      "module": "services.voice_worker.main",
      "console_script": "marvex-voice-worker",
      "exe": "C:\\Users\\username\\.marvex\\runtime\\venv\\Scripts\\marvex-voice-worker.exe",
      "runtime_tier": "tier1_setuptools",
      "kind": "jsonl",
      "port": null
    }
  ]
}
```

The manifest intentionally lists only shell-supervised service children:
`core` and `voice_worker`. Provider, intent, and tool workers are Core-owned
persistent JSONL worker processes and must not appear as Tauri-supervised
manifest services.

---

## Service Lifecycle

### Service Startup

**Code location**: `apps/shell/src-tauri/src/supervisor.rs`

```rust
// Tier 1: Console scripts (production)
if let Some(exe) = venv
    .map(|root| venv_script(root, spec.sidecar))
    .filter(|path| path.is_file())
{
    Command::new(exe)
        .args(&spec.args)
        .current_dir(data_dir)
        .spawn()
}
// Fallback: Dev mode (uv run)
else {
    Command::new("uv")
        .args(["run", "python", "-m", spec.module])
        .args(&spec.args)
        .current_dir(project_root())
        .spawn()
}
```

### Service Arguments

**Core daemon**:
```bash
MARVEX_LOCAL_AUTH_TOKEN=<TOKEN> marvex-core.exe --serve --host 127.0.0.1 --port 8765 --provider provider_worker --worker-provider fake
```

**Shell-supervised worker service**:
```bash
marvex-voice-worker.exe --jsonl
```

ProviderWorker, IntentWorker, and ToolWorker still use the JSONL protocol, but
they are spawned and reused by Core as backend-owned internals. The shell
supervisor no longer launches disconnected provider/intent/tool worker children.

### Process Management

- ✅ Windowless (CREATE_NO_WINDOW flag on Windows)
- ✅ Separate process group (CREATE_NEW_PROCESS_GROUP)
- ✅ Health monitoring (poll every 500ms)
- ✅ Auto-restart on failure (exponential backoff: 1s → 2s → 4s → ... → 30s max)
- ✅ Graceful shutdown (stop commands for JSONL workers, kill for hung processes)
- ✅ Logging to `~/.marvex/logs/` (stdout/stderr separated)

---

## Packaged Runtime Smoke

The non-elevated smoke command verifies the release backend runtime without
installing the Windows service:

```powershell
npm --prefix apps/control_plane_web run build
npm --prefix apps/shell run build
uv build --wheel
Copy-Item dist/marvex-0.1.0-py3-none-any.whl apps/shell/runtime/marvex-0.1.0-py3-none-any.whl -Force
cargo build --release --bin marvex-service --manifest-path apps/shell/src-tauri/Cargo.toml
powershell -ExecutionPolicy Bypass -File scripts/smoke_packaged_runtime.ps1
```

Rebuild and copy the Python wheel before the service build. The smoke verifies
the packaged resource path. For the default `target/release` service binary,
the smoke stages `apps/shell/runtime/*.whl`, `uv.exe`, the built Control Plane
web dist, and voice assets next to the binary before launch.

The smoke starts `marvex-service.exe --console` with a temporary `ProgramData`
root, obtains a token lease from `\\.\pipe\Marvex.TokenHandoff.v1`, verifies
`/health`, `/control/health`, `/control/state`, `/control/state/stream`, and a
protected `/v1/turns` call, checks that the manifest lists only `core` and
`voice_worker`, and then requests a graceful console shutdown.

Expected pass signals:
- token lease reports `auth_token_present: true` and `token_value_logged: false`
- `/v1/turns` metadata reports `provider_boundary: provider_worker_process`
- manifest does not contain the raw bearer token
- ports `8765` and `8766` are free again after shutdown

`marvex-service --install` and `--uninstall` remain elevated service-management
commands. `--console` is only the local smoke/debug mode.

---

## Token Management

### Generation

```rust
// At app startup, Tauri generates cryptographically-secure random token
let token = generate_secure_token();  // 32 bytes, hex-encoded
```

### Propagation

1. Token passed to Supervisor
2. Supervisor passes the token to Core only through `MARVEX_LOCAL_AUTH_TOKEN`
3. Workers do not receive the Core bearer token
4. Installed service exposes an in-memory Windows named-pipe lease broker for the shell attach path
5. Rust shell/service commands use the token for privileged loopback HTTP Bearer calls; Control Plane browser windows use the one-time claim URL and HttpOnly cookie path instead of receiving the raw token

### Security

- **Never persisted**: Only in memory during session
- **Not in argv**: Product supervision uses process environment instead of CLI args
- **Never logged**: Startup metadata reports token presence only
- **Destroyed on shutdown**: Lost when app exits
- **Loopback-only**: Only 127.0.0.1 can use endpoints

---

## Deps Tab: Runtime Package Installation

The Deps tab allows installing new packages into the live venv without restarting.

### Flow

```
User clicks "Install" in Deps tab
  ↓
Frontend calls `/control/deps/install?package=requests`
  ↓
Control Plane API → Dependency Runtime
  ↓
Execute: uv pip install requests --python ~/.marvex/runtime/venv/Scripts/python.exe
  ↓
Package installed into live venv
  ↓
Services can import it immediately (no restart needed)
```

### Why This Works with Setuptools

Setuptools console scripts import from the venv's site-packages at runtime. When new packages are installed, they're immediately visible to running services.

**This CANNOT work with PyInstaller** because frozen executables have sealed sys.path at build time.

---

## Frontend Assets

### Build Output

**Location**: `apps/shell/dist/`

```
dist/
├── index.html              (Single entry point for all surfaces)
├── assets/
│   ├── index-{hash}.js     (React app + dependencies)
│   ├── index-{hash}.css    (Tailwind CSS)
│   └── ...
```

### Surfaces

All surfaces share the same React app, switched via routing:
- `/` → Chat App
- `/overlay` → Status Pill + Waveform
- `/spotlight` → Spotlight Modal

### Bundling

Vite configured in `apps/shell/vite.config.ts`:
```typescript
export default defineConfig({
  plugins: [react()],
  build: {
    target: 'ES2020',
    sourcemap: false,
    minify: 'terser',
  }
});
```

Outputs minified, tree-shaken bundles optimized for WebView2.

---

## Installer Contents

### NSIS Installer

**Filename**: `Marvex_0.1.0_x64-setup.exe` (~260-375 MB)

**Contents**:
```
Installer
├── Tauri runtime (WebView2)
├── Rust executable (marvex-shell.exe)
├── Frontend assets (HTML, JS, CSS)
├── uv.exe (bundled package manager)
├── marvex-0.1.0-py3-none-any.whl (Python package)
└── Start Menu shortcuts
```

**Installation**:
```
User runs Marvex_0.1.0_x64-setup.exe
  ↓
Installs to %ProgramFiles%\Marvex (per-machine)
  ↓
Creates Start Menu shortcuts
  ↓
Registers autostart in Windows Registry
  ↓
User can launch from Start Menu or taskbar
```

### First Run

```
User launches Marvex from Start Menu
  ↓
marvex-shell.exe starts
  ↓
Extracts uv.exe + wheel to app cache
  ↓
Supervisor bootstrap creates ~/.marvex/runtime/venv/
  ↓
Frontend shows "Setting up..." while services initialize
  ↓
Manifest written to ~/.marvex/runtime/manifest.json
  ↓
All services ready
  ↓
Chat window opens, ready for use
```

---

## Testing Checklist

### Post-Install Smoke Tests

✅ **No Terminal Windows**
- Verify no cmd.exe or powershell windows appear

✅ **Chat Message**
- Send message → Verify response from `/v1/turns`

✅ **Status Indicators**
- Change status → Overlay pill updates
- Verify waveform reacts to audio

✅ **Approvals**
- Trigger approval → Spotlight modal appears
- Approve/deny via button and voice

✅ **Autostart**
- Reboot machine
- Verify app starts automatically

✅ **Deps Tab**
- Click "Install" on a package
- Verify package becomes importable

✅ **Clean Shutdown**
- Close app via tray quit
- Verify all child processes terminate
- Check no orphaned Python processes

✅ **Runtime Manifest**
```powershell
type $env:USERPROFILE\.marvex\runtime\manifest.json
# Should show:
#   "runtime_phase": "ready"
#   "runtime_architecture": "tier1_setuptools_console_scripts"
#   "services": [...]
```

---

## Troubleshooting

### Service Fails to Start

Check logs:
```powershell
# Core service
type $env:USERPROFILE\.marvex\logs\core.stdout.log
type $env:USERPROFILE\.marvex\logs\core.stderr.log

# Voice worker
type $env:USERPROFILE\.marvex\logs\voice_worker.stdout.log
```

### Venv Bootstrap Fails

```powershell
type $env:USERPROFILE\.marvex\logs\runtime.bootstrap.log
```

### Token Issues

Tokens are never logged (security). If token verification fails, check:
1. Core received `MARVEX_LOCAL_AUTH_TOKEN` in its private environment
2. Shell attach received a lease from the named-pipe token handoff broker
3. Shell received a token lease and Control Plane browser auth used a one-time claim URL plus HttpOnly cookie
4. Authorization header format: `Bearer <TOKEN>`

---

## Summary

| Aspect | Value |
|--------|-------|
| **Runtime** | Setuptools console scripts (dynamic Python) |
| **Execution** | Tier 1 (production) / Tier 3 (dev) |
| **Frozen?** | ❌ No (real Python, not PyInstaller) |
| **Runtime installs** | ✅ Yes (Deps tab) |
| **Windowless** | ✅ Yes (CREATE_NO_WINDOW) |
| **Single instance** | ✅ Yes (Tauri plugin) |
| **Autostart** | ✅ Yes (Windows Registry) |
| **Installer size** | ~260-375 MB |
| **Token** | Per-session, never persisted |
| **Build script** | `.\build-installer.ps1` from repo root |
