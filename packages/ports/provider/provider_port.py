"""Provider port signatures only.

This module defines the future provider boundary without provider behavior.
"""

from __future__ import annotations

from typing import Any, Protocol


class ProviderPort(Protocol):
    """Signature-only provider adapter boundary."""

    def send(self, request: Any) -> Any:
        ...

