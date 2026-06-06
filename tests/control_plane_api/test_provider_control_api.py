from __future__ import annotations

import json

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore, InMemoryProviderControl
from tests.control_plane_api.asgi_helpers import asgi_call, create_control_plane_test_app


class _ProviderControl:
    def __init__(self) -> None:
        self.active_provider_id = "lmstudio_responses"
        self.active_models = {"lmstudio_responses": "qwen2.5-coder-7b", "litellm": ""}
        self.multi_models = {"lmstudio_responses": ["qwen2.5-coder-7b"], "litellm": []}
        self.secret_present = False

    def provider_catalog(self):
        return {
            "schema_version": "1",
            "active_provider_id": self.active_provider_id,
            "providers": [
                {
                    "provider_id": "lmstudio_responses",
                    "label": "LM Studio",
                    "configured": True,
                    "healthy": True,
                    "active_model": self.active_models["lmstudio_responses"],
                    "models": ["qwen2.5-coder-7b", "llama-3.1-8b"],
                    "multi_models": self.multi_models["lmstudio_responses"],
                    "secret_present": self.secret_present,
                    "secret_display": "********" if self.secret_present else "",
                },
                {
                    "provider_id": "litellm",
                    "label": "LiteLLM",
                    "configured": False,
                    "healthy": False,
                    "active_model": self.active_models["litellm"],
                    "models": ["openrouter/auto"],
                    "multi_models": self.multi_models["litellm"],
                    "secret_present": False,
                    "secret_display": "",
                },
            ],
            "raw_secret_persisted": False,
        }

    def set_active_provider(self, provider_id: str):
        self.active_provider_id = provider_id
        return self.provider_catalog()

    def set_active_model(self, provider_id: str, model: str):
        assert provider_id == self.active_provider_id
        self.active_models[provider_id] = model
        return self.provider_catalog()

    def set_multi_models(self, provider_id: str, models: list[str]):
        assert provider_id == self.active_provider_id
        self.multi_models[provider_id] = models
        return self.provider_catalog()

    def set_secret(self, provider_id: str, secret_value: str):
        assert provider_id
        assert secret_value
        self.secret_present = True
        return self.provider_catalog()

    def remove_secret(self, provider_id: str):
        assert provider_id
        self.secret_present = False
        return self.provider_catalog()


def _app(control: _ProviderControl):
    return create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        provider_control=control,
    )


def test_provider_control_catalog_and_selection_are_live_without_secret_echo() -> None:
    control = _ProviderControl()
    app = _app(control)

    status, _headers, catalog = asgi_call(app, "/control/providers")
    active_status, _headers, active = asgi_call(
        app,
        "/control/providers/active",
        method="POST",
        body={"provider_id": "litellm"},
    )
    model_status, _headers, model = asgi_call(
        app,
        "/control/providers/litellm/models/active",
        method="POST",
        body={"model": "openrouter/auto"},
    )
    multi_status, _headers, multi = asgi_call(
        app,
        "/control/providers/litellm/models/multi",
        method="POST",
        body={"models": ["openrouter/auto", "anthropic/claude"]},
    )

    assert status == "200 OK"
    assert catalog["active_provider_id"] == "lmstudio_responses"
    assert active_status == "200 OK"
    assert active["active_provider_id"] == "litellm"
    assert model_status == "200 OK"
    litellm_model = next(row for row in model["providers"] if row["provider_id"] == "litellm")
    assert litellm_model["active_model"] == "openrouter/auto"
    assert multi_status == "200 OK"
    litellm_multi = next(row for row in multi["providers"] if row["provider_id"] == "litellm")
    assert litellm_multi["multi_models"] == ["openrouter/auto", "anthropic/claude"]
    assert "api_key" not in json.dumps(multi).lower()


def test_provider_secret_update_only_returns_masked_presence() -> None:
    control = _ProviderControl()
    app = _app(control)

    status, _headers, payload = asgi_call(
        app,
        "/control/providers/lmstudio_responses/secret",
        method="POST",
        body={"secret": "sk-real-secret-value"},
    )
    remove_status, _headers, removed = asgi_call(
        app,
        "/control/providers/lmstudio_responses/secret",
        method="DELETE",
    )

    assert status == "200 OK"
    provider = payload["providers"][0]
    assert provider["secret_present"] is True
    assert provider["secret_display"] == "********"
    serialized = json.dumps(payload)
    assert "sk-real-secret-value" not in serialized
    assert remove_status == "200 OK"
    assert removed["providers"][0]["secret_present"] is False


def test_in_memory_provider_secret_projection_includes_prefix_suffix_without_raw_secret() -> None:
    control = InMemoryProviderControl()

    payload = control.set_secret("litellm", "sk-real-secret-value")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["secret_present"] is True
    assert provider["secret_display"] == "sk-r****alue"
    serialized = json.dumps(payload)
    assert "sk-real-secret-value" not in serialized


