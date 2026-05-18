# Library Decision: OpenAI Agents SDK Tools

library name: openai-agents

official source: https://openai.github.io/openai-agents-python/ and https://pypi.org/project/openai-agents/

maintenance status: Active as of May 18, 2026. Dependency audit resolved `openai-agents==0.17.2` with `openai==2.37.0`, `litellm==1.84.0`, `mcp==1.27.1`, and `semantic-router==0.1.14`.

why use it: The OpenAI Agents SDK is relevant for future compatibility with OpenAI tool definitions and agent/tool ecosystems. Marvex should understand that shape before inventing incompatible tool wrappers.

why not custom code: Marvex should not custom-build an OpenAI Agents SDK clone. The SDK is adopted only for compatibility probing and tool-shape awareness; Marvex does not adopt the SDK runner, handoffs, tracing, hosted tools, guardrails, or agent loop as runtime authority.

fallback if abandoned: Keep `packages.adapters.capabilities.openai_agents` as a compatibility seam using Marvex-owned proposal models. If the SDK is abandoned or becomes runtime-invasive, remove the dependency and keep proposal mapping behind CapabilityRuntime.

pyproject dependency: openai-agents

declared dependency: openai-agents==0.17.2

verified date: 2026-05-18

verified by: Codex

scope: Compatibility proposal seam only. `OpenAIAgentsToolCompatibilityProposal.from_installed_sdk_tool` proves the installed SDK package can be detected and mapped into Marvex-owned proposal models. No OpenAI Agents SDK execution, runner, handoff, tracing ownership, hosted tool execution, or agent loop is adopted.

architecture fit: Narrow adoption. The package fits only as an adapter compatibility layer after upgrading the OpenAI SDK pin through a resolver-tested path. CapabilityRuntime remains authoritative for policy, approvals, and execution requests.

adopt / defer / reject decision: Adopt narrowly. `openai==2.24.0` could not satisfy `openai-agents==0.17.2`; resolver dry-run showed `litellm==1.84.0` accepts `openai>=2.20.0`, allowing `openai==2.37.0` and OpenAI Agents SDK compatibility without breaking `mcp==1.27.1`.

risks: Direct SDK adoption could bypass Marvex's CapabilityRuntime permission/approval flow, introduce agent loop semantics, and force dependency churn in provider adapters. The current seam represents tools as proposals only.

comparison to custom routing: OpenAI Agents SDK tools are not Marvex's planner or policy engine. They are a compatibility shape that must map into CapabilityRuntime proposals before any future execution.
