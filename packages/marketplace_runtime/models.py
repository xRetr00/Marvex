from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from packages.mcp_runtime import InstalledMcpServerConfig, McpServerPackageSpec, McpServerTransportConfig
from packages.skills_runtime import SkillManifest, SkillValidationResult

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_/")
_UNSAFE_TEXT = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "raw prompt", "transcript")
_POLICY_OVERRIDE_MARKERS = (
    "ignore previous instructions",
    "ignore system instructions",
    "override system prompt",
    "override marvex policy",
    "bypass policy",
    "system prompt",
)
_DANGEROUS_TOOL_PARTS = ("bash", "browser", "command", "desktop", "file", "filesystem", "fs", "http", "network", "powershell", "shell", "terminal", "url")
_APPROVED_RUNTIME_DEP_GROUP_IDS = frozenset({"browser", "mcp", "computer_use", "web_search"})

MarketplaceSubjectKind = Literal["mcp_server", "skill", "capability", "tool", "provider", "policy"]
MarketplaceSource = Literal["official_registry", "approved_local", "manual_fixture"]


class MarketplaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class McpRegistryToolSummary(MarketplaceModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=500)
    raw_schema_persisted: Literal[False] = False

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("tool name must be non-empty and trimmed")
        if any(part in _normalized(value) for part in ("authorization", "password", "secret", "token")):
            raise ValueError("tool name contains unsafe text")
        return value

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        _reject_unsafe_text(value)
        return value


class McpMarketplaceEntry(MarketplaceModel):
    schema_version: str = Field(..., min_length=1)
    registry_name: Literal["official_mcp_registry", "approved_local_cache", "manual_fixture"]
    server_id: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=800)
    homepage_url: str | None = None
    source_url: str | None = None
    registry_url: str | None = None
    tool_summaries: tuple[McpRegistryToolSummary, ...] = ()
    transport_summaries: tuple[str, ...] = ()
    install_command: None = None
    required_dep_group_id: str | None = None
    package_registry_type: Literal["pypi", "npm", "oci", "local", "none"] = "none"
    package_identifier: str | None = None
    package_version: str | None = None
    remote_url: str | None = None
    remote_transport: Literal["streamable_http", "sse"] | None = None
    read_only_browse: Literal[True] = True
    install_allowed: bool = False
    launch_allowed: Literal[False] = False
    auto_execution_allowed: Literal[False] = False
    raw_registry_payload_persisted: Literal[False] = False

    @field_validator("server_id")
    @classmethod
    def _validate_server_id(cls, value: str) -> str:
        if not value.strip() or value != value.strip():
            raise ValueError("server_id must be non-empty and trimmed")
        if any(character not in _SAFE_ID_CHARS for character in value):
            raise ValueError("server_id contains unsafe characters")
        return value

    @field_validator("display_name", "description")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        _reject_unsafe_text(value)
        return value

    @field_validator("required_dep_group_id")
    @classmethod
    def _validate_required_dep_group_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _APPROVED_RUNTIME_DEP_GROUP_IDS:
            raise ValueError("required_dep_group_id must reference an approved runtime dep group")
        return value

    @model_validator(mode="after")
    def _validate_install_policy(self) -> McpMarketplaceEntry:
        if self.install_allowed and self.required_dep_group_id is None:
            raise ValueError("install_allowed requires an approved runtime dep group")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "server_id": self.server_id,
            "display_name": self.display_name,
            "registry_name": self.registry_name,
            "tool_count": len(self.tool_summaries),
            "transport_count": len(self.transport_summaries),
            "read_only_browse": True,
            "install_allowed": self.required_dep_group_id is not None,
            "required_dep_group_id": self.required_dep_group_id,
            "package_registry_type": self.package_registry_type,
            "package_identifier": self.package_identifier,
            "package_version": self.package_version,
            "remote_transport": self.remote_transport,
            "launch_allowed": False,
            "auto_execution_allowed": False,
            "raw_registry_payload_persisted": False,
        }

    def to_installed_config(self) -> InstalledMcpServerConfig:
        if self.remote_url and self.remote_transport is not None:
            transport = McpServerTransportConfig(type=self.remote_transport, url=self.remote_url)
        elif self.package_identifier and self.package_registry_type == "pypi":
            spec = self.package_identifier if self.package_version is None else f"{self.package_identifier}=={self.package_version}"
            transport = McpServerTransportConfig(type="stdio", command="uvx", args=(spec,))
        elif self.package_identifier and self.package_registry_type == "npm":
            spec = self.package_identifier if self.package_version is None else f"{self.package_identifier}@{self.package_version}"
            transport = McpServerTransportConfig(type="stdio", command="npx", args=("-y", spec))
        else:
            transport = McpServerTransportConfig(type="stdio", command="python", args=("-m", "mcp"))
        return InstalledMcpServerConfig(
            server_id=self.server_id,
            display_name=self.display_name,
            source="official_registry" if self.registry_name == "official_mcp_registry" else "approved_local",
            transport=transport,
            package=McpServerPackageSpec(
                registry_type=self.package_registry_type,
                identifier=self.package_identifier or "none",
                version=self.package_version,
            ),
            allowed_tool_names=tuple(tool.name for tool in self.tool_summaries),
            enabled=True,
        )


