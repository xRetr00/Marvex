from .auth_policy import LOCAL_AUTH_HEADER, LOCAL_AUTH_SCHEME, validate_local_bearer_token
from .contracts import (
    LocalApiConfig,
    LocalTurnRequestEnvelope,
    TraceReader,
    TurnHandler,
)


def create_local_api_asgi_app(*args, **kwargs):
    from .asgi_app import create_local_api_asgi_app as _create_local_api_asgi_app

    return _create_local_api_asgi_app(*args, **kwargs)


def create_default_health_version_provider(*args, **kwargs):
    from .runner import create_default_health_version_provider as _create_default_health_version_provider

    return _create_default_health_version_provider(*args, **kwargs)


def run_local_health_version_api(*args, **kwargs):
    from .runner import run_local_health_version_api as _run_local_health_version_api

    return _run_local_health_version_api(*args, **kwargs)

__all__ = [
    "LOCAL_AUTH_HEADER",
    "LOCAL_AUTH_SCHEME",
    "LocalApiConfig",
    "LocalTurnRequestEnvelope",
    "TraceReader",
    "TurnHandler",
    "create_default_health_version_provider",
    "create_local_api_asgi_app",
    "validate_local_bearer_token",
    "run_local_health_version_api",
]
