# 05 — Grounded answer & web-search wiring

**Theme:** Knowledge · **Size:** L · **Status:** not started

## Problem

Knowledge questions ("What is the latest model by Anthropic?") return:

> "Evidence is missing for this grounded answer, so I cannot answer without
> fabricating."

The anti-fabrication guard is correct in spirit (don't hallucinate citations)
but in practice it fires on almost everything because real web-search evidence
is not actually reaching the grounded-answer stage, and even when search runs
the provider call that should compose the cited answer fails or returns no
citation-bearing text.

## Evidence (current state)

- Trace shows `intent_kind=web_search`, `web_search_executed=true`,
  `tool_status=not_executed`, `citation_validation=citation.required_missing`,
  and the user-facing "evidence is missing" message. So: search was attempted,
  but no validated evidence/citations came out the other side.
- `services/core/main.py` `_run_grounded_path` collects
  `cognition.web_evidence_refs`; if empty it short-circuits to the
  "evidence is missing" text. The provider answer is then citation-validated
  with `validate_grounded_citations`, which rejects when the text has no
  matching evidence ids.
- The default web search provider can be a fake
  (`_FakeCoreWebSearchProvider` in `services/core/main.py`) depending on config
  (`config.web_search == "fake"`); the real adapters live in
  `packages/web_search_runtime` (Wikipedia, DDGS, SearXNG) but need to be
  selected + reachable.
- Earlier turns also failed at the provider stage entirely
  (`PROVIDER_UNAVAILABLE`) because of the provider-selection bug (now fixed) and
  missing API key — so the grounded path never even got a model answer to cite.

## Why this is large, not a patch

- It spans **config (which search provider), evidence plumbing (search →
  cognition evidence refs → prompt), and citation validation** — three layers
  that must agree on evidence ids.
- The citation contract (`GroundedAnswerDraft`, `validate_grounded_citations`)
  is strict by design; making it usable means the *whole* path must reliably
  produce evidence the model can cite, not loosening the validator.
- Needs the model to actually *use* the evidence (cite ids) — which is far more
  reliable once item 02 lets the model call a `web_search` tool and read
  results, versus pre-fetching and hoping the model cites.

## Proposed approach

1. **Default to a real search provider** in the shipped config (Wikipedia or
   DDGS) instead of `fake`, with SearXNG optional. Verify reachability and
   surface a clear status when offline (like the provider auth hint).
2. **Verify evidence plumbing:** confirm `web_search_runtime` results become
   `cognition.web_evidence_refs` with stable `evidence_id`s that flow into the
   prompt and into `validate_grounded_citations`. Add a trace breadcrumb at each
   hop (search hit count → evidence ref count → cited id count) so the gap is
   visible.
3. **Prompt the model to cite:** the grounded prompt must present evidence with
   ids and instruct the model to cite them; validate the returned ids against
   the allowed set (already implemented — feed it real data).
4. **Prefer tool-driven search (after item 02):** expose `web_search` as a model
   tool so the model fetches and reads on demand, then cites. Keep the
   pre-fetch path as fallback.
5. **Graceful "no evidence":** when search genuinely returns nothing, say
   "I couldn't find sources for that" — distinct from the current
   indistinguishable fabrication-guard message.

## Affected files (anticipated)

- `services/core/main.py` — default web-search provider selection;
  `_run_grounded_path` evidence breadcrumbs; clearer no-evidence messaging.
- `packages/web_search_runtime/` — ensure adapters return citeable evidence.
- `packages/cognition_runtime/` — evidence ref assembly into the prompt.
- `packages/grounded_answer_runtime` (citation validation) — feed real data;
  keep strictness.

## Acceptance criteria

- "What is the latest model by Anthropic?" returns a sourced answer with at
  least one valid citation when online.
- When offline / no results, the message clearly says no sources were found
  (not the fabrication-guard phrasing).
- A trace shows the evidence funnel: search hits → evidence refs → cited ids,
  making future regressions obvious.

## Risks / notes

- Free search providers (DDGS) rate-limit and change HTML; prefer an API-ish
  source (Wikipedia) for the default and treat scrapers as best-effort.
- Don't relax `validate_grounded_citations` to "fix" the symptom — the bug is
  upstream (no evidence reaching it), not the validator being too strict.
- Best combined with item 02 so the model reads sources and cites them.
