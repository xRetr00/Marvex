import sys
from pathlib import Path
from PyInstaller.building.build_main import Analysis, EXE, PYZ
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ENTRYPOINT = ROOT / 'services/core/main.py'
EXCLUDES = ['sherpa_onnx', 'sherpa_onnx_core', 'kokoro_onnx', 'funasr', 'moonshine', 'moonshine_voice', 'piper', 'piper_tts', 'piper_phonemize', 'silero_vad', 'webrtcvad', 'fastembed', 'playwright', 'browser_use', 'transformers', 'torch', 'torchaudio', 'onnxruntime', 'nltk', 'scipy', 'llama_index', 'llama_index_core', 'semantic_router']
HIDDEN = collect_submodules("packages") + collect_submodules("services")

a = Analysis([str(ENTRYPOINT)], pathex=[str(ROOT)], binaries=[], datas=[],
    hiddenimports=HIDDEN, hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=EXCLUDES, noarchive=False, optimize=0)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='marvex-core',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
    upx_exclude=[], runtime_tmpdir=None, console=False)
