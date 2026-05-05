# Prompt, Harness, and Context Tooling Research Matrix

verified date: 2026-05-05

verified by: Codex

decision scope: prompt engineering, structured outputs, context delivery,
harness engineering, agent task prompts, evaluation/verification tooling,
observability/tracing, MCP/context servers, desktop context tools, and agent
frameworks.

implementation impact: research and decision record only. No dependency is
approved by this document. No product/runtime behavior changes are approved.

file size justification: this matrix intentionally keeps the reviewed source
list, official candidate checks, per-candidate decisions, immediate impact, next
task recommendations, and risks together so future agents do not separate the
library-first evidence from the resulting prompt/harness/context decisions.

## 1. Executive Verdict

Marvex should not adopt a prompt, harness, context, eval, observability, MCP,
desktop-context, or agent-framework dependency now.

Immediate direction:

- Continue assistant_runtime as thin custom contract-consumption code.
- Use public harness/prompt/context sources as patterns only.
- Prefer already-approved Pydantic contracts and provider-native structured
  outputs over a new structured-output framework for the next provider bridge
  preparation slice.
- Defer eval/observability platforms until Marvex emits real assistant/provider
  traces and has replay fixtures.
- Defer desktop/screen/audio context tooling until Desktop Agent planning has
  an explicit privacy, retention, consent, and local-storage policy.
- Reject central agent frameworks for current runtime work because they would
  take over orchestration, tools, memory, handoffs, or graph state before Marvex
  has approved those boundaries.

No future task is blocked on adopting a candidate. Future tasks are blocked on
doing an adapter/port review before adding any candidate dependency.

## 2. Reviewed Sources

Requested source lists reviewed:

- `https://github.com/alvinreal/awesome-opensource-ai#prompt-engineering--structured-outputs`
  - Extracted: LMQL, structured-output tooling direction, prompt/structured
    output category framing.
- `https://github.com/promptslab/awesome-prompt-engineering`
  - Extracted: prompt-engineering resources as pattern-only material; no
    immediate runtime dependency.
- `https://github.com/ai-boost/awesome-prompts`
  - Extracted: prompt structure/prompt library pattern only; no dependency.
- `https://github.com/ai-boost/awesome-harness-engineering`
  - Extracted: harness categories for context delivery, planning artifacts,
    permissions/sandboxing, verification/evals, memory/state, observability,
    MCP, and orchestration.
- `https://github.com/ai-boost/awesome-harness-engineering#context-delivery--compaction`
  - Extracted: context delivery/compaction as a harness concern, not as runtime
    behavior for this phase.
- `https://github.com/louis030195/awesome-context-ai`
  - Extracted: screenpipe, context/memory systems, MCP context servers,
    LlamaIndex, Haystack, screen/audio context privacy risks.
- `https://github.com/punkpeye/awesome-mcp-servers`
  - Extracted: MCP server ecosystem as future ToolRuntime/DesktopAgent research
    source, not a dependency.

Official sources reviewed for serious candidates:

- LMQL: `https://github.com/eth-sri/lmql`, `https://lmql.ai/`
- Microsoft Prompt Engine: `https://github.com/microsoft/prompt-engine`
- LynxPrompt: `https://github.com/GeiserX/LynxPrompt`, `https://lynxprompt.com/`
- flompt: `https://github.com/Nyrok/flompt`, `https://flompt.dev/`
- DeepEval: `https://github.com/confident-ai/deepeval`, `https://deepeval.com/docs/introduction`
- Langfuse: `https://github.com/langfuse/langfuse`, `https://langfuse.com/`
- Phoenix: `https://github.com/Arize-ai/phoenix`, `https://arize.com/docs/phoenix`
- InspectAI: `https://github.com/UKGovernmentBEIS/inspect_ai`
- Opik: `https://github.com/comet-ml/opik`, `https://www.comet.com/docs/opik/`
- LangGraph: `https://github.com/langchain-ai/langgraph`, `https://docs.langchain.com/oss/python/langgraph/`
- OpenAI Agents SDK: `https://github.com/openai/openai-agents-python`,
  `https://platform.openai.com/docs/guides/agents-sdk/`
