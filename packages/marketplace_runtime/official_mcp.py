from __future__ import annotations

from typing import Any

from packages.marketplace_runtime.models import McpMarketplaceCatalog, McpMarketplaceEntry


def catalog_from_official_registry_payload(payload: dict[str, Any]) -> McpMarketplaceCatalog:
    entries: list[McpMarketplaceEntry] = []
    seen_latest: set[str] = set()
    for row in payload.get("servers", []):
        if not isinstance(row, dict):
            continue
        meta = row.get("_meta", {})
        official = meta.get("io.modelcontextprotocol.registry/official", {}) if isinstance(meta, dict) else {}
        if isinstance(official, dict) and official.get("isLatest") is False:
            continue
        server = row.get("server")
        if not isinstance(server, dict):
            continue
        name = str(server.get("name") or "").strip()
        if not name or name in seen_latest:
            continue
        seen_latest.add(name)
        entry = _entry_from_server(server)
        if entry is not None:
            entries.append(entry)
    return McpMarketplaceCatalog.from_entries(tuple(entries))


def _entry_from_server(server: dict[str, Any]) -> McpMarketplaceEntry | None:
    name = str(server.get("name") or "").strip()
    description = str(server.get("description") or name).strip()[:800]
    if not name or not description:
        return None
    package = _first_package(server.get("packages"))
    remote = _first_remote(server.get("remotes"))
    kwargs: dict[str, Any] = {}
    transports: list[str] = []
    if package is not None:
        registry_type = _registry_type(str(package.get("registryType") or "none"))
        kwargs.update(
            package_registry_type=registry_type,
            package_identifier=str(package.get("identifier") or ""),
            package_version=str(package.get("version") or "") or None,
            required_dep_group_id="mcp",
            install_allowed=True,
        )
        transport = package.get("transport")
        if isinstance(transport, dict) and transport.get("type"):
            transports.append(str(transport["type"]))
    if remote is not None:
        remote_type = _remote_type(str(remote.get("type") or ""))
        if remote_type is not None:
            kwargs.update(remote_transport=remote_type, remote_url=str(remote.get("url") or ""))
            transports.append(remote_type)
    return McpMarketplaceEntry(
        schema_version="1",
        registry_name="official_mcp_registry",
        server_id=name,
        display_name=str(server.get("title") or name)[:120],
        description=description,
        homepage_url=str(server.get("websiteUrl") or "") or None,
        source_url=_repo_url(server.get("repository")),
        registry_url=f"https://registry.modelcontextprotocol.io/v0/servers/{name}",
        transport_summaries=tuple(transports),
        **kwargs,
    )


def _first_package(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), None)
    return None


def _first_remote(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict) and item.get("url")), None)
    return None


def _repo_url(value: Any) -> str | None:
    if isinstance(value, dict):
        text = str(value.get("url") or "").strip()
        return text or None
    return None


def _registry_type(value: str) -> str:
    normalized = value.lower().strip()
    return normalized if normalized in {"pypi", "npm", "oci", "local"} else "none"


def _remote_type(value: str) -> str | None:
    normalized = value.lower().replace("-", "_").strip()
    return normalized if normalized in {"streamable_http", "sse"} else None


__all__ = ["catalog_from_official_registry_payload"]

