from typing import Any

from .models import (
    AssistantFinalResponse,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorEnvelope,
    FinalResponse,
    HealthCheck,
    InputEvent,
    ProviderRequest,
    ProviderResponse,
    TraceEvent,
    TurnInput,
    TurnOutput,
    VersionInfo,
)


CONTRACT_MODELS = {
    "TurnInput": TurnInput,
    "TurnOutput": TurnOutput,
    "FinalResponse": FinalResponse,
    "ProviderRequest": ProviderRequest,
    "ProviderResponse": ProviderResponse,
    "TraceEvent": TraceEvent,
    "ErrorEnvelope": ErrorEnvelope,
    "HealthCheck": HealthCheck,
    "VersionInfo": VersionInfo,
    "InputEvent": InputEvent,
    "AssistantTurnInput": AssistantTurnInput,
    "AssistantTurnResult": AssistantTurnResult,
    "AssistantFinalResponse": AssistantFinalResponse,
}


def contract_schemas() -> dict[str, dict[str, Any]]:
    return {name: model.model_json_schema() for name, model in CONTRACT_MODELS.items()}
