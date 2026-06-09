from __future__ import annotations

from packages.intent_runtime import IntentKind


def test_default_agent_catalog_separates_main_specialists_and_active_voice() -> None:
    from packages.agent_runtime import default_agent_catalog, default_persona_catalog

    agents = default_agent_catalog()
    personas = default_persona_catalog()

    assert agents.active_agent_id == "agent.main.marvex"
    assert personas.active_persona_id == "persona.marvex.female"
    assert personas.active_persona().voice_id == "M1"

    main = agents.get("agent.main.marvex")
    deep_search = agents.get("agent.deep_search")
    coding = agents.get("agent.coding")

    assert main.role == "orchestrator"
    assert main.can_spawn_subagents is True
    assert "agent.deep_search" in main.spawnable_agent_ids
    assert "agent.coding" in main.spawnable_agent_ids
    assert deep_search.role == "specialist"
    assert coding.direct_selectable is True
    assert IntentKind.WEB_SEARCH in deep_search.allowed_intents
    assert IntentKind.FILE_READ_LIST_SEARCH in coding.allowed_intents


def test_subagent_plan_is_bounded_sequential_and_policy_inherited() -> None:
    from packages.agent_runtime import SubagentTaskRequest, default_agent_catalog, plan_subagent_tasks

    catalog = default_agent_catalog()

    plan = plan_subagent_tasks(
        catalog=catalog,
        parent_agent_id="agent.main.marvex",
        requests=(
            SubagentTaskRequest(target_agent_id="agent.deep_search", task_summary="Compare official MCP registry guidance."),
            SubagentTaskRequest(target_agent_id="agent.coding", task_summary="Inspect runtime integration points."),
            SubagentTaskRequest(target_agent_id="agent.verifier", task_summary="Check tests and acceptance criteria."),
        ),
    )

    assert plan.parent_agent_id == "agent.main.marvex"
    assert plan.execution_mode == "sequential"
    assert plan.recursive_spawn_allowed is False
    assert plan.max_subagents == 2
    assert len(plan.tasks) == 2
    assert all(task.policy_inherited for task in plan.tasks)
    assert plan.dropped_request_count == 1
