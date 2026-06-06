# 02 — Model-driven agentic tool-calling loop

**Theme:** Reasoning · **Size:** XL · **Status:** Implemented · **Keystone**

## Problem

The model never decides to call a tool. Tools are selected *before* the model
runs, by a deterministic intent classifier, and the model only ever produces a
final text answer. This means the assistant cannot:

- choose a tool based on its own reasoning,
- chain tools (search → read a result → write a summary),
- react to a tool's output (retry, refine, ask a follow-up),
- recover when the pre-classification picked the wrong route.

What we have today is a **router**, not an **agent**. The continuation loop
added earlier (`packages/core/orchestration/agentic_loop.py`) only re-prompts
the same provider when a reply was truncated by token budget — it does not do
tool calls.

## Evidence (current state)

- Routing is pre-decided in `services/core/main.py` `submit_turn`: a big
  `if "capability_tool" in route_intents … elif "web_search" … elif
  "file_read_list_search" …` ladder dispatches to fixed handlers. The provider
  is called once at the end (default route) or to phrase a pre-computed result.
- The LiteLLM adapter explicitly forbids `tools` in the request and a boundary
  test enforces it: `tests/adapters/test_litellm_provider.py`
  `test_no_tools_mcp_or_streaming_fields_sent` and
  `test_adapter_source_has_no_forbidden_boundary_imports_or_raw_http`
  (forbidden token list includes `tool`, `stream`).
- Tool execution lives behind the ToolWorker process boundary
  (`services/tool_worker/`), invoked directly by Core handlers, not by a model
  tool-call.
- `cognition.step_plan.max_steps` exists and the loop counts steps, but no step
  is ever a model-issued tool call.

## Why this is large, not a patch

- It changes the **fundamental control flow** of a turn from "classify → run
  one handler → phrase" to "model proposes action → execute under policy →
  feed result back → repeat until done".
- It must preserve the existing **approval/policy boundary** (risky actions
  still require human approval; the ToolWorker process boundary stays).
- The provider adapters must learn to send tool schemas and parse tool-call
  responses — which the current boundary contracts deliberately forbid, so the
  boundary tests and governance docs change too.
- Needs a tool-result → provider continuation contract (OpenAI "tool" role
  messages) threaded through the conversation store from item 01.

## Proposed approach (staged, behind a flag)

1. **Capability registry → tool schema:** generate JSON tool schemas from the
   existing `BuiltinToolCatalog` capabilities (calculator, file.read/list/
   search/write, web search, mcp). One source of truth.
2. **Adapter tool support:** add an opt-in `tools=` path to the LiteLLM and
   LMStudio adapters guarded by a capability flag; relax the forbidden-token
   boundary test to allow tools *only* on that path. Parse `tool_calls` from
   the response into the existing `ProviderToolCallMapper`
   (`packages/adapters/providers/tool_calls.py` already maps provider tool calls
   → capability proposals — reuse it).
3. **Agent loop in Core:** replace the default route's single call with a real
   loop:
   - send messages + tool schemas,
   - if response has tool calls → run each through the **existing** capability
     execution + approval path → append tool result messages → continue,
     else finalize on text.
   - bound by `max_steps` (already wired) + the hard ceiling in
     `agentic_loop.py`.
4. **Keep deterministic router as fallback:** when the model/provider doesn't
   support tools (or the flag is off), fall back to today's classify-and-run
   behavior so nothing regresses.
5. **Approval integration:** a model-proposed risky tool call still emits the
   approval request and resumes via the existing `resume_approval` path.

## Affected files (anticipated)

- `packages/adapters/providers/litellm/`, `.../lmstudio_responses/` — tool send
  + parse.
- `packages/adapters/providers/tool_calls.py` — reuse/extend mapper.
- `packages/adapters/capabilities/builtins/` — emit tool schemas.
- `services/core/main.py` — new agent loop in the default route; tool-result
  message threading.
- `packages/assistant_turn_integration/` — `_handle_provider_tool_call_turn`
  already exists for single tool calls; generalize to a loop.
- Boundary tests + `docs/` governance (the forbidden-tools contract).

## Acceptance criteria

- "Search the web for X and write a summary to notes.txt" completes in one user
  turn via model-issued search → write tool calls.
- A model-proposed risky action (file write/delete) still routes through human
  approval before executing.
- With tools disabled / unsupported provider, behavior is identical to today.
- Loop terminates on: final text, max_steps, or error — never spins.

## Risks / notes

- Local models (LM Studio qwen, lfm) have **uneven tool-calling quality**. Gate
  per-model via the capability flag; keep the deterministic fallback strong.
- This is the keystone: items 01 (memory) and 05 (web search) become far more
  useful once the model can drive tools. Sequence 02 first.
- Governance: update the boundary docs that currently assert "no tools sent to
  provider" — that invariant is intentionally being lifted on the new path.
