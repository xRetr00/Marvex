# 01 — Conversational memory & reference resolution

**Theme:** Context · **Size:** L · **Status:** Implemented
## Problem

The assistant has no working memory of entities it produced earlier in the same
conversation. Concretely, the failing case that surfaced this:

1. User: "Write a test txt file on my desktop" → assistant creates
   `Desktop/output.txt`.
2. User: "Write in that file what the OPEN source means" → assistant cannot
   resolve **"that file"** to `Desktop/output.txt`. It re-parses the sentence
   in isolation, picks the default filename again, and writes a *new* file.

Every turn is parsed in isolation. Pronouns and back-references ("that file",
"it", "the one you just made", "the second result", "delete those") have no
referent because nothing carries entities forward.

## Evidence (current state)

- `previous_response_id` now chains provider text (fixed earlier), but that only
  carries the LLM's own message history inside the LiteLLM/LMStudio adapter — it
  does **not** carry structured entities (files created, search results, tool
  outputs) that the orchestrator produced.
- File write target is parsed per-turn from the literal sentence:
  `packages/core/orchestration/file_intent.py` → `file_write_request_from_input`
  always defaults to `output.txt` when no filename token is present. There is no
  lookup of "the file I wrote last turn".
- `packages/session_runtime` tracks turn linkage / response-id chaining but not
  a per-conversation **entity store**.
- `packages/memory_runtime` and `packages/memory_tree_runtime` are about
  long-term/semantic memory and connector documents, not short-term
  within-conversation referents.

## Why this is large, not a patch

- Needs a new **conversation-scoped working-memory store** (entities with type,
  id, human label, created-at, source turn) that lives beside the session.
- Needs a **reference-resolution step** before slot filling: detect anaphora
  ("that/it/those/the X") and bind to the most recent compatible entity.
- Touches the turn contract (entities must be returned in `AssistantTurnResult`
  so the shell/persistence can round-trip them) and every tool route that
  produces a referenceable artifact (file write, file list, web search,
  capability results).
- Has to survive the process boundary: Core is the producer, but the entity
  store must persist across turns within a session (and ideally across restarts
  like the provider-control state now does).

## Proposed approach

1. **Contract:** add a `conversation_entities` projection to
   `AssistantTurnResult.metadata` (safe projection only — ids + labels + types,
   never raw file contents).
2. **Store:** `packages/session_runtime` gains a
   `ConversationEntityStore` keyed by `session_ref`, holding a bounded ring of
   typed entities:
   - `file` (path, last_op), `web_result` (url, title, evidence_id),
     `tool_result` (capability_id, ref), etc.
3. **Resolver:** new `packages/context_runtime` helper
   `resolve_references(text, entities) -> ResolvedReferences` that maps
   "that file" → most-recent `file` entity, "those" → last list, etc. Keep it
   deterministic first (recency + type compatibility); an LLM-assisted resolver
   can come later and should reuse item 03's infrastructure.
4. **Wire-in:** the Core executor records produced entities after each tool
   route and consults the resolver during slot filling (e.g. file write target
   falls back to the last `file` entity when the sentence says "that file").
5. **Persistence:** reuse the JSON-state pattern from
   `InMemoryProviderControl` persistence (see `_provider_control_state_path`)
   for per-session entity snapshots, secrets-free.

## Affected files (anticipated)

- `packages/contracts/models.py` — entity projection on the turn result.
- `packages/session_runtime/` — `ConversationEntityStore` + persistence.
- `packages/context_runtime/` — `resolve_references`.
- `services/core/main.py` — record entities post-tool, consult resolver in
  `_run_file_path` / `_run_approval_path` / grounded path.
- `apps/shell/src/surfaces/ChatApp.tsx` + `sessionStore.ts` — round-trip the
  entity snapshot so it survives reload (optional first cut).

## Acceptance criteria

- "Write a test file … " then "append/overwrite that file …" targets the same
  path without the user repeating it.
- "Search X" then "open the first result" / "summarize those" resolves.
- Entity store is bounded (no unbounded growth), secrets-free, and survives a
  Core restart within the same session id.
- Unit tests for the resolver cover: no-referent (graceful fallback), multiple
  candidates (recency wins), type mismatch (ignored).

## Risks / notes

- Don't over-reach into long-term memory — this is **short-term, conversation
  scoped**. Long-term lives in `memory_tree_runtime`.
- Privacy: entity labels can leak filenames; keep them in the safe projection
  and never persist raw contents.
