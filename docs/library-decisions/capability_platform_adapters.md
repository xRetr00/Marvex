# Library Decision: Capability Platform Adapter Ecosystems

library name: OpenAI API tools / OpenAI Agents SDK / LiteLLM MCP gateway concepts / LM Studio tool calling and MCP host / Claude Skills / LangGraph-LangChain / LlamaIndex / awesome-harness-engineering / awesome-context-ai

official source: OpenAI platform and Agents SDK docs; LiteLLM docs; LM Studio docs; Anthropic Claude Skills docs; LangGraph/LangChain docs; LlamaIndex docs; official GitHub awesome-harness/context sources.

maintenance status: Current-source review performed on 2026-05-17 for this phase. Existing Marvex pins remain `openai==2.24.0`, `litellm==1.83.13`, and `pydantic>=2,<3`.

why use it: These ecosystems define current provider tool-call, MCP, skill, context, connector, and harness vocabulary that Marvex should not invent from scratch.

why not custom code: Marvex should not build custom external protocols or provider-specific tool gateways. CapabilityRuntime should own policy and envelope models while maintained SDKs own protocol mechanics once real protocol execution is approved.

fallback if abandoned: Keep all ecosystem-specific behavior behind adapter seams. Disable the backend, replace the SDK, or model only safe projections until a maintained option is approved.

pyproject dependency: no new dependency in this phase.

declared dependency: existing OpenAI and LiteLLM dependencies remain declared for existing provider adapters only; no MCP, Agents SDK, LangGraph, LlamaIndex, or skills dependency is declared.

adopt / defer / reference decisions:

- OpenAI API tools: adapter seam now using existing OpenAI dependency posture; provider tool calls are proposals only.
- OpenAI Agents SDK: backend disabled/deferred; compatibility boundary only because the SDK must not own Marvex policy or runtime orchestration.
- LiteLLM tool/MCP gateway concepts: adapter seam now; Marvex policy remains authoritative and existing LiteLLM dependency is not widened beyond approved provider adapter posture.
- LM Studio tool calling/MCP host: adapter seam now; LM Studio must not become Marvex tool host owner.
- Claude Skills: reference/model concept now through SkillManifest; no arbitrary skill execution or script execution.
- LangGraph/LangChain and LlamaIndex: reference-only planning/context patterns; no framework takeover.
- awesome-harness-engineering and awesome-context-ai: reference-only vocabulary for harness, context delivery, compaction, permissions, verification, and safety.

scope: CapabilityRuntime and adapter seams only. This decision does not approve real tool execution, arbitrary MCP server connection, account connectors, browser/computer use, shell tools, filesystem edit tools, UI/voice/desktop/proactive behavior, generic provider routing, or autonomous agent loops.

Official MCP Registry and official MCP Python/TypeScript SDKs were included in the 2026-05-17 source review. Registry content is discovery metadata only and does not authorize installing or connecting arbitrary servers.
