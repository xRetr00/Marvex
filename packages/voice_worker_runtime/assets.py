from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel


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


class InstalledModelRegistry(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    installed: tuple[VoiceModelInstallResult, ...]
    installed_count: int
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

    def install_local(self, request: VoiceModelInstallRequest) -> VoiceModelInstallResult:
        target = (self.asset_root / request.relative_path).resolve()
        if not target.is_relative_to(self.asset_root):
            return VoiceModelInstallResult(model_id=request.model_id, backend_id=request.backend_id, model_kind=request.model_kind, status="blocked", exact_blocker="model_path_outside_voice_asset_root")
        result = VoiceModelInstallResult(
            model_id=request.model_id,
            backend_id=request.backend_id,
            model_kind=request.model_kind,
            status="installed",
            local_path_present=True,
            checksum_present=bool(request.checksum_sha256),
        )
        self._installed[request.model_id] = result
        return result

    def remove(self, model_id: str) -> VoiceModelRemoveResult:
        removed = self._installed.pop(model_id, None) is not None
        return VoiceModelRemoveResult(model_id=model_id, removed=removed, reason_code="voice_worker.asset.removed" if removed else "voice_worker.asset.not_found")

    def registry(self) -> InstalledModelRegistry:
        installed = tuple(self._installed.values())
        return InstalledModelRegistry(installed=installed, installed_count=len(installed))
