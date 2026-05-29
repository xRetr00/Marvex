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
- [x] **B2 — model hallucinates capabilities.** Interim fix landed: the system
  prompt now lists the *real* tools from the registries and forbids inventing
  others (`packages/core/orchestration/tool_grounding.py`). Verified in the raw
  LM Studio log — the model now says "I do not have subagents / web browsing".
- [ ] **B5 — persona block contradicts the grounding.** The raw LM log showed
  the prompt-harness still injects *"This agent may propose bounded subagents
  ['agent.deep_search', ...]"* and lists `skill.planning/brainstorming/
  verification` — capabilities with no runtime. Source:
  `packages/prompt_harness_runtime/provider_compiler.py:89` (`_agent_role_block`,
  driven by `AgentProfile.can_spawn_subagents` + `spawnable_agent_ids`). This is
  the residual root of B2: the persona claims subagents the system can't execute.
  **Product decision needed:** are subagents/skills a real roadmap item (a future
  multi-agent runtime) or should they be removed from the personas until real?
  Until decided, the grounding block counteracts it but does not remove the
  contradiction.
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

## Phase 1 — [07 Tool registry per-file refactor](./07-tool-registry-per-file-refactor.md) ✅ DONE

The structural prerequisite for real tool-use. One file per tool
(`read.py`, `list.py`, `search.py`, `write.py`, `patch.py`, `calculator.py`,
…), a uniform `Tool` interface (id, name, description, risk, `params_model`,
`execute`, `json_schema`), and a registry replacing the `if/elif` ladders.
Includes B1 (overwrite/patch semantics) and the new `patch` tool.

**Exit:** all built-ins are per-file, registry-dispatched, old API shimmed,
`registry.tool_schemas()` produces valid JSON schemas, existing tests green.
**Status:** complete (commits 58bf8d8, e979bcb).

---

## Phase 2 — [02 Agentic tool-calling loop](./02-agentic-tool-calling-loop.md) *(keystone)* ✅ DONE

With clean tool schemas from Phase 1, give the model real tool-calling: send
schemas, parse `tool_calls`, execute under the existing approval/policy
boundary, feed results back, loop to `max_steps`. Keep the deterministic router
as fallback for non-tool models.

**Exit:** model tool calls execute in a loop; risky calls gated by approval;
flag-off behaves like today.
**Status:** complete, behind `MARVEX_AGENTIC_TOOLS` (default off). Increments:
  * P2.1 (e9b9e1d) — contract + LiteLLM tool plumbing
  * P2.3a (762f691) — LMStudio Responses tool support (the user's live provider)
  * P2.2 (172bfa9) — tool-execution engine (safe exec / risky->approval / unknown)
  * P2.3b (e0d2a04) — loop driver `run_tool_loop` + wiring in `submit_turn`

Known follow-ups: (a) resume-INTO the loop after approval (today approval stops
the loop and hands to the existing approval path); (b) B5 persona/subagent
contradiction; (c) the deterministic router still runs first for non-default
intents — tool-calling currently augments the default provider route.

---

## Phase 3 — Parallel: intelligence layers on top of 02 ✅ DONE

- [x] [05 Grounded answer & web search](./05-grounded-answer-web-search-wiring.md)
  — `web.search` tool (d208239); grounding now always injects web.search +
  the current date + an anti-stale instruction, and web_search/grounded
  intents route through the agentic loop (1157f0c). Knowledge questions
  search-and-answer instead of hitting the grounded-path reject.
- [x] [03 LLM intent & slot extraction](./03-llm-intent-and-slot-extraction.md)
  — LlmIntentClassifier (ab33241): model emits structured intent, validated
  against IntentKind, deterministic fallback on any failure. Default on
  (MARVEX_LLM_INTENT=0 to disable).
- [x] [01 Conversational memory & reference resolution](./01-conversational-memory-and-reference-resolution.md)
  — ConversationEntityStore + resolve_file_reference (03a1764): "that file"/
  "it" resolves to the most recent file produced this session.

**Exit:** paraphrases route via the model not keywords; knowledge questions
search + answer with the current date in context; "that file" resolves across
turns. **Status:** complete.

Follow-ups: per-route regex slot-fillers can be progressively retired now that
03 exists; entity store is in-memory (persistence is a later nicety); resolve
"those results" for web/list entities (only file refs wired so far).

---

## Phase 4 — Parallel: delivery layers

- [x] [04 End-to-end voice turn loop](./04-end-to-end-voice-turn-loop.md) —
  **wired end-to-end.** Worker: wake → capture → STT → emits transcript_text;
  new `speak` command synthesizes + plays a reply (4d75667). Shell bridge:
  while mic active, polls worker status, picks up a new transcript, runs it as
  a chat turn (agentic, with tools + grounding), and speaks the reply via the
  control-plane `/voice/worker/speak` endpoint (186c133). Resolves B4's loop
  half. Refinement still open: streaming VAD endpointing (capture is a fixed
  ~3s window) and barge-in during capture.
- [ ] [06 Streaming responses](./06-streaming-responses.md) — **deferred with a
  plan.** Token streaming is a transport rework spanning the provider adapters,
  the Core ASGI layer (SSE), the Tauri command, and incremental React render /
  incremental TTS. Its core deliverable lives almost entirely in layers that
  cannot be exercised in the current dev environment (no fastapi, no Tauri, no
  audio), and shipping untested SSE/HTTP streaming risks regressing the
  now-working request/response chat + voice paths. Recommendation: implement it
  against the running stack. Plan unchanged in the item doc:
  adapter `stream=True` → Core SSE turn endpoint emitting deltas + terminal
  full result → shell consumes deltas → voice feeds deltas through
  SentenceBoundaryDetector → TTSQueue. All behind a flag with the
  request/response path as fallback.

**Exit (04):** "Hey Marvex, what's 2+2?" → recognized → answered → spoken, end
to end on a real build. **06** remains for the live-stack session.

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
