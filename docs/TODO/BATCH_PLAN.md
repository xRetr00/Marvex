# Marvex — Batch Execution Plan

A single batch that handles **all** the architecture-level work plus the
small bugs found alongside it. This is the "do everything" plan: it groups the
7 backlog items (`01`–`07`) into ordered phases with explicit dependencies, and
lists the small field bugs to fix in passing so they don't get lost.

> Each linked item has its own self-contained spec. This file is the
> conductor: order, grouping, and exit criteria for the whole batch.

## Why phased, not parallel-everything

These tasks are **not independent**. Item 02 (model-driven tool-calling) is the
keystone; 07 (per-file tool registry) is its prerequisite; 01/03/05 plug into
02; 04/06 are delivery layers on top. Running all 7 as simultaneous agents on
one codebase would collide constantly and produce unmergeable work. So the
batch is phased, and within a phase the pieces are genuinely parallelizable.

```
Phase 0  small bugs (unblock daily use)        ──┐
Phase 1  07 tool registry  ─────────────────────┤ enables
Phase 2  02 agentic tool loop (keystone) ◄───────┘
Phase 3  03 LLM intent+slots   05 web search   01 memory   (parallel, ride on 02)
Phase 4  04 voice loop         06 streaming     (delivery, parallel)
```

---

## Phase 0 — Small field bugs (fast, unblock daily use)

These are patches, not architecture, but they're actively biting and cheap.
Do them first so the tool is usable while the big phases land.

- [ ] **B1 — file.write `file.exists` hard-fail.** `file_write_request_from_input`
  always sends `overwrite: False`; writing to an existing name throws
  `file.exists` ("File write did not complete: file.exists"). Define semantics:
  explicit "overwrite/replace" → overwrite; otherwise append (patch) or
  auto-suffix. (`packages/adapters/capabilities/files.py:242`,
  `packages/core/orchestration/file_intent.py`.) Folds into item 07.
- [ ] **B2 — model hallucinates capabilities.** With the provider now working,
  the model invents tools it lacks ("agent.deep_search subagent", "RAG tools",
  "your memory"). Root fix is items 07+02+03 (ground the model in the real tool
  list). Interim: a system prompt that states the *actual* available tools and
  forbids inventing others. (`services/core/main.py` prompt assembly.)
- [ ] **B3 — PDF / report read returns "No matching file paths found."**
  "Read the contents of the My Uni Report on Desktop" routed to file search and
  found nothing — title-based fuzzy match + PDF text extraction are missing.
  Needs: fuzzy filename match against the directory listing, and a PDF text
  reader (`pypdf` is already a dependency). Partly item 07 (a real `read` tool
  that handles PDFs), partly item 01 (resolve "the My Uni Report" to a listed
  file).
- [ ] **B4 — voice wake word still reported not detecting.** `get_result` fix
  (commit `1620d0e`) must be in the running build — confirm the rebuild shipped
  it. Capture fresh `voice_worker.stderr.log` after "Hey Marvex": if the
  AttributeError is gone but detection still doesn't fire, the remaining gap is
  the live capture/dispatch loop = item 04. Need logs to disambiguate.

**Phase 0 exit:** create-file works on existing names; the model stops
inventing tools; reading a named report (incl. PDF) returns content; voice
failure is pinned to a specific cause (build vs. loop) with fresh logs.

---

## Phase 1 — [07 Tool registry per-file refactor](./07-tool-registry-per-file-refactor.md)

The structural prerequisite for real tool-use. One file per tool
(`read.py`, `list.py`, `search.py`, `write.py`, `patch.py`, `calculator.py`,
…), a uniform `Tool` interface (id, name, description, risk, `params_model`,
`execute`, `json_schema`), and a registry replacing the `if/elif` ladders.
Includes B1 (overwrite/patch semantics) and the new `patch` tool.

**Exit:** all built-ins are per-file, registry-dispatched, old API shimmed,
`registry.tool_schemas()` produces valid JSON schemas, existing tests green.

---

## Phase 2 — [02 Agentic tool-calling loop](./02-agentic-tool-calling-loop.md) *(keystone)*

With clean tool schemas from Phase 1, give the model real tool-calling: send
schemas, parse `tool_calls`, execute under the existing approval/policy
boundary, feed results back, loop to `max_steps`. Keep the deterministic router
as fallback for non-tool models. Resolves B2 properly.

**Exit:** "search X and write a summary to notes.txt" completes via model tool
calls in one turn; risky calls still gated by approval; tools-off behaves like
today.

---

## Phase 3 — Parallel: intelligence layers on top of 02

These three can proceed in parallel once 02 is stable; each is independent.

- [ ] [03 LLM intent & slot extraction](./03-llm-intent-and-slot-extraction.md)
  — replace the keyword `_TOKEN_FEATURES` dict and regex slot parsers with
  model structured-output extraction; deterministic fallback retained.
- [ ] [05 Grounded answer & web search](./05-grounded-answer-web-search-wiring.md)
  — real search provider default, evidence funnel, cite-or-say-no-sources;
  best delivered as a model `web_search` tool (rides on 02).
- [ ] [01 Conversational memory & reference resolution](./01-conversational-memory-and-reference-resolution.md)
  — entity store + "that file"/"those results" resolver; resolves B3's
  reference half.

**Exit:** paraphrases route correctly without code edits; knowledge questions
return sourced answers or an honest "no sources"; back-references resolve across
turns.

---

## Phase 4 — Parallel: delivery layers

- [ ] [04 End-to-end voice turn loop](./04-end-to-end-voice-turn-loop.md) —
  wake → VAD endpointing → STT → chat turn → TTS → playback → barge-in, wired
  into the live worker. Resolves B4's loop half.
- [ ] [06 Streaming responses](./06-streaming-responses.md) — token streaming
  for chat and incremental TTS for voice.

**Exit:** "Hey Marvex, what's 2+2?" answered out loud end-to-end; chat streams
tokens; both degrade cleanly when unsupported.

---

## Tracking

Suggested labels for issues/PRs: `batch:phase-0` … `batch:phase-4`, plus
`item:01`…`item:07`. Each item's doc holds its own acceptance criteria; this
file's phase-exit criteria gate moving to the next phase.

## Honest scope note

This is multiple weeks of work, not a single sitting. The phases are designed so
the tool stays usable throughout: Phase 0 fixes daily pain immediately, and each
later phase ships behind a fallback so nothing regresses if a model or provider
underperforms.
