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
        "source",
        "metadata",
    }
    assert "previous_response_id" in schemas["ProviderRequest"]["required"]
    assert "provider_response_id" in schemas["TurnOutput"]["required"]
    assert "error" in schemas["ProviderResponse"]["required"]
    assert "code" in schemas["ErrorEnvelope"]["required"]


def test_json_schemas_reject_extra_properties():
    schemas = contract_schemas()

    for schema in schemas.values():
        assert schema["additionalProperties"] is False
