from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import json
import os
import secrets
from types import MappingProxyType
from typing import Mapping


SCHEMA_VERSION = "0.1.1-draft"
DEFAULT_SERVICE_NAME = "marvex-local-api"
DEFAULT_SERVICE_VERSION = "0.1.0"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
TOKEN_BYTES = 32


class DiscoveryMode(StrEnum):
    DISABLED = "disabled"
    EXPLICIT_CONFIG = "explicit_config"
    FUTURE_LOCAL_FILE = "future_local_file"


def generate_local_bearer_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _isoformat_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _readonly_copy(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(dict(value))


@dataclass(frozen=True)
class LocalApiServiceStartupConfig:
    bind_host: str = DEFAULT_BIND_HOST
    port: int = DEFAULT_PORT
    service: str = DEFAULT_SERVICE_NAME
    service_version: str = DEFAULT_SERVICE_VERSION
    schema_version: str = SCHEMA_VERSION
    discovery_mode: DiscoveryMode = DiscoveryMode.DISABLED
    discovery_file_path: str | None = None
    contract_versions: Mapping[str, object] = field(
        default_factory=lambda: {"LocalApiStartup": SCHEMA_VERSION}
    )
    local_auth_token: str | None = field(default=None, repr=False)
    started_at: datetime = field(default_factory=_utc_now)
    process_id: int | None = None

    def __post_init__(self) -> None:
        if self.bind_host != DEFAULT_BIND_HOST:
            raise ValueError("bind_host must be 127.0.0.1")
        if not isinstance(self.port, int) or self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")
        if not self.service.strip():
            raise ValueError("service must be non-empty")
        if self.local_auth_token is not None and not self.local_auth_token.strip():
            raise ValueError("local_auth_token must be non-empty when provided")
        object.__setattr__(
            self, "discovery_mode", DiscoveryMode(self.discovery_mode)
        )
        object.__setattr__(self, "contract_versions", _readonly_copy(self.contract_versions))


@dataclass(frozen=True)
class ShutdownSemantics:
    startup_explicit: bool = True
    shutdown_explicit: bool = True
    daemon_loop_started: bool = False
    auto_restart_enabled: bool = False
    supervisor_started: bool = False


@dataclass(frozen=True)
class LocalApiStartupMetadata:
    schema_version: str
    service: str
    base_url: str
    bind_host: str
    port: int
    auth_required: bool
    auth_token_present: bool
    token_value_logged: bool
    discovery_mode: DiscoveryMode
    discovery_file_path: str | None
    process_id: int
    started_at: str
    contract_versions: Mapping[str, object]
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "service": self.service,
            "base_url": self.base_url,
            "bind_host": self.bind_host,
            "port": self.port,
            "auth_required": self.auth_required,
            "auth_token_present": self.auth_token_present,
            "token_value_logged": self.token_value_logged,
            "discovery_mode": self.discovery_mode.value,
            "discovery_file_path": self.discovery_file_path,
            "process_id": self.process_id,
            "started_at": self.started_at,
            "contract_versions": dict(self.contract_versions),
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class LocalApiStartupResult:
    local_auth_token: str = field(repr=False)
    _public_metadata: LocalApiStartupMetadata
    shutdown_semantics: ShutdownSemantics = field(default_factory=ShutdownSemantics)

    def public_metadata(self) -> LocalApiStartupMetadata:
        return self._public_metadata


def create_local_api_startup(
    config: LocalApiServiceStartupConfig | None = None,
) -> LocalApiStartupResult:
    startup_config = config or LocalApiServiceStartupConfig()
    local_auth_token = startup_config.local_auth_token or generate_local_bearer_token()
    warnings = _warnings_for(startup_config)
    metadata = LocalApiStartupMetadata(
        schema_version=startup_config.schema_version,
        service=startup_config.service,
        base_url=f"http://{startup_config.bind_host}:{startup_config.port}",
        bind_host=startup_config.bind_host,
        port=startup_config.port,
        auth_required=True,
        auth_token_present=bool(local_auth_token),
        token_value_logged=False,
        discovery_mode=startup_config.discovery_mode,
        discovery_file_path=startup_config.discovery_file_path,
        process_id=startup_config.process_id or os.getpid(),
        started_at=_isoformat_z(startup_config.started_at),
        contract_versions=startup_config.contract_versions,
        warnings=warnings,
    )
    return LocalApiStartupResult(
        local_auth_token=local_auth_token,
        _public_metadata=metadata,
    )


def _warnings_for(config: LocalApiServiceStartupConfig) -> tuple[str, ...]:
    if config.discovery_mode == DiscoveryMode.FUTURE_LOCAL_FILE:
        return ("discovery_file_write_blocked",)
    return ()

