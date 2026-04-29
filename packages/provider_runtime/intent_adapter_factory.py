from __future__ import annotations

from collections.abc import Callable
from typing import Any


def create_route_adapter(adapter_cls: type, route_layer: Callable[[str], Any]) -> Any:
    return adapter_cls(route_layer=route_layer)


def create_policy_adapter(adapter_cls: type, enforcer: Any) -> Any:
    return adapter_cls(enforcer=enforcer)
