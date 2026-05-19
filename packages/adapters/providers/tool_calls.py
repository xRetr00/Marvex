from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.adapters.capabilities.litellm_gateway import LiteLLMToolCallProposal, LiteLLMToolsetRef
from packages.adapters.capabilities.lmstudio import LMStudioLocalToolProposal
from packages.adapters.capabilities.openai_tools import OpenAIFunctionToolProposal

_SAFE_TOOL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")


class ProviderToolCallSource(str, Enum):
    OPENAI_COMPATIBLE = "openai_compatible"
    LMSTUDIO = "lmstudio"
    LITELLM = "litellm"


class ProviderToolCallMapperModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderToolCallMapper(ProviderToolCallMapperModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    raw_provider_payload_persisted: Literal[False] = False

    def from_openai_compatible(
        self,
        raw_tool_call: dict[str, Any],
        *,
        source: ProviderToolCallSource = ProviderToolCallSource.OPENAI_COMPATIBLE,
    ) -> OpenAIFunctionToolProposal | LMStudioLocalToolProposal:
        function = raw_tool_call.get("function") if isinstance(raw_tool_call, dict) else None
        function = function if isinstance(function, dict) else {}
        raw_name = str(function.get("name") or raw_tool_call.get("name") or "tool")
        name_status = "safe" if _is_safe_tool_name(raw_name) else "unsafe"
        name = _safe_tool_name(raw_name) if name_status == "safe" else "blocked_provider_tool"
        proposal_id = _safe_tool_name(str(raw_tool_call.get("id") or f"{source.value}.{name}"))
        arguments_schema = _schema_from_arguments(function.get("arguments"))
        if source is ProviderToolCallSource.LMSTUDIO:
            return LMStudioLocalToolProposal(
                schema_version=self.schema_version,
                proposal_id=f"lmstudio.{proposal_id}",
                trace_id=self.trace_id,
                turn_id=self.turn_id,
                tool_name=name,
                tool_name_status=name_status,
                marvex_policy_authoritative=True,
            )
        return OpenAIFunctionToolProposal(
            schema_version=self.schema_version,
            proposal_id=f"openai.{proposal_id}",
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            function_name=name,
            tool_name_status=name_status,
            json_schema=arguments_schema,
        )

    def from_litellm(self, raw_tool_call: dict[str, Any]) -> LiteLLMToolCallProposal:
        raw_name = str(raw_tool_call.get("name") or _nested_name(raw_tool_call) or "tool")
        name_status = "safe" if _is_safe_tool_name(raw_name) else "unsafe"
        name = _safe_tool_name(raw_name) if name_status == "safe" else "blocked_provider_tool"
        proposal_id = _safe_tool_name(str(raw_tool_call.get("id") or f"litellm.{name}"))
        return LiteLLMToolCallProposal(
            schema_version=self.schema_version,
            proposal_id=f"litellm.{proposal_id}",
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            tool_name=name,
            tool_name_status=name_status,
            toolset_ref=LiteLLMToolsetRef(toolset_id="provider_tool_calls", external_permission_source="marvex"),
        )


def _nested_name(raw_tool_call: dict[str, Any]) -> str | None:
    function = raw_tool_call.get("function")
    if isinstance(function, dict) and isinstance(function.get("name"), str):
        return function["name"]
    return None


def _schema_from_arguments(arguments: Any) -> dict[str, object]:
    parsed: object
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError:
            parsed = {}
    elif isinstance(arguments, dict):
        parsed = arguments
    else:
        parsed = {}
    argument_count = len([key for key in dict(parsed) if _safe_key(str(key))])
    return {"type": "object", "metadata": {"argument_count": argument_count}} if argument_count else {"type": "object"}


def _json_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _safe_key(value: str) -> bool:
    lowered = value.lower()
    return bool(value) and all(character in _SAFE_TOOL_CHARS for character in value) and not any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "raw", "prompt", "transcript"))


def _safe_tool_name(value: str) -> str:
    safe = "".join(character if character in _SAFE_TOOL_CHARS else "_" for character in value.strip())
    safe = safe.strip("._-:")
    return safe or "tool"



def _is_safe_tool_name(value: str) -> bool:
    stripped = value.strip()
    lowered = stripped.lower()
    if not stripped or stripped != value:
        return False
    if any(character not in _SAFE_TOOL_CHARS for character in stripped):
        return False
    return not any(part in lowered for part in ("authorization", "bearer", "password", "secret", "token", "raw", "prompt", "transcript"))
