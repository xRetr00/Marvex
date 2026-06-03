"""In-process conversation history store for the LiteLLM provider.

LiteLLM is used here through the Responses API surface. Some configured upstream
providers still lack durable server-side conversation state, so to honour
``ProviderRequest.previous_response_id`` the adapter must rebuild the prior turn
context client-side when needed. This module
provides a tiny in-memory store keyed by the response id we hand back to the
caller, so subsequent turns can look up prior ``(user, assistant)`` pairs and
prepend them to the next request.

The store is intentionally minimal: no persistence, no eviction policy beyond a
bounded LRU cap. Callers that need durable conversation memory should layer
their own persistence on top.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Iterable


Message = dict[str, str]


class LiteLLMConversationStore:
    """Bounded in-memory map from provider ``response_id`` -> message history.

    Behaviour:

    * ``recall(None)`` and ``recall(unknown_id)`` both return ``[]``.
    * ``remember(response_id, messages)`` stores a shallow copy of ``messages``.
    * Most-recently-used entries are kept; oldest are evicted past ``max_entries``.
    * System/instructions are stored as the first message just like everything
      else; the caller decides whether to include them.
    """

    def __init__(self, *, max_entries: int = 256) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._histories: "OrderedDict[str, list[Message]]" = OrderedDict()

    def recall(self, response_id: str | None) -> list[Message]:
        if not response_id:
            return []
        history = self._histories.get(response_id)
        if history is None:
            return []
        # Move to most-recently-used position.
        self._histories.move_to_end(response_id)
        return [dict(message) for message in history]

    def remember(self, response_id: str | None, messages: Iterable[Message]) -> None:
        if not response_id:
            return
        snapshot = [dict(message) for message in messages]
        self._histories[response_id] = snapshot
        self._histories.move_to_end(response_id)
        while len(self._histories) > self._max_entries:
            self._histories.popitem(last=False)

    def forget(self, response_id: str | None) -> None:
        if not response_id:
            return
        self._histories.pop(response_id, None)

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self._histories)


__all__ = ["LiteLLMConversationStore", "Message"]
