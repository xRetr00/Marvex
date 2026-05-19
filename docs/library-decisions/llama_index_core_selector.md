# Library Decision: LlamaIndex Core Selector

library name: LlamaIndex Core

official source: https://docs.llamaindex.ai/ and https://github.com/run-llama/llama_index

maintenance status: Active as of May 19, 2026. uv resolved `llama-index-core==0.14.22` in the current Python 3.12.0 environment without downgrading OpenAI, MCP, LiteLLM, Semantic Router, Authlib, Playwright, or browser-use.

why use it: Marvex needs a maintained selector/router proof for intent refinement without handing runtime policy to an agent framework. `llama-index-core` provides the narrowest available LlamaIndex package for selector objects used in `packages.intent_runtime.hybrid`.

why not custom code: A hand-built selector object would only hide the same routing decision in local code and would not prove compatibility with maintained router/selector infrastructure. Using `llama-index-core` lets Marvex test a real library boundary while keeping final decisions internal.

fallback if abandoned: Keep the selector use behind `HybridIntentRuntime` details and replace it with another maintained selector package or a Marvex-owned deterministic selector if LlamaIndex becomes unsafe or unmaintained.

pyproject dependency: llama-index-core

declared dependency: llama-index-core>=0.14.22

verified date: 2026-05-19

verified by: Codex

scope: Adopted narrowly for selector proof only. `packages.intent_runtime.hybrid` imports `llama_index.core.selectors.SingleSelection` and records safe selector details; it does not let LlamaIndex own Core, RuntimeComposition, MemoryRuntime, prompt assembly, planning loops, tool dispatch, or agent execution.

architecture fit: Acceptable for router/selector proof. It is not adopted as a memory system, agent framework, index owner, retriever, vector database, or prompt harness.

adopt / defer / reject decision: Adopt narrowly. Full `llama-index` remains too broad for this goal, but `llama-index-core` is accepted because uv resolved it and tests prove real selector usage without runtime ownership transfer.

risks: The package has a broad dependency footprint compared with a tiny selector. The boundary gate must keep usage narrow and prevent it from becoming MemoryRuntime, ContextRuntime, or planning ownership.
