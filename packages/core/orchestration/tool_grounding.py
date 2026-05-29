"""Authoritative tool-catalog grounding for the provider system prompt.

Generates a system-prompt block listing the *real* tools from the tool
registries so the model stops inventing capabilities it does not have (the
field showed it claiming to "route to the agent.deep_search subagent / your RAG
tools"). Because the list is generated from the same registries that actually
execute tools, it can never drift from reality.

This is the interim fix for B2 (docs/TODO/BATCH_PLAN.md). The full fix is the
agentic tool-calling loop (docs/TODO/02), which will feed these as real tool
schemas the model can call.
"""

from __future__ import annotations

_GROUNDING_CACHE: str | None = None


def available_tools_grounding() -> str:
    """Return the cached grounding block built from the tool registries."""

    global _GROUNDING_CACHE
    if _GROUNDING_CACHE is not None:
        return _GROUNDING_CACHE
    _GROUNDING_CACHE = _build_grounding()
    return _GROUNDING_CACHE


def _build_grounding() -> str:
    try:
        from packages.adapters.capabilities.tools import (
            default_registry,
            file_tools_registry,
        )

        lines: list[str] = []
        for registry in (default_registry(), file_tools_registry()):
            for tool in registry.tools():
                lines.append(f"- {tool.identifier()}: {tool.description}")
        tool_block = "\n".join(lines) if lines else "- (tool catalog unavailable)"
    except Exception:
        tool_block = "- (tool catalog unavailable)"
    return (
        "You are Marvex, a local-first assistant. These are the ONLY tools that "
        "exist in this system; the runtime executes them for you under a policy "
        "and approval boundary:\n"
        f"{tool_block}\n"
        "You do NOT have subagents, RAG pipelines, background workers, web "
        "browsing, or any capability that is not in the list above. Never claim "
        "to invoke, route to, hand off to, or use a tool, subagent, or service "
        "that is not listed. If a request needs a capability you do not have, "
        "say so plainly rather than pretending to perform it."
    )


def with_tool_grounding(instructions: str | None) -> str:
    """Append the tool grounding to provider instructions (or use it alone)."""

    grounding = available_tools_grounding()
    if instructions and instructions.strip():
        return f"{instructions.strip()}\n\n{grounding}"
    return grounding


__all__ = ["available_tools_grounding", "with_tool_grounding"]
