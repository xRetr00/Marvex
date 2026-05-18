# Marketplace, Memory Backend, and Control Plane Expansion

This phase expands Marvex from a local assistant runtime into a safer operable platform surface. It adds read-only marketplace metadata models, local skill package management readiness, a SQLite-backed MemoryRuntime adapter, trace search summaries, approval history projections, policy summaries, runtime diagnostics, and expanded Control Plane web views.

## Implemented

- `packages.marketplace_runtime` owns MCP registry metadata models, manifest validation, allowlist proposal models, skills marketplace entries, prompt contribution previews, and enable/disable state projections.
- MCP marketplace browsing is read-only metadata. Allowlisting creates proposal state only; no install, launch, auto execution, registry package installation, or arbitrary server execution occurs.
- Skills marketplace support imports approved/local Skill manifests, validates existing SkillsRuntime policy constraints, previews bounded prompt contributions, and keeps script execution, arbitrary install, and remote loading disabled.
- `SQLiteMemoryStore` is implemented behind MemoryRuntime using Python standard-library SQLite with local-user path scoping, safe record validation, read/query, safe inspect previews, and forget behavior.
- Telemetry trace search returns safe summaries filtered by session, conversation, tool status, approval status, and turn status without raw payload projection.
- Control Plane API exposes protected endpoints for MCP marketplace, skill marketplace, memory inspect/forget, trace search, approval history, policies, and runtime diagnostics.
- Control Plane web app now has dedicated pages for MCP Marketplace, Skills Marketplace, Memory Inspect, Trace Search, Approval History, Tool Risk Policy, and Runtime Diagnostics.

## Safety Rules

- Marketplace browsing is read-only by default.
- Installs and server launches are not implemented.
- Skill script execution and remote skill loading are not implemented.
- Memory records reject raw transcript/secret-like content and project previews only.
- Control Plane and frontend do not execute tools directly.
- Auth remains required for protected Control Plane routes.
- Raw secrets, tokens, prompts, transcripts, provider payloads, tool payloads, browser DOM, and screenshots are not rendered or persisted by default.

## Ownership

- MemoryRuntime owns memory backend adapters and safe memory projections.
- MarketplaceRuntime owns marketplace metadata and proposal state.
- Control Plane API owns HTTP/auth/JSON and safe projection routes only.
- Telemetry owns trace search and safe trace summaries.
- CapabilityRuntime remains policy, approval, risk, and dispatch authority.

## Recommended Next

Add a local service composition slice that serves the expanded Control Plane API and static frontend assets on loopback with generated local bearer-token handoff, without remote binding, daemon supervision, or direct tool execution.
