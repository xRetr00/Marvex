from __future__ import annotations

from typing import Literal

from pydantic import Field

from packages.capability_runtime.models import CapabilityRuntimeModel, ToolRiskLevel, ToolSideEffectLevel


class RuntimeCapabilitySummary(CapabilityRuntimeModel):
    schema_version: str = Field(default="1", min_length=1)
    identifier: str = Field(..., min_length=1)
    display_name: str = Field(..., min_length=1)
    source: Literal["builtin", "mcp", "skill", "adapter"]
    intent_tags: tuple[str, ...] = ()
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.NONE
    approval_required: bool = False
    execution_enabled: Literal[False] = False
    prompt_summary: str = Field(..., min_length=1, max_length=500)
    raw_schema_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "identifier": self.identifier,
            "display_name": self.display_name,
            "source": self.source,
            "intent_tags": list(self.intent_tags),
            "risk_level": self.risk_level.value,
            "side_effect_level": self.side_effect_level.value,
            "approval_required": self.approval_required,
            "execution_enabled": False,
            "raw_schema_persisted": False,
        }


class RuntimeCapabilityCatalog(CapabilityRuntimeModel):
    schema_version: str = Field(default="1", min_length=1)
    capabilities: tuple[RuntimeCapabilitySummary, ...]
    all_tools_preloaded: Literal[False] = False
    arbitrary_mcp_launch_allowed: Literal[False] = False
    arbitrary_skill_install_allowed: Literal[False] = False
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "capabilities": [capability.safe_projection() for capability in self.capabilities],
            "capability_count": len(self.capabilities),
            "all_tools_preloaded": False,
            "arbitrary_mcp_launch_allowed": False,
            "arbitrary_skill_install_allowed": False,
            "raw_payload_persisted": False,
        }

    def select_for_prompt(
        self,
        *,
        agent_profile: object,
        intent_kind: object,
        max_items: int = 8,
    ) -> tuple[RuntimeCapabilitySummary, ...]:
        wanted = set(getattr(agent_profile, "default_capability_refs", ())) | set(getattr(agent_profile, "default_skill_refs", ()))
        intent_value = str(getattr(intent_kind, "value", intent_kind))
        selected: list[RuntimeCapabilitySummary] = []
        for capability in self.capabilities:
            if capability.identifier in wanted or intent_value in capability.intent_tags:
                selected.append(capability)
            if len(selected) >= max_items:
                break
        return tuple(selected)