- Pydantic AI: `https://github.com/pydantic/pydantic-ai`,
  `https://pydantic.dev/docs/ai/`
- smolagents: `https://github.com/huggingface/smolagents`,
  `https://huggingface.co/docs/smolagents/`
- LlamaIndex: `https://github.com/run-llama/llama_index`,
  `https://docs.llamaindex.ai/`
- Haystack: `https://github.com/deepset-ai/haystack`,
  `https://docs.haystack.deepset.ai/docs/intro`
- screenpipe: `https://github.com/screenpipe/screenpipe`,
  `https://screenpi.pe/`
- Instructor: `https://github.com/567-labs/instructor`
- Outlines: `https://github.com/dottxt-ai/outlines`,
  `https://dottxt-ai.github.io/outlines/`
- OpenAI Structured Outputs:
  `https://platform.openai.com/docs/guides/structured-outputs`
- MCP official servers source: `https://github.com/modelcontextprotocol/servers`

GitHub maintenance snapshot was checked on 2026-05-05 via official GitHub repo
metadata for serious GitHub-hosted candidates.

## 3. Candidate Matrix

### Prompt Management / Prompt Templates

#### Microsoft Prompt Engine

- category: prompt management / prompt templates
- official source: `https://github.com/microsoft/prompt-engine`
- maintenance status: low current maintenance. GitHub snapshot: TypeScript,
  MIT, last pushed 2023-04-25, stars about 2.7k.
- implementation type: library
- language/runtime: TypeScript / npm
- current Marvex fit: poor. Marvex runtime is Python and contract-owned.
- why use: demonstrates composable prompt objects, examples, dialog state, and
  YAML prompt loading.
- why not custom: prompt composition and versioned templates are known problems;
  hand-rolled prompt strings should not become Marvex architecture.
- why not use now: stale relative to current LLM APIs and Node-first; would add
  prompt machinery before Marvex has approved prompt rendering.
- isolation boundary if adopted: future PromptRuntime adapter or prompt template
  repository, never Core or AssistantTurnRuntime directly.
- fallback if abandoned: keep prompts as versioned Markdown/task specs and typed
  contracts.
- decision: pattern only.

#### LynxPrompt

- category: agent task prompt/config management
- official source: `https://github.com/GeiserX/LynxPrompt`,
  `https://lynxprompt.com/`
- maintenance status: active but young. GitHub snapshot: TypeScript, GPL-3.0,
  last pushed 2026-05-04, small project footprint.
- implementation type: app / CLI / self-hosted config platform
- language/runtime: TypeScript, web/CLI
- current Marvex fit: weak for runtime, moderate as external process idea for
  AI-agent config governance.
- why use: centralizes AGENTS/CLAUDE/Cursor-style rule generation and team sync.
- why not custom: multi-agent config sprawl is real; a tool can prevent copied
  rule files diverging.
- why not use now: GPL-3.0, cloud/federation shape, CLI/web app footprint, and
  no need while Marvex has repo-local governance docs.
- isolation boundary if adopted: external developer tooling only; generated docs
  reviewed into repo. No runtime import.
- fallback if abandoned: keep repo-local AGENTS/TASK_SPEC/docs validation gates.
- decision: defer for developer tooling; do not adopt for product runtime.

#### flompt

- category: prompt management / prompt templates
- official source: `https://github.com/Nyrok/flompt`, `https://flompt.dev/`
- maintenance status: active but early. GitHub snapshot: TypeScript, MIT, last
  pushed 2026-03-30, small project footprint.
- implementation type: visual app / browser extension / MCP server
- language/runtime: TypeScript, browser/MCP
- current Marvex fit: poor for runtime; possible prompt-design reference.
- why use: decomposes prompts into blocks and compiles structured prompt text.
- why not custom: block-based prompt decomposition is better than ad hoc giant
  strings when prompt work becomes a real product surface.
- why not use now: visual/MCP workflow, persistent context features, and
  Claude-optimized output are outside the current assistant_runtime scope.
- isolation boundary if adopted: external authoring tool only; checked-in prompt
  artifacts, no runtime dependency.
- fallback if abandoned: Markdown templates plus validation gates.
- decision: pattern only.

### Structured Outputs

#### OpenAI Structured Outputs

