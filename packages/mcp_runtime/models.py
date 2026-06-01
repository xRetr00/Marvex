from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_/")
_SECRET_KEY_PARTS = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey")


class McpRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class McpServerPackageSpec(McpRuntimeModel):
    registry_type: Literal["pypi", "npm", "oci", "local", "none"]
    identifier: str = Field(..., min_length=1)
    version: str | None = None

    @field_validator("identifier", "version")
    @classmethod
    def _safe_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if any(part in value.lower() for part in _SECRET_KEY_PARTS):
            raise ValueError("package metadata cannot contain secret-looking text")
        return value.strip()

    def install_spec(self) -> str | None:
        if self.registry_type == "none":
            return None
        if self.registry_type == "pypi":
            return f"{self.identifier}=={self.version}" if self.version else self.identifier
        if self.registry_type == "npm":
            return f"{self.identifier}@{self.version}" if self.version else self.identifier
        return self.identifier


class McpServerTransportConfig(McpRuntimeModel):
    type: Literal["stdio", "streamable_http", "sse"]
    command: str | None = None
    args: tuple[str, ...] = ()
    url: str | None = None
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def _validate_command(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("command cannot be empty")
        if any(part in stripped.lower() for part in ("powershell", "cmd.exe", "bash", "sh.exe")):
            raise ValueError("shell commands are not valid MCP server commands")
        return stripped

    @field_validator("env")
    @classmethod
    def _validate_env(cls, value: dict[str, str]) -> dict[str, str]:
        for key, item in value.items():
            lowered = key.lower()
            if any(part in lowered for part in _SECRET_KEY_PARTS):
                raise ValueError("secret env values must be supplied through credential adapters, not persisted")
            if any(part in str(item).lower() for part in _SECRET_KEY_PARTS):
                raise ValueError("secret env values must not be persisted")
        return dict(value)


class InstalledMcpServerConfig(McpRuntimeModel):
    schema_version: str = "1"
    server_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    source: Literal["official_registry", "approved_local", "manual_fixture"]
    transport: McpServerTransportConfig
    package: McpServerPackageSpec = Field(default_factory=lambda: McpServerPackageSpec(registry_type="none", identifier="none"))
    allowed_tool_names: tuple[str, ...] = ()
    enabled: bool = False
    raw_registry_payload_persisted: Literal[False] = False

    @field_validator("server_id", "display_name")
    @classmethod
    def _validate_id_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value cannot be empty")
        if any(part in stripped.lower() for part in _SECRET_KEY_PARTS):
            raise ValueError("server metadata cannot contain secret-looking text")
        if value == stripped and all(character in _SAFE_ID_CHARS or character == " " for character in value):
            return value
        return stripped

    def safe_projection(self, *, tool_count: int = 0) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "server_id": self.server_id,
            "display_name": self.display_name,
            "source": self.source,
            "transport": self.transport.type,
            "package_registry_type": self.package.registry_type,
            "package_identifier": self.package.identifier,
            "enabled": self.enabled,
            "allowed_tool_count": len(self.allowed_tool_names),
            "tool_count": tool_count,
            "raw_registry_payload_persisted": False,
        }


class DiscoveredMcpTool(McpRuntimeModel):
    server_id: str
    tool_name: str
    description: str = "MCP tool"
    input_schema: dict[str, Any] = Field(default_factory=lambda: {"type": "object"})

    def capability_id(self) -> str:
        return f"mcp.{_safe_part(self.server_id)}.{_safe_part(self.tool_name)}"


def _safe_part(value: str) -> str:
    safe = "".join(character if character in _SAFE_ID_CHARS else "-" for character in value.strip())
    return safe.strip(".-:_/") or "unnamed"


__all__ = [
    "DiscoveredMcpTool",
    "InstalledMcpServerConfig",
    "McpServerPackageSpec",
    "McpServerTransportConfig",
]

