# Version Management Guide

## Overview

Marvex uses a **centralized version file** (`version.toml`) as the single source of truth for all version information across the project. This eliminates manual version bumping across multiple files while keeping complexity minimal.

---

## Central Version File

**Location**: `version.toml` (repo root)

**Contents**:
```toml
[app]
version = "0.1.0"
wheel_name = "marvex-runtime.whl"
```

This file includes detailed inline comments explaining:
- What needs to be manually synced on version bumps
- Why manual sync is necessary (external tool constraints)
- Which build scripts read automatically from this file

---

## Version Bump Workflow

### Step 1: Update `version.toml`

Edit `version.toml` and change the version:

```toml
[app]
version = "0.1.1"  # Changed from 0.1.0
wheel_name = "marvex-runtime.whl"
```

### Step 2: Manually Sync Three Files

These tools require static version files at build time and cannot read from external sources:

#### File 1: `pyproject.toml`
**Line 7**: Update the version
```toml
version = "0.1.1"  # Was: "0.1.0"
```

#### File 2: `apps/shell/src-tauri/tauri.conf.json`
**Line 4**: Update the version
```json
"version": "0.1.1",  // Was: "0.1.0"
```

#### File 3: `apps/shell/src-tauri/Cargo.toml`
**Line 3**: Update the version
```toml
version = "0.1.1"  # Was: "0.1.0"
```

### Step 3: Build

Run the build script normally:
```powershell
.\build-installer.ps1
```

**What happens**:
- Build scripts automatically read the new version from `version.toml`
- Installers will be named `Marvex_0.1.1_x64-setup.exe` (etc.)
- No further configuration needed

---

## Why This Approach?

### What Gets Automated ✅

| File | Read By | Why Auto |
|------|---------|----------|
| `build-installer.ps1` | Build script | We control it—can read external file |
| `build-installer.bat` | Build script | We control it—can read external file |

### What Stays Manual ⚠️

| File | Read By | Why Manual |
|------|---------|-----------|
| `pyproject.toml` | setuptools | Requires static version in file |
| `tauri.conf.json` | Tauri CLI | Reads at build time; no hook point |
| `Cargo.toml` | Rust compiler | Tied to Tauri version via build system |

**Why don't we automate everything?**

These are third-party tools with their own build systems:
- **setuptools** (Python packaging) expects `pyproject.toml` to contain the definitive version
- **Tauri** (desktop framework) reads `tauri.conf.json` during the build process
- **Cargo** (Rust package manager) expects `Cargo.toml` to have the version

Adding preprocessing hooks would require:
- Complex build script logic
- Hidden version injection (debugging nightmare)
- Multiple points of failure during version bumps

**The manual approach is simpler and more transparent**: 3 files, 30 seconds to update.

---

## Build Script Integration

### PowerShell (`build-installer.ps1`)

```powershell
# Load version from central file
$versionContent = Get-Content -LiteralPath "version.toml"
$versionLine = $versionContent | Where-Object { $_ -match '^\s*version\s*=' } | Select-Object -First 1
# Parse: version = "0.1.1"
$AppVersion = $matches[1]  # ← Gets "0.1.1"

# Display in validation output
Write-Success "Marvex App Version: $AppVersion"

# Used during wheel build, Tauri config, etc.
```

### Batch (`build-installer.bat`)

```batch
setlocal enabledelayedexpansion
for /f "tokens=*" %%A in ('findstr "version = " "%VersionFile%"') do (
    set "line=%%A"
    if "!line:~0,1!" neq "#" (
        for /f "tokens=3 delims="""  %%B in ("%%A") do (
            set "AppVersion=%%B"
        )
    )
)
endlocal & set "AppVersion=%AppVersion%"

REM Display in validation output
echo [OK] Marvex App Version: !AppVersion!
```

Both scripts extract the version at startup and display it in validation output, confirming the correct version is being used.

---

## Documentation Updates

### For Current Version References

Docs that reference the current application version should now point to this guide:

```markdown
See [Version Management Guide](../VERSION_MANAGEMENT.md) for the current version.
```

**Files updated**:
- `docs/BUILD_GUIDE.md` — Build workflow documentation
- `docs/MARVEX_INSTALLER_PACKAGING.md` — Packaging architecture
- `docs/ARCHITECTURE_DECISIONS.md` — Design decisions

### For Version-Specific Docs

Version-specific documentation (e.g., "Marvex v1 Features", "v2 Migration Guide") are left unchanged:
- These docs are intentionally version-specific
- They should not reference the central version file

---

## Quick Reference: Version Bump Checklist

```
□ Update version.toml (line 2)
□ Update pyproject.toml (line 7)
□ Update tauri.conf.json (line 4)
□ Update Cargo.toml (line 3)
□ Commit and push
□ Run .\build-installer.ps1 to verify
□ Test installer on clean Windows machine
```

**Time to complete**: ~1 minute

---

## Troubleshooting

### Build Script Can't Find version.toml

**Symptom**: `✗ ERROR: version.toml not found`

**Fix**: Ensure `version.toml` exists in the repo root (`D:\Marvex\version.toml`)

```powershell
Test-Path D:\Marvex\version.toml
```

### Build Script Can't Parse Version

**Symptom**: `✗ ERROR: Could not parse version from version.toml`

**Fix**: Ensure `version.toml` has correct format:
```toml
[app]
version = "X.Y.Z"
```

Check the line is not commented out and quotes are present.

### Installer Named Incorrectly

**Symptom**: Installer is `Marvex_0.1.0_x64-setup.exe` but should be `0.1.1`

**Fix**: You likely forgot to sync `tauri.conf.json` line 4.

Verify all three files match:
```powershell
grep "version" D:\Marvex\pyproject.toml
grep "version" D:\Marvex\apps\shell\src-tauri\tauri.conf.json
grep "version" D:\Marvex\apps\shell\src-tauri\Cargo.toml
```

---

## Files Involved

| File | Purpose | Updated On |
|------|---------|-----------|
| `version.toml` | Single source of truth | Every version bump |
| `pyproject.toml` | Python package version | Every version bump (manual) |
| `tauri.conf.json` | Tauri app version, installer name | Every version bump (manual) |
| `Cargo.toml` | Rust package version | Every version bump (manual) |
| `build-installer.ps1` | Reads version, displays in output | As-needed for build automation |
| `build-installer.bat` | Reads version, displays in output | As-needed for build automation |
| `VERSION_MANAGEMENT.md` | This guide | Reference only |