def test_in_memory_provider_model_refresh_uses_injected_loopback_discovery() -> None:
    control = InMemoryProviderControl(model_discovery=lambda provider_id: ["qwen2.5-coder-7b"] if provider_id == "lmstudio_responses" else [])

    payload = control.refresh_models("lmstudio_responses")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "lmstudio_responses")
    assert provider["healthy"] is True
    assert provider["active_model"] == "qwen2.5-coder-7b"


def test_default_litellm_model_refresh_uses_configured_model_list(monkeypatch) -> None:
    monkeypatch.setenv("MARVEX_LITELLM_MODELS", "openai/gpt-4.1-mini, openrouter/auto")
    control = InMemoryProviderControl()

    payload = control.refresh_models("litellm")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["healthy"] is True
    assert provider["active_model"] == "openai/gpt-4.1-mini"
    assert provider["models"][:2] == ["openai/gpt-4.1-mini", "openrouter/auto"]


def test_litellm_model_refresh_exposes_model_aware_reasoning_and_context(monkeypatch) -> None:
    monkeypatch.setenv("MARVEX_LITELLM_MODELS", "openai/gpt-5.4")
    control = InMemoryProviderControl()

    payload = control.refresh_models("litellm")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    metadata = provider["model_metadata"]["openai/gpt-5.4"]
    assert metadata["supports_reasoning"] is True
    assert metadata["context_window"] > 0
    assert "high" in metadata["reasoning_effort_options"]
    assert provider["reasoning_effort"] == "medium"


def test_litellm_model_refresh_does_not_inject_openrouter_when_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("MARVEX_LITELLM_MODELS", raising=False)
    monkeypatch.delenv("LITELLM_MODELS", raising=False)
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    control = InMemoryProviderControl(model_discovery=lambda provider_id: [] if provider_id == "litellm" else [])

    payload = control.refresh_models("litellm")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["healthy"] is False
    assert provider["models"] == []


def test_provider_connection_base_url_round_trips_without_secret_echo() -> None:
    control = InMemoryProviderControl()

    payload = control.set_connection(
        "litellm",
        base_url="http://localhost:20128/v1",
        provider_mode="openai_compatible",
    )

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["base_url"] == "http://localhost:20128/v1"
    assert provider["provider_mode"] == "openai_compatible"
    assert provider["supports_custom_base_url"] is True
    assert "api_key" not in json.dumps(payload).lower()


def test_litellm_connection_with_base_url_defaults_to_proxy_responses_mode() -> None:
    control = InMemoryProviderControl()

    payload = control.set_connection(
        "litellm",
        base_url="http://localhost:4000/v1",
    )

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["base_url"] == "http://localhost:4000/v1"
    assert provider["provider_mode"] == "litellm_proxy"


def test_litellm_google_ai_studio_openai_base_url_uses_sdk_responses_mode() -> None:
    control = InMemoryProviderControl()

    payload = control.set_connection(
        "litellm",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["base_url"] == ""
    assert provider["provider_mode"] == "litellm_sdk"


def test_provider_automation_model_keeps_browser_computer_choice_separate() -> None:
    control = InMemoryProviderControl()
    control.set_active_model("litellm", "openai/gpt-4.1-mini")

    payload = control.set_automation_model(
        "litellm",
        model="openai/gpt-4o",
        supports_vision=True,
        vision_required=True,
    )

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["active_model"] == "openai/gpt-4.1-mini"
    assert provider["automation_model"] == "openai/gpt-4o"
    assert provider["automation_model_capabilities"]["vision"] is True
    assert provider["automation_policy"]["vision_required"] is True
    assert provider["automation_validation"]["ready"] is True


def test_provider_automation_validation_blocks_required_vision_without_capability() -> None:
    control = InMemoryProviderControl()

    payload = control.set_automation_model(
        "litellm",
        model="qwen/qwen3-coder",
        supports_vision=False,
        vision_required=True,
    )

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["automation_validation"] == {
        "ready": False,
        "reason_code": "automation_vision_model_required",
    }


def test_provider_connection_and_automation_routes_are_exposed() -> None:
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        provider_control=InMemoryProviderControl(),
    )

    connection_status, _headers, connection = asgi_call(
        app,
        "/control/providers/litellm/connection",
        method="POST",
        body={"base_url": "http://localhost:20128/v1", "provider_mode": "openai_compatible"},
    )
    automation_status, _headers, automation = asgi_call(
        app,
        "/control/providers/litellm/automation",
        method="POST",
        body={"model": "gpt-4o", "supports_vision": True, "vision_required": True},
    )

    assert connection_status == "200 OK"
    litellm_connection = next(row for row in connection["providers"] if row["provider_id"] == "litellm")
    assert litellm_connection["base_url"] == "http://localhost:20128/v1"
    assert automation_status == "200 OK"
    litellm_automation = next(row for row in automation["providers"] if row["provider_id"] == "litellm")
    assert litellm_automation["automation_model"] == "gpt-4o"
    assert litellm_automation["automation_validation"]["ready"] is True


