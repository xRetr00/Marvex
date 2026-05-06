# Provider Structured Output Spike Decision

verified date: 2026-05-05

verified by: Codex

decision scope: future provider bridge behavior that asks models for typed or
structured output.

implementation impact: research and adapter decision only. No dependency is
approved by this document. No provider bridge, runtime behavior, Core behavior,
CLI behavior, prompt rendering, or structured-output execution is implemented.

## 1. Executive Decision

Recommendation: use provider-native structured outputs first, backed by plain
Pydantic validation, and run a no-network adapter skeleton/spike before adding
any new dependency.

Do not adopt Promptify, Instructor, Outlines, Guidance, Pydantic AI, or
LangGraph now.

Concrete path:

1. Keep current dependencies unchanged.
2. Define a future provider structured-output adapter boundary that accepts a
   Marvex prompt/task payload, schema, and provider result object, then returns
   a validated Marvex contract.
3. For OpenAI-compatible Responses paths, prefer provider-native Structured
   Outputs when the configured provider/model supports the required JSON Schema
   subset.
4. Always validate model output with Marvex-owned Pydantic contracts after the
   provider call.
5. Use plain Pydantic validation as the no-new-dependency fallback.
6. Defer Promptify/Instructor/Outlines/Guidance dependency spikes until a
   concrete provider bridge task proves provider-native structured output plus
   Pydantic validation is insufficient.

This means Task 070 should not implement the provider bridge yet. Task 070
should be a no-network structured-output adapter skeleton and fixture task.

## 2. Candidate Comparison

### Promptify

- official source: `https://github.com/promptslab/Promptify`,
  `https://promptify.readthedocs.io/`
- maintenance status: active. GitHub snapshot on 2026-05-05: Python,
  Apache-2.0, last pushed 2026-03-27, about 4.6k stars.
- Python/Windows fit: plausible. Requires Python 3.9+.
- dependency footprint: `litellm>=1.50.0,<=1.82.6`, `jinja2>=3.1`,
  `pydantic>=2.0`, `tenacity>=8.2`; optional eval extras include
  `rouge-score` and `nltk`.
- local model support: yes through LiteLLM model strings such as Ollama.
- LiteLLM compatibility/overlap: major overlap. Promptify pins LiteLLM to
  `<=1.82.6`, while Marvex currently pins `litellm==1.83.13`; adoption would
  require dependency reconciliation and could bypass Marvex's provider adapter.
- Pydantic compatibility: strong. Promptify advertises Pydantic structured
  outputs and custom Pydantic schemas.
- provider-native schema support: wraps providers through LiteLLM and includes
  a safe parser fallback, but it is not the same as directly using OpenAI
  Structured Outputs through Marvex's existing OpenAI SDK boundary.
- retry/parsing behavior: includes safe parsing and `tenacity`; useful, but this
  is exactly where Marvex must avoid hidden retry policy before approval.
- architecture takeover risk: medium. It brings prompt tasks, built-in NLP task
  classes, batch/async execution, cost tracking, and eval helpers.
- adapter isolation: possible behind a future `ProviderStructuredOutputAdapter`
  or `PromptTaskRuntime` adapter. It must not be imported by
  `AssistantTurnRuntime`, Core, CLI, or provider ports.
- fallback if abandoned: OpenAI Structured Outputs plus Pydantic validation,
  Instructor, Outlines, or Guidance behind the same adapter.
- decision: defer. Reconsider only after a no-network adapter skeleton and
  dependency compatibility check.

### OpenAI Structured Outputs

- official source:
  `https://platform.openai.com/docs/guides/structured-outputs`
- maintenance status: active official OpenAI API feature.
- Python/Windows fit: good through the existing OpenAI Python SDK dependency.
- dependency footprint: no new dependency if used through current `openai`
  package. Marvex currently pins `openai==2.24.0`.
- local model support: only if the local OpenAI-compatible provider supports
  the same schema parameters. LM Studio compatibility must be verified before
  relying on it.
- LiteLLM compatibility/overlap: complementary but uneven. LiteLLM may expose
  provider-specific structured-output paths differently; this must stay inside
  the provider adapter.
- Pydantic compatibility: good. OpenAI docs show validating/parsing returned
  JSON with Pydantic models and emphasize type-safe use after schema-constrained
  generation.
