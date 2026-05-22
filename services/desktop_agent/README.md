# Desktop Agent Worker

Contract status: see `docs/CONTRACT_APPROVALS.md`.

`DesktopAgent` is an approved local-only perception worker. It exposes a JSONL
process boundary for health/version/status/start/stop/perceive/recall and owns
safe focused-window content projections.

Allowed inputs:

- Windows UI Automation through `pywinauto` and `uiautomation`.
- screenpipe recall only through the existing MCP adapter/allowlist path.

Safety constraints:

- no raw screen frames persisted by Marvex
- no raw keystrokes persisted by Marvex
- no raw audio/transcript/payload persistence by Marvex
- no desktop actions or computer-use execution in this worker
- bounded redacted content projections only
