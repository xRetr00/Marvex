"""Model-driven UI directives.

The model exposes a builtin UI toolset — show_product / show_info / show_image /
show_plan — that it can call to control what the shell renders. Two delivery
paths are supported (see CONTRACT decision "both: tool-calls + JSON fallback"):

  1. Native provider tool/function calls (when the model supports them), and
  2. a universal structured-response convention: a fenced block in the reply

        ```marvex:ui
        {"directives": [{"kind": "product", "products": [...]}, ...]}
        ```

`parse_ui_directives` extracts + validates the convention block and returns the
clean user-visible text plus the validated directives, so rendering is driven by
the model's explicit intent rather than frontend keyword guessing.
"""
from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "1"

DIRECTIVE_KINDS = ("product", "info", "image", "plan")

# Tool name -> directive kind, for the native tool-call path.
UI_TOOL_TO_KIND = {
    "show_product": "product",
    "show_info": "info",
    "show_image": "image",
    "show_plan": "plan",
}

_BLOCK_RE = re.compile(r"```marvex:ui\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_MAX_PRODUCTS = 12
_MAX_STEPS = 30


def _coerce_product(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    try:
        price = float(raw.get("price")) if raw.get("price") is not None else None
    except (TypeError, ValueError):
        price = None
    product: dict[str, Any] = {"title": title[:120]}
    if price is not None:
        product["price"] = price
    if raw.get("currency"):
        product["currency"] = str(raw["currency"])[:4]
    if raw.get("image"):
        product["image"] = str(raw["image"])[:2000]
    rating = raw.get("rating")
    if isinstance(rating, (int, float)):
        product["rating"] = max(0.0, min(5.0, float(rating)))
    if raw.get("badge"):
        product["badge"] = str(raw["badge"])[:24]
    return product


def _coerce_directive(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    kind = str(raw.get("kind") or "").strip().lower()
    if kind not in DIRECTIVE_KINDS:
        return None
    if kind == "product":
        products = [p for p in (_coerce_product(item) for item in raw.get("products") or []) if p]
        if not products:
            return None
        return {"kind": "product", "products": products[:_MAX_PRODUCTS]}
    if kind == "info":
        title = str(raw.get("title") or "").strip()
        body = str(raw.get("body") or "").strip()
        if not title and not body:
            return None
        return {"kind": "info", "title": title[:200], "body": body[:4000]}
    if kind == "image":
        src = str(raw.get("src") or raw.get("url") or "").strip()
        if not src:
            return None
        return {"kind": "image", "src": src[:2000], "title": str(raw.get("title") or "Image")[:200], "description": str(raw.get("description") or "")[:1000]}
    if kind == "plan":
        steps = [str(s).strip()[:200] for s in raw.get("steps") or [] if str(s).strip()]
        if not steps:
            return None
        return {"kind": "plan", "steps": steps[:_MAX_STEPS]}
    return None


def directives_from_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map native show_* tool calls into validated UI directives."""
    directives: list[dict[str, Any]] = []
    for call in tool_calls or []:
        if not isinstance(call, dict):
            continue
        name = str(call.get("name") or call.get("tool") or "").strip().lower()
        kind = UI_TOOL_TO_KIND.get(name)
        if kind is None:
            continue
        args = call.get("arguments") or call.get("args") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                continue
        coerced = _coerce_directive({"kind": kind, **(args if isinstance(args, dict) else {})})
        if coerced:
            directives.append(coerced)
    return directives


def parse_ui_directives(text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract + validate ```marvex:ui directives. Returns (directives, clean_text)."""
    if not text or "marvex:ui" not in text.lower():
        return [], text
    directives: list[dict[str, Any]] = []
    for match in _BLOCK_RE.finditer(text):
        payload = match.group(1).strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        items = parsed.get("directives") if isinstance(parsed, dict) else parsed
        if isinstance(parsed, dict) and "kind" in parsed:
            items = [parsed]
        for item in items or []:
            coerced = _coerce_directive(item)
            if coerced:
                directives.append(coerced)
    clean_text = _BLOCK_RE.sub("", text).strip()
    return directives, clean_text


__all__ = [
    "SCHEMA_VERSION",
    "DIRECTIVE_KINDS",
    "UI_TOOL_TO_KIND",
    "parse_ui_directives",
    "directives_from_tool_calls",
]