- provider-native schema support: strongest candidate for OpenAI-compatible
  providers. The API supports strict JSON Schema, but only a supported subset.
- retry/parsing behavior: provider enforces schema when supported. Marvex should
  still validate with Pydantic and handle refusal/incomplete/provider errors.
- architecture takeover risk: low if kept in provider adapter.
- adapter isolation: strong. Belongs in an OpenAI/LM Studio provider structured
  output adapter, not Core or AssistantTurnRuntime.
- fallback if abandoned: plain Pydantic validation over text/JSON provider
  output, Instructor, or Promptify.
- decision: use provider-native first where supported, no dependency added.

### Instructor

- official source: `https://github.com/567-labs/instructor`
- maintenance status: active. GitHub snapshot on 2026-05-05: Python, MIT, last
  pushed 2026-04-22, about 12.9k stars.
- Python/Windows fit: plausible. Requires Python 3.9+.
- dependency footprint: moderate. Core dependencies include OpenAI, Pydantic,
  docstring-parser, Typer, Rich, aiohttp, tenacity, jiter, Jinja2, and requests;
  many optional provider extras exist.
- local model support: yes through provider helpers such as Ollama and optional
  LiteLLM integrations.
- LiteLLM compatibility/overlap: optional overlap. Instructor has a LiteLLM
  extra but would still wrap provider calls unless tightly isolated.
- Pydantic compatibility: excellent. Instructor is schema-first and Pydantic
  oriented.
- provider-native schema support: good across major providers, but the adapter
  abstracts provider behavior and retries.
- retry/parsing behavior: strong automatic validation/retry behavior. Useful
  later, risky now because retry policy is not yet approved.
- architecture takeover risk: low-to-medium. It is narrower than agent
  frameworks but can still own provider calls and retries.
- adapter isolation: possible in a provider structured-output adapter.
- fallback if abandoned: OpenAI Structured Outputs plus Pydantic validation, or
  Promptify.
- decision: defer. Candidate if provider-native path is insufficient and Marvex
  explicitly approves retry behavior.

### Outlines

- official source: `https://github.com/dottxt-ai/outlines`,
  `https://dottxt-ai.github.io/outlines/`
- maintenance status: active. GitHub snapshot on 2026-05-05: Python,
  Apache-2.0, last pushed 2026-05-04, about 13.8k stars.
- Python/Windows fit: mixed. Requires Python >=3.10,<3.14; base package is
  Python, but many useful local-model extras are heavier.
- dependency footprint: base package includes Jinja2, cloudpickle, diskcache,
  Pydantic, jsonschema, Pillow, outlines-core, genson, and jsonpath-ng; optional
  extras cover OpenAI, Ollama, LM Studio, transformers, vLLM, llama.cpp, etc.
- local model support: strong.
- LiteLLM compatibility/overlap: limited direct overlap; it is more constrained
  generation than provider abstraction.
- Pydantic compatibility: strong.
- provider-native schema support: not the point; it constrains generation
  itself when supported by backend.
- retry/parsing behavior: reduces parsing failure by constraining generation.
- architecture takeover risk: medium for local-model structured generation,
  because model backend decisions become part of the adapter.
- adapter isolation: possible in a local structured-generation provider adapter.
- fallback if abandoned: OpenAI Structured Outputs or Instructor.
- decision: defer. Better for future local-model constrained generation than
  near-term OpenAI-compatible provider bridge.

### Guidance

- official source: `https://github.com/guidance-ai/guidance`
- maintenance status: active. GitHub snapshot on 2026-05-05: MIT, last pushed
  2026-04-10, about 21.4k stars.
- Python/Windows fit: uncertain. It has Python/C++ style build requirements via
  `pybind11` and optional model integrations.
- dependency footprint: potentially heavier than plain validation; official
  config references optional integrations for llama.cpp, Anthropic, LiteLLM,
  transformers, diskcache, and tokenizers.
- local model support: strong directionally.
- LiteLLM compatibility/overlap: optional integration exists, but adopting it
  would add a second prompt/programming layer around provider calls.
- Pydantic compatibility: weaker than Instructor/Outlines for Marvex's immediate
  Pydantic contract path.
