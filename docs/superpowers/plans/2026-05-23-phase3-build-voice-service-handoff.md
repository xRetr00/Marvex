# Phase 3 — Build, Installer & 24/7 Voice Service: Handoff & Verification

This phase ships the always-on "Hey Marvex" voice stack and the backend Windows
service. The code-level pieces are committed and compile/test green; the items
that need a real Windows machine (admin install, model downloads, NSIS bundling)
are listed under "Manual verification" — they can't be exercised in CI.

## What landed (verified here)
- Wake word enabled by default (`VoiceWorkerWakewordConfig.enabled = True`); voice/control tests updated and green.
- `voice_models.manifest.json` + `scripts/fetch_voice_models.py`: download/copy + extract + SHA-256 verify, with a required-asset gate that fails the build if a required model is missing. Unit-tested (`tests/scripts/test_fetch_voice_models.py`).
- `marvex-service` Windows service binary (`apps/shell/src-tauri/src/service.rs`): runs the full backend supervisor 24/7 under the SCM; `--install` / `--uninstall` / `--console`. Compiles with `windows-service`.
- Thin-client shell: `Supervisor::attach`; originally used a shared token file, now superseded by the Windows-local `token_handoff.rs` named-pipe lease broker. The shell connects to the running service when a lease is available, else self-supervises (dev).
- Bundling: control_plane_web SPA + fetched voice-assets are Tauri resources; the service exe ships via a build-time `externalBin` override (`tauri.bundle.conf.json`); NSIS hooks (`installer-hooks.nsh`) register/start the service on install and remove it on uninstall.
- `build-installer.ps1` and `build-installer.bat` stage the SPA, fetch+verify models, build+stage the service binary, and build with the bundle override config.
- Governance: `PROJECT_STATUS.md` + `docs/CONTRACT_APPROVALS.md` updated for always-on wake word + backend-service + thin-client, preserving no-raw-audio/safe-projection guarantees.

## Model sources — IMPORTANT
WebSearch/WebFetch were unavailable in the build environment, so the URLs in
`voice_models.manifest.json` are the canonical project sources from knowledge and
**must be confirmed on first real build**. If any 404s, the fetch step fails
loudly and prints which model — fix that entry's `source_uri` (and ideally add a
`checksum_sha256`) and re-run. The `extract: true` entries are sherpa-onnx
`.tar.bz2` archives; the `.onnx`/`.bin` entries are direct files.

## Manual verification (Windows, run elevated for the service)
1. Build models + service + installer:
   - `./build-installer.ps1`  (fails if a required model is missing)
   - confirm `apps/shell/voice-assets/` has the wake word + STT + TTS files, and `apps/shell/src-tauri/binaries/marvex-service-x86_64-pc-windows-msvc.exe` exists.
2. Service smoke without installing (foreground):
   - `apps/shell/src-tauri/target/release/marvex-service.exe --console`
   - confirm Core (8765) and Control Plane (8766) come up and `%ProgramData%\Marvex\service.token` is written.
3. Install the produced NSIS installer (`apps/shell/src-tauri/target/release/bundle/nsis/*-setup.exe`):
   - confirm a `MarvexBackend` service exists (`sc query MarvexBackend`), is `RUNNING`, and `Startup type = Automatic` (starts at boot).
   - reboot → confirm the service is up before login and "Hey Marvex" triggers (with mic).
4. Launch the shell → confirm it attaches as a thin client (no duplicate backend), the Control Plane window opens with live data, and chat works.
5. Uninstall → confirm the `MarvexBackend` service is removed.

## Known finalize-on-machine risks
- Tauri resource/externalBin placement vs. the NSIS hook path (`$INSTDIR\marvex-service.exe`) and the service's `resource_dir = exe dir` assumption: verify the service finds the bundled wheel/uv/control_plane_web/voice-assets at runtime; adjust paths if the bundler places them under a `resources\` subdir.
- The service runs as LocalSystem by default — confirm it can reach the microphone for wake word, or configure it to run in the user session if Windows session-0 isolation blocks audio. (If audio is blocked in session 0, run the voice worker in the user session via the shell while keeping Core in the service.)
