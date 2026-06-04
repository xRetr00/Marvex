"""Calculator tool — safe numeric arithmetic only (no names, calls, attrs)."""

from __future__ import annotations

import ast
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result

_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
)


class CalculatorParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str = Field(..., min_length=1, max_length=120, description="Arithmetic expression, e.g. '2 + 2 * 3'.")

    @field_validator("expression")
    @classmethod
    def _validate(cls, value: str) -> str:
        tree = ast.parse(value, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise ValueError("calculator expression allows numeric arithmetic only")
            if isinstance(node, ast.Constant) and not isinstance(node.value, int | float):
                raise ValueError("calculator expression allows numeric constants only")
        return value


class CalculatorTool(Tool):
    id: ClassVar[str] = "calculator"
    name: ClassVar[str] = "Calculator"
    description: ClassVar[str] = "Evaluate an arithmetic expression and return the numeric result."
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY
    params_model: ClassVar[type[BaseModel]] = CalculatorParams

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = CalculatorParams(**request.arguments)
        value = _eval_numeric(ast.parse(params.expression, mode="eval").body)
        return succeeded_result(request, {"result": str(value.normalize())})


def _eval_numeric(node: ast.AST) -> Decimal:
    if isinstance(node, ast.Constant):
        return Decimal(str(node.value))
    if isinstance(node, ast.UnaryOp):
        value = _eval_numeric(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left = _eval_numeric(node.left)
        right = _eval_numeric(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** int(right)
    raise ValueError("unsupported calculator expression")


__all__ = ["CalculatorTool", "CalculatorParams"]
