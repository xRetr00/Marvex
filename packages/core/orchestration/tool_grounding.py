"""Authoritative tool-catalog + temporal grounding for the system prompt.

Generates the always-injected system-prompt block that:

1. Tells the model the *real* tools it has (from the registries) so it stops
   inventing capabilities ("agent.deep_search subagent", "RAG tools"). This is
   the interim B2 fix.
2. Tells the model it has ``web.search`` and the **current date**, and that its
   built-in knowledge has a training cutoff in the past - so for anything
   time-sensitive ("latest"/"newest"/"current", recent releases, prices, who
   holds a role now, etc.) it must use ``web.search`` instead of answering from
   stale memory. This replaces the brittle grounded-answer hard-reject: rather
   than refusing, the model knows where "now" is and searches.

The tool catalog is static (cached); the date is computed per turn.
"""

from __future__ import annotations

from datetime import datetime

_TOOL_CATALOG_CACHE: str | None = None

# web.search lives on the executor (it needs an injected provider), so it is not
# in the static registries. Marvex ships with web search configured, so we
# always advertise it here per product direction.
_WEB_SEARCH_LINE = (
    "- web.search: Search the web and return result titles, URLs, and snippets "
    "to ground a current/factual answer."
)
_MEMORY_TOOL_LINES = (
    "- memory.search: Search approved Marvex memory and return safe previews with memory refs.",
    "- memory.remember: Save memory only when the user explicitly asks to remember something; otherwise create a pending memory candidate.",
    "- memory.forget: Forget an exact approved memory ref through the policy boundary.",
    "- memory.list_recent: List recent approved memory refs and safe previews.",
)


def _static_tool_catalog() -> str:
    global _TOOL_CATALOG_CACHE
    if _TOOL_CATALOG_CACHE is not None:
        return _TOOL_CATALOG_CACHE
    try:
        from packages.adapters.capabilities.tools import (
            default_registry,
            file_tools_registry,
        )

        lines: list[str] = []
        for registry in (default_registry(), file_tools_registry()):
            for tool in registry.tools():
                lines.append(f"- {tool.identifier()}: {tool.description}")
        lines.append(_WEB_SEARCH_LINE)
        lines.extend(_MEMORY_TOOL_LINES)
        _TOOL_CATALOG_CACHE = "\n".join(lines)
    except Exception:
        _TOOL_CATALOG_CACHE = _WEB_SEARCH_LINE
    return _TOOL_CATALOG_CACHE


def available_tools_grounding(*, now: datetime | None = None) -> str:
    """Return the grounding block, including the current date (per turn)."""

    moment = now or datetime.now().astimezone()
    if moment.tzinfo is None:
        moment = moment.astimezone()
    offset = moment.strftime("%z")
    pretty_offset = f"UTC{offset[:3]}:{offset[3:]}" if offset else "UTC"
    date_line = f"The current date and time is {moment.strftime('%Y-%m-%d %H:%M')} {pretty_offset}."
    catalog = _static_tool_catalog()
    return (
        "You are Marvex, a local-first assistant. "
        f"{date_line} Your built-in knowledge has a training cutoff in the past. "
        "For anything time-sensitive - the latest/newest/current version of "
        "something, recent releases, current events, prices, who holds a role "
        "now, or any fact you are not certain is still current - use the "
        "web.search tool instead of answering from memory. Never state a "
        "'latest' or 'current' fact from memory without searching first; if you "
        "cannot verify it, say so plainly.\n"
        "These are the ONLY tools that exist in this system; the runtime "
        "executes them for you under a policy and approval boundary:\n"
        f"{catalog}\n"
        "When the user's request is ambiguous or missing a detail you need to "
        "answer correctly (e.g. an ambiguous name like 'open ai', or two "
        "plausible meanings), call the clarify tool to ask them a brief question "
        "instead of guessing. After they answer, continue with their choice.\n"
        "To act on the web or desktop, call a tool: use 'browser_use' for "
        "browser tasks and 'computer_use' for Windows desktop actions. These "
        "run only after the user approves; describe the task clearly and let "
        "the approval boundary handle execution.\n"
        "You do NOT have subagents, RAG pipelines, background workers, or any "
        "capability that is not in the list above. Never claim to invoke, route "
        "to, hand off to, or use a tool, subagent, or service that is not "
        "listed. If a request needs a capability you do not have, say so plainly "
        "rather than pretending to perform it."
    )


def with_tool_grounding(instructions: str | None, *, now: datetime | None = None) -> str:
    """Append the tool + temporal grounding to provider instructions."""

    grounding = available_tools_grounding(now=now)
    if instructions and instructions.strip():
        return f"{instructions.strip()}\n\n{grounding}"
    return grounding


__all__ = ["available_tools_grounding", "with_tool_grounding"]
