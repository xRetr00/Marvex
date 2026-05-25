from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

from packages.control_plane_api.voice import handle_voice_control_request
from packages.voice_worker_runtime import VoiceAssetManager, VoiceWorkerControlPlaneFacade
from packages.voice_worker_runtime.assets import VoiceModelDownloadRequest


def test_asset_manager_downloads_file_source_into_safe_asset_root_and_registers_it(tmp_path: Path) -> None:
    source = tmp_path / "source" / "hey-marvex.kws"
    source.parent.mkdir()
    source.write_bytes(b"wakeword model bytes")
    checksum = hashlib.sha256(b"wakeword model bytes").hexdigest()
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")

    result = manager.download(
        VoiceModelDownloadRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            source_uri=source.as_uri(),
            relative_path="wakeword/hey-marvex.kws",
            checksum_sha256=checksum,
            explicit_user_triggered=True,
        )
    )

    target = tmp_path / "voice-assets" / "wakeword" / "hey-marvex.kws"
    assert result.status == "installed"
    assert result.download_started is True
    assert result.install_started is True
    assert target.read_bytes() == b"wakeword model bytes"
    assert manager.is_ready(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword") is True
    serialized = json.dumps(result.model_dump(mode="json")).lower()
    assert str(tmp_path).lower() not in serialized
    assert "wakeword model bytes" not in serialized


def test_asset_manager_download_blocks_path_escape_and_checksum_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "source" / "voice.onnx"
    source.parent.mkdir()
    source.write_bytes(b"model bytes")
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")

    escaped = manager.download(
        VoiceModelDownloadRequest(
            model_id="escape",
            backend_id="piper-tts",
            model_kind="tts_voice",
            source_uri=source.as_uri(),
            relative_path="../voice.onnx",
            explicit_user_triggered=True,
        )
    )
    mismatch = manager.download(
        VoiceModelDownloadRequest(
            model_id="piper-default",
            backend_id="piper-tts",
            model_kind="tts_voice",
            source_uri=source.as_uri(),
            relative_path="tts/piper-default/voice.onnx",
            checksum_sha256=hashlib.sha256(b"different").hexdigest(),
            explicit_user_triggered=True,
        )
    )

    assert escaped.status == "blocked"
    assert escaped.exact_blocker == "model_path_outside_voice_asset_root"
    assert mismatch.status == "blocked"
    assert mismatch.exact_blocker == "model_asset_checksum_mismatch"
    assert manager.registry().installed_count == 0


def test_asset_manager_download_uses_injected_fetcher_for_https_without_leaking_payload(tmp_path: Path) -> None:
    observed: list[str] = []

    def fetcher(source_uri: str) -> bytes:
        observed.append(source_uri)
        return b"downloaded model bytes"

    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    result = manager.download(
        VoiceModelDownloadRequest(
            model_id="moonshine-v2",
            backend_id="moonshine-v2",
            model_kind="stt",
            source_uri="https://models.example.test/moonshine-v2/model.onnx",
            relative_path="stt/moonshine-v2/model.onnx",
            explicit_user_triggered=True,
        ),
        fetcher=fetcher,
    )

    assert observed == ["https://models.example.test/moonshine-v2/model.onnx"]
    assert result.status == "installed"
    assert (tmp_path / "voice-assets" / "stt" / "moonshine-v2" / "model.onnx").exists()
    assert "downloaded model bytes" not in json.dumps(result.model_dump(mode="json")).lower()


def test_asset_manager_download_extracts_archive_assets_before_registration(tmp_path: Path) -> None:
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="model/tokens.txt")
        payload = b"hey marvex"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")

    result = manager.download(
        VoiceModelDownloadRequest(
            model_id="hey-marvex",
            backend_id="sherpa-onnx-kws",
            model_kind="wakeword",
            source_uri="https://models.example.test/hey-marvex.tar.gz",
            relative_path="wakeword/hey-marvex",
            extract=True,
            explicit_user_triggered=True,
        ),
        fetcher=lambda _uri: archive.getvalue(),
    )

    assert result.status == "installed"
    assert (tmp_path / "voice-assets" / "wakeword" / "hey-marvex" / "model" / "tokens.txt").read_bytes() == b"hey marvex"
    assert manager.resolve_installed_path("hey-marvex") == (tmp_path / "voice-assets" / "wakeword" / "hey-marvex").resolve()


def test_required_registry_tracks_kokoro_voice_bundle_asset(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    required_ids = {item.model_id for item in manager.registry().required}

    assert "kokoro-af-heart" in required_ids
    assert "kokoro-voices" in required_ids


def test_control_plane_exposes_worker_model_download_endpoint(tmp_path: Path) -> None:
    source = tmp_path / "source" / "voice.onnx"
    source.parent.mkdir()
    source.write_bytes(b"voice model bytes")
    facade = VoiceWorkerControlPlaneFacade(controller=None, assets=VoiceAssetManager(asset_root=tmp_path / "voice-assets"))
    body = json.dumps(
        {
            "model_id": "piper-default",
            "backend_id": "piper-tts",
            "model_kind": "tts_voice",
            "source_uri": source.as_uri(),
            "relative_path": "tts/piper-default/voice.onnx",
            "explicit_user_triggered": True,
        }
    ).encode("utf-8")

    status, payload = handle_voice_control_request(
        method="POST",
        path="/control/voice/worker/models/download",
        environ={"REQUEST_BODY": body},
        voice_control=None,
        voice_worker_control=facade,
    )

    assert status == "200 OK"
    assert payload["status"] == "installed"
    assert payload["download_started"] is True
    assert payload["raw_payload_persisted"] is False
