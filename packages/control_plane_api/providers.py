from __future__ import annotations

import json
from dataclasses import dataclass, field
from collections.abc import Callable
from typing import Any

from .voice import _read_json


SCHEMA_VERSION = "1"
CONTROL_PROVIDERS_PREFIX = "/control/providers"


@dataclass
class ProviderControlState:
    provider_id: str
    label: str
    configured: bool = False
    healthy: bool = False
    active_model: str = ""
    models: list[str] = field(default_factory=list)
    multi_models: list[str] = field(default_factory=list)
    secret_present: bool = False

    def projection(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "configured": self.configured,
            "healthy": self.healthy,
            "active_model": self.active_model,
            "models": list(self.models),
            "multi_models": list(self.multi_models),
            "secret_present": self.secret_present,
            "secret_display": "********" if self.secret_present else "",
            "secret_value_present": False,
        }


class InMemoryProviderControl:
    """Control Plane-owned provider selection state.

    This is deliberately a config/control boundary, not a provider executor.
    Core may consume the active provider/model, but these methods never run a
    turn and never return plaintext credentials.
    """

    def __init__(self, providers: tuple[ProviderControlState, ...] | None = None, on_change: Callable[[dict[str, Any]], None] | None = None) -> None:
        rows = providers or (
            ProviderControlState(
                provider_id="lmstudio_responses",
                label="LM Studio",
                configured=True,
                healthy=True,
                active_model="qwen2.5-coder-7b",
                models=["qwen2.5-coder-7b", "llama-3.1-8b", "local/default"],
                multi_models=["qwen2.5-coder-7b"],
                secret_present=True,
            ),
            ProviderControlState(
                provider_id="litellm",
                label="LiteLLM / Cloud Gateway",
                configured=False,
                healthy=False,
                active_model="openrouter/auto",
                models=["openrouter/auto", "openai/gpt-4.1", "anthropic/claude"],
                multi_models=[],
                secret_present=False,
            ),
        )
        self._providers = {row.provider_id: row for row in rows}
        self.active_provider_id = rows[0].provider_id
        self._on_change = on_change

    def provider_catalog(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "active_provider_id": self.active_provider_id,
            "providers": [row.projection() for row in self._providers.values()],
            "raw_secret_persisted": False,
        }

    def set_active_provider(self, provider_id: str) -> dict[str, Any]:
        if provider_id not in self._providers:
            raise ValueError("provider_not_found")
        self.active_provider_id = provider_id
        self._providers[provider_id].configured = True
        return self._changed()

    def set_active_model(self, provider_id: str, model: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        row.active_model = model
        row.configured = True
        if model and model not in row.models:
            row.models.append(model)
        return self._changed()

    def set_multi_models(self, provider_id: str, models: list[str]) -> dict[str, Any]:
        row = self._provider(provider_id)
        cleaned = [str(model).strip() for model in models if str(model).strip()]
        row.multi_models = cleaned
        for model in cleaned:
            if model not in row.models:
                row.models.append(model)
        row.configured = True
        return self._changed()

    def set_secret(self, provider_id: str, secret_value: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        if not secret_value.strip():
            raise ValueError("secret_required")
        row.secret_present = True
        row.configured = True
        return self._changed()

    def remove_secret(self, provider_id: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        row.secret_present = False
        return self._changed()

    def _provider(self, provider_id: str) -> ProviderControlState:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ValueError("provider_not_found") from exc

    def _changed(self) -> dict[str, Any]:
        catalog = self.provider_catalog()
        if self._on_change is not None:
            self._on_change(catalog)
        return catalog


def handle_provider_control_request(
    *,
    method: str,
    path: str,
    environ: dict[str, Any],
    provider_control: Any | None,
) -> tuple[str, dict[str, Any]] | None:
    if not path.startswith(CONTROL_PROVIDERS_PREFIX):
        return None
    control = provider_control or InMemoryProviderControl()
    try:
        if method == "GET" and path == CONTROL_PROVIDERS_PREFIX:
            return "200 OK", _safe_catalog(control.provider_catalog())
        if method == "POST" and path == f"{CONTROL_PROVIDERS_PREFIX}/active":
            body = _read_json(environ)
            provider_id = str(body.get("provider_id") or "").strip()
            return "200 OK", _safe_catalog(control.set_active_provider(provider_id))
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/models/active") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/models/active")
            body = _read_json(environ)
            model = str(body.get("model") or "").strip()
            if not model:
                raise ValueError("model_required")
            return "200 OK", _safe_catalog(control.set_active_model(provider_id, model))
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/models/multi") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/models/multi")
            body = _read_json(environ)
            models = body.get("models")
            if not isinstance(models, list):
                raise ValueError("models_required")
            return "200 OK", _safe_catalog(control.set_multi_models(provider_id, models))
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/secret"):
            provider_id = _provider_path_id(path, suffix="/secret")
            if method == "POST":
                body = _read_json(environ)
                secret = str(body.get("secret") or body.get("api_key") or "").strip()
                return "200 OK", _safe_catalog(control.set_secret(provider_id, secret))
            if method == "DELETE":
                return "200 OK", _safe_catalog(control.remove_secret(provider_id))
    except ValueError as exc:
        return "400 Bad Request", {
            "schema_version": SCHEMA_VERSION,
            "error": str(exc),
            "raw_secret_persisted": False,
        }
    return "404 Not Found", {
        "schema_version": SCHEMA_VERSION,
        "error": "provider_control_not_found",
        "raw_secret_persisted": False,
    }


def _provider_path_id(path: str, *, suffix: str) -> str:
    return path.removeprefix(f"{CONTROL_PROVIDERS_PREFIX}/").removesuffix(suffix).strip("/")


def _safe_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(payload, default=str)
    if any(part in serialized.lower() for part in ("sk-real-secret-value", "bearer ")):
        raise ValueError("unsafe_provider_payload")
    return _safe_nested(payload)


def _safe_nested(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"secret", "api_key", "apikey", "token", "authorization", "password"}:
                continue
            safe[str(key)] = _safe_nested(item)
        return safe
    if isinstance(value, list | tuple):
        return [_safe_nested(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(part in lowered for part in ("bearer ", "api_key=", "apikey=", "password=")):
            return "[redacted]"
    return value
