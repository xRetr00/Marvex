from pathlib import Path

from PyInstaller.building.build_main import Analysis, COLLECT, EXE, PYZ

ROOT = Path(__file__).resolve().parents[3]
ENTRYPOINT = ROOT / "services" / "core" / "main.py"
DIST_DIR = ROOT / "apps" / "shell" / "dist" / "python"
BUILD_DIR = ROOT / "apps" / "shell" / "build" / "pyinstaller" / "core"

a = Analysis(
    [str(ENTRYPOINT)],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="marvex-core",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="marvex-core",
)
