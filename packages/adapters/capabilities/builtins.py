from __future__ import annotations

import ast
import datetime as dt
from decimal import Decimal
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class BuiltinToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BuiltinToolResult(BuiltinToolModel):
    result: CapabilityResultEnvelope

    @property
    def safe_result(self) -> dict[str, object]:
        return self.result.safe_result


class CalculatorRequest(BuiltinToolModel):
    expression: str = Field(..., min_length=1, max_length=120)

    @field_validator("expression")
    @classmethod
    def _validate_expression(cls, value: str) -> str:
        tree = ast.parse(value, mode="eval")
        allowed = (
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
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise ValueError("calculator expression allows numeric arithmetic only")
            if isinstance(node, ast.Constant) and not isinstance(node.value, int | float):
                raise ValueError("calculator expression allows numeric constants only")
        return value


class TimeDateRequest(BuiltinToolModel):
    timezone: Literal["UTC"] = "UTC"


class RepoStatusSnapshot(BuiltinToolModel):
    branch: str = Field(..., min_length=1)
    clean: bool
    short_status: str = ""


class BuiltinTool(BuiltinToolModel):
    schema_version: str = "1"
    tool_id: str
    display_name: str
    description: str
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.READ_ONLY

    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.TOOL, identifier=f"builtin.{self.tool_id}")

    def to_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            schema_version=self.schema_version,
            capability_ref=self.capability_ref(),
            display_name=self.display_name,
            description=self.description,
            owner_package="packages.adapters.capabilities.builtins",
            adapter_boundary="builtin_tools_foundation",
            permissions=(f"tool.builtin.{self.tool_id}",),
            input_schema={"type": "object"},
            metadata={
                "risk_level": self.risk_level.value,
                "side_effect_level": self.side_effect_level.value,
                "shell_execution_allowed": False,
                "file_write_allowed": False,
                "network_fetch_allowed": False,
            },
            enabled_by_default=False,
        )


class CalculatorBuiltin(BuiltinTool):
    tool_id: str = "calculator"
    display_name: str = "Calculator"
    description: str = "Safe arithmetic calculator."

    def execute(self, request: CalculatorRequest) -> BuiltinToolResult:
        value = _eval_numeric(ast.parse(request.expression, mode="eval").body)
        return _result(self.capability_ref(), {"result": str(value.normalize())})


class TimeDateBuiltin(BuiltinTool):
    tool_id: str = "time_date"
    display_name: str = "Time and Date"
    description: str = "Safe current UTC time/date projection."
    clock: Callable[[], dt.datetime] = Field(exclude=True)

    def execute(self, request: TimeDateRequest) -> BuiltinToolResult:
        now = self.clock().astimezone(dt.timezone.utc)
        return _result(
            self.capability_ref(),
            {"timezone": request.timezone, "iso_datetime": now.isoformat(), "iso_date": now.date().isoformat()},
        )


class CapabilityDiagnosticsBuiltin(BuiltinTool):
    tool_id: str = "capability_diagnostics"
    display_name: str = "Capability Diagnostics"
    description: str = "Read-only safe capability diagnostics."
    capability_count: int = Field(..., ge=0)
    eligible_count: int = Field(..., ge=0)

    def execute(self) -> BuiltinToolResult:
        return _result(
            self.capability_ref(),
            {"capability_count": self.capability_count, "eligible_count": self.eligible_count},
        )


class RepoStatusBuiltin(BuiltinTool):
    tool_id: str = "repo_status"
    display_name: str = "Repo Status"
    description: str = "Injected read-only repository status snapshot."
    snapshot: RepoStatusSnapshot

    def execute(self) -> BuiltinToolResult:
        return _result(
            self.capability_ref(),
            {"branch": self.snapshot.branch, "clean": self.snapshot.clean, "status_length": len(self.snapshot.short_status)},
        )


class BuiltinToolCatalog(BuiltinToolModel):
    tools: tuple[BuiltinTool, ...]

    @classmethod
    def default(cls) -> BuiltinToolCatalog:
        return cls(
            tools=(
                CalculatorBuiltin(),
                TimeDateBuiltin(clock=lambda: dt.datetime.now(dt.timezone.utc)),
                CapabilityDiagnosticsBuiltin(capability_count=4, eligible_count=4),
                RepoStatusBuiltin(snapshot=RepoStatusSnapshot(branch="unknown", clean=True)),
            )
        )

    def calculator(self) -> CalculatorBuiltin:
        return CalculatorBuiltin()

    def time_date(self, *, clock: Callable[[], dt.datetime]) -> TimeDateBuiltin:
        return TimeDateBuiltin(clock=clock)

    def capability_diagnostics(self, *, capability_count: int, eligible_count: int) -> CapabilityDiagnosticsBuiltin:
        return CapabilityDiagnosticsBuiltin(capability_count=capability_count, eligible_count=eligible_count)

    def repo_status(self, *, snapshot: RepoStatusSnapshot) -> RepoStatusBuiltin:
        return RepoStatusBuiltin(snapshot=snapshot)

    def manifests(self) -> tuple[CapabilityManifest, ...]:
        return tuple(tool.to_manifest() for tool in self.tools)

    def execute_request(self, request: CapabilityExecutionRequest) -> BuiltinToolResult:
        # Dispatch now delegates to the per-file tool registry
        # (packages.adapters.capabilities.tools). This catalog remains as a
        # thin backwards-compatible shim for existing callers; the if/elif
        # ladder it used to carry is gone. See docs/TODO/07.
        from packages.adapters.capabilities.tools import default_registry

        registry = default_registry()
        identifier = request.proposal.capability_ref.identifier
        if registry.get(identifier) is None:
            raise ValueError("unsupported builtin tool capability")
        return BuiltinToolResult(result=registry.execute(request))


def _result(capability_ref: CapabilityRef, safe_result: dict[str, object]) -> BuiltinToolResult:
    return BuiltinToolResult(
        result=CapabilityResultEnvelope(
            schema_version="1",
            result_id=f"{capability_ref.identifier}:result",
            trace_id="builtin-trace",
            turn_id="builtin-turn",
            capability_ref=capability_ref,
            status="succeeded",
            safe_result=safe_result,
            raw_input_persisted=False,
            raw_output_persisted=False,
        )
    )


def _result_for_request(request: CapabilityExecutionRequest, safe_result: dict[str, object]) -> BuiltinToolResult:
    return BuiltinToolResult(
        result=CapabilityResultEnvelope(
            schema_version=request.schema_version,
            result_id=f"{request.request_id}:result",
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_ref=request.proposal.capability_ref,
            status="succeeded",
            safe_result=safe_result,
            raw_input_persisted=False,
            raw_output_persisted=False,
        )
    )


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


def _repo_status_snapshot(arguments: dict[str, object]) -> RepoStatusSnapshot:
    branch = str(arguments.get("branch") or "unknown").strip() or "unknown"
    clean = bool(arguments.get("clean", True))
    short_status = str(arguments.get("short_status") or "")
    return RepoStatusSnapshot(branch=branch[:120], clean=clean, short_status=short_status[:4000])
