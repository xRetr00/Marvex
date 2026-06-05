# Marvex Version Bump Checklist

This document lists the files that must be reviewed for every Marvex application
version bump. Keep runtime code centralized where possible, but still update the
static metadata files required by Python packaging, Tauri, Cargo, and npm.

## Source Of Truth

Update this first:

| File | Field |
| --- | --- |
| `version.toml` | `[app].version` |

The shell UI reads this value at Vite build time. The installer scripts also read
this value when building packages and installers.

## Required Manual Updates

These files contain first-party app/package metadata and should match
`version.toml`.

| Area | File | Field |
| --- | --- | --- |
| Python package metadata | `pyproject.toml` | `[project].version` |
| Python runtime constant | `packages/version.py` | `MARVEX_VERSION` |
| Python lock metadata | `uv.lock` | `[[package]] name = "marvex"` version |
| Shell npm package | `apps/shell/package.json` | `version` |
| Shell npm lock | `apps/shell/package-lock.json` | root package versions |
| Control Plane npm package | `apps/control_plane_web/package.json` | `version` |
| Control Plane npm lock | `apps/control_plane_web/package-lock.json` | root package versions |
| Tauri app config | `apps/shell/src-tauri/tauri.conf.json` | `version` |
| Rust package metadata | `apps/shell/src-tauri/Cargo.toml` | `[package].version` |
| Rust lock metadata | `apps/shell/src-tauri/Cargo.lock` | `[[package]] name = "marvex-shell"` version |
| Rust runtime manifest version | `apps/shell/src-tauri/src/supervisor.rs` | `MARVEX_VERSION` |

## Python Runtime Consumers

Do not put version literals in service modules. They should import the packaged
constant from `packages.version`.

Current Python consumers include:

| File | Expected pattern |
| --- | --- |
| `apps/cli/main.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `packages/core/service.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `packages/local_api/runner.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `packages/local_service_startup/startup.py` | `from packages.version import MARVEX_VERSION as DEFAULT_SERVICE_VERSION` |
| `packages/voice_worker_runtime/models.py` | `from packages.version import MARVEX_VERSION` |
| `services/desktop_agent/models.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `services/intent_worker/models.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `services/provider_worker/models.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `services/tool_worker/models.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |
| `services/voice_worker/models.py` | `from packages.version import MARVEX_VERSION as SERVICE_VERSION` |

## Build Scripts

These should not need version edits during a bump:

| File | Behavior |
| --- | --- |
| `build-installer.ps1` | Reads `version.toml`; writes SHA manifests for packaged artifacts |
| `build-installer.bat` | Reads `version.toml`; writes SHA manifests for packaged artifacts |
| `apps/shell/vite.config.ts` / `apps/shell/vite.config.js` | Reads `version.toml` and injects `__MARVEX_APP_VERSION__` |
| `apps/shell/src/lib/appVersion.ts` | Exposes the injected shell UI version |

## Tests To Review

If a test asserts the exact app version, update it or change it to compare
against the central source.

Known exact-version tests:

| File | Check |
| --- | --- |
| `apps/shell/src/lib/appVersion.test.ts` | Expects the shell injected version |
| `tests/test_python_runtime_version.py` | Expects `packages.version.MARVEX_VERSION` |

## Generated Artifacts

Do not hand-edit these. Regenerate them through the normal package/build tools.

| Artifact | How it is produced |
| --- | --- |
| `dist/marvex-<version>-py3-none-any.whl` | `uv build --wheel` |
| `apps/shell/dist/**` | `npm run build` in `apps/shell` |
| `apps/control_plane_web/dist/**` | `npm run build` in `apps/control_plane_web` |
| `apps/shell/runtime/marvex-runtime.sha256` | `build-installer.ps1` / `build-installer.bat` |
| `apps/shell/dist/marvex-shell-frontend.sha256` | `build-installer.ps1` / `build-installer.bat` |
| `apps/control_plane_web/dist/marvex-control-plane.sha256` | `build-installer.ps1` / `build-installer.bat` |
| `apps/shell/src-tauri/binaries/marvex-service.sha256` | `build-installer.ps1` / `build-installer.bat` |

## Suggested Verification

Run focused checks after a version bump:

```powershell
uv run --frozen pytest tests/test_python_runtime_version.py -q
npm test -- --run src/lib/appVersion.test.ts
```

Run packaging checks before producing an installer:

```powershell
uv build --wheel
npm run build --prefix apps/shell
npm run build --prefix apps/control_plane_web
.\build-installer.ps1 -SkipInstaller
```

Use `rg` to catch missed first-party literals:

```powershell
rg -n "0\.X\.Y|MARVEX_VERSION|SERVICE_VERSION|\"version\":|version = " version.toml pyproject.toml apps packages services
```
