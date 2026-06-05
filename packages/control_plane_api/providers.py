from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from collections.abc import Callable
from importlib import import_module
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
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
    automation_model: str = ""
    models: list[str] = field(default_factory=list)
    model_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    multi_models: list[str] = field(default_factory=list)
    base_url: str = ""
    provider_mode: str = "native"
    supports_custom_base_url: bool = False
    automation_model_capabilities: dict[str, bool] = field(default_factory=dict)
    automation_policy: dict[str, bool] = field(default_factory=lambda: {"vision_required": False})
    secret_present: bool = False
    secret_display: str = ""
    reasoning_effort: str = ""

    def projection(self) -> dict[str, Any]:
        automation_capabilities = dict(self.automation_model_capabilities)
        automation_policy = dict(self.automation_policy)
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "configured": self.configured,
            "healthy": self.healthy,
            "active_model": self.active_model,
            "automation_model": self.automation_model,
            "models": list(self.models),
            "model_metadata": {key: dict(value) for key, value in self.model_metadata.items()},
            "multi_models": list(self.multi_models),
            "base_url": self.base_url,
            "provider_mode": self.provider_mode,
            "supports_custom_base_url": self.supports_custom_base_url,
            "automation_model_capabilities": automation_capabilities,
            "automation_policy": automation_policy,
            "automation_validation": _automation_validation(
                automation_model=self.automation_model,
                capabilities=automation_capabilities,
                policy=automation_policy,
            ),
            "secret_present": self.secret_present,
            "secret_display": self.secret_display if self.secret_present else "",
            "secret_value_present": False,
            "reasoning_effort": self.reasoning_effort,
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
        persistence_path: str | None = None,
    ) -> None:
        litellm_base_url = _first_env("MARVEX_LITELLM_BASE_URL", "LITELLM_BASE_URL") or ""
        rows = providers or (
            ProviderControlState(
                provider_id="lmstudio_responses",
                label="LM Studio",
                configured=False,
                healthy=False,
                active_model="",
                automation_model="",
                models=[],
                multi_models=[],
                base_url=_first_env("MARVEX_LMSTUDIO_BASE_URL", "LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1",
                provider_mode="openai_compatible",
                supports_custom_base_url=True,
                secret_present=False,
            ),
            ProviderControlState(
                provider_id="litellm",
                label="LiteLLM / Cloud Gateway",
                configured=False,
                healthy=False,
                active_model="",
                automation_model="",
                models=[],
                multi_models=[],
                base_url=litellm_base_url,
                provider_mode="litellm_proxy" if litellm_base_url else "litellm_sdk",
                supports_custom_base_url=True,
                secret_present=False,
            ),
        )
        self._providers = {row.provider_id: row for row in rows}
        self._secrets: dict[str, str] = {}
        self.active_provider_id = rows[0].provider_id
        self._on_change = on_change
        self._model_discovery = model_discovery or _default_model_discovery
        # Persistence is opt-in. When ``persistence_path`` is provided we load
        # the prior catalog on construct and write it back on every
        # ``_changed()`` callback. Secrets are intentionally not written - the
        # user re-enters the API key on each cold start, which keeps
        # plaintext credentials off disk.
        env_path = os.environ.get("MARVEX_PROVIDER_CONTROL_STATE", "").strip()
        self._persistence_path = persistence_path or env_path or None
        if self._persistence_path:
            self._load_from_disk(self._persistence_path)

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
        self._normalize_reasoning_effort(row)
        return self._changed()

    def set_reasoning_effort(self, provider_id: str, effort: str) -> dict[str, Any]:
        row = self._provider(provider_id)
        cleaned = _normalize_responses_reasoning_effort(effort)
        metadata = row.model_metadata.get(row.active_model, {})
        options = metadata.get("reasoning_effort_options")
        allowed = _responses_reasoning_effort_options(options)
        if cleaned not in allowed:
            raise ValueError("reasoning_effort_not_supported")
        row.reasoning_effort = cleaned
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

    def set_connection(
        self,
        provider_id: str,
        *,
        base_url: str,
        provider_mode: str | None = None,
    ) -> dict[str, Any]:
        row = self._provider(provider_id)
        cleaned_base_url = str(base_url or "").strip()
        if cleaned_base_url and not _safe_provider_base_url(cleaned_base_url):
            raise ValueError("invalid_base_url")
        row.base_url = cleaned_base_url
        if provider_mode is not None:
            cleaned_mode = _clean_provider_mode(str(provider_mode))
            if not cleaned_mode:
                raise ValueError("invalid_provider_mode")
            row.provider_mode = cleaned_mode
        elif provider_id == "litellm" and cleaned_base_url:
            row.provider_mode = "litellm_proxy"
        row.supports_custom_base_url = True
        row.configured = True
        return self._changed()

    def set_automation_model(
        self,
        provider_id: str,
        *,
        model: str,
        supports_vision: bool | None = None,
        vision_required: bool | None = None,
    ) -> dict[str, Any]:
        row = self._provider(provider_id)
        cleaned_model = str(model or "").strip()
        if not cleaned_model:
            raise ValueError("model_required")
        row.automation_model = cleaned_model
        if cleaned_model not in row.models:
            row.models.append(cleaned_model)
        capabilities = dict(row.automation_model_capabilities)
        capabilities["vision"] = bool(
            _model_id_suggests_vision(cleaned_model)
            if supports_vision is None
            else supports_vision
        )
        row.automation_model_capabilities = capabilities
        policy = dict(row.automation_policy)
        if vision_required is not None:
            policy["vision_required"] = bool(vision_required)
        row.automation_policy = policy
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
        row.healthy = bool(models)
        if models:
            row.models = _dedupe([*models, *row.models])
            row.model_metadata = _default_model_metadata(
                provider_id,
                row.models,
                secret=self.secret_value(provider_id),
                base_url=row.base_url,
            )
            if row.active_model not in row.models:
                row.active_model = row.models[0]
            self._normalize_reasoning_effort(row)
            row.configured = True
        return self._changed()

    def _normalize_reasoning_effort(self, row: ProviderControlState) -> None:
        metadata = row.model_metadata.get(row.active_model, {})
        options = metadata.get("reasoning_effort_options")
        allowed = _responses_reasoning_effort_options(options)
        if isinstance(metadata, dict):
            metadata["reasoning_effort_options"] = allowed
            default_value = _normalize_responses_reasoning_effort(
                str(metadata.get("reasoning_default") or "").strip()
            )
            if default_value:
                metadata["reasoning_default"] = default_value
            elif "reasoning_default" in metadata:
                metadata.pop("reasoning_default", None)
        current = _normalize_responses_reasoning_effort(row.reasoning_effort)
        if current not in allowed:
            default = str(metadata.get("reasoning_default") or "").strip().lower()
            if default in allowed:
                row.reasoning_effort = default
            elif "medium" in allowed:
                row.reasoning_effort = "medium"
            else:
                row.reasoning_effort = allowed[0] if allowed else ""
        else:
            row.reasoning_effort = current

    def _provider(self, provider_id: str) -> ProviderControlState:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise ValueError("provider_not_found") from exc

    def _changed(self) -> dict[str, Any]:
        catalog = self.provider_catalog()
        if self._persistence_path:
            self._save_to_disk(self._persistence_path)
        if self._on_change is not None:
            self._on_change(catalog)
        return catalog

    def _load_from_disk(self, path: str) -> None:
        """Best-effort restore from prior persisted catalog.

        Secrets are never read from disk; only provider selection, configured
        flag, and the discovered model lists are restored.
        """

        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        active = data.get("active_provider_id")
        if isinstance(active, str) and active.strip() and active in self._providers:
            self.active_provider_id = active.strip()
        providers = data.get("providers")
        if not isinstance(providers, list):
            return
        for row_data in providers:
            if not isinstance(row_data, dict):
                continue
            provider_id = row_data.get("provider_id")
            if not isinstance(provider_id, str):
                continue
            row = self._providers.get(provider_id)
            if row is None:
                continue
            active_model = row_data.get("active_model")
            if isinstance(active_model, str) and active_model.strip():
                row.active_model = active_model.strip()
            automation_model = row_data.get("automation_model")
            if isinstance(automation_model, str) and automation_model.strip():
                row.automation_model = automation_model.strip()
            base_url = row_data.get("base_url")
            if isinstance(base_url, str) and (not base_url.strip() or _safe_provider_base_url(base_url)):
                row.base_url = base_url.strip()
            provider_mode = row_data.get("provider_mode")
            if isinstance(provider_mode, str):
                cleaned_mode = _clean_provider_mode(provider_mode)
                if cleaned_mode:
                    row.provider_mode = cleaned_mode
            if provider_id == "litellm" and row.base_url and row.provider_mode == "litellm_sdk":
                row.provider_mode = "litellm_proxy"
            models = row_data.get("models")
            if isinstance(models, list):
                row.models = [str(m) for m in models if isinstance(m, str) and m.strip()]
            model_metadata = row_data.get("model_metadata")
            if isinstance(model_metadata, dict):
                row.model_metadata = {
                    str(key): dict(value)
                    for key, value in model_metadata.items()
                    if isinstance(key, str) and isinstance(value, dict)
                }
            multi = row_data.get("multi_models")
            if isinstance(multi, list):
                row.multi_models = [str(m) for m in multi if isinstance(m, str) and m.strip()]
            capabilities = row_data.get("automation_model_capabilities")
            if isinstance(capabilities, dict):
                row.automation_model_capabilities = {
                    str(key): bool(value)
                    for key, value in capabilities.items()
                    if isinstance(key, str)
                }
            policy = row_data.get("automation_policy")
            if isinstance(policy, dict):
                row.automation_policy = {
                    str(key): bool(value)
                    for key, value in policy.items()
                    if isinstance(key, str)
                }
            if row_data.get("configured") is True:
                row.configured = True
            reasoning_effort = row_data.get("reasoning_effort")
            if isinstance(reasoning_effort, str):
                row.reasoning_effort = reasoning_effort.strip().lower()
            self._normalize_reasoning_effort(row)

    def _save_to_disk(self, path: str) -> None:
        """Best-effort persist of the provider catalog (no secrets)."""

        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "active_provider_id": self.active_provider_id,
            "providers": [
                {
                    "provider_id": row.provider_id,
                    "active_model": row.active_model,
                    "automation_model": row.automation_model,
                    "models": list(row.models),
                    "model_metadata": {key: dict(value) for key, value in row.model_metadata.items()},
                    "multi_models": list(row.multi_models),
                    "base_url": row.base_url,
                    "provider_mode": row.provider_mode,
                    "automation_model_capabilities": dict(row.automation_model_capabilities),
                    "automation_policy": dict(row.automation_policy),
                    "configured": row.configured,
                    "reasoning_effort": row.reasoning_effort,
                }
                for row in self._providers.values()
            ],
        }
        try:
            directory = os.path.dirname(path)
            if directory:
                os.makedirs(directory, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(snapshot, handle, sort_keys=True)
        except OSError:
            # Persistence is best-effort; never crash the control plane on
            # a write failure (filesystem full, perms, etc.).
            return

    def _discover_models(self, provider_id: str) -> list[str]:
        secret = self.secret_value(provider_id)
        try:
            row = self._provider(provider_id)
            return _dedupe(self._model_discovery(provider_id, secret, row.base_url))
        except TypeError:
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
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/reasoning") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/reasoning")
            body = _read_json(environ)
            return "200 OK", _safe_catalog(
                control.set_reasoning_effort(
                    provider_id,
                    str(body.get("effort") or "").strip(),
                )
            )
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/connection") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/connection")
            body = _read_json(environ)
            provider_mode = body.get("provider_mode")
            return "200 OK", _safe_catalog(
                control.set_connection(
                    provider_id,
                    base_url=str(body.get("base_url") or "").strip(),
                    provider_mode=str(provider_mode).strip() if provider_mode is not None else None,
                )
            )
        if path.startswith(f"{CONTROL_PROVIDERS_PREFIX}/") and path.endswith("/automation") and method == "POST":
            provider_id = _provider_path_id(path, suffix="/automation")
            body = _read_json(environ)
            supports_vision = body.get("supports_vision")
            vision_required = body.get("vision_required")
            return "200 OK", _safe_catalog(
                control.set_automation_model(
                    provider_id,
                    model=str(body.get("model") or "").strip(),
                    supports_vision=supports_vision if isinstance(supports_vision, bool) else None,
                    vision_required=vision_required if isinstance(vision_required, bool) else None,
                )
            )
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


