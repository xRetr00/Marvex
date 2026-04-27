from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.contracts import HealthCheck, HealthStatus, VersionInfo
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig


def fixed_clock(value: datetime):
    return lambda: value


def make_config(**overrides) -> ProcessRuntimeConfig:
    started_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
    values = {
        "service_name": "core",
        "service_version": "0.1.0",
        "started_at": started_at,
        "clock": fixed_clock(started_at + timedelta(seconds=3.5)),
        "contract_versions": {"HealthCheck": "0.1.1-draft"},
        "build": {"git": "abc123"},
        "dependencies": {"provider": {"status": "not_probed"}},
    }
    values.update(overrides)
    return ProcessRuntimeConfig(**values)


def test_get_health_returns_valid_health_check():
    health = HealthVersionProvider(make_config()).get_health()

    validated = HealthCheck.model_validate(health.model_dump())
    assert validated.schema_version == "0.1.1-draft"
    assert validated.service == "core"
    assert validated.status == HealthStatus.OK
    assert validated.version == "0.1.0"
    assert validated.uptime_seconds == 3.5
    assert validated.dependencies == {"provider": {"status": "not_probed"}}


def test_get_version_returns_valid_version_info():
    version = HealthVersionProvider(make_config()).get_version()

    validated = VersionInfo.model_validate(version.model_dump())
    assert validated.schema_version == "0.1.1-draft"
    assert validated.service == "core"
    assert validated.service_version == "0.1.0"
    assert validated.contract_versions == {"HealthCheck": "0.1.1-draft"}
    assert validated.build == {"git": "abc123"}


def test_default_status_is_ok():
    health = HealthVersionProvider(make_config()).get_health()

    assert health.status == HealthStatus.OK


def test_explicit_starting_status_is_respected():
    health = HealthVersionProvider(
        make_config(status=HealthStatus.STARTING)
    ).get_health()

    assert health.status == HealthStatus.STARTING


def test_uptime_is_deterministic_with_injected_clock():
    started_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
    config = make_config(
        started_at=started_at,
        clock=fixed_clock(started_at + timedelta(seconds=42)),
    )

    health = HealthVersionProvider(config).get_health()

    assert health.uptime_seconds == 42


def test_negative_clock_skew_clamps_uptime_to_zero():
    started_at = datetime(2026, 4, 27, 12, 0, tzinfo=UTC)
    config = make_config(
        started_at=started_at,
        clock=fixed_clock(started_at - timedelta(seconds=10)),
    )

    health = HealthVersionProvider(config).get_health()

    assert health.uptime_seconds == 0.0


def test_config_is_frozen():
    config = make_config()

    with pytest.raises(FrozenInstanceError):
        config.service_name = "other"


def test_mapping_fields_are_copied_and_returned_as_plain_json_objects():
    dependencies = {"provider": {"status": "configured"}}
    contract_versions = {"HealthCheck": "0.1.1-draft"}
    build = {"git": "abc123"}
    config = make_config(
        dependencies=dependencies,
        contract_versions=contract_versions,
        build=build,
    )

    dependencies["provider"] = {"status": "mutated"}
    contract_versions["HealthCheck"] = "mutated"
    build["git"] = "mutated"

    health = HealthVersionProvider(config).get_health()
    version = HealthVersionProvider(config).get_version()

    assert type(health.dependencies) is dict
    assert type(version.contract_versions) is dict
    assert type(version.build) is dict
    assert health.dependencies == {"provider": {"status": "configured"}}
    assert version.contract_versions == {"HealthCheck": "0.1.1-draft"}
    assert version.build == {"git": "abc123"}


def test_dependencies_are_copied_as_provided_without_probing():
    dependencies = {
        "provider": {
            "configured": True,
            "would_fail_if_probed": "not evaluated",
        }
    }

    health = HealthVersionProvider(
        make_config(dependencies=dependencies)
    ).get_health()

    assert health.dependencies == dependencies


def test_process_runtime_source_has_no_forbidden_runtime_behavior():
    source_root = Path("packages") / "process_runtime"
    source = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(source_root.rglob("*.py"))
    )
    forbidden = [
        "http.server",
        "fastapi",
        "flask",
        "uvicorn",
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "daemon",
        "supervisor",
        "threading",
        "multiprocessing",
        "asyncio",
        "open(",
        "path(",
        "os.environ",
        "getenv",
        "packages.provider_runtime",
        "packages.adapters",
        "packages.core",
        "apps.",
        "services.",
        "provider_runtime",
        "provider health",
        "provider probe",
        "cli",
        "tool",
        "memory",
        "intent",
        "voice",
        "desktop",
    ]

    assert [token for token in forbidden if token in source] == []