- category: structured outputs
- official source: `https://platform.openai.com/docs/guides/structured-outputs`
- maintenance status: active official OpenAI API feature.
- implementation type: provider/API feature
- language/runtime: provider-native; Python SDK supports Pydantic schemas.
- current Marvex fit: good later for provider-stage bridge, not for
  assistant_runtime skeleton.
- why use: schema adherence belongs at provider boundary when asking a model for
  typed output.
- why not custom: retry loops and prompt-only JSON instructions duplicate a
  provider-supported feature.
- why not use now: current assistant_runtime path does not call providers.
- isolation boundary if adopted: provider adapter or future structured-output
  bridge; Core sees only Marvex contracts.
- fallback if abandoned: Pydantic validation over raw provider output plus
  adapter-level retries under a separate decision.
- decision: defer; preferred first structured-output mechanism when provider
  bridge asks models for typed data.

#### Instructor

- category: structured outputs
- official source: `https://github.com/567-labs/instructor`
- maintenance status: active. GitHub snapshot: Python, MIT, last pushed
  2026-04-22, stars about 12.9k.
- implementation type: library
- language/runtime: Python
- current Marvex fit: plausible behind provider adapter later.
- why use: mature Pydantic-oriented extraction/structured-output helper.
- why not custom: would avoid custom retry/parsing scaffolding around provider
  JSON.
- why not use now: Marvex already has Pydantic contracts and no provider bridge
  in assistant_runtime; adding a wrapper before real provider structured-output
  needs is premature.
- isolation boundary if adopted: provider structured-output adapter only.
- fallback if abandoned: OpenAI Structured Outputs or plain Pydantic validation
  in provider adapter.
- decision: defer.

#### Outlines

- category: structured outputs / constrained generation
- official source: `https://github.com/dottxt-ai/outlines`,
  `https://dottxt-ai.github.io/outlines/`
- maintenance status: active. GitHub snapshot: Python, Apache-2.0, last pushed
  2026-05-04, stars about 13.8k.
- implementation type: library
- language/runtime: Python
- current Marvex fit: possible for local-model constrained generation, not for
  current provider foundation.
- why use: constrained generation can enforce schemas without provider-specific
  APIs.
- why not custom: grammar/constrained decoding is easy to get wrong.
- why not use now: no local model runtime or constrained generation boundary is
  approved.
- isolation boundary if adopted: local provider adapter or structured-output
  adapter.
- fallback if abandoned: provider-native structured outputs or Instructor.
- decision: defer.

#### LMQL

- category: structured outputs / prompt programming
- official source: `https://github.com/eth-sri/lmql`, `https://lmql.ai/`
- maintenance status: mature but not very current. GitHub snapshot: Python,
  Apache-2.0, last pushed 2025-05-22, stars about 4.2k.
- implementation type: programming language/runtime/IDE
- language/runtime: Python plus optional Node playground and model backends
- current Marvex fit: poor.
- why use: expressive constraints and prompt programming can reduce prompt-only
  schema failure.
- why not custom: custom prompt DSLs should be avoided.
- why not use now: it introduces a language/runtime and secret configuration
  path; this is architecture gravity for a small provider bridge.
- isolation boundary if adopted: isolated experimental prompt compiler, never
  Core/AssistantTurnRuntime.
- fallback if abandoned: OpenAI Structured Outputs, Instructor, or Pydantic.
- decision: reject for current Marvex phase.

### Context Delivery / Compaction and Harness Engineering

#### awesome-harness-engineering

- category: harness engineering / context delivery / compaction
- official source: `https://github.com/ai-boost/awesome-harness-engineering`
- maintenance status: active curated source. GitHub page showed recent active
  issue/PR surface and about 700+ stars at review time.
- implementation type: pattern-only source
- language/runtime: not applicable
- current Marvex fit: strong as process reference.
- why use: reinforces scoped context, explicit permissions, durable files,
  verification loops, sandboxing, and observability as harness primitives.
- why not custom: custom hidden prompt conventions rot; persistent docs/tests
  are better.
- why not use now: it is not a library.
- isolation boundary if adopted: governance docs, task specs, validation gates.
- fallback if abandoned: Marvex AGENT rules and validation gates.
- decision: pattern only.

