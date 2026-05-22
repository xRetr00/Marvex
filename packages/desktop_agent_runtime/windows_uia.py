from __future__ import annotations

import importlib
import sys
from typing import Any

from packages.desktop_agent_runtime.models import DesktopContentItem, DesktopPerceptionSnapshot
from packages.desktop_agent_runtime.redaction import redact_and_bound_text


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 14)].rstrip() + " [TRUNCATED]"


def _sanitize_text(value: Any, max_chars: int) -> str:
    return redact_and_bound_text(str(value or "").strip(), max_chars=max_chars)


def _active_window_projection(pywinauto_module: Any, max_chars: int) -> dict[str, str] | None:
    desktop = pywinauto_module.Desktop(backend="uia")
    window = desktop.get_active()
    element_info = getattr(window, "element_info", None)
    title = _sanitize_text(getattr(element_info, "name", "") if element_info else "", max_chars)
    friendly = getattr(window, "friendly_class_name", None)
    class_name = _sanitize_text(friendly() if callable(friendly) else getattr(element_info, "class_name", ""), max_chars)
    if not title and not class_name:
        return None
    return {"title": title, "class_name": class_name}


def _focused_control_path(uiautomation_module: Any, max_chars: int, max_depth: int) -> list[dict[str, str]]:
    focused = uiautomation_module.GetFocusedControl()
    path: list[dict[str, str]] = []
    current = focused
    steps = 0
    while current is not None and steps < max_depth:
        path.append(
            {
                "name": _sanitize_text(getattr(current, "Name", ""), max_chars),
                "control_type": _sanitize_text(getattr(current, "ControlTypeName", ""), max_chars),
            }
        )
        get_parent = getattr(current, "GetParentControl", None)
        current = get_parent() if callable(get_parent) else None
        steps += 1
    return path


def collect_projection(max_text_chars: int = 120, max_control_depth: int = 8) -> dict[str, Any]:
    projection: dict[str, Any] = {
        "available": False,
        "platform": sys.platform,
        "active_window": None,
        "focused_control_path": [],
        "raw_screen_persisted": False,
        "raw_keystrokes_persisted": False,
    }
    if not sys.platform.startswith("win"):
        return projection

    try:
        pywinauto_module = importlib.import_module("pywinauto")
        uiautomation_module = importlib.import_module("uiautomation")
    except Exception as exc:  # pragma: no cover - validated via unit tests with monkeypatch
        projection["error"] = _truncate(f"uia_dependency_unavailable:{type(exc).__name__}", max_text_chars)
        return projection

    errors: list[str] = []
    try:
        projection["active_window"] = _active_window_projection(pywinauto_module, max_text_chars)
    except Exception as exc:
        errors.append(f"pywinauto:{type(exc).__name__}")
    try:
        projection["focused_control_path"] = _focused_control_path(
            uiautomation_module, max_text_chars, max_control_depth
        )
    except Exception as exc:
        errors.append(f"uiautomation:{type(exc).__name__}")
    projection["available"] = bool(projection["active_window"] or projection["focused_control_path"])
    if errors:
        projection["error"] = _truncate("uia_partial_error:" + ",".join(errors), max_text_chars)

    return projection


class WindowsUIAutomationPerceptionAdapter:
    def focused_content(
        self,
        *,
        trace_id: str,
        content_budget_chars: int = 1600,
    ) -> DesktopPerceptionSnapshot:
        projection = collect_projection(max_text_chars=min(240, content_budget_chars))
        lines: list[str] = []
        active = projection.get("active_window")
        if isinstance(active, dict):
            title = str(active.get("title") or "").strip()
            class_name = str(active.get("class_name") or "").strip()
            if title or class_name:
                lines.append(f"active_window title={title} class={class_name}".strip())
        controls = projection.get("focused_control_path")
        if isinstance(controls, list):
            for control in controls[:8]:
                if not isinstance(control, dict):
                    continue
                name = str(control.get("name") or "").strip()
                control_type = str(control.get("control_type") or "").strip()
                if name or control_type:
                    lines.append(f"focused_control type={control_type} name={name}".strip())
        if not lines and projection.get("error"):
            lines.append(str(projection["error"]))
        item = DesktopContentItem.from_text(
            source_kind="focused_window",
            text="\n".join(lines) or "desktop agent content unavailable",
            application="windows_uia" if projection.get("available") else None,
            max_chars=content_budget_chars,
        )
        return DesktopPerceptionSnapshot.from_items(
            trace_id=trace_id,
            snapshot_id=f"{trace_id}:desktop:u ia".replace(" ", ""),
            items=(item,),
            content_budget_chars=content_budget_chars,
        )
