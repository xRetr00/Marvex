# OpenHuman-Style Memory Tree and Connectors Foundation

status: implemented foundation

Marvex now has an OpenHuman-style memory design concept implemented with Marvex-owned code, without copying OpenHuman code. The implementation is local-first, source-grounded, inspectable, and bounded by policy-owned runtime contracts.

## Ownership

- `packages.memory_tree_runtime` owns canonical documents, chunks, scoring, source/topic/global/daily tree nodes, evidence links, SQLite tree index, vault projection, and traversal/search results.
- `packages.connector_runtime` owns connector manifests, OAuth connection metadata, connector permission decisions, sync requests/results, error envelopes, and auto-fetch policy summaries.
- `packages.memory_runtime` remains the existing memory policy/write/read/forget owner and can delegate tree backend operations later.
- `packages.control_plane_api` exposes HTTP/auth/JSON safe projections only; it does not own connector policy, memory tree policy, OAuth token storage, or sync execution.
- `apps/control_plane_web` displays connector, source, auto-fetch, memory tree, scoring, and evidence summaries as safe projections only.
- `packages.adapters.connectors.authlib_oauth` is an import-backed OAuth seam. It proves `Authlib` availability without token exchange or network sync.

## Implemented Surfaces

- Memory source contracts: source refs, source type, connector kind, provenance, trust, permission scope, ingestion policy, sync mode, sync interval, and safe source projection.
- Connector/OAuth contracts: connector refs/manifests, OAuth status, scopes, permission decisions, sync request/result, error envelope, safe connector projection, and required connector categories for Gmail, Google Calendar, Google Drive, GitHub, Slack, Notion, and generic OAuth.
- Auto-fetch foundation: disabled/enabled/paused control state, per-connector and per-source enablement, schedules, run summaries, Control Plane toggles, and audit-safe summaries. Defaults remain disabled.
- Canonicalization/chunking: deterministic document IDs, normalized Markdown body, source metadata, bounded chunks, content hashes, duplicate-readiness hash, and vault projection.
- SQLite tree index: sources, documents, chunks, scores, tree nodes, and safe query projections.
- Scoring: source weight, recency, interaction, entity/topic boost, keep/drop decision, scoring explanation, and hotness signal.
- Entity/topic foundation: entity refs, topic refs, candidates, assignments, consolidation candidates, duplicate signals, and safe projection aliases.
- Trees/traversal: source tree, topic tree, global/daily digest tree, summary nodes, evidence links, update summaries, traversal results, search, drill-down, source/topic/daily digest retrieval, entity resolve, and query-with-evidence.
- Control Plane endpoints: `/control/connectors`, `/control/sources`, `/control/autofetch`, `/control/memory/tree/search`, `/control/memory/tree/source/{source_id}`, `/control/memory/tree/topic/{topic_id}`, `/control/memory/tree/daily/{date}`, `/control/memory/tree/drill-down/{chunk_id}`, `/control/memory/tree/scoring`, and `/control/sources/{source_id}/forget`.

## Privacy And Policy

- Auto-fetch is configurable and present, but disabled by default.
- Connector manifests are read-only ingestion foundations. Broad account actions such as sending email or posting Slack messages are not implemented.
- OAuth tokens are not exposed in safe projections and are modeled as stored only by a future connector auth backend.
- Source forget/delete and auto-fetch toggles do not start sync or deletion directly from the Control Plane API foundation.
- Telemetry and Control Plane outputs are count/status/evidence summaries only; no raw email, document, message body, token, raw provider payload, or raw tool payload is emitted by default.
- Every summary node requires provenance evidence.

## Validation

- Targeted tests cover connector models, Authlib import proof, auto-fetch policy, canonicalization, chunking, scoring, SQLite tree index, tree traversal, Control Plane endpoints, and Control Plane web views.
- `scripts/check_memory_tree_connector_boundaries.py` enforces owner boundaries, required surfaces, endpoint/view presence, no direct account actions, and no default token/credential persistence.
## Completion audit - 2026-05-18

Status after dependency/uv follow-up audit:

- Complete: source refs and ingestion policies, connector/OAuth metadata, disabled-by-default auto-fetch policy, canonicalization, bounded chunking, content hashes, scoring explanations, source/topic/global/daily tree models, evidence links, traversal/search methods, Authlib OAuth import seam, and safe Control Plane connector/source/autofetch/tree/scoring views.
- Completed in this audit: `MemoryTreeNode.safe_projection()` now carries bounded evidence links, `ScoringExplanation.safe_projection()` exposes component scores, `SQLiteMemoryTreeIndex` reads back evidence metadata and component scores, `SQLiteMemoryTreeIndex.forget_source()` deletes source documents/chunks/scores/evidence-backed nodes, and Control Plane web now shows source tree, topic tree, daily digest, evidence drill-down, source forget controls, and auto-fetch state controls.
- Partial by design: live OAuth sync, connector ETL, background scheduled loops, remote connector services, raw account payload ingestion, and broad account actions remain unimplemented until a backend-specific connector goal approves them.
- Safety invariant: telemetry/control-plane outputs remain count/status/evidence summaries only; OAuth tokens, credentials, raw provider/tool payloads, raw transcripts, and raw account bodies are not exposed by default.
