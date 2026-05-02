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
        "InputEvent",
        "AssistantTurnInput",
        "AssistantTurnResult",
        "AssistantFinalResponse",
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
    assert set(schemas["InputEvent"]["required"]) == {
        "schema_version",
        "trace_id",
        "event_id",
        "source",
        "input_modality",
        "payload",
        "payload_ref",
        "session_ref",
        "privacy",
        "timestamp",
        "metadata",
    }
    assert set(schemas["AssistantTurnInput"]["required"]) == {
        "schema_version",
        "trace_id",
        "turn_id",
        "input_event_id",
        "session_ref",
        "identity_ref",
        "user_visible_input",
        "assistant_mode",
        "policy_context",
        "metadata",
    }
    assert set(schemas["AssistantTurnResult"]["required"]) == {
        "schema_version",
        "trace_id",
        "turn_id",
        "assistant_final_response",
        "output_events",
        "stage_summaries",
        "provider_turn_refs",
        "tool_result_refs",
        "memory_result_refs",
        "session_result_ref",
        "error",
        "metadata",
    }
    assert set(schemas["AssistantFinalResponse"]["required"]) == {
        "schema_version",
        "response_type",
        "text",
        "payload_ref",
        "output_channel_intent",
        "safe_for_display",
        "safe_for_speech",
        "memory_write_candidate_hint",
        "finish_reason",
        "metadata",
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
