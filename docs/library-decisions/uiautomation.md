# Library Decision: uiautomation

library name: uiautomation

official source: https://github.com/yinkaisheng/Python-UIAutomation-for-Windows and https://pypi.org/project/uiautomation/

maintenance status: Candidate for DesktopAgent research posture only. Treat as maintained community Windows UI Automation binding pending explicit version verification at adoption time.

why use it: It provides direct Windows UI Automation capability coverage that can support future policy-gated DesktopAgent interaction paths while preserving Marvex adapter boundaries.

why not custom code: Building direct UI Automation bindings and control traversal behavior in-house would duplicate mature ecosystem work, increase maintenance burden, and blur Core versus adapter responsibilities.

fallback if abandoned: Keep `uiautomation` isolated behind the DesktopAgent adapter port so Marvex can replace it with `pywinauto`, WinAppDriver, or a different Windows accessibility backend without contract or Core lifecycle changes.

pyproject dependency: uiautomation

declared dependency: uiautomation>=2.0; sys_platform == "win32"

architecture fit: Acceptable only as a Windows-only adapter dependency for future DesktopAgent seams. CapabilityRuntime and policy/permission contracts remain authoritative.

policy posture: Local-only policy. No remote-control or hidden autonomous desktop execution. Raw screen data, raw audio buffers, and raw keystroke sequences are not persisted by default.

adopt / defer / reject decision: Adopt for the approved DesktopAgent perception adapter only, behind strict adapter isolation and Windows platform markers.
