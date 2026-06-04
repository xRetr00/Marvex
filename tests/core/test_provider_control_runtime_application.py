from __future__ import annotations

from services.core.main import _apply_provider_control


class _Executor:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def configure_provider(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


class _Service:
    def __init__(self) -> None:
        self._turn_executor = _Executor()


class _ProviderControl:
    def secret_value(self, provider_id: str) -> str:
        assert provider_id == "litellm"
        return "sk-live-secret"


def test_apply_provider_control_passes_connection_and_automation_model() -> None:
    service = _Service()
    catalog = {
        "active_provider_id": "litellm",
        "providers": [
            {
                "provider_id": "litellm",
                "active_model": "anthropic/claude-sonnet-4-5",
                "automation_model": "openai/gpt-4o",
                "base_url": "http://localhost:20128/v1",
                "provider_mode": "openai_compatible",
                "automation_model_capabilities": {"vision": True},
                "automation_policy": {"vision_required": True},
                "automation_validation": {"ready": True, "reason_code": None},
                "model_metadata": {
                    "anthropic/claude-sonnet-4-5": {
                        "context_window": 200000,
                        "supports_reasoning": True,
                        "supports_reasoning_summary": False,
                        "reasoning_effort_options": ["low", "medium", "high"],
                    }
                },
                "reasoning_effort": "high",
            }
        ],
    }

    _apply_provider_control(service, catalog, _ProviderControl())

    assert service._turn_executor.calls == [
        {
            "provider_name": "litellm",
            "model": "anthropic/claude-sonnet-4-5",
            "provider_secret": "sk-live-secret",
            "base_url": "http://localhost:20128/v1",
            "provider_mode": "openai_compatible",
            "automation_model": "openai/gpt-4o",
            "automation_model_supports_vision": True,
            "automation_vision_required": True,
            "provider_options": {"reasoning_effort": "high"},
            "model_context_window": 200000,
        }
    ]