- provider-native schema support: not the primary fit.
- retry/parsing behavior: controls generation through a prompt programming
  layer rather than simple post-validation.
- architecture takeover risk: medium-high. It introduces a guidance language and
  execution model.
- adapter isolation: possible only as an isolated structured-generation adapter.
- fallback if abandoned: Outlines, OpenAI Structured Outputs, Instructor.
- decision: defer/reject for current phase.

### Plain Pydantic Validation Over Provider Output

- official source: `https://docs.pydantic.dev/latest/`
- maintenance status: active. Pydantic docs show current stable version 2.13.3;
  Marvex already depends on `pydantic>=2,<3`.
- Python/Windows fit: already validated in Marvex.
- dependency footprint: none beyond existing dependency.
- local model support: provider-agnostic because it validates after output.
- LiteLLM compatibility/overlap: complementary. LiteLLM/OpenAI adapters return
  raw provider output; Pydantic validates Marvex contracts after extraction.
- Pydantic compatibility: native.
- provider-native schema support: none. It does not constrain generation.
- retry/parsing behavior: none unless Marvex adds policy. This is a feature for
  the skeleton stage: no hidden retry loops.
- architecture takeover risk: low.
- adapter isolation: excellent. Keep in provider structured-output adapter or
  contract conversion helper.
- fallback if abandoned: provider-native Structured Outputs, Instructor.
- decision: use first as validation fallback and no-network skeleton basis.

### Existing Marvex LiteLLM / OpenAI SDK Boundaries

- official/local source: `docs/library-decisions/litellm.md`,
  `docs/library-decisions/lmstudio_responses.md`, `pyproject.toml`
- maintenance status: documented as active in existing Marvex decisions.
- dependency footprint: already present: `litellm==1.83.13`,
  `openai==2.24.0`, `pydantic>=2,<3`.
- local model support: LM Studio Responses adapter uses OpenAI SDK against a
  local OpenAI-compatible endpoint; LiteLLM remains generic cloud/multi-provider
  adapter.
- LiteLLM compatibility/overlap: this is the current provider boundary. Any
  structured-output tool must not replace or bypass it casually.
- Pydantic compatibility: existing contracts already use Pydantic.
- provider-native schema support: OpenAI SDK path is the best near-term path to
  test. LiteLLM behavior must be checked separately.
- retry/parsing behavior: current provider decisions explicitly do not approve
  routing/fallback/retry/session history expansion.
- architecture takeover risk: low if structured-output logic stays adapter-side.
- adapter isolation: existing approved pattern.
- fallback if abandoned: add a new structured-output adapter decision, not raw
  HTTP in Core.
- decision: preserve boundaries; build no-network skeleton before provider
  bridge.

### Pydantic AI and LangGraph Comparison

- Pydantic AI is active and Python-native, but it is an agent framework with
  tools/evals/MCP/runtime gravity. It is not needed for provider structured
  output.
- LangGraph is active but workflow orchestration. This task is not workflow
  orchestration.
- decision: reference only; do not adopt.

## 3. Recommended Boundary

Future structured-output behavior should live in a provider-adjacent adapter
boundary, not in `AssistantTurnRuntime`.

Recommended shape:

- package owner: future provider structured-output adapter under provider
  adapter ownership, or a small provider-stage bridge package if a separate task
  approves it.
- inputs: Marvex-owned prompt/task payload, target Pydantic contract/schema,
  explicit provider identity, and provider output object.
- outputs: validated Marvex contract object or `ErrorEnvelope`.
- allowed dependencies at first: existing Pydantic only.
- provider-native path: OpenAI-compatible provider adapter may pass JSON Schema
  parameters when explicitly supported.
- forbidden in this boundary: Core imports, AssistantTurnRuntime imports,
  provider routing, fallback chains, model routing, session history, memory,
  tools, prompt registry, eval platform, and hidden retries.

The adapter must not bypass `ProviderRuntime`. ProviderRuntime remains the
provider selection/factory boundary; provider adapters own provider-specific
request shapes.

## 4. Impact on Next Tasks

Should Task 070 implement provider bridge?

No. A provider bridge would require prompt rendering, provider call shape, error
mapping, schema transport, and possibly retry semantics. That is too much for
the next slice.

Should Task 070 be a no-network structured-output adapter skeleton?

