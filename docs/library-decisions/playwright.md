# Library Decision: Playwright Python

library name: playwright

official source: https://playwright.dev/python/ and https://pypi.org/project/playwright/

maintenance status: Active as of May 18, 2026. PyPI latest version observed locally with `python -m pip index versions playwright` as `playwright==1.60.0`.

why use it: Browser automation is a mature SDK domain and Marvex must not custom-build browser control, page/session abstractions, click/type/read/screenshot primitives, or browser lifecycle machinery from scratch. Playwright is the approved SDK-backed browser adapter dependency for this foundation.

why not custom code: Custom browser automation would recreate a maintained browser driver stack, increase security and compatibility risk, and make isolated-session policy harder to enforce. Marvex should own policy and envelopes, not browser protocol mechanics.

fallback if abandoned: Keep Playwright behind `packages.adapters.capabilities.browser` so Marvex can replace it with another browser backend or disable browser execution without changing Core, AssistantRuntime, ProviderRuntime, Local API, or CapabilityRuntime policy authority.

pyproject dependency: playwright

declared dependency: playwright==1.60.0

verified date: 2026-05-18

verified by: Codex

scope: Adopted only inside the browser adapter foundation. It may provide SDK type boundaries for isolated browser/session/page mechanics, but all browser actions remain CapabilityRuntime proposals or approved execution requests. Raw DOM, page text, screenshots, credentials, prompts, transcripts, and payloads are not persisted by default.

architecture fit: Good. Browser protocol mechanics belong behind an adapter. CapabilityRuntime remains authoritative for permission, approval, execution mode, loop guards, context delivery, result envelopes, and safe summaries.

adopt / defer / reject decision: Adopt narrowly for browser automation adapter mechanics. Defer real product browser sessions, credentialed browsing, form submission, checkout/payment, CAPTCHA/anti-bot handling, stealth/proxy scraping, UI integration, and arbitrary desktop control.

risks: Browser automation can perform real-world actions, expose credentials, submit forms, persist screenshots/DOM, and violate site rules. Mitigations in this phase are isolated-session policy, risk/side-effect classification, approval-required browser actions, no sensitive form submission, no CAPTCHA/anti-bot bypass, and safe result envelopes only.

comparison to custom routing: Playwright is not an assistant planner, browser brain, provider router, or policy engine. It is a browser SDK behind a Marvex adapter and cannot bypass CapabilityRuntime policy.
