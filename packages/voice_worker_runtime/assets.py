from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Callable
from typing import Literal
from urllib.parse import urlparse
from urllib.request import url2pathname, urlopen

from pydantic import Field
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel


REQUIRED_VOICE_ASSETS: tuple[tuple[str, str, str], ...] = (
    ("moonshine-v2", "moonshine-v2", "stt"),
    ("sensevoice-small", "sensevoice-small", "stt"),
    ("hey-marvex", "sherpa-onnx-kws", "wakeword"),
    ("kokoro-af-heart", "kokoro-onnx", "tts_voice"),
    ("piper-default", "piper-tts", "tts_voice"),
    ("silero-vad", "silero-vad", "vad"),
    ("webrtcvad-wheels", "webrtcvad-wheels", "vad"),
)


class VoiceModelInstallRequest(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str = Field(..., min_length=1)
    backend_id: str = Field(..., min_length=1)
    model_kind: Literal["stt", "tts_voice", "wakeword", "vad"]
    relative_path: str = Field(..., min_length=1)
    checksum_sha256: str | None = None
    explicit_user_triggered: Literal[True] = True


class VoiceModelInstallResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str
    backend_id: str
    model_kind: str
    status: Literal["installed", "blocked", "not_installed"]
    local_path_present: bool = False
    checksum_present: bool = False
    exact_blocker: str | None = None
    raw_model_internals_rendered: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class VoiceModelDownloadRequest(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str = Field(..., min_length=1)
    backend_id: str = Field(..., min_length=1)
    model_kind: Literal["stt", "tts_voice", "wakeword", "vad"]
    source_uri: str = Field(..., min_length=1)
    relative_path: str = Field(..., min_length=1)
    checksum_sha256: str | None = None
    explicit_user_triggered: Literal[True] = True


class VoiceModelDownloadResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str
    backend_id: str
    model_kind: str
    status: Literal["installed", "blocked", "not_installed"]
    download_started: bool
    install_started: bool
    checksum_present: bool = False
    exact_blocker: str | None = None
    raw_model_internals_rendered: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class InstalledModelRegistry(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    installed: tuple[VoiceModelInstallResult, ...]
    installed_count: int
    required: tuple[VoiceModelInstallResult, ...] = ()
    required_ready_count: int = 0
    required_blocked_count: int = 0
    raw_model_internals_rendered: Literal[False] = False


class VoiceModelRemoveResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str
    removed: bool
    reason_code: str
    raw_model_internals_rendered: Literal[False] = False


class VoiceAssetManager:
    def __init__(self, *, asset_root: Path | None = None) -> None:
        self.asset_root = (asset_root or Path(".marvex") / "voice-assets").resolve()
        self._installed: dict[str, VoiceModelInstallResult] = {}
        self._paths: dict[str, Path] = {}

    def install_local(self, request: VoiceModelInstallRequest) -> VoiceModelInstallResult:
        target = (self.asset_root / request.relative_path).resolve()
        if not target.is_relative_to(self.asset_root):
            return VoiceModelInstallResult(model_id=request.model_id, backend_id=request.backend_id, model_kind=request.model_kind, status="blocked", exact_blocker="model_path_outside_voice_asset_root")
        if not target.exists():
            return VoiceModelInstallResult(
                model_id=request.model_id,
                backend_id=request.backend_id,
                model_kind=request.model_kind,
                status="not_installed",
                local_path_present=False,
                checksum_present=bool(request.checksum_sha256),
                exact_blocker="model_path_not_found_under_voice_asset_root",
            )
        if request.checksum_sha256 and _looks_like_sha256(request.checksum_sha256) and target.is_file():
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if digest.lower() != request.checksum_sha256.lower():
                return VoiceModelInstallResult(
                    model_id=request.model_id,
                    backend_id=request.backend_id,
                    model_kind=request.model_kind,
                    status="blocked",
                    local_path_present=True,
                    checksum_present=True,
                    exact_blocker="model_asset_checksum_mismatch",
                )
        result = VoiceModelInstallResult(
            model_id=request.model_id,
            backend_id=request.backend_id,
            model_kind=request.model_kind,
            status="installed",
            local_path_present=True,
            checksum_present=bool(request.checksum_sha256),
        )
        self._installed[request.model_id] = result
        self._paths[request.model_id] = target
        return result

    def download(
        self,
        request: VoiceModelDownloadRequest,
        *,
        fetcher: Callable[[str], bytes] | None = None,
    ) -> VoiceModelDownloadResult:
        target = (self.asset_root / request.relative_path).resolve()
        if not target.is_relative_to(self.asset_root):
            return _download_result_from_request(
                request,
                status="blocked",
                download_started=False,
                install_started=False,
                exact_blocker="model_path_outside_voice_asset_root",
            )
        blocker = self._download_to_target(source_uri=request.source_uri, target=target, fetcher=fetcher)
        if blocker is not None:
            return _download_result_from_request(
                request,
                status="blocked",
                download_started=True,
                install_started=False,
                exact_blocker=blocker,
            )
        installed = self.install_local(
            VoiceModelInstallRequest(
                model_id=request.model_id,
                backend_id=request.backend_id,
                model_kind=request.model_kind,
                relative_path=request.relative_path,
                checksum_sha256=request.checksum_sha256,
                explicit_user_triggered=True,
            )
        )
        if installed.status == "blocked" and installed.exact_blocker == "model_asset_checksum_mismatch" and target.is_file():
            target.unlink(missing_ok=True)
        return VoiceModelDownloadResult(
            model_id=installed.model_id,
            backend_id=installed.backend_id,
            model_kind=installed.model_kind,
            status=installed.status,
            download_started=True,
            install_started=True,
            checksum_present=installed.checksum_present,
            exact_blocker=installed.exact_blocker,
        )

    def _download_to_target(
        self,
        *,
        source_uri: str,
        target: Path,
        fetcher: Callable[[str], bytes] | None,
    ) -> str | None:
        parsed = urlparse(source_uri)
        try:
            if parsed.scheme == "file":
                source = Path(url2pathname(parsed.path)).resolve()
                if not source.exists():
                    return "model_source_not_found"
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                return None
            if parsed.scheme == "https":
                data = fetcher(source_uri) if fetcher is not None else _fetch_https(source_uri)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                return None
        except Exception:
            return "model_download_failed"
        return "model_download_source_scheme_not_allowed"

    def remove(self, model_id: str) -> VoiceModelRemoveResult:
        removed = self._installed.pop(model_id, None) is not None
        self._paths.pop(model_id, None)
        return VoiceModelRemoveResult(model_id=model_id, removed=removed, reason_code="voice_worker.asset.removed" if removed else "voice_worker.asset.not_found")

    def resolve_installed_path(self, model_id: str) -> Path | None:
        item = self._installed.get(model_id)
        target = self._paths.get(model_id)
        if item is None or item.status != "installed" or target is None:
            return None
        if not target.resolve().is_relative_to(self.asset_root):
            return None
        if not target.exists():
            return None
        return target

    def registry(self) -> InstalledModelRegistry:
        installed = tuple(self._installed.values())
        required = tuple(self._required_status(model_id=model_id, backend_id=backend_id, model_kind=model_kind) for model_id, backend_id, model_kind in REQUIRED_VOICE_ASSETS)
        return InstalledModelRegistry(
            installed=installed,
            installed_count=len(installed),
            required=required,
            required_ready_count=sum(1 for item in required if item.status == "installed"),
            required_blocked_count=sum(1 for item in required if item.status != "installed"),
        )

    def is_ready(self, *, model_id: str, backend_id: str | None = None, model_kind: str | None = None) -> bool:
        item = self._installed.get(model_id)
        if item is None or item.status != "installed":
            return False
        if backend_id is not None and item.backend_id != backend_id:
            return False
        if model_kind is not None and item.model_kind != model_kind:
            return False
        return True

    def required_status(self, *, model_id: str, backend_id: str, model_kind: str) -> VoiceModelInstallResult:
        return self._required_status(model_id=model_id, backend_id=backend_id, model_kind=model_kind)

    def _required_status(self, *, model_id: str, backend_id: str, model_kind: str) -> VoiceModelInstallResult:
        installed = self._installed.get(model_id)
        if installed is not None:
            return installed
        return VoiceModelInstallResult(
            model_id=model_id,
            backend_id=backend_id,
            model_kind=model_kind,
            status="not_installed",
            exact_blocker="model_path_not_found_under_voice_asset_root",
        )


def _looks_like_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def _fetch_https(source_uri: str) -> bytes:
    with urlopen(source_uri, timeout=30) as response:  # noqa: S310 - explicit user-triggered model download.
        return response.read()


def _download_result_from_request(
    request: VoiceModelDownloadRequest,
    *,
    status: Literal["installed", "blocked", "not_installed"],
    download_started: bool,
    install_started: bool,
    exact_blocker: str | None = None,
) -> VoiceModelDownloadResult:
    return VoiceModelDownloadResult(
        model_id=request.model_id,
        backend_id=request.backend_id,
        model_kind=request.model_kind,
        status=status,
        download_started=download_started,
        install_started=install_started,
        checksum_present=bool(request.checksum_sha256),
        exact_blocker=exact_blocker,
    )