Yes. It should define and test a no-network adapter skeleton around Pydantic
schemas and fake provider payloads. It should prove where structured-output
conversion lives without calling providers or adding dependencies.

Should dependencies be added?

No. Use existing Pydantic for the skeleton. Add dependencies only after a
separate dependency-governance task proves provider-native output is
insufficient.

Should provider contracts change?

Not yet. Start with fixture objects and existing contracts. If the skeleton
shows a missing contract shape, stop and write a contract task.

Should AssistantTurnRuntime change?

No. AssistantTurnRuntime should remain no-provider runtime contract glue.
Structured provider output belongs provider-side.

## 5. Risks

framework takeover:

- Promptify adds task classes, async/batch behavior, cost tracking, evals, and
  LiteLLM backend ownership. Guidance adds a prompt programming model. Pydantic
  AI and LangGraph are broader runtime frameworks.

dependency bloat:

- Promptify would currently conflict with Marvex's LiteLLM pin range.
  Instructor, Outlines, and Guidance add meaningful transitive dependencies and
  provider extras.

bypassing ProviderRuntime:

- Any tool that calls providers directly can bypass the existing provider
  factory/adapter boundary unless isolated carefully.

provider-specific leakage into Core:

- JSON Schema limitations, OpenAI refusal handling, LiteLLM quirks, and local
  model backend choices must remain outside Core.

local model compatibility:

- OpenAI Structured Outputs may not apply to LM Studio or LiteLLM paths. Outlines
  and Guidance may fit local constrained generation later, but their backend
  requirements are not approved.

typed-output hallucination/parsing failures:

- Plain Pydantic validation can reject bad output but cannot constrain
  generation. Provider-native schemas reduce malformed output where supported.
  Retry policy must be explicit, not accidental.

retry loop overengineering:

- Instructor/Promptify retries are useful but can hide cost, latency, and
  failure semantics. Do not add retries until contracts define retry reporting.

## 6. Final Decision

Immediate next task recommendation:

Task 070 should create a no-network provider structured-output adapter skeleton
using existing Pydantic contracts and fake provider payloads. It should not call
providers, render prompts, add dependencies, or change ProviderRuntime.

After Task 070, if the adapter skeleton proves a real provider call is needed,
run a narrow OpenAI Structured Outputs compatibility spike using the existing
OpenAI SDK path before considering Promptify or Instructor.

## 7. Task 073 Handoff Contract Gate

decision date: 2026-05-06

Decision: keep the result-shaped handoff object as a README/test fixture for
now. Do not promote it into a formal Marvex contract yet.

Current tested fixture shape:

- `trace_id`
- `structured_payload`

Reasoning:

- The shape has only been proven by no-network examples and tests.
- No provider bridge or provider adapter has emitted this shape yet.
- The boundary has not yet proven how missing payloads, malformed structured
  payloads, refusal-like results, incomplete results, or provider-side error
  result shapes should be represented at the handoff point.
- Promoting the shape now would freeze field names and ownership before the
  bridge boundary has real pressure from adapter-shaped data.
- Existing Marvex-owned Pydantic contracts already validate the nested target
  payload, so a new outer contract is not needed for the current skeleton.

What must be proven before formalizing:

1. A no-network provider bridge skeleton can construct the handoff shape from
   fake adapter-shaped result data without changing ProviderRuntime, provider
   adapters, Core, AssistantTurnRuntime, CLI, services, or dependencies.
2. The skeleton can preserve `trace_id` and pass `structured_payload` into
   `validate_structured_result(...)` without adding provider references or
   response identifiers.
3. Missing, malformed, incomplete, and error-like result-shaped data can map to
   deterministic `ErrorEnvelope` objects without a new dependency or retry
   policy.
4. A later provider-native structured-output compatibility spike confirms
   whether real provider responses can supply an equivalent already-structured
   payload shape.

Next implementation-safe task:

Run a no-network provider bridge skeleton task that uses fake adapter-shaped
result data and the existing `validate_structured_result(...)` helper. The task
must not change ProviderRuntime, provider adapters, Core, AssistantTurnRuntime,
CLI, services, dependencies, or contracts.

AssistantTurnRuntime must not change yet. ProviderRuntime and provider adapters
must not change in this decision task. No dependencies should be added.
