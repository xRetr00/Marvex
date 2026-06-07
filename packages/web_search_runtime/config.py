from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel


DEFAULT_SEARXNG_BASE_URL = "http://127.0.0.1:8888"
WEB_SEARCH_STATE_ENV = "MARVEX_WEB_SEARCH_STATE"


class WebSearchSettings(CapabilityRuntimeModel):
    schema_version: str = "1"
    primary_provider: str = "searxng"
    fallback_provider: str = "ddgs"
    searxng_base_url: str = Field(default=DEFAULT_SEARXNG_BASE_URL, min_length=1, max_length=500)
    raw_payload_persisted: bool = False

    @property
    def provider_order(self) -> tuple[str, str]:
        return (self.primary_provider, self.fallback_provider)

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider,
            "provider_order": list(self.provider_order),
            "searxng_base_url": self.searxng_base_url,
            "raw_payload_persisted": False,
        }


class WebSearchSettingsStore:
    def __init__(self, *, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else _default_state_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> WebSearchSettings:
        try:
            if not self._path.exists():
                return WebSearchSettings()
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return WebSearchSettings()
            return WebSearchSettings.model_validate(data)
        except Exception:
            return WebSearchSettings()

    def save(self, settings: WebSearchSettings) -> WebSearchSettings:
        normalized = WebSearchSettings(
            searxng_base_url=_normalize_base_url(settings.searxng_base_url),
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(normalized.model_dump(mode="json"), sort_keys=True, indent=2), encoding="utf-8")
        return normalized

    def update(self, payload: dict[str, Any]) -> WebSearchSettings:
        current = self.load()
        base_url = payload.get("searxng_base_url", current.searxng_base_url)
        return self.save(current.model_copy(update={"searxng_base_url": _normalize_base_url(str(base_url))}))


def _normalize_base_url(value: str) -> str:
    cleaned = value.strip().rstrip("/")
    if not cleaned:
        return DEFAULT_SEARXNG_BASE_URL
    if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
        raise ValueError("searxng_base_url must start with http:// or https://")
    return cleaned


def _default_state_path() -> Path:
    explicit = os.environ.get(WEB_SEARCH_STATE_ENV)
    if explicit:
        return Path(explicit)
    return Path(".marvex-web-search.json")
