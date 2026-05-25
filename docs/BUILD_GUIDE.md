# Build Script Validation & Execution Guide

## Quick Start

From the workspace root (`D:\Marvex`):

```powershell
# Full build (recommended for first run)
.\build-installer.ps1

# Fast build (skip validation, for experienced users)
.\build-installer.ps1 -SkipValidation

# With verbose output
.\build-installer.ps1 -Verbose
```

**Note**: The build system automatically reads the application version from `version.toml` in the repo root. See [Version Management](#version-management) for details.

---

## Pre-Requisites

The script validates these automatically (or use `-SkipValidation`):

| Tool | Version | Install URL |
|------|---------|-------------|
| Node.js | Latest | https://nodejs.org/ |
| npm | Bundled with Node | Automatic |
| Rust/Cargo | Latest | https://rustup.rs/ |
| uv | Latest | `pip install uv` |
| Python | 3.11+ | https://www.python.org/ |

**Quick install check**:
```powershell
node --version
npm --version
cargo --version
uv --version
python --version
```

---

## Build Steps Explained

### ✅ Step 1: Validate Environment
```powershell
[1/5] Validating environment
  - Node.js v20.x.x
  - npm 10.x.x
  - Cargo 1.x.x
  - uv 0.x.x
  - Python 3.11+
```

**What it does**: Ensures all required tools are installed and accessible.

**If it fails**: Install missing tools from URLs above.

---

### ✅ Step 2: Build Python Wheel
```powershell
[2/5] Building Python wheel
  - uv build --wheel
  - Verifies console scripts in wheel
```

**Output**: `dist/marvex-<version>-py3-none-any.whl` (~20-30 MB)

**What it contains**:
- Python packages from `pyproject.toml`
- Service modules (core, workers)
- Console script definitions (setuptools)

**If it fails**:
```powershell
# Check Python installation
python -m pip --version

# Try building manually
uv build --wheel

# Check logs for missing dependencies
```

---

### ✅ Step 3: Prepare Runtime Resources
```powershell
[3/5] Preparing runtime resources
  - Copying wheel to apps/shell/runtime/
  - Copying uv.exe to apps/shell/runtime/
```

**Output**:
```
apps/shell/runtime/
├── marvex-<version>-py3-none-any.whl
└── uv.exe
```

These get bundled in the final installer.

---

### ✅ Step 4: Build Frontend
```powershell
[4/5] Building frontend (React/Vite)
  - npm install (dependencies)
  - npm build (bundle)
```

**Output**: `apps/shell/dist/` with React app

**Typical times**:
- First build: 3-5 minutes
- Incremental: 1-2 minutes

**If it fails**:
```powershell
# Check npm
npm --version

# Try building manually
npm --prefix apps/shell install
npm --prefix apps/shell run build

# Check for build errors
```

---

### ✅ Step 5: Build Tauri App & Installers
```powershell
[5/5] Building Tauri app & installers
  - Compiling Rust code
  - Creating installers (NSIS/MSI)
```

**Output**:
```
apps/shell/src-tauri/target/release/bundle/
├── nsis/
│   ├── Marvex_0.1.0_x64-setup.exe (~260-375 MB)
│   └── Marvex_0.1.0_x64-setup.exe.sig
└── wix/
    └── Marvex_0.1.0_x64_en-US.msi
```

**Typical time**: 5-15 minutes (depends on system)

**If it fails**:
```powershell
# Check Rust
cargo --version

# Try building manually
npm --prefix apps/shell run tauri build

# Check for Rust compilation errors
```

---

## Expected Output

### Successful Build

```
╔════════════════════════════════════════════════════════════╗
║             MARVEX INSTALLER BUILD SCRIPT                  ║
║         Tier 1: Production (Setuptools Console Scripts)    ║
╚════════════════════════════════════════════════════════════╝

┌──────────────────────────────────────────────────────────┐
│ Validating Environment                                    │
└──────────────────────────────────────────────────────────┘

✓ Node.js: v20.11.0
✓ npm: 10.2.4
✓ Cargo: cargo 1.77.0
✓ uv: uv 0.1.45
✓ Python: 3.11.8

[1/5] Building Python Wheel...
✓ Wheel built: marvex-<version>-py3-none-any.whl

[2/5] Preparing runtime resources...
✓ Wheel copied to apps/shell/runtime/
✓ uv.exe copied to apps/shell/runtime/

[3/5] Building frontend...
✓ Control Plane built
✓ Shell frontend built

[4/5] Verifying frontend assets...
✓ index.html present
✓ assets present
JavaScript files: 5
CSS files: 2

[5/5] Building Tauri app & installers...
✓ Tauri app built successfully

┌──────────────────────────────────────────────────────────┐
│ Installer Artifacts                                       │
└──────────────────────────────────────────────────────────┘

✓ NSIS Installer: Marvex_0.1.0_x64-setup.exe
  Location: ...\apps\shell\src-tauri\target\release\bundle\nsis\...
  Size: 315.45 MB

✓ MSI Installer: Marvex_0.1.0_x64_en-US.msi
  Location: ...\apps\shell\src-tauri\target\release\bundle\wix\...
  Size: 298.20 MB

┌──────────────────────────────────────────────────────────┐
│ Build Complete! ✓                                         │
└──────────────────────────────────────────────────────────┘

Runtime packaging (Tier 1: Production):
  ✓ Setuptools console scripts (not frozen PyInstaller)
  ✓ Dynamic Python runtime in ~/.marvex/runtime/venv/
  ✓ Supports runtime package installation via Deps tab

Next steps:
  1. Test the installer on a clean Windows machine
  2. Run smoke tests (see apps/shell/README.md)
  3. Verify no terminal windows appear during runtime
  4. Check ~/.marvex/runtime/manifest.json after first run
```

---

## Testing the Installer

### 1. Install
```powershell
# Run the NSIS installer
.\Marvex_0.1.0_x64-setup.exe

# Follow prompts (or just click "Next" for defaults)
```

### 2. Launch
```powershell
# From Start Menu
# OR
marvex  # if in PATH
# OR
C:\Program Files\Marvex\marvex-shell.exe
```

### 3. Verify Setup
First launch should:
1. Show "Setting up..." message
2. Create `~/.marvex/runtime/venv/` (takes 1-2 minutes on slow networks)
3. Install wheel and generate console scripts
4. Launch services
5. Open chat window

**Check bootstrap log**:
```powershell
type $env:USERPROFILE\.marvex\logs\runtime.bootstrap.log
# Should show:
# Creating environment
# Installing packages
# Complete
```

### 4. Smoke Tests

**Chat**:
- Type message → Should get response

**Status Pill** (overlay):
- Type anything → Top-left pill should show "Thinking"
- Overlay should not interfere with desktop

**Approvals**:
- Type "approve this task" → Should trigger approval modal
- Button click should work
- Voice approval should work (if mic enabled)

**Deps Tab**:
- Go to Deps tab
- Try installing a small package (e.g., `requests`)
- Should complete without restart

**Logs**:
```powershell
ls $env:USERPROFILE\.marvex\logs\
# Should have:
# core.stdout.log
# core.stderr.log
# provider_worker.stdout.log
# ... etc
```

---

## Troubleshooting

### Build Fails at Step 2 (Wheel Build)

**Error**: `PyInstaller module not found`
**Fix**: PyInstaller is optional. If you see this, it's normal—not needed for Tier 1.

**Error**: `setuptools not found`
**Fix**: 
```powershell
uv pip install setuptools build
uv build --wheel
```

### Build Fails at Step 3 (Frontend)

**Error**: `npm: command not found`
**Fix**: Install Node.js from https://nodejs.org/

**Error**: `node_modules missing`
**Fix**: 
```powershell
npm --prefix apps/shell install --force
```

### Build Fails at Step 5 (Tauri)

**Error**: `cargo not found`
**Fix**: Install Rust from https://rustup.rs/

**Error**: `WebView2 not found`
**Fix**: Install WebView2: https://developer.microsoft.com/en-us/microsoft-edge/webview2/

**Error**: Long compile times
**Note**: First Tauri build takes 10-15 minutes. Subsequent builds are faster (incremental).

### Installer Won't Start Services

**Check**:
```powershell
# Look at supervisor status
type $env:USERPROFILE\.marvex\logs\runtime.bootstrap.log

# Check individual service logs
type $env:USERPROFILE\.marvex\logs\core.stderr.log
```

### Deps Tab Shows "Installing" Forever

**Check**:
```powershell
# Verify venv exists
ls $env:USERPROFILE\.marvex\runtime\venv\Scripts\marvex-*.exe

# Check uv path
echo $env:MARVEX_UV_PATH
```

---

## Clean Build (Fresh Start)

If you want to clean everything and rebuild from scratch:

```powershell
.\build-installer.ps1 -Clean
```

This removes:
- `apps/shell/dist/`
- `apps/shell/build/`
- `apps/shell/node_modules/`
- `apps/shell/src-tauri/target/`
- `apps/control_plane_web/dist/`
- `apps/control_plane_web/node_modules/`
- `dist/` (Python wheel)

Then rebuilds from scratch.

---

## Build Variants

### Fastest (Dev Testing)
```powershell
.\build-installer.ps1 -SkipValidation
```
Assumes all tools are installed. Saves validation time.

### Verbose Output (Debugging)
```powershell
.\build-installer.ps1 -Verbose
```
Shows full command output, useful if something fails.

### Full Validation (Recommended First Run)
```powershell
.\build-installer.ps1
```
Validates all dependencies, safest option.

---

## Architecture Reference

**Build script implements**:
```
Tier 1: Production
  ↓
Setuptools console scripts (real Python)
  ↓
~/.marvex/runtime/venv/Scripts/marvex-*.exe
  ↓
Supports runtime package installation
```

**NOT using**:
```
✗ PyInstaller (frozen bytecode)
✗ Legacy sidecar tier
✗ Pre-compiled executables
```

---

## Build Times (Typical)

| Step | Time | Notes |
|------|------|-------|
| Validate | < 1s | Fast |
| Wheel build | 1-2 min | Depends on network (deps download) |
| Runtime prep | < 1s | File copies |
| Frontend build | 3-5 min | First run (incremental: 1-2 min) |
| Tauri build | 5-15 min | First run (incremental: 2-5 min) |
| **TOTAL** | **15-30 min** | First run |

---

## Production Build Checklist

✅ Pre-build:
- [ ] All prerequisites installed
- [ ] Working git checkout
- [ ] Enough disk space (~5-10 GB)

✅ Build:
- [ ] Run `.\build-installer.ps1` successfully
- [ ] No error messages
- [ ] Installers exist in bundle/ directory

✅ Post-build:
- [ ] Test installer on clean Windows machine
- [ ] Verify no terminal windows
- [ ] Check manifest.json after first run
- [ ] Send chat message successfully
- [ ] Install package via Deps tab

✅ Release:
- [ ] Version bumped in `version.toml` and synced to pyproject.toml + tauri.conf.json
- [ ] Release notes written
- [ ] Installer tested on Windows 10 + Windows 11

---

## Version Management

**Central version file**: `version.toml` (repo root)

**On every version bump** (e.g., `0.1.0` → `0.1.1`):

1. Update `version.toml`:
   ```toml
   [app]
   version = "0.1.1"
   ```

2. Manually sync to these files (build scripts read `version.toml`, but these tools require static files):
   - `pyproject.toml` — line 7: `version = "0.1.1"`
   - `apps/shell/src-tauri/tauri.conf.json` — line 4: `"version": "0.1.1"`
   - `apps/shell/src-tauri/Cargo.toml` — line 3: `version = "0.1.1"`

3. Build normally—`build-installer.ps1` automatically reads the new version from `version.toml`

**Why manual sync?** External tools (setuptools, Tauri, Cargo) read these files at build time and don't support reading from external sources. This approach keeps complexity minimal while automating the build scripts.
