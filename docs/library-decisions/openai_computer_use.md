# Library Decision: OpenAI Computer Use

library name: OpenAI Responses API computer use

official source: https://platform.openai.com/docs/guides/tools-computer-use and https://platform.openai.com/docs/api-reference/responses

maintenance status: Active OpenAI platform feature as of May 18, 2026, based on official documentation lookup. It is accessed through the existing OpenAI SDK dependency rather than a separate package.

why use it: OpenAI computer use is a maintained backend for model-proposed computer/browser actions and should be represented as one computer-use adapter option rather than custom-building a model-screen action harness.

why not custom code: Marvex should not invent a competing computer-use action protocol for the OpenAI Responses API. However, Marvex must own the adapter boundary, approval policy, untrusted screen-content rule, safe result envelope, and isolated environment policy.

fallback if abandoned: Keep `packages.adapters.capabilities.openai_computer_use` and `packages.adapters.capabilities.computer_use` as proposal-only seams. Marvex can use Playwright directly, another computer-use backend, or disable computer use without changing Core or CapabilityRuntime.

pyproject dependency: openai

declared dependency: openai==2.24.0

verified date: 2026-05-18

verified by: Codex

scope: Adapter foundation only. Computer-use actions are represented as proposals/result envelopes with approval requirements. No real OpenAI computer-use execution is wired into runtime turn flow.

architecture fit: Good as one adapter backend. It must not be the only Marvex computer-use path and cannot own policy, loop guards, approvals, telemetry persistence, or assistant planning.

adopt / defer / reject decision: Adopt the compatibility seam using the existing OpenAI SDK dependency. Defer real Responses API computer-use execution to a future explicit provider/runtime integration task.

risks: Computer use can click, type, submit sensitive data, interact with untrusted screens, and leak screenshots. Mitigations in this phase are approval-required action proposals, untrusted screen/page content policy, isolated environment requirement, and no raw screen persistence by default.

comparison to custom routing: OpenAI Computer Use is not Marvex's computer-use brain. It is one adapter backend that must pass through CapabilityRuntime proposals and approved execution requests.
