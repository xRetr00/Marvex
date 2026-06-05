from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

from packages.control_plane_api.voice import handle_voice_control_request
from packages.voice_worker_runtime import VoiceAssetManager, VoiceWorkerControlPlaneFacade
from packages.voice_worker_runtime.assets import (
    VoiceModelCatalog,
    VoiceModelCatalogAsset,
    VoiceModelDownloadRequest,
    bundled_install_relative_paths,
    downloadable_voice_model_catalog,
    load_voice_model_catalog,
)


def test_shipped_manifest_bundles_stt_and_wakeword_only() -> None:
    catalog = load_voice_model_catalog()
    bundled = {asset.model_id for asset in catalog.assets if asset.bundled}
    downloadable = {asset.model_id for asset in catalog.assets if not asset.bundled}
    # STT + wakeword ship in the installer; everything else downloads at runtime.
    assert bundled == {"moonshine-v2", "hey-marvex"}
    assert {"kokoro-af-heart", "kokoro-voices", "sensevoice-small"} <= downloadable
    assert "moonshine-v2" not in downloadable


def test_bundled_install_relative_paths_are_the_seeded_dirs() -> None:
    paths = bundled_install_relative_paths()
    assert "stt/moonshine-v2" in paths
    assert "wakeword/hey-marvex" in paths
    # Each bundled install dir appears once even though moonshine has many files.
    assert len(paths) == len(set(paths))


def test_downloadable_catalog_excludes_bundled_assets() -> None:
    downloadable = downloadable_voice_model_catalog()
    assert downloadable.assets, "expected runtime-downloadable assets to remain"
    assert all(asset.bundled is False for asset in downloadable.assets)
    assert not any(asset.model_id == "moonshine-v2" for asset in downloadable.assets)


def test_facade_model_catalog_marks_bundled_but_keeps_them_selectable() -> None:
    facade = VoiceWorkerControlPlaneFacade(assets=VoiceAssetManager(asset_root=Path(".marvex") / "voice-assets"))
    assets = {asset["model_id"]: asset for asset in facade.model_catalog()["assets"]}
    # Bundled backends stay in the catalog (so the STT picker keeps them) but are
    # flagged so the UI can hide their download action.
    assert assets["moonshine-v2"]["bundled"] is True
    assert assets["kokoro-af-heart"]["bundled"] is False


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


def test_asset_manager_does_not_register_multi_file_download_until_catalog_group_is_complete(tmp_path: Path) -> None:
    manager = VoiceAssetManager(asset_root=tmp_path / "voice-assets")
    result = manager.download(
        VoiceModelDownloadRequest(
            model_id="moonshine-v2",
            backend_id="moonshine-v2",
            model_kind="stt",
            source_uri="https://models.example.test/moonshine-v2/encoder.ort",
            relative_path="stt/moonshine-v2/encoder.ort",
            install_relative_path="stt/moonshine-v2",
            explicit_user_triggered=True,
        ),
        fetcher=lambda _uri: b"encoder bytes",
    )

    assert result.status == "not_installed"
    assert result.download_started is True
    assert result.install_started is False
    assert manager.is_ready(model_id="moonshine-v2", backend_id="moonshine-v2", model_kind="stt") is False


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


def test_asset_manager_discovers_bundled_catalog_assets_from_voice_asset_root(tmp_path: Path) -> None:
    asset_root = tmp_path / "voice-assets"
    (asset_root / "wakeword" / "hey-marvex" / "model").mkdir(parents=True)
    (asset_root / "wakeword" / "hey-marvex" / "model" / "tokens.txt").write_bytes(b"hey marvex")
    catalog = VoiceModelCatalog(
        assets=(
            VoiceModelCatalogAsset(
                model_id="hey-marvex",
                backend_id="sherpa-onnx-kws",
                model_kind="wakeword",
                source_uri="https://models.example.test/hey-marvex.tar.gz",
                relative_path="wakeword/hey-marvex",
                extract=True,
                required=True,
                explicit_user_triggered=True,
            ),
        )
    )
    manager = VoiceAssetManager(asset_root=asset_root)

    registry = manager.discover_installed(catalog)

    assert registry.installed_count == 1
    assert manager.is_ready(model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword") is True


def test_load_voice_model_catalog_honors_packaged_manifest_env(tmp_path: Path, monkeypatch) -> None:
    manifest = tmp_path / "voice_models.manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "assets": [
                    {
                        "model_id": "custom-stt",
                        "backend_id": "custom-backend",
                        "model_kind": "stt",
                        "source_uri": "https://models.example.test/custom/model.onnx",
                        "relative_path": "stt/custom/model.onnx",
                        "required": True,
                        "explicit_user_triggered": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MARVEX_VOICE_MODEL_MANIFEST", str(manifest))

    catalog = load_voice_model_catalog()

    assert [asset.model_id for asset in catalog.assets] == ["custom-stt"]


def test_asset_manager_discovers_multi_file_model_only_after_all_catalog_parts_exist(tmp_path: Path) -> None:
    asset_root = tmp_path / "voice-assets"
    (asset_root / "stt" / "moonshine-v2").mkdir(parents=True)
    (asset_root / "stt" / "moonshine-v2" / "encoder.ort").write_bytes(b"encoder")
    catalog = VoiceModelCatalog(
        assets=(
            VoiceModelCatalogAsset(
                model_id="moonshine-v2",
                backend_id="moonshine-v2",
                model_kind="stt",
                source_uri="https://models.example.test/encoder.ort",
                relative_path="stt/moonshine-v2/encoder.ort",
                install_relative_path="stt/moonshine-v2",
                required=True,
                explicit_user_triggered=True,
            ),
            VoiceModelCatalogAsset(
                model_id="moonshine-v2",
                backend_id="moonshine-v2",
                model_kind="stt",
                source_uri="https://models.example.test/tokenizer.bin",
                relative_path="stt/moonshine-v2/tokenizer.bin",
                install_relative_path="stt/moonshine-v2",
                required=True,
                explicit_user_triggered=True,
            ),
        )
    )
    manager = VoiceAssetManager(asset_root=asset_root)

    partial = manager.discover_installed(catalog)
    (asset_root / "stt" / "moonshine-v2" / "tokenizer.bin").write_bytes(b"tokenizer")
    complete = manager.discover_installed(catalog)

    assert partial.installed_count == 0
    assert complete.installed_count == 1
    assert manager.resolve_installed_path("moonshine-v2") == (asset_root / "stt" / "moonshine-v2").resolve()


def test_control_plane_status_discovers_bundled_assets_before_reporting_required_models(tmp_path: Path) -> None:
    asset_root = tmp_path / "voice-assets"
    (asset_root / "wakeword" / "hey-marvex").mkdir(parents=True)
    manager = VoiceAssetManager(asset_root=asset_root)
    catalog = VoiceModelCatalog(
        assets=(
            VoiceModelCatalogAsset(
                model_id="hey-marvex",
                backend_id="sherpa-onnx-kws",
                model_kind="wakeword",
                source_uri="https://models.example.test/hey-marvex.tar.gz",
                relative_path="wakeword/hey-marvex",
                extract=True,
                required=True,
                explicit_user_triggered=True,
            ),
        )
    )
    facade = VoiceWorkerControlPlaneFacade(controller=None, assets=manager, model_catalog_loader=lambda: catalog)

    assets = facade.assets_status()

    required = {item["model_id"]: item for item in assets["required"]}
    assert required["hey-marvex"]["status"] == "installed"


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