def _clean_provider_mode(value: str) -> str:
    cleaned = value.strip()
    return cleaned if cleaned in {"native", "litellm_sdk", "litellm_proxy", "openai_compatible"} else ""


def _safe_provider_base_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _model_id_suggests_vision(model: str) -> bool:
    normalized = "".join(character.lower() if character.isalnum() else "-" for character in model)
    markers = (
        "vision",
        "visual",
        "multimodal",
        "omni",
        "gpt-4o",
        "gpt-5",
        "gemini",
        "qwen-vl",
        "qwen2-vl",
        "qwen2-5-vl",
        "qwen3-vl",
        "pixtral",
        "llava",
        "vl-",
        "-vl",
    )
    return any(marker in normalized for marker in markers)


def _automation_validation(
    *,
    automation_model: str,
    capabilities: dict[str, bool],
    policy: dict[str, bool],
) -> dict[str, object]:
    if not automation_model.strip():
        return {"ready": False, "reason_code": "automation_model_required"}
    if policy.get("vision_required") and not capabilities.get("vision"):
        return {"ready": False, "reason_code": "automation_vision_model_required"}
    return {"ready": True, "reason_code": None}


def _default_model_discovery(provider_id: str, secret: str | None = None, base_url: str | None = None) -> list[str]:
    if provider_id == "lmstudio_responses":
        effective_base_url = base_url or _first_env("MARVEX_LMSTUDIO_BASE_URL", "LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"
        return _openai_compatible_models(effective_base_url, api_key=secret)
    if provider_id == "litellm":
        configured = _split_models(
            _first_env("MARVEX_LITELLM_MODELS", "LITELLM_MODELS", "LITELLM_MODEL")
        )
        effective_base_url = base_url or _first_env("MARVEX_LITELLM_BASE_URL", "LITELLM_BASE_URL")
        if effective_base_url:
            configured.extend(_openai_compatible_models(effective_base_url, api_key=secret or _first_env("MARVEX_LITELLM_API_KEY", "LITELLM_API_KEY")))
        configured.extend(_litellm_sdk_models(api_key=secret or _first_env("MARVEX_LITELLM_API_KEY", "LITELLM_API_KEY"), api_base=effective_base_url))
        return _dedupe(configured)
    return []


def _default_model_metadata(
    provider_id: str,
    models: list[str],
    *,
    secret: str | None = None,
    base_url: str | None = None,
) -> dict[str, dict[str, Any]]:
    if provider_id == "lmstudio_responses":
        effective_base_url = base_url or _first_env("MARVEX_LMSTUDIO_BASE_URL", "LMSTUDIO_BASE_URL") or "http://127.0.0.1:1234/v1"
        return _lmstudio_model_metadata(effective_base_url, api_key=secret)
    if provider_id == "litellm":
        return _litellm_model_metadata(models, api_base=base_url)
    return {}


def _lmstudio_model_metadata(base_url: str, *, api_key: str | None = None) -> dict[str, dict[str, Any]]:
    parsed = urlparse(base_url.strip())
    url = f"{parsed.scheme}://{parsed.netloc}/api/v1/models"
    headers: dict[str, str] = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        with urlopen(Request(url, headers=headers), timeout=2.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return {}
    items = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("key") or item.get("id") or "").strip()
        if not model_id:
            continue
        context_window = item.get("max_context_length")
        loaded = item.get("loaded_instances")
        if isinstance(loaded, list) and loaded:
            config = loaded[0].get("config") if isinstance(loaded[0], dict) else None
            if isinstance(config, dict) and isinstance(config.get("context_length"), int):
                context_window = config["context_length"]
        capabilities = item.get("capabilities")
        reasoning = capabilities.get("reasoning") if isinstance(capabilities, dict) else None
        allowed_options = reasoning.get("allowed_options") if isinstance(reasoning, dict) else None
        reasoning_options = _responses_reasoning_effort_options(allowed_options)
        reasoning_default = ""
        if isinstance(reasoning, dict):
            candidate = _normalize_responses_reasoning_effort(
                str(reasoning.get("default") or reasoning.get("default_option") or "").strip()
            )
            if candidate in reasoning_options:
                reasoning_default = candidate
        row: dict[str, Any] = {
            "supports_reasoning": bool(reasoning_options),
            "supports_reasoning_summary": False,
            "reasoning_effort_options": _dedupe(reasoning_options),
        }
        if reasoning_default:
            row["reasoning_default"] = reasoning_default
        if isinstance(context_window, int) and context_window > 0:
            row["context_window"] = context_window
        metadata[model_id] = row
    return metadata


def _litellm_model_metadata(models: list[str], *, api_base: str | None) -> dict[str, dict[str, Any]]:
    try:
        litellm = import_module("litellm")
        get_model_info = getattr(litellm, "get_model_info")
    except Exception:
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for model in models:
        info = None
        for candidate in _litellm_model_info_candidates(model):
            try:
                info = get_model_info(candidate, api_base=api_base)
            except Exception:
                continue
            if isinstance(info, dict):
                break
        if not isinstance(info, dict):
            continue
        supports_reasoning = info.get("supports_reasoning") is True
        options: list[str] = []
        if supports_reasoning:
            if info.get("supports_none_reasoning_effort") is True:
                options.append("none")
            if info.get("supports_minimal_reasoning_effort") is True:
                options.append("minimal")
            options.extend(["low", "medium", "high"])
            if info.get("supports_xhigh_reasoning_effort") is True or info.get("supports_max_reasoning_effort") is True:
                options.append("xhigh")
        context_window = info.get("max_input_tokens") or info.get("max_tokens")
        row: dict[str, Any] = {
            "supports_reasoning": supports_reasoning,
            "supports_reasoning_summary": supports_reasoning and info.get("litellm_provider") == "openai",
            "reasoning_effort_options": _dedupe(options),
        }
        if isinstance(context_window, int) and context_window > 0:
            row["context_window"] = context_window
        metadata[model] = row
    return metadata


def _litellm_model_info_candidates(model: str) -> list[str]:
    candidates = [model]
    tail = model.rsplit("/", 1)[-1]
    if tail != model:
        candidates.extend([tail, f"openai/{tail}"])
    return _dedupe(candidates)


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


def _normalize_responses_reasoning_effort(value: str | None) -> str:
    cleaned = str(value or "").strip().lower()
    aliases = {
        "off": "none",
        "on": "medium",
        "max": "xhigh",
    }
    cleaned = aliases.get(cleaned, cleaned)
    return cleaned if cleaned in {"none", "minimal", "low", "medium", "high", "xhigh"} else ""


def _responses_reasoning_effort_options(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return _dedupe(
        [
            normalized
            for value in values
            if (normalized := _normalize_responses_reasoning_effort(str(value)))
        ]
    )


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
