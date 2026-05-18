# Library Decision: OpenAI Agents SDK Tools

library name: openai-agents

official source: https://openai.github.io/openai-agents-python/ and https://pypi.org/project/openai-agents/

maintenance status: Active as of May 18, 2026. PyPI latest version observed locally with `python -m pip index versions openai-agents` as `openai-agents==0.17.2`.

why use it: The OpenAI Agents SDK is relevant for future compatibility with OpenAI tool definitions and agent/tool ecosystems. Marvex should understand that shape before inventing incompatible tool wrappers.

why not custom code: Marvex should not custom-build an OpenAI Agents SDK clone. However, adopting the package now would conflict with the current pinned `openai==2.24.0` dependency because `openai-agents==0.17.2` requires `openai>=2.26.0`, and it also imports agent runner behavior beyond this foundation.

fallback if abandoned: Keep `packages.adapters.capabilities.openai_agents` as a compatibility seam using Marvex-owned proposal models. Future work can adopt `openai-agents` behind this seam after an explicit OpenAI SDK upgrade decision.

pyproject dependency: none

declared dependency: not declared

verified date: 2026-05-18

verified by: Codex

scope: Compatibility proposal seam only. No OpenAI Agents SDK execution, runner, handoff, or tracing ownership is adopted.

architecture fit: Defer dependency adoption. The concept fits as an adapter compatibility layer, but the package is not safe to add until Marvex intentionally upgrades its OpenAI SDK pin and reviews agent-runner ownership.

adopt / defer / reject decision: Defer package adoption. Implement the adapter compatibility seam now.

risks: Direct SDK adoption could bypass Marvex's CapabilityRuntime permission/approval flow, introduce agent loop semantics, and force dependency churn in provider adapters. The current seam represents tools as proposals only.

comparison to custom routing: OpenAI Agents SDK tools are not Marvex's planner or policy engine. They are a compatibility shape that must map into CapabilityRuntime proposals before any future execution.
