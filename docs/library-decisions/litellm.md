# Library Decision: LiteLLM

library name: LiteLLM

official source: https://docs.litellm.ai/ and https://github.com/BerriAI/litellm

maintenance status: Active as of May 18, 2026. Marvex moved to 1.84.0 because `openai-agents==0.17.2` requires `openai>=2.26.0`, while `litellm==1.83.13` pinned `openai==2.24.0` and blocked safe OpenAI Agents SDK compatibility adoption.

why use it: Marvex needs one maintained Python SDK abstraction for OpenRouter and future cloud providers without embedding provider-specific SDKs or request formats in Core.

why not custom code: Custom HTTP clients would duplicate provider authentication, request shape, response parsing, and error handling across providers, increasing security and maintenance risk.

fallback if abandoned: Keep LiteLLM isolated behind the provider adapter boundary, replace it with another maintained provider abstraction, or add separate native adapters through approved task specs.

pyproject dependency: litellm

declared dependency: litellm==1.84.0

verified date: 2026-05-18

verified by: Codex

scope: `packages/adapters/providers/litellm/` only. Core and ports must not mention LiteLLM.

exact dependency pin: `litellm==1.84.0`

pin decision: Adopt `litellm==1.84.0` for the SDK adoption fix because resolver dry-run showed it accepts `openai>=2.20.0` and can coexist with `openai-agents==0.17.2`, `openai==2.37.0`, `mcp==1.27.1`, `playwright==1.59.0`, and `semantic-router==0.1.14`.

risks: LiteLLM PyPI versions 1.82.7 and 1.82.8 were reported compromised in March 2026 and must not be used. Any future LiteLLM upgrade requires a separate dependency-upgrade task with tests and an updated decision record. LiteLLM chat completions do not guarantee support for Marvex `previous_response_id`, so this adapter records it only as raw metadata. LM Studio stateful Responses should remain a separate native adapter.