def test_provider_reasoning_route_updates_supported_model(monkeypatch) -> None:
    monkeypatch.setenv("MARVEX_LITELLM_MODELS", "openai/gpt-5.4")
    control = InMemoryProviderControl()
    control.refresh_models("litellm")
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        provider_control=control,
    )

    status, _headers, payload = asgi_call(
        app,
        "/control/providers/litellm/reasoning",
        method="POST",
        body={"effort": "high"},
    )

    assert status == "200 OK"
    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert provider["reasoning_effort"] == "high"


def test_snapshot_settings_include_provider_control_catalog() -> None:
    control = InMemoryProviderControl()
    control.set_active_provider("litellm")
    control.set_active_model("litellm", "openai/gpt-4.1-mini")
    app = create_control_plane_test_app(
        approval_store=InMemoryApprovalStore.from_requests(()),
        snapshot=ControlPlaneSnapshot.foundation_default(schema_version="1"),
        local_auth_token="fake-control-token",
        provider_control=control,
    )

    status, _headers, payload = asgi_call(app, "/control/snapshot")

    assert status == "200 OK"
    assert payload["settings"]["active_provider_id"] == "litellm"
    assert payload["settings"]["provider_control"]["active_provider_id"] == "litellm"
    provider = next(
        row
        for row in payload["settings"]["provider_control"]["providers"]
        if row["provider_id"] == "litellm"
    )
    assert provider["active_model"] == "openai/gpt-4.1-mini"
    assert "api_key" not in json.dumps(payload).lower()


def test_litellm_model_refresh_uses_in_memory_secret_for_sdk_discovery(monkeypatch) -> None:
    captured = {}

    def fake_import_module(name: str):
        assert name == "litellm"

        class LiteLLM:
            @staticmethod
            def get_valid_models(*, api_key=None, api_base=None):
                captured["api_key"] = api_key
                captured["api_base"] = api_base
                return ["openai/gpt-4.1-mini"]

        return LiteLLM

    monkeypatch.setattr("packages.control_plane_api.providers.import_module", fake_import_module)
    control = InMemoryProviderControl()
    control.set_secret("litellm", "sk-litellm-secret")

    payload = control.refresh_models("litellm")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "litellm")
    assert captured == {"api_key": "sk-litellm-secret", "api_base": None}
    assert provider["models"][0] == "openai/gpt-4.1-mini"
    assert "sk-litellm-secret" not in json.dumps(payload)


def test_default_lmstudio_model_refresh_reads_openai_compatible_models(monkeypatch) -> None:
    class Response:
        def __init__(self, payload: dict[str, object]):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    captured = []

    def fake_urlopen(request, timeout: float):
        captured.append({"url": request.full_url, "timeout": timeout})
        if request.full_url.endswith("/api/v1/models"):
            return Response(
                {
                    "models": [
                        {
                            "key": "local/qwen",
                            "max_context_length": 131072,
                            "capabilities": {
                                "reasoning": {
                                    "allowed_options": ["off", "low", "medium", "high", "on"],
                                    "default": "medium",
                                }
                            },
                        }
                    ]
                }
            )
        return Response({"data": [{"id": "local/qwen"}, {"id": "local/llama"}]})

    monkeypatch.setattr("packages.control_plane_api.providers.urlopen", fake_urlopen)
    monkeypatch.setenv("MARVEX_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    control = InMemoryProviderControl()

    payload = control.refresh_models("lmstudio_responses")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "lmstudio_responses")
    assert captured == [
        {"url": "http://127.0.0.1:1234/v1/models", "timeout": 2.0},
        {"url": "http://127.0.0.1:1234/api/v1/models", "timeout": 2.0},
    ]
    assert provider["healthy"] is True
    assert provider["active_model"] == "local/qwen"
    assert provider["model_metadata"]["local/qwen"] == {
        "supports_reasoning": True,
        "supports_reasoning_summary": False,
        "reasoning_effort_options": ["none", "low", "medium", "high"],
        "reasoning_default": "medium",
        "context_window": 131072,
    }
    assert provider["reasoning_effort"] == "medium"


def test_reasoning_effort_aliases_are_normalized_for_responses_api(monkeypatch) -> None:
    class Response:
        def __init__(self, payload: dict[str, object]):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self) -> bytes:
            return json.dumps(self.payload).encode("utf-8")

    def fake_urlopen(request, timeout: float):
        if request.full_url.endswith("/api/v1/models"):
            return Response(
                {
                    "models": [
                        {
                            "key": "local/gemma",
                            "capabilities": {
                                "reasoning": {
                                    "allowed_options": ["off", "on", "max"],
                                    "default": "on",
                                }
                            },
                        }
                    ]
                }
            )
        return Response({"data": [{"id": "local/gemma"}]})

    monkeypatch.setattr("packages.control_plane_api.providers.urlopen", fake_urlopen)
    monkeypatch.setenv("MARVEX_LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    control = InMemoryProviderControl()

    payload = control.refresh_models("lmstudio_responses")

    provider = next(row for row in payload["providers"] if row["provider_id"] == "lmstudio_responses")
    metadata = provider["model_metadata"]["local/gemma"]
    assert metadata["reasoning_effort_options"] == ["none", "medium", "xhigh"]
    assert metadata["reasoning_default"] == "medium"
    assert provider["reasoning_effort"] == "medium"
