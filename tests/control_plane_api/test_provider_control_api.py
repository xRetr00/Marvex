from __future__ import annotations

import json

from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
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
