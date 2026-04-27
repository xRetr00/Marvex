from packages.contracts import contract_schemas


def test_contract_schemas_include_all_v1_contracts():
    schemas = contract_schemas()

    assert set(schemas) == {
        "TurnInput",
        "TurnOutput",
        "FinalResponse",
        "ProviderRequest",
        "ProviderResponse",
        "TraceEvent",
        "ErrorEnvelope",
        "HealthCheck",
        "VersionInfo",
    }


def test_json_schemas_mark_documented_fields_required():
    schemas = contract_schemas()

    assert set(schemas["TurnInput"]["required"]) == {
        "schema_version",
        "trace_id",
        "turn_id",
        "input_text",
        "previous_response_id",
        "source",
        "metadata",
    }
    assert "previous_response_id" in schemas["ProviderRequest"]["required"]
    assert "provider_response_id" in schemas["TurnOutput"]["required"]
    assert "error" in schemas["ProviderResponse"]["required"]
    assert "code" in schemas["ErrorEnvelope"]["required"]
    assert set(schemas["HealthCheck"]["required"]) == {
        "schema_version",
        "service",
        "status",
        "version",
        "uptime_seconds",
        "dependencies",
    }
    assert set(schemas["VersionInfo"]["required"]) == {
        "schema_version",
        "service",
        "service_version",
        "contract_versions",
        "build",
    }


def test_json_schemas_reject_extra_properties():
    schemas = contract_schemas()

    for schema in schemas.values():
        assert schema["additionalProperties"] is False


def test_health_check_schema_defines_allowed_status_values():
    health_status = contract_schemas()["HealthCheck"]["$defs"]["HealthStatus"]

    assert health_status["enum"] == [
        "ok",
        "degraded",
        "starting",
        "stopping",
        "error",
    ]


def test_health_check_schema_requires_non_negative_uptime():
    uptime = contract_schemas()["HealthCheck"]["properties"]["uptime_seconds"]

    assert uptime["minimum"] == 0
