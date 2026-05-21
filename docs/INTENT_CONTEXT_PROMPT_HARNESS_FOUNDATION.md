# Intent, Context, and Prompt Harness Foundation

Status: complete foundation boundary.

This foundation gives Marvex a safe intent, context, and prompt harness layer without making Core, ProviderRuntime, Local API, RuntimeComposition, Telemetry, MemoryRuntime, or AssistantRuntime own prompt assembly or routing policy.

## Ownership

IntentRuntime exists in `packages.intent_runtime` and owns safe intent classification models, route decisions, confidence buckets, ambiguity signals, risky-intent signals, clarification decisions, and safe intent projections.

ContextRuntime/PromptHarness exists in `packages.context_runtime` and `packages.prompt_harness_runtime`. ContextRuntime owns context source refs, context candidates, eligibility decisions, context packs, budgets, delivery policy, exclusion reasons, and safe context projections. PromptHarnessRuntime owns bounded prompt sections, prompt harness plans, prompt assembly requests/results, budget reports, compaction/offload/clearing decisions, planning readiness, validation results, and telemetry-safe harness summaries.

CapabilityRuntime remains authoritative for capability permissions, eligibility, dispatch, approvals, execution requests, result envelopes, and loop guards. The harness can select safe capability schema projections by intent/context; it cannot approve execution or bypass policy.

## Adapter Decisions

Semantic Router has a Marvex adapter seam with disabled/proof backend. Guardrails-style validation has a safe projection-only adapter seam. LlamaIndex, LangChain/LangGraph, OpenAI Agents SDK, Anthropic context engineering patterns, and awesome harness/context resources are represented by decision records and disabled/reference seams until a later task explicitly adopts runtime dependencies.

## Safety Rules

The harness assembles from safe projections only. It records section source refs, token estimates, include/exclude reasons, and budget status. It blocks raw transcript dumps, raw provider payloads, raw tool outputs, secrets, environment variables, all-tools dumping, all-skills dumping, and all-memory dumping by default.

Browser and computer-use schemas are excluded by default unless browser/computer intent and later CapabilityRuntime policy allow them. Planning and verification readiness are model-level only; no autonomous planner loop, recursive agent loop, or automatic retry loop is started.

## Integration Proof

Tests prove input summary to intent classification, semantic route adapter to Marvex route decision, context candidate filtering by intent/source/budget, bounded prompt harness assembly, compaction/offload decisions, validation adapter seams, and telemetry-safe summaries. Boundary gates keep ownership from leaking into Core, Local API, RuntimeComposition, ProviderRuntime, Telemetry, MemoryRuntime, SessionRuntime, or Control Plane API.

## Live Fidelity Update

Core worker-backed turns now use the adaptive harness path for live cognition
assembly. The user channel carries the actual bounded user question plus
route-relevant context sections. The provider `instructions` channel carries
persistent system policy and approval policy sections. Recalled memory sections
contain bounded memory text and provenance refs; they no longer use tombstone
strings such as a generic approved-memory notice.

The live path calls `adaptive_context_policy_for_route` and
`assemble_adaptive_prompt_harness` instead of hardcoded tiny budgets. It also
invokes compaction, tool-result-clearing, and memory-offload decision models at
context assembly boundaries so pressure is handled by safe summaries or refs,
not by dumping all context or mutating a subtask midway through execution.
