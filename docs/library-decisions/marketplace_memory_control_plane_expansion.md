# Marketplace, Memory Backend, and Control Plane Expansion

## Decision

Adopt local SQLite through Python's standard-library `sqlite3` module as the first durable MemoryRuntime backend adapter. No new package dependency is added.

Use the existing official `mcp==1.27.1` SDK only for MCP protocol mechanics. Marketplace/registry browsing is metadata-only and does not add a new MCP registry client dependency in this checkpoint.

## Rationale

SQLite is maintained with Python, works locally without a service dependency, supports deterministic tests, and fits the current single-user local control-plane boundary. It is sufficient for safe memory records, inspect projections, and forget behavior without introducing a remote database, credential store, or provider dependency.

The MCP registry surface is treated as official registry metadata, not protocol execution. Marvex stores and projects approved/cached registry entries read-only, validates manifests, and creates allowlist proposals. It does not install packages, launch servers, or execute tools from registry data.

Skills marketplace support is local/approved metadata only. Existing SkillsRuntime models validate local manifests, reject policy override language, expose bounded prompt contribution previews, and keep script execution, arbitrary install, and remote loading disabled.

## Boundaries

- MemoryRuntime owns the SQLite adapter and safe memory projections.
- Control Plane API owns HTTP/auth/JSON projection routes only.
- CapabilityRuntime remains authoritative for capability policy, risk, approvals, and dispatch.
- MarketplaceRuntime owns safe metadata models, validation results, allowlist proposals, and enablement state.
- MCP protocol execution remains only in the existing official SDK adapter.

## Fallback

If SQLite becomes insufficient, a future MemoryRuntime backend adapter may add a maintained local database or embedded search backend behind the same safe read/write/forget contract. Raw transcripts remain blocked by default.

## Blocked

- Arbitrary MCP registry install or server launch.
- Untrusted skill script execution or remote skill loading.
- Credential storage.
- Raw transcript, prompt, provider payload, browser DOM, screenshot, or tool payload persistence by default.

## Dependency Status

- pyproject dependency: none (sqlite3 is Python standard library; mcp is documented in mcp_sdk.md)
- declared dependency: none
