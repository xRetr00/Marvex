from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .startup import LocalApiStartupMetadata


@dataclass(frozen=True)
class LocalApiDiscoveryWriteResult:
    discovery_file_path: str
    token_value_written: bool = False


def write_local_api_discovery_metadata(
    metadata: LocalApiStartupMetadata,
    *,
    discovery_file_path: str,
    local_user_root: str | Path | None = None,
) -> LocalApiDiscoveryWriteResult:
    root = _resolve_local_user_root(local_user_root)
    path = Path(discovery_file_path).expanduser().resolve()
    if not _is_relative_to(path, root):
        raise ValueError("discovery_file_path must be local-user scoped")

    payload = metadata.to_dict()
    _validate_safe_discovery_payload(payload)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return LocalApiDiscoveryWriteResult(discovery_file_path=str(path))


def _resolve_local_user_root(local_user_root: str | Path | None) -> Path:
    if local_user_root is None:
        return Path.home().resolve()
    return Path(local_user_root).expanduser().resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_safe_discovery_payload(payload: dict[str, Any]) -> None:
    if payload.get("bind_host") != "127.0.0.1":
        raise ValueError("discovery metadata must be loopback-only")
    if payload.get("base_url") != f"http://127.0.0.1:{payload.get('port')}":
        raise ValueError("discovery metadata must use loopback base_url")
    if payload.get("token_value_logged") is not False:
        raise ValueError("discovery metadata must not log token values")

    serialized = json.dumps(payload, sort_keys=True).lower()
    forbidden_fragments = (
        "local_auth_token",
        "bearer ",
        "api_key",
        "apikey",
        "provider_token",
        "0.0.0.0",
    )
    for fragment in forbidden_fragments:
        if fragment in serialized:
            raise ValueError("discovery metadata contains unsafe fields")
