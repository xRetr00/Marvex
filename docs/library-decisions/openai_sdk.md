# Library Decision: OpenAI Python SDK

library name: openai

official source: https://github.com/openai/openai-python and https://pypi.org/project/openai/

maintenance status: Active as of May 18, 2026. Resolver audit selected `openai==2.37.0` to satisfy `openai-agents==0.17.2` while remaining compatible with `litellm==1.85.0`, `mcp==1.27.1`, `playwright==1.60.0`, and `semantic-router==0.1.14`.

why use it: Marvex already uses the maintained OpenAI Python SDK through provider and compatibility adapter boundaries. The SDK is required by LiteLLM and OpenAI Agents SDK compatibility work.

why not custom code: Marvex should not custom-build OpenAI HTTP clients or SDK compatibility shims when a maintained official SDK exists. Custom clients would duplicate request, response, auth, error, and streaming behavior.

fallback if abandoned: Keep OpenAI SDK usage behind provider and capability adapters. If the SDK becomes unsafe or abandoned, replace it behind those adapters without moving provider mechanics, policy, or agent-loop behavior into Core.

pyproject dependency: openai

declared dependency: openai==2.37.0

verified date: 2026-05-18

verified by: Codex

scope: Provider/compatibility SDK dependency only. OpenAI SDK objects must not own Marvex policy, routing, prompt harness, tool dispatch, memory, or agent loop.

architecture fit: Good when isolated. ProviderRuntime and capability adapters may use SDK-compatible shapes behind Marvex-owned ports and proposal models; CapabilityRuntime remains authoritative for approvals and execution.

adopt / defer / reject decision: Adopt `openai==2.37.0` as part of the safe OpenAI Agents SDK compatibility path. The previous `openai==2.24.0` pin blocked `openai-agents==0.17.2`.

risks: SDK upgrades can change provider behavior and transitive constraints. Mitigation is exact pinning, `python -m pip check`, targeted adapter tests, full pytest, and boundary gates.

comparison to custom routing: The OpenAI SDK is not a router, policy engine, prompt harness, memory runtime, or agent loop. It remains a provider/compatibility dependency behind adapters.
