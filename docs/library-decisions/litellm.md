# Library Decision: LiteLLM

library name: LiteLLM

official source: https://docs.litellm.ai/ and https://github.com/BerriAI/litellm

maintenance status: Active as of April 24, 2026. PyPI latest version verified as 1.83.13, and the GitHub project shows frequent releases and broad provider support.

why use it: Marvex needs one maintained Python SDK abstraction for OpenRouter and future cloud providers without embedding provider-specific SDKs or request formats in Core.

why not custom code: Custom HTTP clients would duplicate provider authentication, request shape, response parsing, and error handling across providers, increasing security and maintenance risk.

fallback if abandoned: Keep LiteLLM isolated behind the provider adapter boundary, replace it with another maintained provider abstraction, or add separate native adapters through approved task specs.

verified date: 2026-04-24

verified by: Codex

scope: `packages/adapters/providers/litellm/` only. Core and ports must not mention LiteLLM.

exact dependency pin: `litellm==1.83.13`

risks: LiteLLM PyPI versions 1.82.7 and 1.82.8 were reported compromised in March 2026 and must not be used. Any future LiteLLM upgrade requires a separate dependency-upgrade task with tests and an updated decision record. LiteLLM chat completions do not guarantee support for Marvex `previous_response_id`, so this adapter records it only as raw metadata. LM Studio stateful Responses should remain a separate native adapter later.