def default_runtime_capability_catalog() -> RuntimeCapabilityCatalog:
    return RuntimeCapabilityCatalog(
        capabilities=(
            RuntimeCapabilitySummary(
                identifier="builtin.calculator",
                display_name="Calculator",
                source="builtin",
                intent_tags=("capability_tool",),
                risk_level=ToolRiskLevel.LOW,
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Safe arithmetic only.",
            ),
            RuntimeCapabilitySummary(
                identifier="builtin.time_date",
                display_name="Time and Date",
                source="builtin",
                intent_tags=("provider_simple_chat",),
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Safe UTC time/date projection.",
            ),
            RuntimeCapabilitySummary(
                identifier="builtin.capability_diagnostics",
                display_name="Capability Diagnostics",
                source="builtin",
                intent_tags=("settings_control_plane",),
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Read-only capability status summary.",
            ),
            RuntimeCapabilitySummary(
                identifier="builtin.repo_status",
                display_name="Repo Status",
                source="builtin",
                intent_tags=("file_read_list_search",),
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Read-only repository status projection.",
            ),
            RuntimeCapabilitySummary(
                identifier="filesystem.read",
                display_name="Filesystem Read",
                source="adapter",
                intent_tags=("file_read_list_search",),
                risk_level=ToolRiskLevel.LOW,
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Root-scoped file read/list/search capability projection.",
            ),
            RuntimeCapabilitySummary(
                identifier="filesystem.search",
                display_name="Filesystem Search",
                source="adapter",
                intent_tags=("file_read_list_search",),
                risk_level=ToolRiskLevel.LOW,
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                prompt_summary="Root-scoped text and filename search capability projection.",
            ),
            RuntimeCapabilitySummary(
                identifier="web_search.search",
                display_name="Web Search",
                source="adapter",
                intent_tags=("web_search", "grounded_answer"),
                risk_level=ToolRiskLevel.LOW,
                side_effect_level=ToolSideEffectLevel.NETWORK,
                prompt_summary="Search adapter projection selected only for freshness or grounded lookup routes.",
            ),
            RuntimeCapabilitySummary(
                identifier="mcp.filesystem.read",
                display_name="MCP Filesystem",
                source="mcp",
                intent_tags=("mcp_needed", "file_read_list_search"),
                risk_level=ToolRiskLevel.MEDIUM,
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                approval_required=True,
                prompt_summary="Allowlisted MCP filesystem read projection; launch remains disabled until configured.",
            ),
            RuntimeCapabilitySummary(
                identifier="mcp.memory.read",
                display_name="MCP Memory",
                source="mcp",
                intent_tags=("mcp_needed", "memory", "memory_tree_needed"),
                risk_level=ToolRiskLevel.LOW,
                side_effect_level=ToolSideEffectLevel.READ_ONLY,
                approval_required=True,
                prompt_summary="Allowlisted MCP memory read projection; execution remains approval-gated.",
            ),
            RuntimeCapabilitySummary(
                identifier="browser.playwright",
                display_name="Playwright Browser",
                source="adapter",
                intent_tags=("browser_computer_use",),
                risk_level=ToolRiskLevel.HIGH,
                side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
                approval_required=True,
                prompt_summary="Low-level browser automation projection requiring permission flow.",
            ),
            RuntimeCapabilitySummary(
                identifier="browser_use.task",
                display_name="Browser Use",
                source="adapter",
                intent_tags=("browser_computer_use",),
                risk_level=ToolRiskLevel.HIGH,
                side_effect_level=ToolSideEffectLevel.BROWSER_ACTION,
                approval_required=True,
                prompt_summary="Agentic browser-use seam disabled until policy worker allows execution.",
            ),
            RuntimeCapabilitySummary(
                identifier="computer_use.proposal",
                display_name="Computer Use",
                source="adapter",
                intent_tags=("browser_computer_use",),
                risk_level=ToolRiskLevel.HIGH,
                side_effect_level=ToolSideEffectLevel.DESKTOP_ACTION,
                approval_required=True,
                prompt_summary="Computer-use proposal surface; screen content is untrusted.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.planning",
                display_name="Planning Skill",
                source="skill",
                intent_tags=("provider_simple_chat",),
                prompt_summary="Planning prompt contribution selected when planning is useful.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.brainstorming",
                display_name="Brainstorming Skill",
                source="skill",
                intent_tags=("provider_simple_chat",),
                prompt_summary="Requirement exploration prompt contribution.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.deep_search",
                display_name="Deep Search Skill",
                source="skill",
                intent_tags=("web_search", "grounded_answer"),
                prompt_summary="Evidence comparison and citation discipline.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.coding",
                display_name="Coding Skill",
                source="skill",
                intent_tags=("file_read_list_search", "capability_tool"),
                prompt_summary="Repository inspection and implementation workflow guidance.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.browser_automation",
                display_name="Browser Automation Skill",
                source="skill",
                intent_tags=("browser_computer_use",),
                prompt_summary="Browser automation workflow guidance.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.computer_use_safety",
                display_name="Computer Use Safety Skill",
                source="skill",
                intent_tags=("browser_computer_use",),
                prompt_summary="Computer-use safety and approval guidance.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.memory",
                display_name="Memory Skill",
                source="skill",
                intent_tags=("memory", "memory_tree_needed"),
                prompt_summary="Memory retrieval and source-grounded summarization guidance.",
            ),
            RuntimeCapabilitySummary(
                identifier="skill.verification",
                display_name="Verification Skill",
                source="skill",
                intent_tags=("capability_tool", "file_read_list_search", "grounded_answer"),
                prompt_summary="Verification before completion guidance.",
            ),
        )
    )
