"""Conversation-scoped working memory of entities Marvex produced (docs/TODO/01).

Short-term, per-session memory of the concrete things a turn produced - the
file it wrote, the directory it listed, the search results it returned - so a
later turn can resolve back-references like "that file", "it", or "those
results" to a real referent instead of re-parsing the sentence in isolation.

This is NOT long-term/semantic memory (that lives in memory_tree_runtime). It
is a small bounded ring per session, holds only safe labels/refs (never raw
file contents), and is pure + unit-testable (no provider, no fastapi).
"""

from __future__ import annotations

from collections import OrderedDict, deque
from typing import Deque

from pydantic import BaseModel, ConfigDict

# Entity type constants.
ENTITY_FILE = "file"
ENTITY_DIRECTORY = "directory"
ENTITY_WEB_RESULT = "web_result"

_FILE_SUFFIXES = (".txt", ".md", ".json", ".csv", ".log", ".pdf")

# Multi-word back-reference phrases (substring match on lowercased text).
_BACKREF_PHRASES = (
    "that file",
    "the file",
    "this file",
    "same file",
    "that one",
    "the same",
)
# Single-word back-references (matched as whole words).
_BACKREF_WORDS = frozenset({"it", "them", "those", "they"})


class ConversationEntity(BaseModel):
    model_config = ConfigDict(frozen=True)
    entity_type: str
    ref_id: str  # e.g. a relative file path "notes/output.txt" or a url
    label: str  # short, safe human label
    turn_id: str

    def safe_projection(self) -> dict[str, str]:
        return {
            "entity_type": self.entity_type,
            "ref_id": self.ref_id,
            "label": self.label,
            "turn_id": self.turn_id,
        }


class ConversationEntityStore:
    """Bounded per-session ring of produced entities (most-recent last)."""

    def __init__(self, *, max_per_session: int = 64, max_sessions: int = 256) -> None:
        if max_per_session < 1 or max_sessions < 1:
            raise ValueError("bounds must be >= 1")
        self._max_per_session = max_per_session
        self._max_sessions = max_sessions
        self._sessions: "OrderedDict[str, Deque[ConversationEntity]]" = OrderedDict()

    def remember(
        self, session_id: str, *, entity_type: str, ref_id: str, label: str, turn_id: str
    ) -> None:
        if not session_id or not ref_id:
            return
        ring = self._sessions.get(session_id)
        if ring is None:
            ring = deque(maxlen=self._max_per_session)
            self._sessions[session_id] = ring
        ring.append(
            ConversationEntity(entity_type=entity_type, ref_id=ref_id, label=label or ref_id, turn_id=turn_id)
        )
        self._sessions.move_to_end(session_id)
        while len(self._sessions) > self._max_sessions:
            self._sessions.popitem(last=False)

    def recent(self, session_id: str, *, entity_type: str | None = None) -> list[ConversationEntity]:
        ring = self._sessions.get(session_id)
        if not ring:
            return []
        items = list(ring)[::-1]  # most recent first
        if entity_type is None:
            return items
        return [item for item in items if item.entity_type == entity_type]

    def most_recent(self, session_id: str, *, entity_type: str | None = None) -> ConversationEntity | None:
        items = self.recent(session_id, entity_type=entity_type)
        return items[0] if items else None


def _words(text: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() else " " for ch in text.lower())
    return cleaned.split()


def _has_explicit_filename(lowered: str) -> bool:
    for word in lowered.split():
        stripped = word.strip("\"'(),")
        if any(stripped.endswith(suffix) and len(stripped) > len(suffix) for suffix in _FILE_SUFFIXES):
            return True
    return False


def text_references_prior_file(text: str | None) -> bool:
    """True when the text refers back to a file without naming a new one."""

    value = (text or "").strip().lower()
    if not value:
        return False
    if _has_explicit_filename(value):
        return False  # an explicit filename is present; not a back-reference
    if any(phrase in value for phrase in _BACKREF_PHRASES):
        return True
    return bool(_BACKREF_WORDS.intersection(_words(value)))


def resolve_file_reference(
    text: str | None, store: ConversationEntityStore, session_id: str
) -> str | None:
    """Resolve "that file"/"it"/... to the most recent file ref for the session.

    Returns the file ref_id (path) or None if the text doesn't back-reference a
    file or there is no prior file entity.
    """

    if not text_references_prior_file(text):
        return None
    entity = store.most_recent(session_id, entity_type=ENTITY_FILE)
    return entity.ref_id if entity is not None else None


__all__ = [
    "ENTITY_FILE",
    "ENTITY_DIRECTORY",
    "ENTITY_WEB_RESULT",
    "ConversationEntity",
    "ConversationEntityStore",
    "resolve_file_reference",
    "text_references_prior_file",
]
