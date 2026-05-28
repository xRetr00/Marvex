from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from collections.abc import Callable
from importlib import import_module
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from .voice import _read_json


SCHEMA_VERSION = "1"
CONTROL_PROVIDERS_PREFIX = "/control/providers"
ProviderModelDiscovery = Callable[..., list[str]]


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
    secret_display: str = ""

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
            "secret_display": self.secret_display if self.secret_present else "",
            "secret_value_present": False,
        }


class InMemoryProviderControl:
    """Control Plane-owned provider selection state.

    This is deliberately a config/control boundary, not a provider executor.
    Core may consume the active provider/model, but these methods never run a
    turn and never return plaintext credentials.
    """

    def __init__(
        self,
        providers: tuple[ProviderControlState, ...] | None = None,
        on_change: Callable[[dict[str, Any]], None] | None = None,
        model_discovery: ProviderModelDiscovery | None = None,
    ) -> None:
        rows = providers or (
            ProviderControlState(
                provider_id="lmstudio_responses",
                label="LM Studio",
                configured=False,
                healthy=False,
                active_model="",
                models=[],
                multi_models=[],
                secret_present=False,
            ),
            ProviderControlState(
                provider_id="litellm",
                label="LiteLLM / Cloud Gateway",
                configured=False,
                healthy=False,
                active_model="",
                models=[],
                multi_models=[],
                secret_present=False,
            ),
        )
        self._providers = {row.provider_id: row for row in rows}
        self._secrets: dict[str, str] = {}
        self.active_provider_id = rows[0].provider_id
        self._on_change = on_change
        self._model_discovery = model_discovery or _default_model_discovery

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
        row.secret_display = _mask_secret(secret_value)
        self._secrets[provider_id] = secret_value.strip()
        row.configured = True
        return self._changed()

    def remove_secret(self, provider_id: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        row.secret_present = False
        row.secret_display = ""
        self._secrets.pop(provider_id, None)
        return self._changed()

    def secret_value(self, provider_id: str) -> str | None:
        value = self._secrets.get(provider_id)
        return value if isinstance(value, str) and value.strip() else None

    def refresh_models(self, provider_id: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        models = self._discover_models(provider_id)
        if provider_id == "litellm":
            models = _dedupe([*models, "openrouter/auto"])
        row.healthy = bool(models)
        if models:
            row.models = _dedupe([*models, *row.models])
            if row.active_model not in row.models:
                row.active_model = row.models[0]
            row.configured = True
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

    def _discover_models(self, provider_id: str) -> list[str]:
        secret = self.secret_value(provider_id)
        try:
            return _dedupe(self._model_discovery(provider_id, secret))
        except TypeError:
            return _dedupe(self._model_discovery(provider_id))


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
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/models/refresh") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/models/refresh")
            if not hasattr(control, "refresh_models"):
                return "200 OK", _safe_catalog(control.provider_catalog())
            return "200 OK", _safe_catalog(control.refresh_models(provider_id))
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


def _mask_secret(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}****{cleaned[-4:]}"


def _default_model_discovery(provider_id: str, secret: str | None = None) -> list[str]:
    if provider_id == "lmstudio_responses":
        base_url = _first_env("MARVEX_LMSTUDIO_BASE_URL", "LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"
        return _openai_compatible_models(base_url, api_key=secret)
    if provider_id == "litellm":
        configured = _split_models(
            _first_env("MARVEX_LITELLM_MODELS", "LITELLM_MODELS", "LITELLM_MODEL")
        )
        base_url = _first_env("MARVEX_LITELLM_BASE_URL", "LITELLM_BASE_URL")
        if base_url:
            configured.extend(_openai_compatible_models(base_url, api_key=secret or _first_env("MARVEX_LITELLM_API_KEY", "LITELLM_API_KEY")))
        configured.extend(_litellm_sdk_models(api_key=secret or _first_env("MARVEX_LITELLM_API_KEY", "LITELLM_API_KEY"), api_base=base_url))
        return _dedupe(configured)
    return []


def _openai_compatible_models(base_url: str, *, api_key: str | None = None) -> list[str]:
    url = _models_url(base_url)
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with urlopen(Request(url, headers=headers), timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        data = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    models: list[str] = []
    for item in data:
        if isinstance(item, str) and item.strip():
            models.append(item.strip())
        if isinstance(item, dict):
            model_id = str(item.get("id") or item.get("model_name") or item.get("name") or "").strip()
            if model_id:
                models.append(model_id)
    return _dedupe(models)


def _litellm_sdk_models(*, api_key: str | None, api_base: str | None) -> list[str]:
    if not api_key and not api_base:
        return []
    try:
        litellm = import_module("litellm")
        get_valid_models = getattr(litellm, "get_valid_models")
        models = get_valid_models(api_key=api_key, api_base=api_base)
    except Exception:
        return []
    if not isinstance(models, list):
        return []
    return _dedupe([str(model) for model in models])


def _models_url(base_url: str) -> str:
    cleaned = base_url.strip().rstrip("/")
    if cleaned.endswith("/models"):
        return cleaned
    return f"{cleaned}/models"


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _split_models(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace(";", ",").replace("\n", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _dedupe(models: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for model in models:
        cleaned = str(model).strip()
        if cleaned and cleaned not in seen:
            unique.append(cleaned)
            seen.add(cleaned)
    return unique


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
