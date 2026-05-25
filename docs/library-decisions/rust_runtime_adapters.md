# Library Decision: Rust Runtime Adapters

library name: reqwest, process-wrap

official source: https://docs.rs/reqwest/latest/reqwest/, https://docs.rs/process-wrap/latest/process_wrap/

maintenance status: Active as of May 25, 2026. `reqwest` is the existing Rust HTTP client in the shell runtime. `process-wrap` 9.1.0 is current in docs.rs/crates.io metadata and provides std/Tokio child-process wrapping.

why use it: The shell runtime needs a maintained HTTP client for local loopback JSON calls and a maintained child-process wrapper for safer process cleanup. `reqwest` stays behind the shell `LoopbackHttpClient` adapter. `process-wrap` stays behind the supervisor spawn helper and provides Windows job-object wrapping without making Tauri own worker IPC.

why not custom code: Custom HTTP behavior would duplicate `reqwest` request/timeout/TLS mechanics. Custom Windows job-object process handling would duplicate low-level process lifecycle behavior better kept in a focused crate.

fallback if abandoned: Keep both dependencies isolated behind `apps/shell/src-tauri/src/http.rs` and the supervisor spawn helper. Replace `reqwest` with another Rust HTTP client or replace `process-wrap` with direct Windows API handling without changing Core, Local API, Control Plane, or worker contracts.

pyproject dependency: none

declared dependency: `apps/shell/src-tauri/Cargo.toml`

verified date: 2026-05-25

verified by: Codex

scope: Rust/Tauri shell runtime only. Core, Local API, ProviderWorker, IntentWorker, and ToolWorker must not import or depend on these crates.

architecture fit: Good. `reqwest` handles shell-to-loopback HTTP only. `process-wrap` handles shell-supervised backend/voice child process cleanup only. Provider, intent, and tool worker IPC is backend-owned Python stdio JSONL in this slice.

adopt / defer / reject decision: Adopt `reqwest` and `process-wrap`. Reject `tauri-plugin-http` for this privileged shell command path because it broadens browser-side HTTP capability and does not improve Rust command proxy safety. Defer `interprocess`/named-pipe worker IPC because this slice intentionally preserves existing stdio JSONL worker contracts.

risks: Process wrapping has Windows-specific behavior and can conflict with direct creation flag handling. Mitigation is one spawn helper, focused Rust tests, and preserving the existing sidecar/dev fallback and log-redaction behavior.
