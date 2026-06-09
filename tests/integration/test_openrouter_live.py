from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest

from packages.contracts import FinishReason, ProviderRequest
from packages.provider_runtime import ProviderRuntimeConfig, create_provider


SCHEMA_VERSION = "0.1.1-draft"
DEFAULT_OPENROUTER_FREE_MODEL = "openai/gpt-oss-20b:free"
PROJECT_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _project_env_value(name: str) -> str | None:
    if not PROJECT_ENV_PATH.exists():
        return None
    for raw_line in PROJECT_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != name:
            continue
        cleaned = value.strip().strip('"').strip("'")
        return cleaned or None
    return None


def _config_value(name: str) -> str | None:
    value = os.environ.get(name)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _project_env_value(name)


def _openrouter_api_key() -> str | None:
    for name in ("MARVEX_OPENROUTER_API_KEY", "OPENROUTER_API_KEY"):
        value = _config_value(name)
        if value:
            return value
    return None


@pytest.mark.live
def test_openrouter_provider_live_responses_smoke() -> None:
    api_key = _openrouter_api_key()
    if api_key is None:
        pytest.skip("set MARVEX_OPENROUTER_API_KEY or OPENROUTER_API_KEY for live OpenRouter smoke")

    provider = create_provider(
        ProviderRuntimeConfig(
            provider_name="openrouter",
            openrouter_api_key=api_key,
            timeout_seconds=45,
        )
    )
    trace_id = f"trace-live-openrouter-{uuid4()}"
    request = ProviderRequest(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        turn_id=f"turn-live-openrouter-{uuid4()}",
        model=_config_value("MARVEX_OPENROUTER_SMOKE_MODEL") or DEFAULT_OPENROUTER_FREE_MODEL,
        input_text="Reply with one short sentence containing the exact token marvex-openrouter-ok.",
        instructions="Keep the response short.",
        previous_response_id=None,
        provider_options={"max_output_tokens": 32, "temperature": 0},
    )

    response = provider.send(request)

    assert response.error is None, response.error.message if response.error else ""
    assert response.finish_reason in {FinishReason.STOP, FinishReason.UNKNOWN}
    assert response.raw_metadata["api_surface"] == "responses"
    assert response.output_text.strip()
    assert "marvex-openrouter-ok" in response.output_text.lower()
