from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from packages.local_service_startup.discovery import read_local_api_discovery_metadata


JsonRequester = Callable[
    [str, str, dict[str, str], bytes | None],
    tuple[int, dict[str, Any]],
]


@dataclass(frozen=True)
class LocalApiClientResponse:
    status_code: int
    body: dict[str, Any]


@dataclass(frozen=True)
class LocalApiClient:
    base_url: str
    auth_required: bool
    auth_token_present: bool
    _requester: JsonRequester = field(
        default_factory=lambda: _default_json_requester,
        repr=False,
    )

    @classmethod
    def from_discovery_metadata(
        cls,
        metadata: dict[str, Any],
        *,
        requester: JsonRequester | None = None,
    ) -> LocalApiClient:
        _validate_safe_client_metadata(metadata)
        return cls(
            base_url=str(metadata["base_url"]).rstrip("/"),
            auth_required=metadata["auth_required"] is True,
            auth_token_present=metadata["auth_token_present"] is True,
            _requester=requester or _default_json_requester,
        )

    def get_health(self) -> LocalApiClientResponse:
        return self._request_json("GET", "/health")

    def get_version(self) -> LocalApiClientResponse:
        return self._request_json("GET", "/version")

    def post_turn(
        self,
        body: dict[str, Any],
        *,
        local_auth_token: str | None = None,
    ) -> LocalApiClientResponse:
        return self._request_json(
            "POST",
            "/v1/turns",
            body=body,
            local_auth_token=local_auth_token,
        )

    def get_trace(
        self,
        trace_id: str,
        *,
        local_auth_token: str | None = None,
    ) -> LocalApiClientResponse:
        if not trace_id.strip():
            raise ValueError("trace_id must be non-empty")
        if not all(character.isalnum() or character in ".:-_" for character in trace_id):
            raise ValueError("trace_id contains unsupported characters")
        return self._request_json(
            "GET",
            f"/v1/traces/{trace_id}",
            local_auth_token=local_auth_token,
        )

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        local_auth_token: str | None = None,
    ) -> LocalApiClientResponse:
        if not path.startswith("/") or "://" in path:
            raise ValueError("path must be a local API path")

        headers = {"Accept": "application/json"}
        if path.startswith(("/v1/turns", "/v1/traces/")):
            if local_auth_token is None or not local_auth_token.strip():
                raise ValueError("local_auth_token is required for protected calls")
            headers["Authorization"] = f"Bearer {local_auth_token}"

        raw_body = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            raw_body = json.dumps(
                body,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")

        status_code, response_body = self._requester(
            method=method,
            url=f"{self.base_url}{path}",
            headers=headers,
            body=raw_body,
        )
        return LocalApiClientResponse(status_code=status_code, body=response_body)


def load_local_api_client_from_discovery(
    *,
    discovery_file_path: str,
    local_user_root: str | Path | None = None,
    requester: JsonRequester | None = None,
) -> LocalApiClient:
    metadata = read_local_api_discovery_metadata(
        discovery_file_path=discovery_file_path,
        local_user_root=local_user_root,
    )
    return LocalApiClient.from_discovery_metadata(metadata, requester=requester)


def _default_json_requester(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
) -> tuple[int, dict[str, Any]]:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            status_code = response.status
            response_body = response.read()
    except HTTPError as exc:
        status_code = exc.code
        response_body = exc.read()

    parsed = json.loads(response_body.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("local API response must be a JSON object")
    return status_code, parsed


def _validate_safe_client_metadata(metadata: dict[str, Any]) -> None:
    if metadata.get("bind_host") != "127.0.0.1":
        raise ValueError("discovery metadata must be loopback-only")
    if not isinstance(metadata.get("port"), int):
        raise ValueError("discovery metadata port must be an integer")
    if metadata.get("base_url") != f"http://127.0.0.1:{metadata['port']}":
        raise ValueError("discovery metadata must use loopback base_url")

    serialized = json.dumps(metadata, sort_keys=True).lower()
    forbidden_fragments = (
        "local_auth_token",
        "bearer ",
        "api_key",
        "apikey",
        "provider_token",
        "0.0.0.0",
    )
    for fragment in forbidden_fragments:
        if fragment in serialized:
            raise ValueError("discovery metadata contains unsafe fields")

    if metadata.get("auth_required") is not True:
        raise ValueError("discovery metadata must require auth")
    if metadata.get("auth_token_present") is not True:
        raise ValueError("discovery metadata must report token presence")
    if metadata.get("token_value_logged") is not False:
        raise ValueError("discovery metadata must not log token values")
