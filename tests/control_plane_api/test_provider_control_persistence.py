"""Tests for InMemoryProviderControl on-disk persistence.

The Control Plane lost the active provider/model choice on every Core
restart because InMemoryProviderControl had no persistence layer. These
tests verify the new opt-in persistence path round-trips the catalog
without ever writing secrets.
"""

from pathlib import Path
import json

import pytest

pytest.importorskip("fastapi", reason="control_plane_api requires fastapi")

from packages.control_plane_api.providers import InMemoryProviderControl


def test_persistence_path_disabled_when_unset(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MARVEX_PROVIDER_CONTROL_STATE", raising=False)
    control = InMemoryProviderControl()
    control.set_active_provider("litellm")
    # No persistence path => no file written anywhere we can check.
    assert not any(tmp_path.iterdir())


def test_explicit_persistence_path_round_trips_active_provider(tmp_path: Path) -> None:
    state = tmp_path / "provider_control.json"
    first = InMemoryProviderControl(persistence_path=str(state))
    first.set_active_provider("litellm")
    first.set_active_model("litellm", "openrouter/anthropic/claude-3.5-sonnet")
    assert state.exists()

    second = InMemoryProviderControl(persistence_path=str(state))
    catalog = second.provider_catalog()
    assert catalog["active_provider_id"] == "litellm"
    litellm_row = next(row for row in catalog["providers"] if row["provider_id"] == "litellm")
    assert litellm_row["active_model"] == "openrouter/anthropic/claude-3.5-sonnet"
    assert litellm_row["configured"] is True


def test_env_override_picks_up_persistence_path(tmp_path: Path, monkeypatch) -> None:
    state = tmp_path / "via_env.json"
    monkeypatch.setenv("MARVEX_PROVIDER_CONTROL_STATE", str(state))
    control = InMemoryProviderControl()
    control.set_active_provider("lmstudio_responses")
    control.set_active_model("lmstudio_responses", "qwen2.5-coder-7b")
    assert state.exists()

    monkeypatch.setenv("MARVEX_PROVIDER_CONTROL_STATE", str(state))
    restored = InMemoryProviderControl()
    catalog = restored.provider_catalog()
    assert catalog["active_provider_id"] == "lmstudio_responses"
    lmstudio_row = next(row for row in catalog["providers"] if row["provider_id"] == "lmstudio_responses")
    assert lmstudio_row["active_model"] == "qwen2.5-coder-7b"


def test_secret_value_is_never_written_to_disk(tmp_path: Path) -> None:
    state = tmp_path / "secrets_check.json"
    control = InMemoryProviderControl(persistence_path=str(state))
    control.set_secret("litellm", "sk-or-shouldnotbepersisted-12345")
    contents = state.read_text(encoding="utf-8")
    assert "sk-or-shouldnotbepersisted-12345" not in contents
    assert "secret_present" not in contents  # row projection skipped entirely


def test_unknown_persistence_file_does_not_crash(tmp_path: Path) -> None:
    state = tmp_path / "does_not_exist_yet.json"
    control = InMemoryProviderControl(persistence_path=str(state))
    # First mutation writes the file; nothing should raise.
    control.set_active_provider("litellm")
    assert state.exists()


def test_malformed_persistence_file_is_ignored(tmp_path: Path) -> None:
    state = tmp_path / "malformed.json"
    state.write_text("this is not json {", encoding="utf-8")
    control = InMemoryProviderControl(persistence_path=str(state))
    # Falls back to default catalog; first provider id stays active.
    assert control.active_provider_id == "lmstudio_responses"


def test_persistence_preserves_model_list(tmp_path: Path) -> None:
    state = tmp_path / "models.json"
    first = InMemoryProviderControl(persistence_path=str(state))
    first.set_multi_models("litellm", ["openrouter/anthropic/claude-3.5-sonnet", "openrouter/openai/gpt-4o"])

    second = InMemoryProviderControl(persistence_path=str(state))
    litellm_row = next(row for row in second.provider_catalog()["providers"] if row["provider_id"] == "litellm")
    assert "openrouter/anthropic/claude-3.5-sonnet" in litellm_row["models"]
    assert litellm_row["multi_models"] == [
        "openrouter/anthropic/claude-3.5-sonnet",
        "openrouter/openai/gpt-4o",
    ]


def test_persistence_migrates_litellm_proxy_base_url_from_sdk_mode(tmp_path: Path) -> None:
    state = tmp_path / "providers.json"
    state.write_text(
        json.dumps(
            {
                "active_provider_id": "litellm",
                "providers": [
                    {
                        "provider_id": "litellm",
                        "base_url": "http://localhost:4000/v1",
                        "provider_mode": "litellm_sdk",
                        "configured": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    control = InMemoryProviderControl(persistence_path=str(state))
    row = next(item for item in control.provider_catalog()["providers"] if item["provider_id"] == "litellm")

    assert row["base_url"] == "http://localhost:4000/v1"
    assert row["provider_mode"] == "litellm_proxy"


def test_persistence_migrates_litellm_proxy_base_url_from_native_mode(tmp_path: Path) -> None:
    state = tmp_path / "providers.json"
    state.write_text(
        json.dumps(
            {
                "active_provider_id": "litellm",
                "providers": [
                    {
                        "provider_id": "litellm",
                        "base_url": "https://openrouter.ai/api/v1/",
                        "provider_mode": "native",
                        "configured": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    control = InMemoryProviderControl(persistence_path=str(state))
    row = next(item for item in control.provider_catalog()["providers"] if item["provider_id"] == "litellm")

    assert row["base_url"] == "https://openrouter.ai/api/v1/"
    assert row["provider_mode"] == "litellm_proxy"
