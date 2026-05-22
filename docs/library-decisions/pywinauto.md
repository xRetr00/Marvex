# Library Decision: pywinauto

library name: pywinauto

official source: https://pywinauto.readthedocs.io/ and https://pypi.org/project/pywinauto/

maintenance status: Candidate for DesktopAgent research posture only. Treat as maintained community desktop automation library pending explicit version verification at adoption time.

why use it: It provides established Windows UI automation primitives for window discovery, control targeting, and bounded interaction paths needed for future DesktopAgent evaluation without building Win32/UIA automation mechanics from scratch.

why not custom code: Custom desktop automation would recreate fragile OS-level input and accessibility integration, increase security risk, and delay Assistant OS boundary work. Marvex should own policy, approvals, contracts, and telemetry envelopes while adapter code owns library integration only.

fallback if abandoned: Keep all pywinauto usage isolated behind a DesktopAgent adapter port so Marvex can switch to `uiautomation`, WinAppDriver, or keep DesktopAgent disabled without changing Core, CapabilityRuntime policy authority, or assistant turn contracts.

pyproject dependency: pywinauto

declared dependency: pywinauto>=0.6; sys_platform == "win32"

architecture fit: Acceptable only as a Windows-scoped adapter dependency behind DesktopAgent boundaries. It must not own planning, approvals, policy decisions, memory semantics, or proactive behavior.

policy posture: Local-only policy. No remote desktop control surface. Require explicit approval flow for side-effecting desktop actions. Raw screen captures, raw audio, and raw keystroke streams are not persisted by default.

adopt / defer / reject decision: Adopt for the approved DesktopAgent perception adapter only, behind adapter isolation and Windows platform marker constraints.
