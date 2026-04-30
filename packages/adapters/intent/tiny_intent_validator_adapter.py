from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from packages.contracts.intent_models import IntentDecision
from packages.contracts.intent_validation_models import IntentValidationResult


@dataclass(frozen=True)
class AdapterModelUnavailableError(RuntimeError):
    model_name: str
    adapter_name: str
    dependency_name: str | None = None
    reason_code: str = "model_unavailable"

    def __str__(self) -> str:
        dependency = f" dependency unavailable: {self.dependency_name}" if self.dependency_name else ""
        return f"{self.adapter_name} model unavailable: {self.model_name}{dependency}"


class TinyIntentValidatorAdapter:
    def __init__(self, model_client: Any) -> None:
        self._model_client = model_client

    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        raw_result = self._model_client.validate_intent(
            {
                "input_text": input_text,
                "route_family": intent_decision.route_family.value,
                "confidence": intent_decision.confidence,
                "ambiguity_flag": intent_decision.ambiguity_flag,
            }
        )
        return IntentValidationResult.model_validate(self._result_mapping(raw_result))

    @classmethod
    def from_library(
        cls,
        model_name: str = "LiquidAI/LFM2.5-350M",
        importer: Callable[[str], Any] = importlib.import_module,
    ) -> "TinyIntentValidatorAdapter":
        try:
            importer("transformers")
        except ModuleNotFoundError as exc:
            raise AdapterModelUnavailableError(
                model_name=model_name,
                adapter_name="TinyIntentValidatorAdapter",
                dependency_name="transformers",
            ) from exc

        raise AdapterModelUnavailableError(
            model_name=model_name,
            adapter_name="TinyIntentValidatorAdapter",
            reason_code="model_runtime_not_configured",
        )

    @staticmethod
    def _result_mapping(raw_result: Any) -> Mapping[str, Any]:
        if isinstance(raw_result, Mapping):
            return raw_result
        if hasattr(raw_result, "model_dump"):
            return raw_result.model_dump()
        raise TypeError("tiny intent validator result must be a mapping or pydantic model")
