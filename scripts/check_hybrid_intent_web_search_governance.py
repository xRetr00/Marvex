from __future__ import annotations

from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
RUN_ALL_CHECKS = ROOT / "scripts" / "run_all_checks.py"


def _deps() -> list[str]:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return list(data.get("project", {}).get("dependencies", ()))


def _has_dep(dependencies: list[str], name: str) -> bool:
    normalized = [dep.lower().replace("_", "-") for dep in dependencies]
    return any(dep == name or dep.startswith(f"{name}[") or dep.startswith(f"{name}=") or dep.startswith(f"{name}>") for dep in normalized)


def _request(text: str):
    from packages.intent_runtime import IntentClassificationRequest

    return IntentClassificationRequest(schema_version="1", trace_id="trace-gate", turn_id="turn-gate", user_input_summary=text)


def main() -> int:
    failures: list[str] = []
    dependencies = _deps()
    for dependency in ("semantic-router", "llama-index-core", "ddgs"):
        if not _has_dep(dependencies, dependency):
            failures.append(f"missing runtime dependency: {dependency}")

    web_search_path = ROOT / "packages" / "web_search_runtime" / "__init__.py"
    grounded_path = ROOT / "packages" / "grounded_answer_runtime" / "__init__.py"
    risk_path = ROOT / "packages" / "capability_runtime" / "risk_governance.py"
    for path in (web_search_path, grounded_path, risk_path):
        if not path.is_file():
            failures.append(f"missing required runtime file: {path.relative_to(ROOT).as_posix()}")

    if web_search_path.is_file():
        text = web_search_path.read_text(encoding="utf-8")
        for term in ("SearXNGWebSearchAdapter", "DDGSWebSearchAdapter", "WebSearchProviderSelector", "WebSearchGroundingBundle"):
            if term not in text:
                failures.append(f"web search runtime missing term: {term}")

    if grounded_path.is_file():
        text = grounded_path.read_text(encoding="utf-8")
        for term in ("validate_grounded_citations", "WebSearchEvidenceRef", "citation.evidence_ref_missing"):
            if term not in text:
                failures.append(f"grounded answer runtime missing term: {term}")

    try:
        from packages.capability_runtime.risk_governance import RiskGovernancePolicy
        from packages.capability_runtime.models import CapabilityExecutionMode
        from packages.intent_runtime import IntentKind, classify_intent
        from packages.web_search_runtime import WebSearchEvidenceRef, WebSearchFreshness
        from packages.grounded_answer_runtime import GroundedAnswerDraft, validate_grounded_citations
    except Exception as exc:  # pragma: no cover - validation diagnostic
        failures.append(f"failed importing hybrid intent/search/governance runtimes: {type(exc).__name__}")
    else:
        examples = {
            "2+2": IntentKind.CAPABILITY_TOOL,
            "search latest browser-use version": IntentKind.WEB_SEARCH,
            "list MCP tools": IntentKind.MCP_NEEDED,
            "what changed in my memory tree about Marvex?": IntentKind.MEMORY_TREE_NEEDED,
            "do it": IntentKind.CLARIFICATION,
        }
        for prompt, expected in examples.items():
            result = classify_intent(_request(prompt))
            if result.selected_intent.intent_kind != expected:
                failures.append(f"hybrid intent routed {prompt!r} to {result.selected_intent.intent_kind.value}, expected {expected.value}")
            if result.backend_name != "hybrid_intent_runtime.deterministic_local_encoder":
                failures.append(f"hybrid intent backend regressed for {prompt!r}: {result.backend_name}")
            if result.hybrid_details.get("semantic_encoder_backend_name") != "deterministic_local_encoder":
                failures.append(f"hybrid intent encoder seam missing for {prompt!r}")
            if result.library_owns_policy is not False:
                failures.append("hybrid intent library ownership flag must remain false")

        policy = RiskGovernancePolicy.default()
        for action in ("read public page", "list MCP tools", "search web"):
            decision = policy.classify(action)
            if decision.hard_blocked or decision.requires_confirmation:
                failures.append(f"safe read/list/search action over-blocked: {action}")
        for action in ("delete this file", "send this file outside", "install package", "run command"):
            decision = policy.classify(action)
            if decision.hard_blocked or decision.execution_mode != CapabilityExecutionMode.REQUIRES_APPROVAL:
                failures.append(f"risky action must require approval without hard block: {action}")
        for action in ("credential theft", "command injection exploitation", "exfiltrate data", "bypass captcha"):
            if not policy.classify(action).hard_blocked:
                failures.append(f"abuse action must be hard-blocked: {action}")

        evidence = (WebSearchEvidenceRef(evidence_id="web.evidence.1", source_url="https://example.com", domain="example.com", title="Example", snippet="safe snippet", freshness=WebSearchFreshness.CURRENT),)
        good = GroundedAnswerDraft(text="Grounded answer [web.evidence.1]", citation_ids=("web.evidence.1",))
        bad = GroundedAnswerDraft(text="Grounded answer [web.evidence.99]", citation_ids=("web.evidence.99",))
        if not validate_grounded_citations(good, evidence_refs=evidence).valid:
            failures.append("grounded citation validator rejected mapped evidence")
        if validate_grounded_citations(bad, evidence_refs=evidence).valid:
            failures.append("grounded citation validator accepted hallucinated evidence")

    checks = RUN_ALL_CHECKS.read_text(encoding="utf-8") if RUN_ALL_CHECKS.is_file() else ""
    if "check_hybrid_intent_web_search_governance.py" not in checks:
        failures.append("scripts/run_all_checks.py must run check_hybrid_intent_web_search_governance.py")

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    print("PASS hybrid intent web search governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
