# Library Decision: LiteLLM

library name: LiteLLM

official source: https://docs.litellm.ai/ and https://github.com/BerriAI/litellm

maintenance status: Active as of April 26, 2026. PyPI latest version observed as 1.83.14. Marvex keeps 1.83.13 pinned for this milestone because it is already validated by the Provider Foundation test suite and remains close to current release state.

why use it: Marvex needs one maintained Python SDK abstraction for OpenRouter and future cloud providers without embedding provider-specific SDKs or request formats in Core.

why not custom code: Custom HTTP clients would duplicate provider authentication, request shape, response parsing, and error handling across providers, increasing security and maintenance risk.

fallback if abandoned: Keep LiteLLM isolated behind the provider adapter boundary, replace it with another maintained provider abstraction, or add separate native adapters through approved task specs.

pyproject dependency: litellm

declared dependency: litellm==1.83.13

verified date: 2026-04-26

verified by: Codex

scope: `packages/adapters/providers/litellm/` only. Core and ports must not mention LiteLLM.

exact dependency pin: `litellm==1.83.13`

pin decision: Keep `litellm==1.83.13` unchanged in Task 018. Upgrading to a newer LiteLLM release is a separate dependency-upgrade task requiring updated dependency research, adapter tests, CLI tests, provider runtime boundary tests, and fake smoke validation.

risks: LiteLLM PyPI versions 1.82.7 and 1.82.8 were reported compromised in March 2026 and must not be used. Any future LiteLLM upgrade requires a separate dependency-upgrade task with tests and an updated decision record. LiteLLM chat completions do not guarantee support for Marvex `previous_response_id`, so this adapter records it only as raw metadata. LM Studio stateful Responses should remain a separate native adapter.
