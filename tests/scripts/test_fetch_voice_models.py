import io
import tarfile
from pathlib import Path

import pytest

from scripts.fetch_voice_models import (
    VoiceAsset,
    asset_present,
    fetch_asset,
    fetch_all,
    load_manifest,
    missing_required,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_load_manifest_reads_required_wakeword() -> None:
    manifest = load_manifest(REPO_ROOT / "voice_models.manifest.json")
    by_id = {a.model_id: a for a in manifest}
    assert "hey-marvex" in by_id
    wake = by_id["hey-marvex"]
    assert wake.model_kind == "wakeword"
    assert wake.backend_id == "sherpa-onnx-kws"
    assert wake.required is True


def test_manifest_uses_moonshine_package_cdn_for_active_moonshine_backend() -> None:
    manifest = load_manifest(REPO_ROOT / "voice_models.manifest.json")
    moonshine = [asset for asset in manifest if asset.model_id == "moonshine-v2"]

    assert moonshine
    assert all(asset.source_uri.startswith("https://download.moonshine.ai/model/") for asset in moonshine)
    assert {Path(asset.relative_path).name for asset in moonshine} >= {"encoder.ort", "frontend.ort", "tokenizer.bin"}


def test_fetch_plain_file_via_file_uri(tmp_path: Path) -> None:
    source = tmp_path / "model.onnx"
    source.write_bytes(b"weights")
    asset = VoiceAsset(
        model_id="m", backend_id="b", model_kind="tts_voice",
        relative_path="tts/model.onnx", source_uri=source.as_uri(), extract=False,
    )
    root = tmp_path / "assets"
    fetch_asset(root, asset)
    assert asset_present(root, asset)
    assert (root / "tts/model.onnx").read_bytes() == b"weights"


def test_fetch_and_extract_archive(tmp_path: Path) -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="model/tokens.txt")
        payload = b"hey marvex"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    archive = tmp_path / "kws.tar.gz"
    archive.write_bytes(buf.getvalue())
    asset = VoiceAsset(
        model_id="hey-marvex", backend_id="sherpa-onnx-kws", model_kind="wakeword",
        relative_path="wakeword/hey-marvex", source_uri=archive.as_uri(), extract=True,
    )
    root = tmp_path / "assets"
    fetch_asset(root, asset)
    assert asset_present(root, asset)
    assert (root / "wakeword/hey-marvex/model/tokens.txt").read_bytes() == b"hey marvex"


def test_checksum_mismatch_raises(tmp_path: Path) -> None:
    source = tmp_path / "model.onnx"
    source.write_bytes(b"weights")
    asset = VoiceAsset(
        model_id="m", backend_id="b", model_kind="tts_voice",
        relative_path="tts/model.onnx", source_uri=source.as_uri(),
        checksum_sha256="0" * 64,
    )
    with pytest.raises(ValueError, match="checksum mismatch"):
        fetch_asset(tmp_path / "assets", asset)


def test_missing_required_reports_absent(tmp_path: Path) -> None:
    present = tmp_path / "a.bin"
    present.write_bytes(b"x")
    manifest = [
        VoiceAsset(model_id="have", backend_id="b", model_kind="vad", relative_path="a.bin", source_uri=present.as_uri(), required=True),
        VoiceAsset(model_id="missing", backend_id="b", model_kind="wakeword", relative_path="b.bin", source_uri="https://example.invalid/x", required=True),
        VoiceAsset(model_id="optional", backend_id="b", model_kind="stt", relative_path="c.bin", source_uri="https://example.invalid/y", required=False),
    ]
    root = tmp_path / "assets"
    fetch_all(root, manifest, fetcher=lambda _uri: (_ for _ in ()).throw(RuntimeError("no network")))
    assert missing_required(root, manifest) == ["missing"]