#### awesome-prompts and promptslab prompt resources

- category: prompt structure / prompt examples
- official source: `https://github.com/ai-boost/awesome-prompts`,
  `https://github.com/promptslab/awesome-prompt-engineering`
- maintenance status: curated prompt resources; maintenance varies by list.
- implementation type: pattern-only source
- language/runtime: not applicable
- current Marvex fit: weak-to-moderate as style reference, not as runtime input.
- why use: helps avoid naive prompt structure when task prompts become product
  artifacts.
- why not custom: prompt structure should be reviewed, versioned, and tested.
- why not use now: prompt examples are not contract/runtime infrastructure.
- isolation boundary if adopted: templates/docs only.
- fallback if abandoned: Marvex templates and task specs.
- decision: pattern only.

### Eval / Verification

#### DeepEval

- category: eval/verification
- official source: `https://github.com/confident-ai/deepeval`,
  `https://deepeval.com/docs/introduction`
- maintenance status: active. GitHub snapshot: Python, Apache-2.0, last pushed
  2026-05-05, stars about 15.1k.
- implementation type: library with optional platform integration
- language/runtime: Python
- current Marvex fit: good later for assistant/provider replay evals.
- why use: Pytest-style LLM evals, agent/RAG/tool/MCP metrics, CI fit.
- why not custom: LLM eval metric design is nontrivial and easy to bias.
- why not use now: Marvex has no provider bridge replay corpus or real agent
  traces yet; using LLM-as-judge now would be theater.
- isolation boundary if adopted: `tests/evals` or EvalRuntime/test harness, not
  Core.
- fallback if abandoned: InspectAI or local pytest fixtures plus typed contracts.
- decision: defer; likely first eval candidate once replay fixtures exist.

#### InspectAI

- category: eval/verification
- official source: `https://github.com/UKGovernmentBEIS/inspect_ai`
- maintenance status: active. GitHub snapshot: Python, MIT, last pushed
  2026-05-05, stars about 2.0k.
- implementation type: library/framework for LLM evaluations
- language/runtime: Python
- current Marvex fit: good for model and task evals later.
- why use: government-backed evaluation framework with explicit tasks/scorers.
- why not custom: custom eval runners are brittle and hard to compare.
- why not use now: heavier than needed for current deterministic contract tests.
- isolation boundary if adopted: evaluation harness only.
- fallback if abandoned: DeepEval or pytest fixtures.
- decision: defer.

### Observability / Tracing / Prompt Ops

#### Langfuse

- category: observability/tracing, evals, prompt management
- official source: `https://github.com/langfuse/langfuse`, `https://langfuse.com/`
- maintenance status: very active. GitHub snapshot: TypeScript, license requires
  review because repo reports no single SPDX; site says MIT/open source with
  platform features, last pushed 2026-05-05, stars about 26.6k.
- implementation type: platform/app/SaaS/self-host plus SDKs
- language/runtime: TypeScript server, SDKs
- current Marvex fit: promising later for traces/evals/prompt management.
- why use: mature all-in-one LLM observability, prompts, datasets, evals.
- why not custom: tracing/eval dashboards are expensive to build well.
- why not use now: platform dependency before Marvex emits trace events; prompt
  management could pull prompts out of repo governance too early.
- isolation boundary if adopted: Telemetry/EventRuntime exporter and optional
  prompt registry adapter.
- fallback if abandoned: Phoenix, Opik, OpenTelemetry files.
- decision: defer.

#### Phoenix

- category: observability/tracing, evals, prompt management
- official source: `https://github.com/Arize-ai/phoenix`,
  `https://arize.com/docs/phoenix`
- maintenance status: very active. GitHub snapshot: Python, license review
  needed; official docs/license state Elastic License 2.0, last pushed
  2026-05-05, stars about 9.5k.
- implementation type: platform/app/SaaS/self-host plus SDKs
- language/runtime: Python with OpenTelemetry/OpenInference
- current Marvex fit: good later for trace/eval/prompt iteration.
- why use: strong OpenTelemetry fit, prompt playground, datasets, experiments.
- why not custom: observability needs standards and replay tooling.
- why not use now: too much platform for deterministic local skeleton.
- isolation boundary if adopted: Telemetry/EventRuntime exporter.
- fallback if abandoned: Langfuse, Opik, raw OpenTelemetry.
- decision: defer.

