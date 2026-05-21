"""Memory backend configuration.

The default backend is ``local`` (the existing in-process / SQLite store).
The ``agentmemory`` backend is an OPTIONAL deferred future feature; it is
disabled by default and must be explicitly opted-in at construction time.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Safe-characters set shared with memory_runtime — no import needed here.
_SAFE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789.:-_/"
)

MemoryBackendKind = Literal["local", "agentmemory"]
_DEFAULT_BACKEND: MemoryBackendKind = "local"
_DEFAULT_DAEMON_URL = "http://localhost:3111"


class AgentMemoryBackendConfig(BaseModel):
    """Wire-level configuration for the agentmemory external daemon backend.

    This config object is only used when ``MemoryBackendConfig.backend`` is
    ``"agentmemory"``.  The daemon URL must be a loopback address or an
    explicit non-loopback address with an opt-in override (a warning is
    emitted for non-loopback plaintext HTTP).

    No credentials or raw account content are persisted here; the optional
    bearer token is held only in memory for the lifetime of the process.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    daemon_url: str = Field(
        default=_DEFAULT_DAEMON_URL,
        description="Base URL of the agentmemory daemon (default: http://localhost:3111).",
    )
    namespace: str = Field(
        default="marvex",
        min_length=1,
        description="Project/namespace sent as the agentmemory 'project' field.",
    )
    # Bearer token held only in-memory — never persisted.
    bearer_token: str | None = Field(
        default=None,
        description="Optional in-memory bearer token.  Never persisted to disk.",
    )
    timeout_seconds: float = Field(
        default=5.0,
        gt=0,
        description="HTTP request timeout in seconds.",
    )
    warn_non_loopback_plaintext: bool = Field(
        default=True,
        description=(
            "When True, emit a warning if the daemon URL uses plaintext HTTP "
            "on a non-loopback address."
        ),
    )

    @field_validator("daemon_url")
    @classmethod
    def _validate_daemon_url(cls, value: str) -> str:
        value = value.rstrip("/")
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("daemon_url must start with http:// or https://")
        return value

    @field_validator("namespace")
    @classmethod
    def _validate_namespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("namespace must be non-empty")
        for char in value:
            if char not in _SAFE_CHARS:
                raise ValueError(
                    f"namespace contains unsafe character: {char!r}"
                )
        return value


class MemoryBackendConfig(BaseModel):
    """Top-level memory backend selector.

    ``backend`` defaults to ``"local"`` so existing deployments are
    completely unaffected.  Set to ``"agentmemory"`` and supply
    ``agentmemory`` config to route writes/reads to the external daemon.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: MemoryBackendKind = Field(
        default=_DEFAULT_BACKEND,
        description="Which memory backend to use.  Defaults to 'local'.",
    )
    agentmemory: AgentMemoryBackendConfig | None = Field(
        default=None,
        description=(
            "agentmemory daemon config.  Required when backend='agentmemory', "
            "ignored otherwise."
        ),
    )

    @property
    def is_agentmemory_enabled(self) -> bool:
        """Return True only when the agentmemory backend has been explicitly selected."""
        return self.backend == "agentmemory"


def default_memory_backend_config() -> MemoryBackendConfig:
    """Return the default config — local backend, agentmemory disabled."""
    return MemoryBackendConfig(backend="local", agentmemory=None)
