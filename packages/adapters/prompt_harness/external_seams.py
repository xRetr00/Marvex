from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel


class HarnessExternalBackend(str, Enum):
    LLAMAINDEX_ROUTERS = "llamaindex_routers"
    LANGCHAIN_LANGGRAPH = "langchain_langgraph"
    OPENAI_AGENTS = "openai_agents"
    ANTHROPIC_CONTEXT_PATTERNS = "anthropic_context_patterns"
    AWESOME_HARNESS_REFERENCES = "awesome_harness_references"


class HarnessBackendStatus(str, Enum):
    BACKEND_DISABLED = "backend_disabled"
    REFERENCE_ONLY = "reference_only"
    ADAPTER_SEAM_READY = "adapter_seam_ready"


class HarnessExternalAdapterConfig(CapabilityRuntimeModel):
    schema_version: str
    backend: HarnessExternalBackend
    status: HarnessBackendStatus
    reason_code: str = Field(..., min_length=1)
    library_owns_policy: Literal[False] = False
    raw_prompt_access_allowed: Literal[False] = False
    automatic_retry_allowed: Literal[False] = False
    autonomous_loop_allowed: Literal[False] = False


class DisabledHarnessLibraryBackend:
    def __init__(self, *, config: HarnessExternalAdapterConfig) -> None:
        self.config = config

    def safe_capabilities(self) -> dict[str, str | bool]:
        return {
            "backend": self.config.backend.value,
            "status": self.config.status.value,
            "reason_code": self.config.reason_code,
            "library_owns_policy": False,
            "raw_prompt_access_allowed": False,
            "automatic_retry_allowed": False,
            "autonomous_loop_allowed": False,
        }