#### Opik

- category: observability/tracing, evals, prompt optimization
- official source: `https://github.com/comet-ml/opik`,
  `https://www.comet.com/docs/opik/`
- maintenance status: very active. GitHub snapshot: Python, Apache-2.0, last
  pushed 2026-05-05, stars about 19.2k.
- implementation type: platform/app/SaaS/self-host plus SDKs
- language/runtime: Python
- current Marvex fit: plausible later for eval/observability.
- why use: integrated logging, evals, dashboards, prompt/agent optimization.
- why not custom: production eval dashboards and trace storage are not Marvex
  differentiators.
- why not use now: optimization/prompt management before traces would create
  tool-driven sprawl.
- isolation boundary if adopted: Telemetry/EventRuntime and EvalRuntime adapter.
- fallback if abandoned: Langfuse/Phoenix/DeepEval.
- decision: defer.

### MCP / Context Servers

#### awesome-mcp-servers and official MCP servers

- category: MCP/context servers
- official source: `https://github.com/punkpeye/awesome-mcp-servers`,
  `https://github.com/modelcontextprotocol/servers`
- maintenance status: active ecosystem; official servers GitHub snapshot:
  TypeScript, last pushed 2026-04-17, large community footprint.
- implementation type: curated source plus server collection
- language/runtime: mixed, often TypeScript/Python
- current Marvex fit: future ToolRuntime/DesktopAgent research source only.
- why use: avoids custom protocol/server discovery once MCP work is approved.
- why not custom: custom MCP protocol/server code would duplicate a moving
  ecosystem.
- why not use now: tools/MCP are forbidden in current assistant_runtime phase.
- isolation boundary if adopted: ToolRuntime/MCP adapter behind policy gates.
- fallback if abandoned: official MCP SDK or native explicit tool adapters.
- decision: defer as source; do not adopt dependency.

### Desktop / Screen / Audio Context Tools

#### screenpipe

- category: desktop/screen/audio context
- official source: `https://github.com/screenpipe/screenpipe`,
  `https://screenpi.pe/`
- maintenance status: active. GitHub snapshot: Rust, license needs manual review
  because GitHub API reports no single SPDX; repo page states MIT, last pushed
  2026-05-05, stars about 18.5k.
- implementation type: app/local service/SDK/MCP ecosystem
- language/runtime: Rust plus app/service stack
- current Marvex fit: future DesktopAgent research only.
- why use: mature local-first screen/audio capture and search could avoid
  building desktop recall infrastructure from scratch.
- why not custom: screen/audio capture, OCR, retention, and privacy are high-risk
  infrastructure.
- why not use now: forbidden by current scope; severe privacy, consent,
  retention, and Windows integration questions.
- isolation boundary if adopted: DesktopAgent context adapter with explicit
  local-only policy, consent, retention, redaction, and disable switch.
- fallback if abandoned: OS accessibility/OCR APIs behind DesktopAgent adapter.
- decision: defer; security/privacy review required before any adoption.

### Agent Frameworks

#### OpenAI Agents SDK

- category: agent framework / harness / tracing
- official source: `https://github.com/openai/openai-agents-python`,
  `https://platform.openai.com/docs/guides/agents-sdk/`
- maintenance status: very active. GitHub snapshot: Python, MIT, last pushed
  2026-05-05, stars about 25.9k.
- implementation type: framework/library
- language/runtime: Python
- current Marvex fit: useful reference; risky as runtime dependency now.
- why use: mature agent primitives, handoffs, tools, guardrails, tracing.
- why not custom: if Marvex later needs full multi-agent orchestration, SDKs may
  avoid bespoke agent-loop bugs.
- why not use now: it would own agents/tools/handoffs/tracing before Marvex has
  approved those runtime boundaries.
- isolation boundary if adopted: isolated future Provider/Agent worker adapter,
  never Core/AssistantTurnRuntime ownership.
- fallback if abandoned: thin Marvex contracts plus provider SDK adapters.
- decision: defer; pattern/reference only now.

#### Pydantic AI

