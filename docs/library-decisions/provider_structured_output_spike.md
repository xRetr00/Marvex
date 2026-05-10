# Provider Structured Output Spike Decision

verified date: 2026-05-10

verified by: Codex

decision scope: future provider bridge behavior that asks models for typed or
structured output.

implementation impact: research and adapter decision only. No dependency is
approved by this document. No provider bridge, runtime behavior, Core behavior,
CLI behavior, prompt rendering, or structured-output execution is implemented.

file size justification: this decision record keeps the structured-output
candidate comparison, skeleton decisions, manual harness instructions, and
sanitized provider observations together so future implementation tasks do not
separate observed provider behavior from the dependency and boundary decision.

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

After Task 070 through Task 075, the no-network skeleton and fake
adapter-shaped pressure tests have proven the local validation boundary. The
next task must be a narrow provider-native structured-output compatibility spike
spec before any real provider bridge implementation.

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

## 8. Task 078 Provider-Native Compatibility Spike Spec

decision date: 2026-05-10

Decision: run the first real compatibility spike against the existing LM Studio
Responses provider path using the pinned OpenAI Python SDK surface already
approved for `packages/adapters/providers/lmstudio_responses/`.

This is the first provider path because it is already approved, uses the
existing `openai==2.24.0` dependency, can test provider-native schema transport
closest to Marvex's local model path, and keeps provider-specific behavior in
adapter/provider ownership instead of Core, AssistantTurnRuntime, CLI, or ports.

The spike must use provider-native structured outputs before custom parsing
because schema-constrained provider behavior, when supported, is less brittle
than prompt-only JSON instructions plus a hand-written parser. Plain Pydantic
validation remains mandatory after the provider call, but Pydantic alone cannot
prove whether the provider can honor the schema, report refusal-like outcomes,
or signal incomplete results in a way Marvex can model safely.

Maintained surfaces to check first: the installed `openai==2.24.0` SDK surface,
official OpenAI Responses structured-output behavior and JSON Schema subset as
applicable to that SDK, LM Studio's OpenAI-compatible Responses behavior, and
LiteLLM only as a secondary comparison if the LM Studio Responses path cannot
exercise provider-native schema transport. Promptify, Instructor, Outlines,
Guidance, Pydantic AI, and LangGraph remain deferred alternatives unless a
separate library-decision update proves the provider-native path insufficient.

Exact provider behavior the spike must observe:

- valid structured success: a real provider call returns data that can be
  converted into the target Marvex Pydantic contract without custom parsing.
- invalid or malformed structured result: the provider either rejects the
  request, returns a schema-invalid result, or exposes enough raw output for
  Marvex to produce a deterministic validation failure.
- refusal-like response if supported: the provider or SDK exposes a refusal,
  safety refusal, blocked answer, or equivalent non-answer signal without
  forcing Marvex to infer refusal from arbitrary text.
- incomplete or length-like response if supported: the provider or SDK exposes
  truncation, max-output, incomplete, length, or equivalent finish state
  separately from a normal successful structured result.
- provider error or timeout behavior if observable without unsafe overreach:
  connection failure, unsupported schema parameter, model error, or timeout must
  be recorded as provider behavior, not collapsed into a fake success.

Outputs the spike must record in the spike report: sanitized request shape,
sanitized response shape, parsed object behavior, raw fallback behavior,
refusal/incomplete/error representation, and `trace_id` handling expectations.
Sanitization must remove secrets, local paths, hostnames beyond localhost, and
user-private content. Do not invent contract names for missing semantics, and do
not depend on provider response ids or provider metadata as assistant state.

Forbidden during the compatibility spike: no Core integration, ProviderRuntime
structured-output changes, AssistantTurnRuntime provider integration, CLI
behavior change, service or worker behavior change, formal handoff contract
promotion, custom parser framework, retry policy implementation, or dependency
addition without an updated library decision record and validation plan. No
provider response id, provider metadata, or raw response blob may become hidden
assistant state.

Decision gates before implementation may start:

1. Provider behavior has been observed from a real call or the spike records
   clearly that the configured provider path cannot support provider-native
   structured outputs.
2. The Pydantic validation path is confirmed against the observed provider
   payload or against the raw fallback payload.
3. Refusal and incomplete semantics are understood enough to decide whether
   existing contracts are sufficient or a contract task is required.
4. Fallback behavior is documented: parsed object, JSON object, text, raw SDK
   response, or provider error.
5. The implementation boundary is selected without expanding Core,
   AssistantTurnRuntime, CLI, services, ports, or ProviderRuntime beyond an
   explicitly approved task.
6. Validation commands pass before any implementation task is considered:
   `python scripts/check_provider_structured_output_boundaries.py`,
   `python -m pytest tests/provider_structured_output -q`,
   `python -m pytest -q`, and `python scripts/run_all_checks.py`.

