# 08 — Live browser & desktop computer-use automation

**Theme:** Agentic actuation · **Size:** L · **Status:** not started

## Problem

Asking Marvex to "run browser on YouTube" or to control the desktop reports
success ("Action executed after approval…" / "Computer-use request completed
through the approval-gated ToolWorker boundary.") **without performing any real
browser navigation or desktop action.** The user sees a confident success
message but nothing happens on screen.

## Root cause (as of this fix)

Two layers were broken:

1. **Approval-resume never reached the browser capability.** Every approved turn
   funnels through `_run_approval_path` (top-level resume interception in
   `services/core/main.py::submit_turn`). That method only special-cased
   `file.write`; browser/computer-use approvals fell into a generic branch that
   executed `fake.status` and returned the stub text *"Action executed after
   approval…"*. The `browser_use.task` execution code in the
   `browser_computer_use` route was effectively **dead** (the resume short-circuit
   ran first).

2. **The capability itself is a readiness projection, not real automation.**
   `services/tool_worker/controller.py::_browser_use_result` only checks that the
   `browser_use` package imports and a task string is present, then returns
   `status="succeeded"`. It never launches Playwright or drives a page.
   `_computer_use_result` likewise only collects a UIA projection
   (`ufo_external_process` / `omniparser_external_process` are placeholders).

## What this fix changed (honesty, not full function)

- `_run_approval_path` now detects browser/desktop requests on approve and routes
  them to the **real** capability id (`browser_use.task` / `computer_use.action`)
  instead of `fake.status`.
- The user-visible text is now **honest** via
  `_browser_or_computer_use_final_text`: it states the backend is detected but
  live control is not wired yet and **no on-screen action was performed**, rather
  than falsely claiming success.

## Remaining work (this item)

Wire genuine actuation behind the existing approval boundary:

- **Browser:** drive `browser_use.Agent` (browser-use 0.11.x) with Playwright
  (1.60.x, both already installed). The Agent needs an LLM — reuse the user's
  configured provider (LM Studio / LiteLLM via an OpenAI-compatible base URL).
  Run inside the tool-worker process with its own asyncio loop; stream
  step/screenshot telemetry through ToolWorker result envelopes and approved
  owner-mode raw automation artifacts. Return a real per-step result, not a
  readiness flag.
- **Desktop computer-use:** integrate Windows-MCP and local UIA fallback so
  `computer_use.action` performs gated clicks/typing. In personal owner mode,
  arbitrary desktop control and credential entry are allowed after approval; delete,
  shutdown, restart, registry, PowerShell, and comparable destructive actions still
  require explicit per-action approval.
- **Safety:** keep both HIGH-risk + approval-required; add per-action approval for
  destructive steps; cap step count; allowlist domains/apps via control plane.
- **Tests:** fake Playwright/Agent doubles to assert the resume path executes the
  real capability and that telemetry is redacted; an opt-in live smoke test.

## Acceptance

- Approving "open youtube in the browser" actually opens the page and reports the
  steps taken (or a precise, honest failure) — never a generic success stub.
- Raw DOM, screenshot, screen, action, and keystroke payloads may be persisted only
  under the approved owner-mode `RawAutomationCapture` contract.
