from __future__ import annotations

from collections import OrderedDict, deque
from typing import Deque, Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionContextItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: Literal["user", "assistant", "tool"]
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    safe_summary: str = Field(..., min_length=1, max_length=2400)
    tool_result_refs: tuple[str, ...] = ()
    memory_refs: tuple[str, ...] = ()
    entity_refs: tuple[str, ...] = ()
    transcript_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "role": self.role,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "safe_summary": self.safe_summary,
            "tool_result_refs": list(self.tool_result_refs),
            "memory_refs": list(self.memory_refs),
            "entity_refs": list(self.entity_refs),
            "transcript_persisted": False,
        }


class SessionContextStore:
    """Provider-independent recent context for one local session."""

    def __init__(self, *, max_items_per_session: int = 32, max_sessions: int = 256) -> None:
        if max_items_per_session < 1 or max_sessions < 1:
            raise ValueError("bounds must be >= 1")
        self._max_items_per_session = max_items_per_session
        self._max_sessions = max_sessions
        self._sessions: "OrderedDict[str, Deque[SessionContextItem]]" = OrderedDict()

    def record_user_turn(self, session_id: str, *, trace_id: str, turn_id: str, text: str) -> None:
        self._append(
            session_id,
            SessionContextItem(
                role="user",
                trace_id=trace_id,
                turn_id=turn_id,
                safe_summary=_summarize(text, prefix="User"),
            ),
        )

    def record_assistant_turn(
        self,
        session_id: str,
        *,
        trace_id: str,
        turn_id: str,
        text: str,
        tool_result_refs: tuple[str, ...] = (),
        memory_refs: tuple[str, ...] = (),
        entity_refs: tuple[str, ...] = (),
    ) -> None:
        self._append(
            session_id,
            SessionContextItem(
                role="assistant",
                trace_id=trace_id,
                turn_id=turn_id,
                safe_summary=_summarize(text, prefix="Assistant"),
                tool_result_refs=tuple(tool_result_refs),
                memory_refs=tuple(memory_refs),
                entity_refs=tuple(entity_refs),
            ),
        )

    def recent(self, session_id: str) -> tuple[SessionContextItem, ...]:
        return tuple(self._sessions.get(session_id, ()))

    def safe_projection(self, session_id: str) -> dict[str, object]:
        items = self.recent(session_id)
        return {
            "session_id": session_id,
            "item_count": len(items),
            "items": [item.safe_projection() for item in items],
            "transcript_persisted": False,
        }

    def safe_snapshot(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "sessions": {
                session_id: [item.safe_projection() for item in ring]
                for session_id, ring in self._sessions.items()
            },
            "transcript_persisted": False,
        }

    @classmethod
    def from_snapshot(
        cls,
        payload: dict[str, object],
        *,
        max_items_per_session: int = 32,
        max_sessions: int = 256,
    ) -> "SessionContextStore":
        store = cls(max_items_per_session=max_items_per_session, max_sessions=max_sessions)
        sessions = payload.get("sessions", {}) if isinstance(payload, dict) else {}
        if not isinstance(sessions, dict):
            return store
        for session_id, rows in sessions.items():
            if not isinstance(session_id, str) or not isinstance(rows, list):
                continue
            for row in rows[-max_items_per_session:]:
                if not isinstance(row, dict):
                    continue
                try:
                    store._append(
                        session_id,
                        SessionContextItem(
                            role=str(row.get("role") or "user"),  # type: ignore[arg-type]
                            trace_id=str(row.get("trace_id") or "trace-restored"),
                            turn_id=str(row.get("turn_id") or "turn-restored"),
                            safe_summary=str(row.get("safe_summary") or "Restored context.")[:2400],
                            tool_result_refs=tuple(str(value) for value in row.get("tool_result_refs", ()) if value),
                            memory_refs=tuple(str(value) for value in row.get("memory_refs", ()) if value),
                            entity_refs=tuple(str(value) for value in row.get("entity_refs", ()) if value),
                        ),
                    )
                except Exception:
                    continue
        return store

    def prompt_context(self, session_id: str) -> str:
        items = self.recent(session_id)
        if not items:
            return ""
        lines = ["Recent chat context:"]
        for item in items:
            refs: list[str] = []
            if item.tool_result_refs:
                refs.append("tools=" + ",".join(item.tool_result_refs[:3]))
            if item.memory_refs:
                refs.append("memory=" + ",".join(item.memory_refs[:3]))
            if item.entity_refs:
                refs.append("entities=" + ",".join(item.entity_refs[:3]))
            suffix = f" [{' ; '.join(refs)}]" if refs else ""
            lines.append(f"- {item.role} {item.turn_id}: {item.safe_summary}{suffix}")
        return "\n".join(lines)

    def _append(self, session_id: str, item: SessionContextItem) -> None:
        if not session_id:
            return
        ring = self._sessions.get(session_id)
        if ring is None:
            ring = deque(maxlen=self._max_items_per_session)
            self._sessions[session_id] = ring
        ring.append(item)
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)


def _summarize(text: str, *, prefix: str) -> str:
    value = " ".join((text or "").strip().split())
    if not value:
        value = "empty turn"
    if len(value) > 2000:
        value = value[:1997].rstrip() + "..."
    return f"{prefix}: {value}"


__all__ = ["SessionContextItem", "SessionContextStore"]