Implementation recommendation after this spec:

Run one provider-native compatibility spike as a manual, bounded,
no-persistence provider observation task. The spike may use temporary local
scripts or terminal-only commands if the task spec allows them, but it must not
commit product/runtime/provider behavior unless a later implementation task is
approved. The result should be a report that decides whether the next build
slice can use provider-native structured outputs plus Pydantic validation, or
whether Marvex needs a separate dependency decision for Promptify, Instructor,
Outlines, Guidance, or another maintained structured-output helper.

## 9. Task 079 Manual Spike Harness
decision date: 2026-05-10
Task 079 adds `scripts/spike_lmstudio_structured_output.py` as a manual,
opt-in observation harness. It stays out of `run_all_checks.py`, persists no
traces or outputs, and does not integrate provider-native structured outputs.
Manual run:
```powershell
python scripts/spike_lmstudio_structured_output.py --model <local-model>
```
Optional flags: `--base-url`, `--timeout-seconds`, and `--show-raw-preview`;
raw preview output is off by default and bounded to 300 characters when enabled.
Copy sanitized fields into the final report: case, trace, request mode,
status/finish, parsed-object yes/no, raw-fallback yes/no, refusal-like yes/no,
incomplete/length-like yes/no, and sanitized error class/code/message. To unlock
implementation, the report must show whether `openai==2.24.0` plus LM Studio
Responses can produce usable structured output, malformed-pressure behavior,
refusal/incomplete signals, and Pydantic consumption of parsed or safe fallback
payloads.
Still forbidden: Core, ProviderRuntime, AssistantTurnRuntime, CLI normal-turn,
or service integration; handoff contract promotion; custom parser frameworks;
retry policy; dependency additions; and hidden assistant state in provider
metadata.

## 10. Task 080 Manual Spike Observations

observed date: 2026-05-10

model: `qwen3.5-0.8b`

endpoint: `http://localhost:1234/v1`

command:

```powershell
python scripts/spike_lmstudio_structured_output.py --model "qwen3.5-0.8b"
```

Sanitized observations:

| case | request mode | status/finish | parsed object | raw fallback | refusal-like | incomplete/length-like | sanitized error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| valid_structured_success | responses.parse | error / unavailable | no | no | no | no | ValidationError, json_invalid |
| invalid_schema_request_pressure | responses.create.invalid_schema | completed / completed | no | yes | no | no | none |
| refusal_like_pressure | responses.parse | error / unavailable | no | no | no | no | ValidationError, extra_forbidden and missing |
| incomplete_length_pressure | responses.parse | error / unavailable | no | no | no | no | ValidationError, json_invalid |

Interpretation:

- LM Studio Responses with `qwen3.5-0.8b` through `openai==2.24.0` did not
  produce SDK-parsed provider-native structured output in this run.
- The valid structured success case failed client-side Pydantic parsing, which
  means this model/path did not provide usable schema-constrained output for the
  target contract shape.
- The invalid-schema pressure case completed and exposed raw fallback text,
  rather than surfacing a provider schema rejection. Treat this as evidence that
  schema transport may be ignored or only partially honored on this path until a
  narrower provider/API-shape check proves otherwise.
- The refusal-like case did not expose a provider refusal field or signal. It
  produced validation errors against a non-target shape instead.
- The incomplete/length pressure case did not expose an incomplete or
  length-like provider signal through the sanitized observation fields.

Decision after Task 080:

This observed LM Studio Responses path is not yet usable enough to unlock a
runtime implementation of provider-native structured output. The next planning
step should either test a different loaded LM Studio model or a narrower
OpenAI-compatible request shape, or document a fallback path that treats LM
Studio structured output as raw provider text plus explicit Pydantic validation
and deterministic error mapping. Do not add a dependency, custom parser
framework, retry policy, formal handoff contract, ProviderRuntime behavior, Core
integration, CLI integration, or AssistantTurnRuntime provider integration from
this observation alone.

## 11. Task 081 Fallback Decision After LM Studio Spike

decision date: 2026-05-10

Tested path:

- endpoint: LM Studio Responses at `http://localhost:1234/v1`
- SDK/dependency: pinned `openai==2.24.0`
- model: `qwen3.5-0.8b`
- harness: `scripts/spike_lmstudio_structured_output.py`

Outcome:

- `responses.parse` was not usable enough on the tested path/model.
- A parsed structured object was not reliably returned.
- Raw fallback text appeared only in the invalid schema pressure case.
- Refusal and incomplete semantics remain unresolved for this path.
- The observed behavior does not justify provider-native structured-output
  runtime integration.

Security and safety note:

