from __future__ import annotations

from typing import Any

from pydantic import Field

from packages.capability_runtime.models import CapabilityEligibilityDecision, CapabilityRuntimeModel


class CapabilityContextDeliveryPolicy(CapabilityRuntimeModel):
    max_capabilities: int = Field(..., ge=0, le=100)
    include_excluded_reasons: bool
    deliver_full_schema: bool = False


class CapabilityCompactionPolicy(CapabilityRuntimeModel):
    max_schema_bytes: int = Field(..., ge=1, le=100_000)
    offload_large_schemas: bool
    offload_ref_prefix: str = "local://capability-context/"


class CapabilityContextPack(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    delivery_policy: CapabilityContextDeliveryPolicy
    compaction_policy: CapabilityCompactionPolicy
    eligibility_decisions: tuple[Any, ...]
    prompt_contributions: tuple[str, ...] = ()

    def schema_delivery(self) -> dict[str, object]:
        eligible = [decision for decision in self.eligibility_decisions if decision.eligible]
        included = eligible[: self.delivery_policy.max_capabilities]
        excluded = [decision for decision in self.eligibility_decisions if not decision.eligible]
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "included_capabilities": [
                {
                    "identifier": decision.capability_ref.identifier,
                    "kind": decision.capability_ref.kind.value,
                    "reason_code": decision.reason_code,
                }
                for decision in included
            ],
            "excluded_capabilities": [
                {"identifier": decision.capability_ref.identifier, "reason_code": decision.reason_code}
                for decision in excluded
            ] if self.delivery_policy.include_excluded_reasons else [],
            "prompt_contributions": list(self.prompt_contributions),
            "all_capabilities_injected": False,
            "offload_large_schemas": self.compaction_policy.offload_large_schemas,
        }


class CapabilityToolContextDelivery(CapabilityRuntimeModel):
    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    manifests: tuple[Any, ...]
    eligibility_decisions: tuple[CapabilityEligibilityDecision, ...]
    delivery_policy: CapabilityContextDeliveryPolicy
    compaction_policy: CapabilityCompactionPolicy

    def schema_delivery(self) -> dict[str, object]:
        eligible_refs = {
            decision.capability_ref
            for decision in self.eligibility_decisions
            if decision.eligible
        }
        included = [manifest for manifest in self.manifests if manifest.capability_ref in eligible_refs]
        included = included[: self.delivery_policy.max_capabilities]
        included_ids = {manifest.capability_ref.identifier for manifest in included}
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "included_tools": [manifest.capability_ref.identifier for manifest in included],
            "excluded_tools": [
                manifest.capability_ref.identifier
                for manifest in self.manifests
                if manifest.capability_ref.identifier not in included_ids
            ],
            "all_tools_injected": False,
            "raw_schema_persisted": False,
        }
