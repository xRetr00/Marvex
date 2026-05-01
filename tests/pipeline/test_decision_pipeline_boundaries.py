from pathlib import Path
import ast

from packages.adapters.pipeline.decision_pipeline import DecisionPipeline
from packages.contracts.decision_pipeline_models import DecisionFinalAction
from packages.contracts.intent_models import IntentDecision, PolicyDecision, RouteFamily
from packages.contracts.intent_validation_models import IntentRiskLevel, IntentValidationResult
from packages.contracts.prompt_plan_models import PromptAssemblyReport, PromptPlan
from packages.decision_runtime.decision_pipeline_factory import create_decision_pipeline


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


def test_factory_creates_pipeline_from_injected_components_only() -> None:
    pipeline = create_decision_pipeline(
        pipeline_cls=DecisionPipeline,
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


def test_decision_pipeline_factory_source_is_tiny_and_has_no_runtime_logic() -> None:
    source = read_source("packages/decision_runtime/decision_pipeline_factory.py")
    tree = ast.parse(source)

    class_names = [node.name for node in tree.body if isinstance(node, ast.ClassDef)]
    function_names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef)]
    forbidden_names = [
        name
        for name in class_names + function_names
        if "dev" in name.lower()
        or "payload" in name.lower()
        or "summary" in name.lower()
        or "report" in name.lower()
        or "run_" in name.lower()
    ]

    assert class_names == []
    assert forbidden_names == []
    assert function_names == ["create_decision_pipeline"]
