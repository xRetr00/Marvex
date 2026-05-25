# Marvex Shell Python Packaging

## Production Runtime (Tier 1)

The installer uses **setuptools console scripts** for service execution.

On first launch:
1. Supervisor detects missing venv in `~/.marvex/runtime/venv/`
2. Finds bundled `uv.exe` and `marvex-<version>-py3-none-any.whl`
3. Creates venv: `uv venv ~/.marvex/runtime/venv --python 3.12`
4. Installs wheel: `uv pip install --no-index --find-links wheels marvex-<version>-py3-none-any.whl`
5. Setuptools generates console scripts at `~/.marvex/runtime/venv/Scripts/`:
   - `marvex-core.exe`
   - `marvex-provider-worker.exe`
   - `marvex-intent-worker.exe`
   - `marvex-tool-worker.exe`
   - `marvex-voice-worker.exe`

Services are launched via these setuptools-generated console scripts (real Python, not frozen bytecode).

**Advantages**:
- Supports runtime package installation (Deps tab)
- Debuggable and profiler-friendly
- Dynamic module loading
- Significantly smaller distribution than frozen executables

## Development Fallback (Tier 3)

If venv doesn't exist and no bundled resources:
```powershell
uv run python -m services.core.main --serve ...
```

Runs services directly from source code.
