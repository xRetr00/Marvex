from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Callable
from typing import Literal
from urllib.parse import urlparse
from urllib.request import url2pathname, urlopen

from pydantic import Field
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel


REQUIRED_VOICE_ASSETS: tuple[tuple[str, str, str], ...] = (
    ("moonshine-v2", "moonshine-v2", "stt"),
    ("hey-marvex", "sherpa-onnx-kws", "wakeword"),
    ("kokoro-af-heart", "kokoro-onnx", "tts_voice"),
    ("kokoro-voices", "kokoro-onnx", "tts_voice"),
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
    install_relative_path: str | None = Field(default=None, min_length=1)
    extract: bool = False
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


class VoiceModelCatalogAsset(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model_id: str
    backend_id: str
    model_kind: Literal["stt", "tts_voice", "wakeword", "vad"]
    source_uri: str
    relative_path: str
    install_relative_path: str | None = None
    extract: bool = False
    checksum_sha256: str | None = None
    required: bool = True
    explicit_user_triggered: Literal[True] = True
    raw_payload_persisted: Literal[False] = False

    def to_download_request(self) -> VoiceModelDownloadRequest:
        return VoiceModelDownloadRequest(
            model_id=self.model_id,
            backend_id=self.backend_id,
            model_kind=self.model_kind,
            source_uri=self.source_uri,
            relative_path=self.relative_path,
            install_relative_path=self.install_relative_path,
            extract=self.extract,
            checksum_sha256=self.checksum_sha256,
            explicit_user_triggered=True,
        )


class VoiceModelCatalog(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    assets: tuple[VoiceModelCatalogAsset, ...]
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
        install_relative_path = request.install_relative_path or request.relative_path
        install_target = (self.asset_root / install_relative_path).resolve()
        if not target.is_relative_to(self.asset_root):
            return _download_result_from_request(
                request,
                status="blocked",
                download_started=False,
                install_started=False,
                exact_blocker="model_path_outside_voice_asset_root",
            )
        if not install_target.is_relative_to(self.asset_root):
            return _download_result_from_request(
                request,
                status="blocked",
                download_started=False,
                install_started=False,
                exact_blocker="model_path_outside_voice_asset_root",
            )
        blocker = self._download_to_target(source_uri=request.source_uri, target=target, fetcher=fetcher, extract=request.extract)
        if blocker is not None:
            return _download_result_from_request(
                request,
                status="blocked",
                download_started=True,
                install_started=False,
                exact_blocker=blocker,
            )
        if not self._catalog_group_complete(request):
            return _download_result_from_request(
                request,
                status="not_installed",
                download_started=True,
                install_started=False,
                exact_blocker="model_catalog_group_incomplete",
            )
        installed = self.install_local(
            VoiceModelInstallRequest(
                model_id=request.model_id,
                backend_id=request.backend_id,
                model_kind=request.model_kind,
                relative_path=install_relative_path,
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
        extract: bool,
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
                if extract or _is_archive(parsed.path):
                    _extract_archive(data, parsed.path, target if extract else target.parent)
                else:
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

    def discover_installed(self, catalog: VoiceModelCatalog | None = None) -> InstalledModelRegistry:
        grouped_assets: dict[tuple[str, str, str, str], list[VoiceModelCatalogAsset]] = {}
        for asset in (catalog or load_voice_model_catalog()).assets:
            install_relative_path = asset.install_relative_path or asset.relative_path
            key = (asset.model_id, asset.backend_id, asset.model_kind, install_relative_path)
            grouped_assets.setdefault(key, []).append(asset)

        for (model_id, backend_id, model_kind, install_relative_path), assets in grouped_assets.items():
            if model_id in self._installed and self.resolve_installed_path(model_id) is not None:
                continue
            if not all(self._catalog_asset_present(asset) for asset in assets):
                continue
            self.install_local(
                VoiceModelInstallRequest(
                    model_id=model_id,
                    backend_id=backend_id,
                    model_kind=model_kind,  # type: ignore[arg-type]
                    relative_path=install_relative_path,
                    explicit_user_triggered=True,
                )
            )
        return self.registry()

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

    def _catalog_asset_present(self, asset: VoiceModelCatalogAsset) -> bool:
        target = (self.asset_root / asset.relative_path).resolve()
        if not target.is_relative_to(self.asset_root):
            return False
        return target.exists()

    def _catalog_group_complete(self, request: VoiceModelDownloadRequest) -> bool:
        install_relative_path = request.install_relative_path or request.relative_path
        if install_relative_path == request.relative_path:
            return True
        matching_assets = [
            asset
            for asset in load_voice_model_catalog().assets
            if asset.model_id == request.model_id
            and asset.backend_id == request.backend_id
            and asset.model_kind == request.model_kind
            and (asset.install_relative_path or asset.relative_path) == install_relative_path
        ]
        if len(matching_assets) <= 1:
            return True
        return all(self._catalog_asset_present(asset) for asset in matching_assets)


def _looks_like_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdefABCDEF" for character in value)


def load_voice_model_catalog(manifest_path: Path | None = None) -> VoiceModelCatalog:
    path = manifest_path or Path(__file__).resolve().parents[2] / "voice_models.manifest.json"
    if not path.exists():
        return VoiceModelCatalog(assets=())
    data = json.loads(path.read_text(encoding="utf-8"))
    assets: list[VoiceModelCatalogAsset] = []
    for item in data.get("assets", []):
        assets.append(
            VoiceModelCatalogAsset(
                model_id=str(item["model_id"]),
                backend_id=str(item["backend_id"]),
                model_kind=item["model_kind"],
                source_uri=str(item["source_uri"]),
                relative_path=str(item["relative_path"]),
                install_relative_path=item.get("install_relative_path") or None,
                extract=bool(item.get("extract", False)),
                checksum_sha256=item.get("checksum_sha256") or None,
                required=bool(item.get("required", True)),
                explicit_user_triggered=True,
            )
        )
    return VoiceModelCatalog(assets=tuple(assets))


def _is_archive(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((".tar.bz2", ".tar.gz", ".tgz", ".tar", ".zip"))


def _extract_archive(data: bytes, source_name: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    lowered = source_name.lower()
    if lowered.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(data)) as archive:
            archive.extractall(dest_dir)
        return
    mode = "r:bz2" if lowered.endswith(".tar.bz2") else "r:gz" if lowered.endswith((".tar.gz", ".tgz")) else "r:"
    with tarfile.open(fileobj=BytesIO(data), mode=mode) as archive:
        archive.extractall(dest_dir, filter="data")


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
