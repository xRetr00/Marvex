from pathlib import Path

from packages.adapters.pipeline.decision_pipeline import DecisionPipeline
from packages.contracts.decision_pipeline_models import DecisionFinalAction
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan


ROOT = Path(__file__).resolve().parents[2]


class StaticRouter:
    def decide_route(self, input_text: str) -> IntentDecision:
        return IntentDecision(route_family=RouteFamily.DIRECT_ANSWER, confidence=0.9, ambiguity_flag=False)


class StaticValidator:
    def validate(self, input_text: str, intent_decision: IntentDecision) -> IntentValidationResult:
        return IntentValidationResult(
            accepted=True,
            needs_clarification=False,
            risk_level=IntentRiskLevel.LOW,
            reason_code="validator.accepted",
            corrected_route_family=None,
        )


class StaticPolicy:
    def decide(self, intent_decision: IntentDecision) -> PolicyDecision:
        return PolicyDecision(allow=True, clarify=False, deny=False, reason_code="policy.allowed")


class StaticContextBuilder:
    def build_prompt_plan(
        self,
        input_text: str,
        intent_decision: IntentDecision,
        policy_decision: PolicyDecision,
    ) -> tuple[PromptPlan, PromptAssemblyReport]:
        return (
            PromptPlan(route_family=intent_decision.route_family, blocks=[], total_budget=0),
            PromptAssemblyReport(included_blocks=[], suppressed_blocks=[], reason_codes=[], budget_used=0),
        )


def read_source(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_decision_pipeline_adapter_runs_from_injected_components_only() -> None:
    pipeline = DecisionPipeline(
        router=StaticRouter(),
        validator=StaticValidator(),
        policy_gate=StaticPolicy(),
        context_builder=StaticContextBuilder(),
    )

    result = pipeline.run("input")

    assert result.final_action == DecisionFinalAction.PROCEED
    assert result.prompt_plan.tool_surface_exposed == []


def test_pipeline_adapter_source_does_not_import_core_providers_tools_mcp_or_memory() -> None:
    source = read_source("packages/adapters/pipeline/decision_pipeline.py").lower()

    forbidden = [
        "packages.core",
        "packages.adapters.providers",
        "provider_runtime",
        " tool",
        "tools",
        "mcp",
        "memory",
        "render",
    ]
    assert [token for token in forbidden if token in source] == []


def test_redundant_decision_runtime_package_and_gate_are_removed() -> None:
    decision_runtime_root = ROOT / "packages" / "decision_runtime"
    assert not list(decision_runtime_root.glob("*.py"))
    assert not (ROOT / "scripts" / "check_decision_runtime_boundaries.py").exists()
    assert "check_decision_runtime_boundaries.py" not in read_source("scripts/run_all_checks.py")
