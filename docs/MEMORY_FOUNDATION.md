# Memory Foundation

## Decision

Memory in Marvex means policy-governed assistant recall material. The first
approved memory shapes are safe records, references, write candidates, policy
decisions, policy-approved read queries, policy-approved forget requests, read
results, forget results, and safe projections owned by
`packages.memory_runtime`.

Memory is not a transcript store, telemetry store, session store, provider
state store, prompt cache, vector database, tool state, UI state, voice state,
desktop context, vision state, proactive state, router, model selector, daemon,
or WebSocket/event stream.

## Safe Stored Fields

Allowed in this foundation:

- `memory_ref` with `ref_type: "memory"` and safe `ref_id`
- `scope`: `session` or `conversation`
- `memory_kind`: `fact`, `preference`, `instruction`, or `summary`
- safe `session_ref` and `conversation_ref`
- `trace_id` and `turn_id` provenance
- safe normalized memory content only after `explicit_user` or `policy_approved`
  authorization
- safe tags
- `raw_transcript_persisted: false`

Forbidden by default:

- raw prompts or user-visible input bodies copied as transcripts
- raw assistant outputs or provider outputs
- provider payloads, provider response ids, raw metadata, or provider continuity
  ids
- full transcripts or hidden conversation history
- tokens, credentials, environment values, auth material, secrets, and private
  stack traces
- embeddings, vector indexes, semantic search stores, automatic extraction,
  tools, UI, voice, desktop, vision, proactive behavior, generic provider
  routing, retry/fallback/model selection, daemon supervision, or WebSocket
  streams

## Relation To Session And Telemetry

SessionRuntime owns `session_ref` and `conversation_ref` only. MemoryRuntime may
link records to those references, but SessionRuntime must not own memory storage
or recall.

Telemetry owns trace events and trace persistence only. MemoryRuntime may keep
`trace_id` and `turn_id` provenance, but telemetry must not become memory
storage.

AssistantRuntime may receive safe memory context in a future approved task, but
it must not own memory storage or recall. Core, Local API, RuntimeComposition,
ProviderRuntime, and local service startup remain memory-owner blind.

## Live Derived Memory Loop

The first live memory loop is active for Core worker-backed turns when an
explicit local vault root is configured. It remains a derived-memory loop, not a
transcript store.

Current live behavior:

- turn start recall reads approved `MemoryRecord` rows through the existing
  bounded `MemoryReadQuery` path
- prompt context receives bounded memory text and provenance refs, not opaque
  embeddings or tombstone placeholders
- turn end write derives safe facts from the current turn and evaluates
  `AutonomyPolicy` for `memory_auto_write`
- approved automated writes use `MemoryWriteCandidate(source="future_policy")`
  plus a `MemoryPolicyDecision(decided_by="future_policy")`
- persisted records use `write_authorization: policy_approved`
- belief revision replaces the prior topic record before writing the new current
  fact
- local persistence uses `SQLiteMemoryStore` and an explicit local vault root

The default vault shape is OpenHuman/Karpathy-inspired and human editable:

```text
<vault-root>/
  memory.sqlite
  memory_tree.sqlite
  wiki/
    summaries/
    notes/
    sources/
```

Generated Markdown uses YAML frontmatter with provenance fields and
`raw_secret_persisted: false`. Bodies use Obsidian-compatible `[[wikilinks]]`.
Manual notes under `wiki/notes/` are reserved for user-owned Markdown edits and
feed the same safe note-read path.

## Future Policy

Future broad extraction remains policy controlled. Write candidates default to
`pending` unless they are explicit user writes or derived `future_policy`
records approved by the autonomy policy path. Provider-driven or automatic
transcript-derived raw writes remain blocked. Forget/delete behavior must be
addressable by `MemoryRef` and return a safe result without exposing stored
content.

The current write path can build a `MemoryRecord` only from an approved
`MemoryWriteCandidate` and approved `MemoryPolicyDecision`. The current generic
read and forget request shapes require `policy_status: approved`; pending
requests fail before store dispatch.