- category: agent framework / structured outputs / harness
- official source: `https://github.com/pydantic/pydantic-ai`,
  `https://pydantic.dev/docs/ai/`
- maintenance status: very active. GitHub snapshot: Python, MIT, last pushed
  2026-05-05, stars about 16.9k.
- implementation type: framework/library
- language/runtime: Python
- current Marvex fit: strong conceptual fit with typed Python, poor timing.
- why use: typed agents, test models, structured outputs, model-agnostic
  providers, and official harness capability split.
- why not custom: typed agent/harness features are difficult to maintain
  correctly from scratch.
- why not use now: central agent loop/harness would collide with Marvex-owned
  AssistantTurnRuntime and future subsystem boundaries.
- isolation boundary if adopted: optional isolated experiment/adapter around a
  single runtime slice after approval.
- fallback if abandoned: Pydantic contracts plus provider-native structured
  outputs.
- decision: defer; best candidate to re-evaluate before a real agent-loop slice.

#### LangGraph

- category: agent framework / graph orchestration / context state
- official source: `https://github.com/langchain-ai/langgraph`,
  `https://docs.langchain.com/oss/python/langgraph/`
- maintenance status: very active. GitHub snapshot: Python, MIT, last pushed
  2026-05-05, stars about 31.2k.
- implementation type: framework/library
- language/runtime: Python and TypeScript ecosystem
- current Marvex fit: poor for current phase; possible future orchestration
  reference.
- why use: durable graph execution and stateful workflows are mature problems.
- why not custom: long-running graph orchestration is hard.
- why not use now: graph/state/memory/checkpointing would take over architecture
  before Marvex has approved process/session/runtime ownership.
- isolation boundary if adopted: separate orchestration adapter/worker, not Core.
- fallback if abandoned: explicit Marvex state machine or another workflow
  engine after RFC.
- decision: reject now; defer only as future orchestration reference.

#### smolagents

- category: agent framework
- official source: `https://github.com/huggingface/smolagents`,
  `https://huggingface.co/docs/smolagents/`
- maintenance status: active. GitHub snapshot: Python, Apache-2.0, last pushed
  2026-04-24, stars about 27.1k.
- implementation type: framework/library
- language/runtime: Python
- current Marvex fit: poor.
- why use: small code-agent framework with sandbox integrations and broad model
  support.
- why not custom: code-agent execution and sandboxing are hard.
- why not use now: code execution, tools, memory, MCP, and agent loop are
  explicitly out of scope and high risk.
- isolation boundary if adopted: separate experimental worker only.
- fallback if abandoned: no code-agent runtime until explicitly approved.
- decision: reject for current architecture phase.

#### LlamaIndex

- category: agent framework / context/RAG
- official source: `https://github.com/run-llama/llama_index`,
  `https://docs.llamaindex.ai/`
- maintenance status: very active. GitHub snapshot: Python, MIT, last pushed
  2026-05-04, stars about 49.1k.
- implementation type: framework/library/platform ecosystem
- language/runtime: Python with TS ecosystem
- current Marvex fit: future RAG/context adapter candidate, not assistant
  runtime.
- why use: broad data connectors, indexes, RAG workflows, document agents.
- why not custom: data ingestion/RAG connector ecosystems are large.
- why not use now: memory/context/RAG is not approved and would bloat next
  provider bridge work.
- isolation boundary if adopted: MemoryRuntime/ContextRuntime adapter.
- fallback if abandoned: smaller retrieval libraries or custom SQLite/FTS only
  after library review.
- decision: defer.

#### Haystack

- category: agent framework / context/RAG / pipelines
- official source: `https://github.com/deepset-ai/haystack`,
  `https://docs.haystack.deepset.ai/docs/intro`
- maintenance status: very active. GitHub snapshot: Apache-2.0, last pushed
  2026-05-05, stars about 25.1k.
- implementation type: framework/library
- language/runtime: Python
- current Marvex fit: future RAG/pipeline candidate, not current assistant
  runtime.
- why use: explicit pipeline components for retrieval, routing, memory,
  generation.
- why not custom: RAG and pipeline orchestration are mature library territory.
- why not use now: would introduce a pipeline framework before Marvex has
  MemoryRuntime/ContextRuntime boundaries.
