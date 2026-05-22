from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.desktop_agent_runtime.redaction import redact_and_bound_text


SCHEMA_VERSION = "0.1.1-draft"
DEFAULT_CONTENT_BUDGET_CHARS = 1600


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


class DesktopAgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DesktopContentItem(DesktopAgentModel):
    source_kind: Literal["focused_window", "screenpipe_recall", "uia_tree", "browser_tab", "terminal_output"]
    safe_text: str = Field(..., max_length=DEFAULT_CONTENT_BUDGET_CHARS)
    application: str | None = Field(default=None, max_length=80)
    content_chars: int = Field(..., ge=0)
    observed_at: str = Field(default_factory=_utc_iso)
    raw_content_persisted: Literal[False] = False

    @classmethod
    def from_text(
        cls,
        *,
        source_kind: Literal["focused_window", "screenpipe_recall", "uia_tree", "browser_tab", "terminal_output"],
        text: str,
        application: str | None = None,
        max_chars: int = DEFAULT_CONTENT_BUDGET_CHARS,
    ) -> "DesktopContentItem":
        safe = redact_and_bound_text(text, max_chars=max_chars)
        return cls(
            source_kind=source_kind,
            safe_text=safe,
            application=application,
            content_chars=len(safe),
        )


class DesktopPerceptionSnapshot(DesktopAgentModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1)
    snapshot_id: str = Field(..., min_length=1)
    observed_at: str = Field(default_factory=_utc_iso)
    items: tuple[DesktopContentItem, ...] = ()
    content_budget_chars: int = Field(default=DEFAULT_CONTENT_BUDGET_CHARS, ge=1, le=8000)
    local_only: Literal[True] = True
    approved_contract: Literal[True] = True
    raw_screen_persisted: Literal[False] = False
    raw_keystrokes_persisted: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False

    @field_validator("items")
    @classmethod
    def _bound_items(cls, value: tuple[DesktopContentItem, ...]) -> tuple[DesktopContentItem, ...]:
        return value[:8]

    @classmethod
    def from_items(
        cls,
        *,
        trace_id: str,
        snapshot_id: str,
        items: tuple[DesktopContentItem, ...],
        content_budget_chars: int = DEFAULT_CONTENT_BUDGET_CHARS,
    ) -> "DesktopPerceptionSnapshot":
        remaining = content_budget_chars
        bounded: list[DesktopContentItem] = []
        for item in items[:8]:
            if remaining <= 0:
                break
            safe_text = redact_and_bound_text(item.safe_text, max_chars=remaining)
            bounded.append(item.model_copy(update={"safe_text": safe_text, "content_chars": len(safe_text)}))
            remaining -= len(safe_text)
        return cls(
            trace_id=trace_id,
            snapshot_id=snapshot_id,
            items=tuple(bounded),
            content_budget_chars=content_budget_chars,
        )

    def context_text(self) -> str:
        return "\n".join(item.safe_text for item in self.items if item.safe_text).strip()

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "snapshot_id": self.snapshot_id,
            "observed_at": self.observed_at,
            "item_count": len(self.items),
            "content_chars": len(self.context_text()),
            "content": self.context_text(),
            "local_only": True,
            "approved_contract": True,
            "raw_screen_persisted": False,
            "raw_keystrokes_persisted": False,
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
        }


class DesktopRecallResult(DesktopAgentModel):
    schema_version: str = SCHEMA_VERSION
    trace_id: str = Field(..., min_length=1)
    query_summary: str = Field(..., min_length=1, max_length=240)
    items: tuple[DesktopContentItem, ...] = ()
    local_only: Literal[True] = True
    raw_screen_persisted: Literal[False] = False
    raw_audio_persisted: Literal[False] = False
    raw_transcript_persisted: Literal[False] = False
    raw_mcp_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "query_summary": self.query_summary,
            "item_count": len(self.items),
            "content": "\n".join(item.safe_text for item in self.items),
            "local_only": True,
            "raw_screen_persisted": False,
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
            "raw_mcp_payload_persisted": False,
        }
