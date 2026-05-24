# Marvex Shell

Marvex Shell is the Tauri v2 Windows product surface. It is a loopback client and supervisor for the existing bounded backend contracts; it does not implement provider, intent, tool, voice, memory, cognition, or policy logic.

## Layout

- `src-tauri/`: Rust Tauri supervisor, tray, windows, single-instance, autostart, global shortcut, state stream client, and local proxy commands.
- `src/`: React/Vite shell surfaces for chat and the single Dynamic Island overlay for state, waveform, cards, and approvals.
- `runtime/`: Bundled resources for production deployment (uv.exe, marvex wheel).

## Development

```powershell
npm install
npm run test
npm run build
cargo test --manifest-path apps\shell\src-tauri\Cargo.toml
cargo build --manifest-path apps\shell\src-tauri\Cargo.toml
```

The dev shell falls back to `uv run python -m ...` when running from source.

## Packaging (Tier 1: Production)

The production installer uses **setuptools console scripts** (dynamic Python, not frozen executables):

**Build process**:
1. Frontend: `npm run build` (React/Vite)
2. Tauri: `npm run tauri build` (produces NSIS/MSI installers)

**Runtime behavior**:
- On first launch, supervisor creates `~/.marvex/runtime/venv/`
- Installs bundled `marvex-0.1.0-py3-none-any.whl` via `uv pip install`
- Setuptools generates console scripts: `~/.marvex/runtime/venv/Scripts/marvex-*.exe`
- Services launched via console scripts (real Python, not frozen)
- Supports runtime package installation (Deps tab)

**No PyInstaller**: Services use setuptools console script wrappers (setuptools-generated entry points), not frozen bytecode. This enables dynamic module loading and runtime package installs.

The shell generates its local bearer token at runtime, passes it to Core, uses it for protected loopback calls, and never writes or logs the token value.

## Operator Smoke

After installing the packaged app:

1. Launch Marvex from Start Menu or the installer finish action.
2. Confirm no backend terminal windows are visible.
3. Confirm the tray menu opens chat, voice pause/resume, and quit.
4. Send a chat message and confirm a real Core `/v1/turns` response.
5. Trigger assistant/voice state and confirm the Dynamic Island expands with a large waveform from `/control/state/stream`.
6. Trigger an approval and confirm the Dynamic Island accepts button or voice decisions.
7. Reboot or log out/in and confirm autostart.
8. Quit from tray and confirm child processes are stopped.

This smoke requires the runtime Control Plane `/control/state` and `/control/state/stream` endpoints to be available.
