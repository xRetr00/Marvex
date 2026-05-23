from __future__ import annotations

import json
from typing import Any


SCHEMA_VERSION = "1"
CONTROL_PREFIX = "/control"


def handle_agent_control_request(
    *,
    method: str,
    path: str,
    environ: dict[str, Any],
    agent_catalog_projection: dict[str, Any] | None = None,
    persona_catalog_projection: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    if method == "GET" and path == f"{CONTROL_PREFIX}/agents":
        return "200 OK", agent_catalog_projection or default_agent_catalog_projection()
    if method == "POST" and path == f"{CONTROL_PREFIX}/agents/active":
        projection = select_agent_projection(agent_catalog_projection or default_agent_catalog_projection(), _parse_active_selection(environ, key="agent_id"))
        return ("200 OK", {**projection, "execution_started": False}) if projection else ("404 Not Found", _not_found("agent_not_found", path))
    if method == "GET" and path == f"{CONTROL_PREFIX}/personas":
        return "200 OK", persona_catalog_projection or default_persona_catalog_projection()
    if method == "POST" and path == f"{CONTROL_PREFIX}/personas/active":
        projection = select_persona_projection(persona_catalog_projection or default_persona_catalog_projection(), _parse_active_selection(environ, key="persona_id"))
        if projection is None:
            return "404 Not Found", _not_found("persona_not_found", path)
        return "200 OK", {**projection, "voice_id": active_persona_voice_id(projection), "execution_started": False}
    return None


def default_agent_catalog_projection() -> dict[str, Any]:
    agents = (
        _agent(
            "agent.main.marvex",
            "Main Marvex",
            "orchestrator",
            ["provider_simple_chat", "capability_tool", "web_search", "grounded_answer", "memory", "memory_tree_needed", "browser_computer_use", "mcp_needed", "mcp_skill", "skill_needed", "file_read_list_search"],
            ["builtin.time_date", "builtin.capability_diagnostics", "builtin.repo_status"],
            ["skill.planning", "skill.brainstorming", "skill.verification"],
            can_spawn=True,
            spawnable=["agent.deep_search", "agent.coding", "agent.browser_operator", "agent.memory_knowledge", "agent.verifier"],
            max_subagents=2,
        ),
        _agent("agent.deep_search", "Deep Search", "specialist", ["web_search", "grounded_answer", "memory_tree_needed"], ["web_search.search", "mcp.memory.read"], ["skill.deep_search"]),
        _agent("agent.coding", "Coding", "specialist", ["file_read_list_search", "capability_tool", "skill_needed"], ["filesystem.read", "filesystem.search", "builtin.repo_status"], ["skill.coding", "skill.verification"]),
        _agent("agent.browser_operator", "Browser Operator", "specialist", ["browser_computer_use", "web_search"], ["browser.playwright", "browser_use.task", "computer_use.proposal"], ["skill.browser_automation", "skill.computer_use_safety"]),
        _agent("agent.memory_knowledge", "Memory Knowledge", "specialist", ["memory", "memory_tree_needed", "grounded_answer"], ["memory.read", "memory_tree.search"], ["skill.memory"]),
        _agent("agent.verifier", "Verifier", "verifier", ["capability_tool", "file_read_list_search", "grounded_answer"], ["builtin.repo_status", "test.runner"], ["skill.verification"]),
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "active_agent_id": "agent.main.marvex",
        "agents": list(agents),
        "agent_count": len(agents),
        "selectable_count": sum(1 for agent in agents if agent["direct_selectable"]),
        "raw_payload_persisted": False,
    }


def default_persona_catalog_projection() -> dict[str, Any]:
    personas = (
        {
            "schema_version": SCHEMA_VERSION,
            "persona_id": "persona.marvex.female",
            "display_name": "Marvex",
            "assistant_identity": "Marvex is the Assistant OS runtime companion, not a provider wrapper.",
            "voice_id": "af_heart",
            "voice_gender_presentation": "female",
            "speaking_style": "Concise, direct, pragmatic, and suitable for a female TTS voice.",
            "raw_prompt_persisted": False,
        },
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "active_persona_id": "persona.marvex.female",
        "personas": list(personas),
        "persona_count": len(personas),
        "raw_payload_persisted": False,
    }


def select_agent_projection(projection: dict[str, Any], agent_id: str | None) -> dict[str, Any] | None:
    selected = agent_id or str(projection.get("active_agent_id") or "")
    agents = [dict(agent) for agent in projection.get("agents", ()) if isinstance(agent, dict)]
    if not any(str(agent.get("agent_id")) == selected for agent in agents):
        return None
    return {**projection, "active_agent_id": selected, "agents": agents}


def select_persona_projection(projection: dict[str, Any], persona_id: str | None) -> dict[str, Any] | None:
    selected = persona_id or str(projection.get("active_persona_id") or "")
    personas = [dict(persona) for persona in projection.get("personas", ()) if isinstance(persona, dict)]
    if not any(str(persona.get("persona_id")) == selected for persona in personas):
        return None
    return {**projection, "active_persona_id": selected, "personas": personas}


def active_persona_voice_id(projection: dict[str, Any]) -> str:
    selected = str(projection.get("active_persona_id") or "")
    for persona in projection.get("personas", ()):
        if isinstance(persona, dict) and str(persona.get("persona_id")) == selected:
            return str(persona.get("voice_id") or "")
    return ""


def _agent(
    agent_id: str,
    display_name: str,
    role: str,
    allowed_intents: list[str],
    default_capability_refs: list[str],
    default_skill_refs: list[str],
    *,
    can_spawn: bool = False,
    spawnable: list[str] | None = None,
    max_subagents: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "agent_id": agent_id,
        "display_name": display_name,
        "role": role,
        "allowed_intents": allowed_intents,
        "default_capability_refs": default_capability_refs,
        "default_skill_refs": default_skill_refs,
        "direct_selectable": True,
        "can_spawn_subagents": can_spawn,
        "spawnable_agent_ids": list(spawnable or []),
        "max_subagents_per_turn": max_subagents,
        "raw_prompt_persisted": False,
    }


def _parse_active_selection(environ: dict[str, Any], *, key: str) -> str | None:
    try:
        payload = json.loads(_read_request_body(environ))
    except Exception:
        return None
    value = payload.get(key) if isinstance(payload, dict) else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _read_request_body(environ: dict[str, Any]) -> str:
    length_text = str(environ.get("CONTENT_LENGTH") or "0")
    content_length = int(length_text) if length_text.strip() else 0
    raw_body = environ["wsgi.input"].read(content_length)
    return raw_body.decode("utf-8") if isinstance(raw_body, bytes) else str(raw_body)


def _not_found(reason: str, path: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-control-plane-error",
        "error_id": "control-plane-error",
        "code": "NOT_FOUND",
        "message": "Control Plane resource not found.",
        "recoverable": False,
        "source": "control_plane_api",
        "details": {"reason": reason, "path": path},
    }
