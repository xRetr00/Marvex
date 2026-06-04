"""Fetch + verify Marvex voice model assets after installation or for dev.

Reads ``voice_models.manifest.json`` and downloads/copies each asset into the
voice-asset root, extracting archives, verifying optional SHA-256 checksums, and
failing (non-zero exit) if any *required* asset is missing afterwards. The
installer does not bundle these assets; packaged runs download them into the
per-user voice asset root from the manifest.

Pure helpers (``load_manifest``, ``asset_present``, ``fetch_asset``,
``missing_required``) are import-friendly and unit-tested with a fake fetcher;
the CLI does the real HTTPS download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from urllib.request import url2pathname, urlopen

Fetcher = Callable[[str], bytes]


@dataclass(frozen=True)
class VoiceAsset:
    model_id: str
    backend_id: str
    model_kind: str
    relative_path: str
    source_uri: str
    extract: bool = False
    checksum_sha256: str | None = None
    required: bool = True


def load_manifest(path: Path) -> list[VoiceAsset]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    assets: list[VoiceAsset] = []
    for entry in data.get("assets", []):
        assets.append(
            VoiceAsset(
                model_id=str(entry["model_id"]),
                backend_id=str(entry["backend_id"]),
                model_kind=str(entry["model_kind"]),
                relative_path=str(entry["relative_path"]),
                source_uri=str(entry["source_uri"]),
                extract=bool(entry.get("extract", False)),
                checksum_sha256=entry.get("checksum_sha256") or None,
                required=bool(entry.get("required", True)),
            )
        )
    return assets


def _target(asset_root: Path, asset: VoiceAsset) -> Path:
    return (asset_root / asset.relative_path).resolve()


_MARKER_NAME = ".marvex-source-sha256"


def _marker_path(asset_root: Path, asset: VoiceAsset) -> Path:
    target = _target(asset_root, asset)
    base = target if asset.extract else target.parent
    return base / f"{_MARKER_NAME}-{asset.model_id}"


def asset_present(asset_root: Path, asset: VoiceAsset) -> bool:
    target = _target(asset_root, asset)
    if asset.extract:
        if not (target.is_dir() and any(target.iterdir())):
            return False
    elif not (target.is_file() and target.stat().st_size > 0):
        return False
    # Self-heal a stale/partial/wrong cache: when the manifest pins a checksum,
    # a cached asset is only "present" if a marker written by a prior successful
    # fetch matches that checksum. An old cache (no marker), or one extracted
    # from a different/older archive (wrong marker), is re-fetched - this is the
    # fix for "the wake model was cached before" silently shipping a mismatched
    # encoder that never detects.
    if asset.checksum_sha256:
        marker = _marker_path(asset_root, asset)
        try:
            return marker.read_text(encoding="utf-8").strip().lower() == asset.checksum_sha256.strip().lower()
        except OSError:
            return False
    return True


def _is_archive(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((".tar.bz2", ".tar.gz", ".tgz", ".tar", ".zip"))


def _extract(data: bytes, source_name: str, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    lowered = source_name.lower()
    if lowered.endswith(".zip"):
        with zipfile.ZipFile(BytesIO(data)) as archive:
            archive.extractall(dest_dir)
        return
    mode = "r:bz2" if lowered.endswith(".tar.bz2") else "r:gz" if lowered.endswith((".tar.gz", ".tgz")) else "r:"
    with tarfile.open(fileobj=BytesIO(data), mode=mode) as archive:
        # Flatten a single top-level dir (sherpa archives wrap everything in one).
        archive.extractall(dest_dir, filter="data")


def _read_source(source_uri: str, fetcher: Fetcher | None) -> bytes:
    parsed = urlparse(source_uri)
    if parsed.scheme == "file":
        return Path(url2pathname(parsed.path)).read_bytes()
    if parsed.scheme in ("http", "https"):
        if fetcher is not None:
            return fetcher(source_uri)
        with urlopen(source_uri, timeout=120) as response:  # noqa: S310 - explicit build-time model fetch.
            return response.read()
    raise ValueError(f"unsupported source scheme: {source_uri}")


def fetch_asset(asset_root: Path, asset: VoiceAsset, *, fetcher: Fetcher | None = None) -> None:
    data = _read_source(asset.source_uri, fetcher)
    if asset.checksum_sha256:
        digest = hashlib.sha256(data).hexdigest()
        if digest.lower() != asset.checksum_sha256.lower():
            raise ValueError(f"checksum mismatch for {asset.model_id}: expected {asset.checksum_sha256}, got {digest}")
    target = _target(asset_root, asset)
    if asset.extract or _is_archive(urlparse(asset.source_uri).path):
        _extract(data, urlparse(asset.source_uri).path, target if asset.extract else target.parent)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Record the source checksum so a later build can tell this cache apart from
    # a stale/wrong one (see asset_present).
    if asset.checksum_sha256:
        marker = _marker_path(asset_root, asset)
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(hashlib.sha256(data).hexdigest(), encoding="utf-8")
        except OSError:
            pass


def missing_required(asset_root: Path, manifest: list[VoiceAsset]) -> list[str]:
    return [a.model_id for a in manifest if a.required and not asset_present(asset_root, a)]


def fetch_all(asset_root: Path, manifest: list[VoiceAsset], *, fetcher: Fetcher | None = None, skip_existing: bool = True) -> list[tuple[str, str]]:
    """Returns a list of (model_id, status) where status is fetched/skipped/failed."""
    results: list[tuple[str, str]] = []
    for asset in manifest:
        if skip_existing and asset_present(asset_root, asset):
            results.append((asset.model_id, "skipped"))
            continue
        try:
            fetch_asset(asset_root, asset, fetcher=fetcher)
            results.append((asset.model_id, "fetched"))
        except Exception as exc:  # noqa: BLE001 - report and continue; required-gate decides exit.
            results.append((asset.model_id, f"failed: {exc}"))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch and verify Marvex voice model assets.")
    parser.add_argument("--manifest", default=str(Path(__file__).resolve().parent.parent / "voice_models.manifest.json"))
    parser.add_argument("--asset-root", required=True, help="Voice-asset root the models are written under.")
    parser.add_argument("--force", action="store_true", help="Re-download even if assets already exist.")
    parser.add_argument("--require-all", action="store_true", help="Treat optional assets as required too.")
    args = parser.parse_args(argv)

    manifest = load_manifest(Path(args.manifest))
    if args.require_all:
        manifest = [VoiceAsset(**{**a.__dict__, "required": True}) for a in manifest]
    asset_root = Path(args.asset_root).resolve()
    asset_root.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {len(manifest)} voice assets into {asset_root}")
    for model_id, status in fetch_all(asset_root, manifest, skip_existing=not args.force):
        print(f"  - {model_id}: {status}")

    missing = missing_required(asset_root, manifest)
    if missing:
        print(f"ERROR: required voice assets missing after fetch: {', '.join(missing)}", file=sys.stderr)
        print("Fix the source_uri/checksum entries in voice_models.manifest.json and re-run.", file=sys.stderr)
        return 1
    print("All required voice assets present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
