# Marvex Shell Python Packaging

These commands build the Python runtime executables used by the Tauri v2 Windows shell.

## Build all runtime targets

```powershell
.\apps\shell\scripts\build-python-runtime.ps1
```

## Build specific runtime targets

```powershell
.\apps\shell\scripts\build-python-runtime.ps1 -Targets core,provider_worker,intent_worker,tool_worker,voice_worker
```

## Direct PyInstaller commands

```powershell
uv run python -m PyInstaller --noconfirm --distpath .\apps\shell\dist\python --workpath .\apps\shell\build\pyinstaller\core .\apps\shell\packaging\core.spec
uv run python -m PyInstaller --noconfirm --distpath .\apps\shell\dist\python --workpath .\apps\shell\build\pyinstaller\provider_worker .\apps\shell\packaging\provider_worker.spec
uv run python -m PyInstaller --noconfirm --distpath .\apps\shell\dist\python --workpath .\apps\shell\build\pyinstaller\intent_worker .\apps\shell\packaging\intent_worker.spec
uv run python -m PyInstaller --noconfirm --distpath .\apps\shell\dist\python --workpath .\apps\shell\build\pyinstaller\tool_worker .\apps\shell\packaging\tool_worker.spec
uv run python -m PyInstaller --noconfirm --distpath .\apps\shell\dist\python --workpath .\apps\shell\build\pyinstaller\voice_worker .\apps\shell\packaging\voice_worker.spec
```

All specs build with `console=False` to keep Windows packaging windowless.