- isolation boundary if adopted: ContextRuntime/MemoryRuntime adapter.
- fallback if abandoned: LlamaIndex or narrower retrieval/search libraries.
- decision: defer.

## 4. Immediate Marvex Impact

Should Task 067 InputEvent binding still proceed as custom code?

Yes, if it remains thin contract glue. It should bind existing approved
`InputEvent` / `AssistantTurnInput` data without prompt rendering, provider
execution, tools, memory, or hidden metadata. None of the reviewed tools should
own that slice.

Should prompts for Codex agents be managed by a prompt/config tool?

No for now. Keep prompt/task structure in repo files: `AGENTS.md`, task specs,
docs, validation gates, and tests. LynxPrompt/flompt are pattern references,
not required tooling.

Should Marvex add a prompt/harness dependency now?

No. Harness lessons should become explicit context packs, docs, and validation
gates, not a dependency.

Should Marvex add an eval/observability dependency now?

No. DeepEval, InspectAI, Langfuse, Phoenix, and Opik are serious later
candidates, but current deterministic assistant_runtime has no LLM outputs,
trace corpus, or replay fixtures that justify them.

Should screenpipe/context tools affect future Desktop Agent planning?

Yes as a warning and research source only. Desktop Agent planning must include
privacy, consent, retention, redaction, local storage, Windows fit, and kill
switches before any screen/audio/context tool is considered.

Should any future task be blocked until a candidate is adopted?

No. Future tasks should be blocked only if they attempt prompt management,
structured provider output, eval/observability, MCP, memory, desktop context, or
agent orchestration without a focused adapter/library decision.

## 5. Recommendation for Next 5 Tasks

1. Task 068: continue assistant_runtime custom thin code for InputEvent binding.
   Decision: continue custom thin code. Keep it contract-only and no-provider.
2. Task 069: write a provider structured-output adapter decision before any
   provider bridge asks a model for typed data. Decision: write adapter boundary
   first. Re-evaluate OpenAI Structured Outputs, Instructor, and Outlines.
3. Task 070: add assistant/provider replay fixture shape before adopting evals.
   Decision: defer eval tools; create deterministic local fixtures first.
4. Task 071: observability export boundary planning. Decision: write adapter
   boundary first. Re-evaluate Langfuse, Phoenix, Opik, and raw OpenTelemetry.
5. Task 072: Desktop Agent context threat model and library review. Decision:
   defer implementation. Re-evaluate screenpipe and OS-native APIs only after
   privacy/retention rules are approved.

## 6. Risks

framework takeover:

- OpenAI Agents SDK, Pydantic AI, LangGraph, smolagents, LlamaIndex, and
  Haystack can all become de facto runtime owners. That conflicts with Marvex
  Assistant OS boundaries unless isolated behind explicit workers/adapters.

dependency bloat:

- Prompt/harness/context tooling tends to pull SDKs, servers, dashboards,
  database services, or browser/desktop stacks. Do not add any of these until a
  task has a concrete runtime boundary and rollback plan.

building from scratch unnecessarily:

- Structured output parsing, eval metrics, tracing, RAG connectors, MCP
  protocol handling, and screen/audio capture should not be custom-built once
  those areas become real implementation tasks.

over-planning:

- Adopting a framework before there is a provider bridge or replay corpus would
  produce architecture theater. Keep near-term code boring.

prompt config sprawl:

- Prompt tools can scatter source of truth across SaaS, CLI stores, browser
  extensions, and generated files. Marvex should keep prompt/task state in
  versioned repo artifacts until a prompt registry adapter is approved.

eval/tooling overkill:

- LLM-as-judge/eval dashboards are useful only after Marvex has nontrivial LLM
  behavior to evaluate. Current assistant_runtime tests should stay normal
  pytest contract tests.

privacy risk for screen/audio context tools:

- screenpipe-like tooling is powerful but high risk: always-on capture, OCR,
  audio transcription, local databases, and possible MCP exposure require a
  dedicated privacy/security design.

Windows fit:

- Marvex runs in a Windows PowerShell environment. Python libraries fit best.
  TypeScript apps, Node CLIs, Rust desktop services, Docker-heavy platforms, and
  WSL/GPU assumptions need explicit Windows validation before adoption.
