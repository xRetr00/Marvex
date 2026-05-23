from __future__ import annotations

from packages.intent_runtime import IntentKind


def test_default_runtime_catalog_registers_builtins_mcp_and_skills_without_execution_rights() -> None:
    from packages.capability_runtime.runtime_catalog import default_runtime_capability_catalog

    catalog = default_runtime_capability_catalog()
    projection = catalog.safe_projection()

    assert projection["all_tools_preloaded"] is False
    assert projection["arbitrary_mcp_launch_allowed"] is False
    assert projection["arbitrary_skill_install_allowed"] is False
    assert any(entry["identifier"] == "builtin.calculator" for entry in projection["capabilities"])
    assert any(entry["identifier"] == "mcp.filesystem.read" and entry["execution_enabled"] is False for entry in projection["capabilities"])
    assert any(entry["identifier"] == "skill.deep_search" and entry["execution_enabled"] is False for entry in projection["capabilities"])
    assert projection["raw_payload_persisted"] is False


def test_runtime_catalog_adaptively_exposes_only_relevant_capability_summaries() -> None:
    from packages.agent_runtime import default_agent_catalog
    from packages.capability_runtime.runtime_catalog import default_runtime_capability_catalog

    catalog = default_runtime_capability_catalog()
    agents = default_agent_catalog()

    search_context = catalog.select_for_prompt(
        agent_profile=agents.get("agent.deep_search"),
        intent_kind=IntentKind.WEB_SEARCH,
    )
    coding_context = catalog.select_for_prompt(
        agent_profile=agents.get("agent.coding"),
        intent_kind=IntentKind.FILE_READ_LIST_SEARCH,
    )

    assert any(item.identifier == "web_search.search" for item in search_context)
    assert any(item.identifier == "skill.deep_search" for item in search_context)
    assert all(item.identifier != "browser_use.task" for item in search_context)
    assert any(item.identifier == "filesystem.read" for item in coding_context)
    assert any(item.identifier == "skill.coding" for item in coding_context)
    assert all(item.execution_enabled is False for item in (*search_context, *coding_context))
