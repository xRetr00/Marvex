from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    failures: list[str] = []
    try:
        from packages.capability_runtime import AutonomyAction, AutonomyMode, AutonomyPolicy, PolicyDecision, evaluate_autonomy_action
    except Exception as exc:
        failures.append(f"autonomy policy import failed: {type(exc).__name__}")
    else:
        policy = AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX)
        projection = policy.safe_projection()
        if projection.mode != AutonomyMode.AUTO_MARVEX:
            failures.append("Auto Marvex mode must exist")
        if not projection.hard_block_blacklist_only:
            failures.append("hard-block must be blacklist-only")
        for capability in ("read", "list", "search", "web_search"):
            decision = evaluate_autonomy_action(policy, AutonomyAction(action=capability, resource_type="public", capability=capability))
            if decision.decision == PolicyDecision.HARD_BLOCK:
                failures.append(f"{capability} cannot be globally hard-blocked")
        for capability in ("auto_fetch", "live_oauth_sync", "memory_auto_write", "profile_write", "mcp_execute", "skills_update_create", "provider_retry_fallback", "file_delete"):
            permission = projection.matrix.get(capability)
            if permission not in {"allow", "ask", "deny", "quarantine", "hard_block"}:
                failures.append(f"{capability} must be policy-controlled")
        for capability in ("file_write", "file_delete", "external_upload_send", "shell_command_execution"):
            decision = evaluate_autonomy_action(policy, AutonomyAction(action=f"normal {capability}", resource_type="side_effect", capability=capability))
            if decision.decision == PolicyDecision.HARD_BLOCK:
                failures.append(f"normal {capability} cannot hard-block outside blacklist")
            if not decision.reason_codes:
                failures.append(f"{capability} decision needs reason codes")
        blacklist = evaluate_autonomy_action(policy, AutonomyAction(action="command injection exfiltrate credentials", resource_type="shell", capability="shell_command_execution"))
        if blacklist.decision != PolicyDecision.HARD_BLOCK:
            failures.append("blacklist abuse must hard-block")
        if not blacklist.reason_codes:
            failures.append("hard-block decisions must include reason codes")

    app_py = ROOT / "packages" / "control_plane_api" / "app.py"
    app_text = app_py.read_text(encoding="utf-8")
    if "/runtime-policy" not in app_text:
        failures.append("Control Plane runtime-policy endpoint is required")
    ui_text = (ROOT / "apps" / "control_plane_web" / "src" / "App.tsx").read_text(encoding="utf-8")
    views_text = (ROOT / "apps" / "control_plane_web" / "src" / "views" / "ExpandedViews.tsx").read_text(encoding="utf-8")
    if "Runtime Policy" not in ui_text or "Runtime Policy / Autonomy Modes" not in views_text:
        failures.append("Control Plane runtime policy selector view is required")
    docs_text = (ROOT / "docs" / "GOVERNANCE_CLASSIFICATION.md").read_text(encoding="utf-8")
    if "policy-controlled" not in docs_text or "hard-blocked blacklist only" not in docs_text:
        failures.append("governance docs must distinguish policy-controlled from hard-blocked blacklist only")
    run_all = (ROOT / "scripts" / "run_all_checks.py").read_text(encoding="utf-8")
    if "check_autonomy_policy_boundaries.py" not in run_all:
        failures.append("scripts/run_all_checks.py must run check_autonomy_policy_boundaries.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS autonomy policy boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
