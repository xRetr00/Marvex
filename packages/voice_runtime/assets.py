from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.voice_runtime.base import SCHEMA_VERSION, VoiceRuntimeModel, safe_mapping
from packages.voice_runtime.config import VoiceInstallStatus


class VoiceModelRef(VoiceRuntimeModel):
    model_id: str = Field(..., min_length=1)
    backend_id: str = Field(..., min_length=1)
    model_kind: Literal["stt", "tts_voice", "wakeword", "vad"]


class VoiceModelManifest(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model: VoiceModelRef
    install_status: VoiceInstallStatus = VoiceInstallStatus.NOT_INSTALLED
    local_uri: str | None = None
    checksum_present: bool = False
    raw_model_internals_rendered: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        if self.local_uri is not None:
            payload["local_uri_present"] = True
            payload.pop("local_uri", None)
        return safe_mapping(payload)


class VoiceDownloadRequest(VoiceRuntimeModel):
    model_id: str = Field(..., min_length=1)
    backend_id: str = Field(..., min_length=1)
    model_kind: Literal["stt", "tts_voice", "wakeword", "vad"]
    source_uri: str = Field(..., min_length=1)
    explicit_user_triggered: Literal[True] = True


class VoiceDownloadResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    model: VoiceModelRef
    status: VoiceInstallStatus
    download_started: bool
    install_started: bool
    exact_blocker: str | None = None
    raw_model_internals_rendered: Literal[False] = False
    raw_payload_persisted: Literal[False] = False


class VoiceRemoveResult(VoiceRuntimeModel):
    model_id: str
    removed: bool
    reason_code: str
    raw_model_internals_rendered: Literal[False] = False


class VoiceAssetProjection(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    installed: tuple[dict[str, object], ...]
    installed_count: int
    raw_model_internals_rendered: Literal[False] = False


class VoiceTestRequest(VoiceRuntimeModel):
    test_id: str = Field(..., min_length=1)
    backend_id: str = Field(..., min_length=1)
    phrase: str | None = Field(default=None, max_length=300)
    sample_ref_id: str | None = Field(default=None, max_length=120)
    raw_audio_persisted: Literal[False] = False


class VoiceTestResult(VoiceRuntimeModel):
    schema_version: str = SCHEMA_VERSION
    test_id: str
    backend_id: str
    status: Literal["passed", "failed", "blocked"]
    reason_code: str = "voice.test.safe_probe"
    raw_audio_persisted: Literal[False] = False
    raw_generated_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @classmethod
    def from_request(cls, request: VoiceTestRequest, *, status: Literal["passed", "failed", "blocked"]) -> "VoiceTestResult":
        return cls(test_id=request.test_id, backend_id=request.backend_id, status=status)


class _ModelRegistry:
    def __init__(self) -> None:
        self._items: dict[str, VoiceModelManifest] = {}

    def install(self, manifest: VoiceModelManifest) -> VoiceModelManifest:
        self._items[manifest.model.model_id] = manifest
        return manifest

    def download(self, request: VoiceDownloadRequest) -> VoiceDownloadResult:
        model = VoiceModelRef(model_id=request.model_id, backend_id=request.backend_id, model_kind=request.model_kind)
        if not request.source_uri.startswith("local://"):
            return VoiceDownloadResult(model=model, status=VoiceInstallStatus.DOWNLOAD_BLOCKED, download_started=False, install_started=False, exact_blocker="network_model_download_not_enabled_in_control_plane")
        self.install(VoiceModelManifest(model=model, install_status=VoiceInstallStatus.INSTALLED, local_uri=f"local://voice-assets/{request.model_kind}/{request.model_id}"))
        return VoiceDownloadResult(model=model, status=VoiceInstallStatus.INSTALLED, download_started=True, install_started=True)

    def list_installed(self) -> tuple[VoiceModelManifest, ...]:
        return tuple(item for item in self._items.values() if item.install_status == VoiceInstallStatus.INSTALLED)

    def remove(self, model_id: str) -> VoiceRemoveResult:
        removed = self._items.pop(model_id, None) is not None
        return VoiceRemoveResult(model_id=model_id, removed=removed, reason_code="voice.asset.removed" if removed else "voice.asset.not_found")

    def safe_projection(self) -> dict[str, object]:
        projection = VoiceAssetProjection(installed=tuple(item.safe_projection() for item in self.list_installed()), installed_count=len(self.list_installed()))
        return projection.model_dump(mode="json")


class STTModelRegistry(_ModelRegistry):
    pass


class TTSVoiceRegistry(_ModelRegistry):
    pass


class WakeWordModelRegistry(_ModelRegistry):
    pass
