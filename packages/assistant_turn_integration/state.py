from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from packages.capability_runtime import CapabilityApprovalRequest
from packages.control_plane_api import ControlPlaneSnapshot, InMemoryApprovalStore
from packages.telemetry import InMemoryTraceReader

from packages.assistant_turn_integration.models import EndToEndAssistantTurnResult


@dataclass
class EndToEndTurnStateStore:
    trace_reader: InMemoryTraceReader = field(default_factory=InMemoryTraceReader)
    approval_store: InMemoryApprovalStore = field(default_factory=InMemoryApprovalStore)
    last_result: EndToEndAssistantTurnResult | None = None
    last_mcp_summary: dict[str, Any] | None = None
    memory_store: Any | None = None

    def add_pending_approval(self, request: CapabilityApprovalRequest) -> None:
        self.approval_store.add_pending(request)

    def record_result(self, result: EndToEndAssistantTurnResult) -> None:
        self.last_result = result

    def control_plane_snapshot(self) -> ControlPlaneSnapshot:
        if self.last_result is None:
            return ControlPlaneSnapshot.foundation_default(schema_version="1")
        trace = self.trace_reader.read_trace(self.last_result.trace_id)
        projection = self.last_result.safe_projection()
        mcp_servers: tuple[dict[str, Any], ...] = ()
        if self.last_mcp_summary is not None:
            mcp_servers = (self.last_mcp_summary,)
        memory_rows: tuple[dict[str, Any], ...] = ()
        if self.memory_store is not None and hasattr(self.memory_store, "safe_inspect"):
            memory_rows = tuple(self.memory_store.safe_inspect(max_records=10))
        return ControlPlaneSnapshot.foundation_default(
            schema_version="1",
            providers=({"provider_id": "fake", "configured": True, "secret_present": False},),
            capabilities=({"identifier": "builtin.calculator", "kind": "tool", "risk_level": "safe"},),
            tools=({"tool_id": "builtin.calculator", "side_effect_level": "read_only"},),
            mcp_servers=mcp_servers,
            traces=({"trace_id": self.last_result.trace_id, "event_count": (trace or {}).get("event_count", 0), "raw_payload_persisted": False},),
            memory=memory_rows,
            sessions=({"session_id": "session-linked", "turn_count": 1},),
            agent_loops=(self.last_result.tool_state_projection,),
            telemetry={"trace_count": 1, "telemetry_event_count": projection.telemetry_event_count, "raw_payload_persisted": False},
            settings={"browser_tools_enabled": False, "computer_use_enabled": False},
        )

