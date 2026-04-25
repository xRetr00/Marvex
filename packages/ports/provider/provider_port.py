"""Provider port signatures only.

This module defines the future provider boundary without provider behavior.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts import ProviderRequest, ProviderResponse


@runtime_checkable
class ProviderPort(Protocol):
    """Signature-only provider adapter boundary."""

    def send(self, request: ProviderRequest) -> ProviderResponse:
        ...