class MarketplaceValidationResult(MarketplaceModel):
    schema_version: str
    subject_id: str
    subject_kind: MarketplaceSubjectKind
    valid: bool
    reason_codes: tuple[str, ...]
    arbitrary_server_execution_allowed: Literal[False] = False
    script_execution_allowed: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()


class McpMarketplaceCatalog(MarketplaceModel):
    schema_version: str = "1"
    entries: tuple[McpMarketplaceEntry, ...]
    source: MarketplaceSource = "official_registry"
    read_only_browse: Literal[True] = True

    @classmethod
    def from_entries(cls, entries: tuple[McpMarketplaceEntry, ...]) -> McpMarketplaceCatalog:
        return cls(entries=entries)

    def safe_projection(self) -> tuple[dict[str, object], ...]:
        return tuple(entry.safe_projection() for entry in self.entries)


class McpAllowlistProposal(MarketplaceModel):
    schema_version: str
    proposal_id: str = Field(..., min_length=1)
    server_id: str = Field(..., min_length=1)
    requested_by: Literal["control_plane", "local_config"]
    tool_count: int = Field(..., ge=0)
    requires_human_approval: Literal[True] = True
    install_started: Literal[False] = False
    launch_started: Literal[False] = False
    auto_execution_allowed: Literal[False] = False

    @classmethod
    def from_entry(cls, entry: McpMarketplaceEntry, *, proposal_id: str, requested_by: Literal["control_plane", "local_config"]) -> McpAllowlistProposal:
        return cls(
            schema_version=entry.schema_version,
            proposal_id=proposal_id,
            server_id=entry.server_id,
            requested_by=requested_by,
            tool_count=len(entry.tool_summaries),
        )

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()


class SkillMarketplaceEntry(MarketplaceModel):
    schema_version: str
    skill_id: str
    display_name: str
    source: Literal["approved_local", "manual_fixture"]
    validation: SkillValidationResult
    prompt_contribution_count: int = Field(..., ge=0)
    script_execution_allowed: Literal[False] = False
    remote_loading_allowed: Literal[False] = False
    arbitrary_install_allowed: Literal[False] = False
    can_override_system_policy: Literal[False] = False
    raw_instruction_persisted: Literal[False] = False

    @classmethod
    def from_manifest(cls, manifest: SkillManifest, *, source: Literal["approved_local", "manual_fixture"]) -> SkillMarketplaceEntry:
        _reject_unsafe_text(manifest.display_name)
        _reject_unsafe_text(manifest.description)
        validation = SkillValidationResult.from_manifest(manifest)
        if validation.policy_override_detected:
            raise ValueError("skill policy override detected")
        return cls(
            schema_version=manifest.schema_version,
            skill_id=manifest.skill_ref.skill_id,
            display_name=manifest.display_name,
            source=source,
            validation=validation,
            prompt_contribution_count=len(manifest.prompt_contributions),
        )

    def prompt_contribution_preview(self, *, max_chars: int = 300) -> str:
        preview = " ".join(self.validation.prompt_contributions)
        return preview[: max(1, max_chars)]

    def safe_projection(self) -> dict[str, object]:
        return {
            "skill_id": self.skill_id,
            "display_name": self.display_name,
            "source": self.source,
            "validated": self.validation.valid,
            "prompt_contribution_count": self.prompt_contribution_count,
            "script_execution_allowed": False,
            "remote_loading_allowed": False,
            "arbitrary_install_allowed": False,
            "can_override_system_policy": False,
            "raw_instruction_persisted": False,
        }


class SkillMarketplaceCatalog(MarketplaceModel):
    schema_version: str = "1"
    entries: tuple[SkillMarketplaceEntry, ...]
    source: Literal["approved_local", "manual_fixture"] = "approved_local"

    @classmethod
    def from_entries(cls, entries: tuple[SkillMarketplaceEntry, ...]) -> SkillMarketplaceCatalog:
        return cls(entries=entries)

    def safe_projection(self) -> tuple[dict[str, object], ...]:
        return tuple(entry.safe_projection() for entry in self.entries)


class MarketplaceEnablementState(MarketplaceModel):
    schema_version: str = "1"
    subject_id: str = Field(..., min_length=1)
    subject_kind: MarketplaceSubjectKind
    enabled: bool
    reason_code: str = Field(..., min_length=1)
    requires_validation: Literal[True] = True
    execution_started: Literal[False] = False
    install_started: Literal[False] = False

    @classmethod
    def with_enabled(cls, *, subject_id: str, subject_kind: MarketplaceSubjectKind, reason_code: str) -> MarketplaceEnablementState:
        return cls(subject_id=subject_id, subject_kind=subject_kind, enabled=True, reason_code=reason_code)

    @classmethod
    def disabled(cls, *, subject_id: str, subject_kind: MarketplaceSubjectKind, reason_code: str) -> MarketplaceEnablementState:
        return cls(subject_id=subject_id, subject_kind=subject_kind, enabled=False, reason_code=reason_code)

    def safe_projection(self) -> dict[str, object]:
        return self.model_dump()


