# Library Decision: LM Studio Responses Adapter

library name: OpenAI Python SDK

official source: https://github.com/openai/openai-python and https://platform.openai.com/docs/api-reference/responses

maintenance status: Active as of April 26, 2026. PyPI latest version observed as 2.32.0. Marvex keeps 2.24.0 pinned because the Provider Foundation test suite is validated against that version and LiteLLM compatibility must be evaluated before any OpenAI SDK upgrade.

why use it: LM Studio exposes an OpenAI-compatible `/v1/responses` endpoint, and its documentation recommends reusing OpenAI clients by setting `base_url` to the local LM Studio server.

why not custom code: Custom HTTP code would duplicate request construction, timeout handling, SDK response parsing, and exception behavior that the official SDK already provides.

fallback if abandoned: Keep this adapter isolated behind the provider adapter boundary. If OpenAI SDK compatibility fails, write an RFC before adding any raw HTTP implementation.

pyproject dependency: openai

declared dependency: openai==2.24.0

verified date: 2026-04-26

verified by: Codex

scope: `packages/adapters/providers/lmstudio_responses/` only. Core, ports, ProviderRuntime, CLI, telemetry, and services must not mention LM Studio implementation details.

exact dependency pin: `openai==2.24.0`

compatibility decision: `openai==2.24.0` is selected to keep the dependency graph installable with `litellm==1.83.13`. The LM Studio adapter tests pass with mocked SDK usage on this SDK version. Upgrading the OpenAI SDK is deferred to a separate dependency-upgrade task that must evaluate LiteLLM compatibility.

pin decision: Keep `openai==2.24.0` unchanged in Task 018. This cleanup task documents dependency governance only and does not change dependency versions.

limitations: This adapter is for LM Studio native OpenAI-compatible Responses only. It does not implement streaming, tools, MCP, provider routing, retries, fallback chains, session storage, or manual history reconstruction.

relation to LiteLLM: LiteLLM remains the generic cloud and multi-provider adapter. This adapter exists because LM Studio Responses supports `previous_response_id` directly for local stateful continuation.
