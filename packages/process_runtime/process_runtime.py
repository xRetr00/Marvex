from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Callable, Mapping
import copy

from packages.contracts import HealthCheck, HealthStatus, VersionInfo


SCHEMA_VERSION = "0.1.1-draft"
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _readonly_copy(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType(copy.deepcopy(dict(value)))


def _plain_copy(value: Mapping[str, object]) -> dict[str, object]:
    return copy.deepcopy(dict(value))


@dataclass(frozen=True)
class ProcessRuntimeConfig:
    service_name: str
    service_version: str
    schema_version: str = SCHEMA_VERSION
    status: HealthStatus = HealthStatus.OK
    started_at: datetime = field(default_factory=_utc_now)
    clock: Clock = _utc_now
    contract_versions: Mapping[str, object] = field(default_factory=dict)
    build: Mapping[str, object] = field(default_factory=dict)
    dependencies: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "contract_versions", _readonly_copy(self.contract_versions)
        )
        object.__setattr__(self, "build", _readonly_copy(self.build))
        object.__setattr__(self, "dependencies", _readonly_copy(self.dependencies))


class HealthVersionProvider:
    def __init__(self, config: ProcessRuntimeConfig) -> None:
        self._config = config

    def get_health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=self._config.schema_version,
            service=self._config.service_name,
            status=self._config.status,
            version=self._config.service_version,
            uptime_seconds=self._uptime_seconds(),
            dependencies=_plain_copy(self._config.dependencies),
        )

    def get_version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=self._config.schema_version,
            service=self._config.service_name,
            service_version=self._config.service_version,
            contract_versions=_plain_copy(self._config.contract_versions),
            build=_plain_copy(self._config.build),
        )

    def _uptime_seconds(self) -> float:
        return max(0.0, (self._config.clock() - self._config.started_at).total_seconds())