class MarketplaceEnablementProposal(MarketplaceModel):
    schema_version: str = "1"
    proposal_id: str = Field(..., min_length=1)
    subject_id: str = Field(..., min_length=1)
    subject_kind: MarketplaceSubjectKind
    requested_by: Literal["control_plane", "local_config"]
    reason_code: str = Field(..., min_length=1)
    review_required: Literal[True] = True
    requires_human_approval: Literal[True] = True
    feeds_mcp_allowlist: bool = False
    feeds_skill_enablement: bool = False
    mcp_allowlist_proposal: McpAllowlistProposal | None = None
    enablement_applied: Literal[False] = False
    execution_started: Literal[False] = False
    install_started: Literal[False] = False
    launch_started: Literal[False] = False
    auto_execution_allowed: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    @model_validator(mode="after")
    def _validate_feed(self) -> MarketplaceEnablementProposal:
        if self.subject_kind == "mcp_server":
            if not self.feeds_mcp_allowlist or self.mcp_allowlist_proposal is None:
                raise ValueError("mcp_server proposals must feed MCP allowlist review")
            return self
        if self.subject_kind == "skill":
            if not self.feeds_skill_enablement or self.mcp_allowlist_proposal is not None:
                raise ValueError("skill proposals must feed skill enablement review only")
            return self
        raise ValueError("marketplace enablement proposals support only mcp_server or skill")

    def safe_projection(self) -> dict[str, object]:
        payload = self.model_dump(mode="json")
        payload["mcp_allowlist_proposal"] = (
            self.mcp_allowlist_proposal.safe_projection()
            if self.mcp_allowlist_proposal is not None
            else None
        )
        return payload


class MarketplaceProposalStore:
    def __init__(self) -> None:
        self._proposals: list[MarketplaceEnablementProposal] = []

    def propose_mcp_allowlist(
        self,
        entry: McpMarketplaceEntry,
        *,
        requested_by: Literal["control_plane", "local_config"],
    ) -> MarketplaceEnablementProposal:
        validation = validate_mcp_server_manifest(entry)
        if not validation.valid:
            raise ValueError("invalid MCP marketplace entry cannot be proposed")
        allowlist = McpAllowlistProposal.from_entry(
            entry,
            proposal_id=f"allowlist:{entry.server_id}",
            requested_by=requested_by,
        )
        proposal = MarketplaceEnablementProposal(
            proposal_id=f"marketplace.mcp.{_proposal_id_part(entry.server_id)}",
            subject_id=entry.server_id,
            subject_kind="mcp_server",
            requested_by=requested_by,
            reason_code="review_required_mcp_allowlist",
            feeds_mcp_allowlist=True,
            mcp_allowlist_proposal=allowlist,
        )
        self._proposals.append(proposal)
        return proposal

    def propose_skill_enablement(
        self,
        entry: SkillMarketplaceEntry,
        *,
        requested_by: Literal["control_plane", "local_config"],
    ) -> MarketplaceEnablementProposal:
        if not entry.validation.valid:
            raise ValueError("invalid skill marketplace entry cannot be proposed")
        proposal = MarketplaceEnablementProposal(
            proposal_id=f"marketplace.skill.{_proposal_id_part(entry.skill_id)}",
            subject_id=entry.skill_id,
            subject_kind="skill",
            requested_by=requested_by,
            reason_code="review_required_skill_enablement",
            feeds_skill_enablement=True,
        )
        self._proposals.append(proposal)
        return proposal

    def list_review_required(self) -> tuple[MarketplaceEnablementProposal, ...]:
        return tuple(self._proposals)


def validate_mcp_server_manifest(entry: McpMarketplaceEntry) -> MarketplaceValidationResult:
    reasons: list[str] = []
    for tool in entry.tool_summaries:
        if _dangerous_tool_name(tool.name):
            reasons.append("blocked_dangerous_tool_name")
    if entry.install_allowed and entry.required_dep_group_id is None:
        reasons.append("unsafe_execution_allowed")
    if entry.launch_allowed or entry.auto_execution_allowed:
        reasons.append("unsafe_execution_allowed")
    return MarketplaceValidationResult(
        schema_version=entry.schema_version,
        subject_id=entry.server_id,
        subject_kind="mcp_server",
        valid=not reasons,
        reason_codes=tuple(reasons or ["valid"]),
    )


def _dangerous_tool_name(value: str) -> bool:
    normalized = _normalized(value)
    return any(part in normalized for part in _DANGEROUS_TOOL_PARTS)


def _reject_unsafe_text(value: str) -> None:
    normalized = value.lower()
    if any(part in normalized for part in _UNSAFE_TEXT) or any(marker in normalized for marker in _POLICY_OVERRIDE_MARKERS):
        raise ValueError("marketplace text contains unsafe or policy-overriding content")


def _normalized(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _proposal_id_part(value: str) -> str:
    safe = "".join(character if character in _SAFE_ID_CHARS else "-" for character in value)
    return safe.strip(".-:_/") or "unknown"
