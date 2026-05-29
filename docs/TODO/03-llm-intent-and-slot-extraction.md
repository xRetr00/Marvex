# 03 — LLM-based intent & slot extraction

**Theme:** Reasoning · **Size:** L · **Status:** not started

## Problem

Intent classification and argument ("slot") extraction are built from
hand-maintained keyword tables and regexes. They are brittle, English-only,
phrasing-sensitive, and the source of most "it didn't understand me" bugs we
have been patching one phrase at a time:

- "what is the PDF files on my desktop" was hard-routed to `file.read` until we
  added more keywords.
- "write what the open source means" wrote an empty file until we added
  generative-marker keywords.
- Each fix adds another keyword/regex. This does not converge.

## Evidence (current state)

- Intent scoring uses a **hardcoded token→feature dictionary**:
  `packages/intent_runtime/hybrid.py` → `_TOKEN_FEATURES` (e.g.
  `"hello": {"provider": 1.0}`, `"hi": {"provider": 1.0}`) and a fixed
  `_SEMANTIC_FEATURES` list, with `DeterministicLocalIntentEncoder` summing
  per-token features. `semantic-router` / `llama-index` are optional and the
  code "falls back to deterministic" when absent.
- Slot extraction is all regex in `services/core/main.py` /
  `packages/core/orchestration/file_intent.py`:
  `file_request_from_input`, `file_write_request_from_input`,
  `file_write_topic`, `_file_search_query`, `_file_rg_query`,
  `_calculator_expression`, etc.
- Directory shorthands, generative markers, list markers — all literal string
  lists maintained by hand.

## Why this is large, not a patch

- It replaces the **classification + slot-filling brain** with a model-driven
  approach (structured output / function-style extraction), which touches the
  intent worker, the cognition runtime, and every per-route arg parser.
- Needs a **structured-output contract** (intent kind + confidence + extracted
  slots) validated against the existing `IntentKind` enum, with the
  deterministic table kept as an offline/fallback path.
- Must stay fast and offline-capable: a tiny local model (the qwen3.5-0.8b /
  lfm2.5-350m already in the LM Studio list) should do intent+slots in one
  cheap call; cloud is optional.

## Proposed approach

1. **Structured intent contract:** define a pydantic `IntentExtraction`
   (intent_kind, confidence, slots: typed dict per intent — e.g. file ops get
   `{operation, path, content?, topic?}`). Reuse
   `packages/provider_structured_output` which already validates raw model
   output into target models.
2. **LLM classifier backend:** add an `LlmIntentClassifier` to
   `packages/intent_runtime` that calls a small local model for
   intent+slots and validates into `IntentExtraction`. It plugs into the same
   `classify_intent` seam the hybrid encoder uses today.
3. **Keep deterministic as fallback:** when no model is available or the call
   fails/times out, fall back to the current `_TOKEN_FEATURES` path. Same
   public contract, so Core doesn't care which ran.
4. **Retire per-route regex incrementally:** once slots come from the model,
   `file_request_from_input` / `file_write_request_from_input` become thin
   validators of model-provided slots rather than parsers. Keep them as the
   fallback when running deterministic.
5. **Confidence → clarify:** low confidence routes to the existing
   clarification path instead of guessing.

## Affected files (anticipated)

- `packages/intent_runtime/` — new `LlmIntentClassifier`, `IntentExtraction`.
- `services/intent_worker/controller.py` — option to use the LLM backend.
- `packages/provider_structured_output/` — reuse for validation.
- `packages/core/orchestration/file_intent.py` — accept model slots; keep regex
  as fallback.
- `services/core/main.py` — consume structured slots where available.

## Acceptance criteria

- Paraphrases that today need new keywords ("could you jot down what FOSS is
  into a file on the desktop") classify + slot-fill correctly without code
  edits.
- Non-English or unusual phrasing degrades gracefully (clarify, not
  mis-execute).
- With no model available, behavior matches today's deterministic path
  (existing intent tests still pass).
- Latency budget: intent+slots under a configurable timeout; exceed → fallback.

## Risks / notes

- Small local models hallucinate slots; validate hard against the enum + schema
  and treat invalid extractions as low-confidence → clarify.
- Strongly coupled with item 02 (the agent loop can itself do slot-filling via
  tool-call arguments). Decide whether 03 is a standalone preprocessor or folds
  into 02's tool-arg extraction. Recommendation: build 03 as the fast
  front-door classifier; let 02 handle deep multi-step arg-filling.
