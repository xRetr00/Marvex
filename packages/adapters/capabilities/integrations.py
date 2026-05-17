from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityKind, CapabilityRef


class IntegrationAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataAccessClassification(str, Enum):
    NONE = "none"
    READ_METADATA = "read_metadata"
    READ_CONTENT = "read_content"
    WRITE_CONTENT = "write_content"


class SideEffectClassification(str, Enum):
    NONE = "none"
    LOCAL_ONLY = "local_only"
    EXTERNAL_WRITE = "external_write"


class AuthRequirement(IntegrationAdapterModel):
    required: bool
    secret_storage: Literal["none", "external_only"]


class PluginRef(IntegrationAdapterModel):
    plugin_id: str = Field(..., min_length=1)


class ConnectorRef(IntegrationAdapterModel):
    connector_id: str = Field(..., min_length=1)


class IntegrationRef(IntegrationAdapterModel):
    integration_id: str = Field(..., min_length=1)


class PluginManifest(IntegrationAdapterModel):
    schema_version: str = Field(..., min_length=1)
    plugin_ref: PluginRef
    connector_refs: tuple[ConnectorRef, ...] = ()
    arbitrary_execution_allowed: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "plugin_id": self.plugin_ref.plugin_id,
            "connector_count": len(self.connector_refs),
            "arbitrary_execution_allowed": False,
        }


class ConnectorManifest(IntegrationAdapterModel):
    schema_version: str = Field(..., min_length=1)
    connector_ref: ConnectorRef
    auth_requirement: AuthRequirement
    data_access: DataAccessClassification
    side_effects: SideEffectClassification
    secrets_stored_by_default: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "connector_id": self.connector_ref.connector_id,
            "auth_required": self.auth_requirement.required,
            "data_access": self.data_access.value,
            "side_effects": self.side_effects.value,
            "secrets_stored_by_default": False,
        }


class IntegrationManifest(IntegrationAdapterModel):
    schema_version: str = Field(..., min_length=1)
    integration_ref: IntegrationRef
    connector_ref: ConnectorRef
    plugin_ref: PluginRef | None
    auth_requirement: AuthRequirement
    data_access: DataAccessClassification
    side_effects: SideEffectClassification

    def to_capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.INTEGRATION, identifier=f"integration.{self.integration_ref.integration_id}")
