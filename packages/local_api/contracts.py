from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from packages.contracts import AssistantTurnInput, AssistantTurnResult


SCHEMA_VERSION = "0.1.1-draft"
LOCAL_TURNS_PATH = "/v1/turns"
LOCAL_TRACES_PREFIX = "/v1/traces/"
LOCAL_TURNS_FAKE_EXECUTION_MODE = "assistant_runtime_fake_provider"
LOCAL_TURNS_LMSTUDIO_RESPONSES_EXECUTION_MODE = "assistant_runtime_lmstudio_responses"
LOCAL_TURNS_EXECUTION_MODE = LOCAL_TURNS_FAKE_EXECUTION_MODE
LOCAL_TURN_REQUEST_FIELDS = {
    "schema_version",
    "execution_mode",
    "assistant_turn_input",
    "model",
    "instructions",
    "previous_response_id",
    "provider_options",
}
LOCAL_TURN_OPTIONAL_REQUEST_FIELDS = {
    "resume_approval_id",
    "approval_decision",
}


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def is_loopback_host(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


@dataclass(frozen=True)
class LocalApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    allow_remote: bool = False

    def __post_init__(self) -> None:
        if not self.host or not self.host.strip():
            raise ValueError("host must be a non-empty string")
        if not is_loopback_host(self.host) and not self.allow_remote:
            raise ValueError("host must be loopback-only")
        if not isinstance(self.port, int) or self.port < 1 or self.port > 65535:
            raise ValueError("port must be between 1 and 65535")


@dataclass(frozen=True)
class LocalTurnRequestEnvelope:
    schema_version: str
    execution_mode: str
    assistant_turn_input: AssistantTurnInput
    model: str
    instructions: str | None
    previous_response_id: str | None
    resume_approval_id: str | None
    approval_decision: str | None
    provider_options: dict[str, Any]


TurnHandler = Callable[[LocalTurnRequestEnvelope], AssistantTurnResult]


class TraceReader(Protocol):
    def read_trace(self, trace_id: str) -> dict[str, Any] | None:
        ...