Validation errors can leak raw provider output snippets if error strings are
printed directly. Sanitized error reporting is mandatory for all future
structured-output spike, fallback, and implementation work. Reports may include
bounded sanitized previews only when explicitly requested; raw full provider
outputs, prompts, secrets, environment values, and persistent trace logs remain
forbidden.

Decision:

- Do not implement provider-native structured-output runtime integration from
  Task 080 evidence.
- Do not promote the current handoff fixture into a formal Marvex contract yet.
- Do not add parser, retry, dependency, framework, ProviderRuntime, Core, CLI,
  service, or AssistantTurnRuntime behavior yet.

Next safe options, as alternatives only:

1. Run a second manual spike with a stronger or different loaded LM Studio
   model, using the same sanitized observation rules.
2. Try a narrower OpenAI-compatible request shape if the installed client and
   local server expose one without adding dependencies or changing runtime code.
3. Design a fallback path around raw provider text, strict Pydantic validation,
   deterministic validation failure mapping, sanitized error output, and no
   custom JSON repair parser unless a separate decision justifies it.

Evidence required before implementation may start:

- stable parsed-object behavior from provider-native structured output, or an
  explicit fallback decision accepted with deterministic invalid-output
  semantics.
- documented refusal, incomplete, provider error, and validation failure mapping.
- clear `trace_id` propagation behavior that does not depend on provider
  response ids or provider metadata as assistant state.
- passing validation gates: targeted structured-output checks, relevant tests,
  full pytest if implementation code changes, and `python scripts/run_all_checks.py`.

Implementation remains blocked until one of those evidence paths is satisfied.

## 12. Task 082 Structured Output Fallback Design

decision date: 2026-05-10

Purpose: define the safe fallback path after Task 080/081 showed the tested LM
Studio Responses provider-native path is not implementation-ready. This is a
design only; it does not approve runtime integration.

Fallback input:

- raw provider output text from an already-completed provider call.
- explicit target schema or Marvex-owned Pydantic contract type.
- `trace_id` and `turn_id` context supplied by the caller.
- optional provider error/timeout classification from the provider adapter when
  no output text is available.

Fallback process:

1. Do not trust raw provider output as structured data.
2. Attempt strict JSON extraction only when the entire provider output is valid
   JSON, or when the provider explicitly returns a JSON/structured field.
3. Do not scrape braces, repair JSON, trim prose around JSON, or infer hidden
   fields from text.
4. Validate the candidate object through Marvex-owned Pydantic contracts.
5. Map validation failure to deterministic structured failure without leaking
   raw provider text.
6. Sanitize every validation and provider error message before reporting.

Fallback output states:

- `valid_structured_result`: strict JSON/Pydantic validation succeeded.
- `invalid_structured_output`: provider returned output, but no strict valid
  structured object could be validated.
- `provider_error`: provider or SDK returned a provider error before usable
  output existed.
- `provider_timeout`: timeout occurred before usable output existed.
- `refusal_unresolved_or_provider_specific`: refusal-like behavior was present
  or suspected, but not mapped to a stable Marvex contract.
- `incomplete_unresolved_or_provider_specific`: incomplete/length-like behavior
  was present or suspected, but not mapped to a stable Marvex contract.

Explicitly forbidden:

- custom JSON repair parser.
- heuristic brace scraping.
- silent retries.
- hidden provider prompt mutation.
- promotion to a formal handoff contract before implementation evidence.
- raw provider output in telemetry or logs by default.
- using provider metadata, provider response ids, or raw response blobs as
  hidden assistant state.

Security rules:

- never log full provider output by default.
- validation errors must be sanitized and must not include `input_value` or raw
  provider snippets.
- bounded previews are allowed only in manual diagnostic mode.
- `trace_id` must be preserved through every fallback result or failure.
- `turn_id` must remain explicit caller context, not recovered from metadata.

Future implementation may:

- create a small adapter-local fallback mapper behind provider/adapter ownership.
- keep fallback mapping outside Core, ProviderRuntime, AssistantTurnRuntime, CLI,
  services, and ports unless a later task explicitly approves integration.
- return deterministic invalid-output semantics for malformed or non-JSON model
  text.
- keep refusal and incomplete semantics conservative until stronger provider
  evidence exists.

Future tasks still required before product behavior:

- contract shape or typed result shape decision.
- focused tests for valid JSON, invalid JSON, provider error, timeout, sanitized
  validation errors, trace preservation, and conservative refusal/incomplete
  states.
- ProviderRuntime integration decision, if provider selection must expose the
  fallback.
- AssistantTurnRuntime handoff decision, if assistant-level stages consume the
  fallback result.
- optional second provider-native model spike, if better LM Studio model
  evidence is desired before accepting fallback-first behavior.

Implementation remains blocked until this fallback design is accepted by a
separate implementation task with explicit allowed files, tests, validation
commands, and boundary constraints.
