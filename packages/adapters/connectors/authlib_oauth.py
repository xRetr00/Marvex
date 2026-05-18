from __future__ import annotations

from typing import Any


class AuthlibOAuthBackend:
    """Import-backed OAuth seam; token exchange is intentionally not performed here."""

    def safe_import_probe(self) -> dict[str, Any]:
        from authlib.integrations.requests_client import OAuth2Session

        return {
            "backend": "authlib",
            "oauth2_session_available": OAuth2Session is not None,
            "network_call_started": False,
            "raw_token_persisted": False,
        }
