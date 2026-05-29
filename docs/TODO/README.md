# Marvex — Large Work Backlog (architecture-level)

This folder collects **large, architectural pieces of work** — the kind that
need a design + multi-file refactor, not the small targeted patches we have
been landing while stabilizing the tool. Each item here was discovered while
debugging real failures (provider routing, voice wake word, file
read/write/list, multi-turn). The small patches got the tool *working*; these
items get it *right*.

> Do not start these until the day-to-day tool is stable. Each doc is
> self-contained: problem, evidence (with `file:line` refs), why it's large,
> proposed approach, affected files, acceptance criteria, and risks.

## Index

| # | Title | Theme | Rough size |
|---|-------|-------|-----------|
| 01 | [Conversational memory & reference resolution](./01-conversational-memory-and-reference-resolution.md) | Context | L |
| 02 | [Model-driven agentic tool-calling loop](./02-agentic-tool-calling-loop.md) | Reasoning | XL |
| 03 | [LLM-based intent & slot extraction](./03-llm-intent-and-slot-extraction.md) | Reasoning | L |
| 04 | [End-to-end voice turn loop](./04-end-to-end-voice-turn-loop.md) | Voice | XL |
| 05 | [Grounded answer & web-search wiring](./05-grounded-answer-web-search-wiring.md) | Knowledge | L |
| 06 | [Streaming responses (text + voice)](./06-streaming-responses.md) | UX/Infra | L |

## How these relate

```
                 ┌─────────────────────────────┐
   user input →  │ 03 LLM intent + slot extract │  (replaces keyword dict)
                 └──────────────┬──────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │ 02 agentic tool-calling loop │  (model calls tools, reacts)
                 └──────┬───────────────┬───────┘
                        │               │
        ┌───────────────▼──┐     ┌──────▼─────────────┐
        │ 01 conversational │     │ 05 grounded answer │
        │ memory / refs     │     │ + web search       │
        └───────────────────┘     └────────────────────┘

   06 streaming + 04 voice loop are cross-cutting delivery layers that ride on
   top of whatever 02 produces.
```

Recommended order: **02 → 03** first (they unblock real agent behavior), then
**01** (memory makes 02 useful across turns), then **05**, then **04** and
**06** as delivery polish. They can be parallelized if more than one person is
working, but 02 is the keystone.

## Sizing legend
- **L** — a focused feature: ~1–2 weeks, one subsystem, a handful of files.
- **XL** — cross-cutting: multiple runtimes + contracts + workers, design doc
  first, staged rollout behind a flag.
