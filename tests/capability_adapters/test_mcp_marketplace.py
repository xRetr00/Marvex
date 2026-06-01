from __future__ import annotations

import pytest

from packages.marketplace_runtime import (
    McpAllowlistProposal,
    McpMarketplaceCatalog,
    McpMarketplaceEntry,
    McpRegistryToolSummary,
    MarketplaceEnablementState,
    MarketplaceProposalStore,
    catalog_from_official_registry_payload,
    validate_mcp_server_manifest,
)


def _entry(tool_name: str = "calculator") -> McpMarketplaceEntry:
    return McpMarketplaceEntry(
        schema_version="1",
        registry_name="official_mcp_registry",
        server_id="io.github.example/safe-server",
        display_name="Safe Server",
        description="Read-only arithmetic helper",
        homepage_url="https://github.com/example/safe-server",
        source_url="https://github.com/example/safe-server",
        registry_url="https://registry.modelcontextprotocol.io/servers/io.github.example/safe-server",
        tool_summaries=(McpRegistryToolSummary(name=tool_name, description="Safe helper"),),
        transport_summaries=("stdio",),
    )


def test_mcp_marketplace_catalog_is_read_only_safe_metadata() -> None:
    catalog = McpMarketplaceCatalog.from_entries((_entry(),))

    rows = catalog.safe_projection()

    assert rows[0]["server_id"] == "io.github.example/safe-server"
    assert rows[0]["tool_count"] == 1
    assert rows[0]["read_only_browse"] is True
    assert rows[0]["install_allowed"] is False
    assert rows[0]["launch_allowed"] is False
    assert rows[0]["auto_execution_allowed"] is False
    assert "install_command" not in rows[0]


def test_mcp_marketplace_can_expose_approved_dependency_install_hint() -> None:
    entry = _entry().model_copy(update={"required_dep_group_id": "mcp"})
    catalog = McpMarketplaceCatalog.from_entries((entry,))

    rows = catalog.safe_projection()
    validation = validate_mcp_server_manifest(entry)

    assert rows[0]["install_allowed"] is True
    assert rows[0]["required_dep_group_id"] == "mcp"
    assert validation.valid is True
    assert "unsafe_execution_allowed" not in validation.reason_codes


def test_official_registry_payload_maps_package_and_remote_install_metadata() -> None:
    catalog = catalog_from_official_registry_payload(
        {
            "servers": [
                {
                    "server": {
                        "name": "vendor/demo",
                        "description": "Demo MCP server",
                        "title": "Demo",
                        "version": "1.0.0",
                        "packages": [
                            {
                                "registryType": "npm",
                                "identifier": "@vendor/demo-mcp",
                                "version": "1.0.0",
                                "transport": {"type": "stdio"},
                            }
                        ],
                        "remotes": [{"type": "streamable-http", "url": "https://demo.example/mcp"}],
                    },
                    "_meta": {"io.modelcontextprotocol.registry/official": {"isLatest": True}},
                }
            ]
        }
    )

    entry = catalog.entries[0]
    config = entry.to_installed_config()

    assert entry.package_registry_type == "npm"
    assert entry.package_identifier == "@vendor/demo-mcp"
    assert entry.required_dep_group_id == "mcp"
    assert config.transport.type == "streamable_http"
    assert config.transport.url == "https://demo.example/mcp"


def test_mcp_manifest_validation_blocks_dangerous_tool_metadata() -> None:
    result = validate_mcp_server_manifest(_entry("shell_exec"))

    assert result.valid is False
    assert "blocked_dangerous_tool_name" in result.reason_codes
    assert result.safe_projection()["arbitrary_server_execution_allowed"] is False


def test_mcp_allowlist_proposal_and_enablement_are_metadata_only() -> None:
    entry = _entry()
    proposal = McpAllowlistProposal.from_entry(entry, proposal_id="proposal-1", requested_by="control_plane")
    state = MarketplaceEnablementState.disabled(
        subject_id=entry.server_id,
        subject_kind="mcp_server",
        reason_code="not_allowlisted",
    )

    assert proposal.server_id == entry.server_id
    assert proposal.requires_human_approval is True
    assert proposal.install_started is False
    assert proposal.launch_started is False
    assert state.enabled is False
    assert state.safe_projection()["execution_started"] is False


def test_mcp_marketplace_rejects_install_commands_and_raw_payloads() -> None:
    with pytest.raises(ValueError):
        McpMarketplaceEntry(
            schema_version="1",
            registry_name="official_mcp_registry",
            server_id="io.github.example/unsafe-server",
            display_name="Unsafe Server",
            description="tries to expose install command",
            homepage_url="https://github.com/example/unsafe-server",
            source_url="https://github.com/example/unsafe-server",
            registry_url="https://registry.modelcontextprotocol.io/servers/io.github.example/unsafe-server",
            tool_summaries=(McpRegistryToolSummary(name="calculator", description="Safe helper"),),
            transport_summaries=("stdio",),
            install_command="npm install unsafe",
        )


def test_marketplace_proposal_store_creates_review_required_mcp_allowlist_proposal() -> None:
    entry = _entry()
    store = MarketplaceProposalStore()

    proposal = store.propose_mcp_allowlist(entry, requested_by="control_plane")

    projection = proposal.safe_projection()
    assert projection["subject_kind"] == "mcp_server"
    assert projection["subject_id"] == entry.server_id
    assert projection["review_required"] is True
    assert projection["feeds_mcp_allowlist"] is True
    assert projection["enablement_applied"] is False
    assert projection["execution_started"] is False
    assert projection["mcp_allowlist_proposal"]["requires_human_approval"] is True
    assert store.list_review_required()[0] == proposal
