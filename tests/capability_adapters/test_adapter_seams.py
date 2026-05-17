from __future__ import annotations

import pytest
from pydantic import ValidationError

from packages.adapters.capabilities.integrations import (
    AuthRequirement,
    ConnectorManifest,
    ConnectorRef,
    DataAccessClassification,
    IntegrationManifest,
    IntegrationRef,
    PluginManifest,
    PluginRef,
    SideEffectClassification,
)
from packages.adapters.capabilities.harness import CapabilityHarnessManifest, CapabilityHarnessRef
from packages.adapters.capabilities.litellm_gateway import LiteLLMToolsetRef, LiteLLMToolsetProjection
from packages.adapters.capabilities.lmstudio import LMStudioLocalToolProposal, LMStudioMcpHostRef
from packages.adapters.capabilities.mcp import (
    DisabledMcpBackend,
    McpAllowlist,
    McpServerRef,
    McpToolCallProposal,
    McpToolListingProjection,
    McpToolRef,
    McpTransport,
)
from packages.adapters.capabilities.openai_tools import (
    OpenAIFunctionToolProposal,
    OpenAIHostedToolRef,
    OpenAIRemoteMcpToolRef,
    OpenAIToolSchemaDelivery,
)
from packages.adapters.capabilities.skills import SkillManifest, SkillRef, SkillValidationResult
from packages.capability_runtime import CapabilityKind, CapabilityRef


def test_mcp_adapter_models_projection_and_disabled_backend() -> None:
    server = McpServerRef(server_id="weather", transport=McpTransport.STREAMABLE_HTTP, origin="local_config")
    tool = McpToolRef(server_ref=server, tool_name="current_weather")
    allowlist = McpAllowlist(allowed_server_ids=("weather",), allowed_tool_names=("current_weather",))
    projection = McpToolListingProjection.from_tool_ref(tool, allowlist=allowlist)
    proposal = McpToolCallProposal.from_listing(
        projection,
        proposal_id="proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
    )

    assert projection.allowed is True
    assert proposal.capability_ref == CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier="mcp.weather.current_weather")
    with pytest.raises(RuntimeError, match="disabled"):
        DisabledMcpBackend().list_tools(server)


def test_openai_litellm_and_lmstudio_tool_calls_are_proposals_only() -> None:
    openai_proposal = OpenAIFunctionToolProposal(
        schema_version="1",
        proposal_id="openai-proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        function_name="lookup_order",
        json_schema={"type": "object"},
        hosted_tool_ref=OpenAIHostedToolRef(tool_type="web_search_preview", provider_owned=True),
        remote_mcp_tool_ref=OpenAIRemoteMcpToolRef(server_label="docs", tool_name="search"),
    )
    toolset = LiteLLMToolsetProjection(
        schema_version="1",
        toolset_ref=LiteLLMToolsetRef(toolset_id="team-safe-tools", external_permission_source="team_metadata"),
        listed_capability_refs=(CapabilityRef(kind=CapabilityKind.TOOL, identifier="litellm.team-safe-tools.lookup"),),
        marvex_policy_authoritative=True,
    )
    lmstudio = LMStudioLocalToolProposal(
        schema_version="1",
        proposal_id="lmstudio-proposal-1",
        trace_id="trace-1",
        turn_id="turn-1",
        tool_name="local_fake_status",
        mcp_host_ref=LMStudioMcpHostRef(host_id="lmstudio-local", api_surface="local_server"),
        marvex_policy_authoritative=True,
    )

    assert openai_proposal.to_capability_proposal().raw_arguments_persisted is False
    assert toolset.safe_projection()["marvex_policy_authoritative"] is True
    delivery = OpenAIToolSchemaDelivery(schema_version="1", proposals=(openai_proposal,), delivery_target="provider_schema", raw_schema_persisted=False)

    assert delivery.safe_projection()["proposal_count"] == 1
    assert lmstudio.to_capability_proposal().capability_ref.identifier == "lmstudio.local_fake_status"


def test_skill_manifest_cannot_override_policy_or_execute_scripts() -> None:
    manifest = SkillManifest(
        schema_version="1",
        skill_ref=SkillRef(skill_id="summary"),
        instruction_uri="local://skills/summary/SKILL.md",
        resource_uris=("local://skills/summary/templates/default.md",),
        script_uris=("local://skills/summary/scripts/check.py",),
        can_override_system_policy=False,
        arbitrary_script_execution_allowed=False,
    )
    validation = SkillValidationResult.from_manifest(manifest)

    assert validation.valid is True
    with pytest.raises(ValidationError):
        SkillManifest(
            schema_version="1",
            skill_ref=SkillRef(skill_id="bad"),
            instruction_uri="local://skills/bad/SKILL.md",
            can_override_system_policy=True,
            arbitrary_script_execution_allowed=False,
        )


def test_plugin_connector_and_integration_manifests_classify_auth_data_and_side_effects() -> None:
    connector = ConnectorManifest(
        schema_version="1",
        connector_ref=ConnectorRef(connector_id="linear-readonly"),
        auth_requirement=AuthRequirement(required=True, secret_storage="external_only"),
        data_access=DataAccessClassification.READ_METADATA,
        side_effects=SideEffectClassification.NONE,
        secrets_stored_by_default=False,
    )
    plugin = PluginManifest(
        schema_version="1",
        plugin_ref=PluginRef(plugin_id="codex-linear"),
        connector_refs=(connector.connector_ref,),
        arbitrary_execution_allowed=False,
    )
    integration = IntegrationManifest(
        schema_version="1",
        integration_ref=IntegrationRef(integration_id="linear-summary"),
        connector_ref=connector.connector_ref,
        plugin_ref=plugin.plugin_ref,
        auth_requirement=connector.auth_requirement,
        data_access=connector.data_access,
        side_effects=connector.side_effects,
    )

    assert connector.safe_projection()["secrets_stored_by_default"] is False
    assert plugin.safe_projection()["arbitrary_execution_allowed"] is False
    assert integration.to_capability_ref().kind is CapabilityKind.INTEGRATION




def test_harness_manifest_models_prompt_context_and_verification_hooks() -> None:
    manifest = CapabilityHarnessManifest(
        schema_version="1",
        harness_ref=CapabilityHarnessRef(harness_id="prompt-context-safe"),
        prompt_contribution_kinds=("capability_schema_summary",),
        context_delivery_ready=True,
        compaction_ready=True,
        verification_hook_ready=True,
        raw_prompt_persisted=False,
    )

    assert manifest.to_capability_ref().kind is CapabilityKind.HARNESS
    assert manifest.safe_projection()["raw_prompt_persisted"] is False

