from __future__ import annotations

# file size justification: the approved Core service entrypoint is constrained by
# service placeholder gates to this file, so local IPC composition helpers live
# here until a later approved service split expands the allowed file set.

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from wsgiref.simple_server import make_server

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.assistant_turn_integration.models import EndToEndAssistantTurnProjection
from packages.capability_runtime import (
    ApprovalPrompt,
    AutonomyPolicy,
    CapabilityApprovalRequest,
    CapabilityKind,
    CapabilityRef,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.cognition_runtime import CognitionRuntime, CognitionTurnAssembly
from packages.cognition_runtime import LocalMemoryLoop
from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    OutputChannelIntent,
    ProviderRequest,
    ProviderResponse,
    StageStatus,
    StageSummary,
    ToolResultRef,
    TraceLevel,
    TraceStage,
)
from packages.core import CoreService
from packages.core.orchestration.assistant_provider_stage import (
    run_assistant_provider_stage_turn,
)
from packages.grounded_answer_runtime import GroundedAnswerDraft, validate_grounded_citations
from packages.learning_runtime import (
    FeedbackEvent,
    FeedbackSignalKind,
    LearningCandidateStore,
    LearningLoop,
    LearningPipelineRunner,
    ToolOutcomeFeedback,
)
from packages.local_api import LocalApiConfig, create_health_version_api_app
from packages.local_api.health_version_api import LOCAL_TURNS_EXECUTION_MODE
from packages.provider_selection_runtime import (
    ModelCapabilityRequirement,
    ProviderCandidate,
    ProviderFallbackPolicy,
    ProviderRetryPolicy,
    ProviderSelectionRequest,
    ProviderSelectionRuntime,
)
from packages.provider_structured_output import validate_raw_structured_output
from packages.session_runtime import (
    CurrentProcessSessionRegistry,
    build_turn_linkage_from_assistant_turn_input,
)
from packages.skills_runtime import (
    SkillInstructionLoader,
    SkillManifest,
    SkillRef,
    SkillResourceKind,
    SkillResourceRef,
)
from packages.telemetry import InMemoryTraceReader, PersistentTraceStore, make_trace_event
from packages.web_search_runtime import (
    DDGSWebSearchAdapter,
    MultiProviderWebSearch,
    SearXNGWebSearchAdapter,
    WebSearchEvidenceRef,
    WebSearchFreshness,
    WebSearchGroundingBundle,
    WebSearchQuery,
    WebSearchResult,
    WikipediaWebSearchAdapter,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_FOUNDATION_MODEL = "fake-model"
DEFAULT_PROVIDER = "fake"
STARTUP_MESSAGE_PREFIX = "Core service startup metadata: "

ServerFactory = Callable[[str, int, Any], Any]


DEFAULT_TELEMETRY_STORE_PATH = ".marvex-telemetry/traces.jsonl"
_TURN_AUTONOMY_POLICY = AutonomyPolicy.for_mode("ask_before_risky")


@dataclass(frozen=True)
class CoreServiceEntrypointConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    local_auth_token: str | None = None
    foundation_model: str = DEFAULT_FOUNDATION_MODEL
    provider: str = DEFAULT_PROVIDER
    worker_provider: str | None = None
    base_url: str | None = None
    web_search: str = "fake"
    web_base_url: str | None = None
    demo_memory_evidence: bool = False
    memory_vault_root: str | None = None
    file_capability_root: str | None = None
    resume_approval: str | None = None
    approval_decision: str | None = None
    timeout_seconds: float | None = None
    allow_remote: bool = False
    telemetry_store_path: str | None = None
    skills_root: str | None = None

    def local_api_config(self) -> LocalApiConfig:
        return LocalApiConfig(
            host=self.host,
            port=self.port,
            allow_remote=self.allow_remote,
        )


@dataclass(frozen=True)
class _CoreTurnExecutorRequest:
    schema_version: str
    execution_mode: str
    assistant_turn_input: Any
    model: str
    instructions: str | None
    previous_response_id: str | None
    provider_options: dict[str, object]


class _CoreServiceFoundationTurnExecutor:
    def __init__(
        self,
        *,
        foundation_turn_handler: Callable[[_CoreTurnExecutorRequest], Any],
        model: str,
    ) -> None:
        self._foundation_turn_handler = foundation_turn_handler
        self._model = model

    def submit_turn(self, turn_input):
        return self._foundation_turn_handler(
            _CoreTurnExecutorRequest(
                schema_version=turn_input.schema_version,
                execution_mode=LOCAL_TURNS_EXECUTION_MODE,
                assistant_turn_input=turn_input,
                model=self._model,
                instructions=None,
                previous_response_id=None,
                provider_options={},
            )
        )


class _ProviderWorkerProcessProvider:
    def __init__(
        self,
        *,
        provider_name: str,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._provider_name = provider_name
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def send(self, request: ProviderRequest) -> ProviderResponse:
        send_command: dict[str, object] = {
            "command": "send",
            "trace_id": request.trace_id,
            "provider_name": self._provider_name,
            "request": request.model_dump(mode="json"),
        }
        if self._base_url is not None:
            send_command["base_url"] = self._base_url
        if self._timeout_seconds is not None:
            send_command["timeout_seconds"] = self._timeout_seconds
        stop_command = {"command": "stop", "trace_id": request.trace_id}
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.provider_worker.main",
                "--jsonl",
            ],
            input=json.dumps(send_command) + "\n" + json.dumps(stop_command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("ProviderWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("ProviderWorker returned no response.")
        payload = json.loads(lines[0])
        if isinstance(payload, dict) and payload.get("response") is not None:
            return ProviderResponse.model_validate(payload["response"])
        if isinstance(payload, dict) and payload.get("error") is not None:
            error = ErrorEnvelope.model_validate(payload["error"])
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name=self._provider_name,
                response_id=None,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata={},
                error=error,
            )
        raise RuntimeError("ProviderWorker response was invalid.")

    def map_raw_output_to_structured_result(
        self,
        *,
        schema_version: str,
        trace_id: str,
        turn_id: str,
        target_contract: str,
        raw_output_text: str,
    ) -> dict[str, object] | None:
        command: dict[str, object] = {
            "command": "structured_output",
            "schema_version": schema_version,
            "trace_id": trace_id,
            "turn_id": turn_id,
            "provider_name": self._provider_name,
            "target_contract": target_contract,
            "raw_output_text": raw_output_text,
        }
        if self._base_url is not None:
            command["base_url"] = self._base_url
        if self._timeout_seconds is not None:
            command["timeout_seconds"] = self._timeout_seconds
        stop_command = {"command": "stop", "trace_id": trace_id}
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.provider_worker.main",
                "--jsonl",
            ],
            input=json.dumps(command) + "\n" + json.dumps(stop_command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            return None
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            return None
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            return None
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return None
        structured = metadata.get("structured_output")
        return dict(structured) if isinstance(structured, dict) else None


class _IntentWorkerProcessClassifier:
    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def classify(self, turn_input: AssistantTurnInput) -> dict[str, object]:
        command = {
            "command": "classify",
            "trace_id": turn_input.trace_id,
            "turn_id": turn_input.turn_id,
            "user_input_summary": turn_input.user_visible_input or "",
        }
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.intent_worker.main",
                "--jsonl",
            ],
            input=json.dumps(command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("IntentWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("IntentWorker returned no response.")
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("classification") is None:
            raise RuntimeError("IntentWorker response was invalid.")
        return payload


class _ToolWorkerProcessExecutor:
    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        python_executable: str = sys.executable,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._python_executable = python_executable

    def execute(
        self,
        turn_input: AssistantTurnInput,
        *,
        action: str,
        capability: str,
        resource_type: str,
        capability_id: str = "fake.status",
        arguments: dict[str, object] | None = None,
    ) -> dict[str, object]:
        command = {
            "command": "execute",
            "trace_id": turn_input.trace_id,
            "turn_id": turn_input.turn_id,
            "capability_id": capability_id,
            "action": action,
            "capability": capability,
            "resource_type": resource_type,
            "arguments": dict(arguments or {"input_present": bool(turn_input.user_visible_input)}),
        }
        completed = subprocess.run(
            [
                self._python_executable,
                "-m",
                "services.tool_worker.main",
                "--jsonl",
            ],
            input=json.dumps(command) + "\n",
            text=True,
            capture_output=True,
            timeout=(self._timeout_seconds or 15) + 5,
        )
        if completed.returncode != 0:
            raise ConnectionError("ToolWorker process unavailable.")
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        if not lines:
            raise ConnectionError("ToolWorker returned no response.")
        payload = json.loads(lines[0])
        if not isinstance(payload, dict) or payload.get("result") is None:
            raise RuntimeError("ToolWorker response was invalid.")
        return payload


class _CoreServiceProviderWorkerTurnExecutor:
    def __init__(
        self,
        *,
        provider_name: str,
        model: str,
        trace_reader: InMemoryTraceReader,
        web_search_provider: object | None = None,
        memory_tree_runtime: object | None = None,
        memory_loop: LocalMemoryLoop | None = None,
        file_capability_root: str | None = None,
        resume_approval: str | None = None,
        approval_decision: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        session_registry: CurrentProcessSessionRegistry | None = None,
        provider_selection_runtime: ProviderSelectionRuntime | None = None,
        learning_pipeline: LearningPipelineRunner | None = None,
        persistent_trace_store: PersistentTraceStore | None = None,
        skill_manifests: tuple[SkillManifest, ...] = (),
        skill_loader: SkillInstructionLoader | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._provider = _ProviderWorkerProcessProvider(
            provider_name=provider_name,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
        )
        self._intent_classifier = _IntentWorkerProcessClassifier(
            timeout_seconds=timeout_seconds,
        )
        self._tool_executor = _ToolWorkerProcessExecutor(
            timeout_seconds=timeout_seconds,
        )
        self._model = model
        self._trace_reader = trace_reader
        self._web_search_provider = web_search_provider
        self._memory_tree_runtime = memory_tree_runtime
        self._memory_loop = memory_loop
        self._file_capability_root = file_capability_root
        self._resume_approval = resume_approval
        self._approval_decision = approval_decision
        self._session_registry = session_registry or CurrentProcessSessionRegistry()
        self._provider_selection = provider_selection_runtime
        self._learning_pipeline = learning_pipeline
        self._persistent_trace_store = persistent_trace_store
        self._skill_manifests = skill_manifests
        self._skill_loader = skill_loader

    def submit_turn(self, turn_input: AssistantTurnInput) -> AssistantTurnResult:
        linkage = build_turn_linkage_from_assistant_turn_input(turn_input)
        self._session_registry.record_turn(linkage)
        session_projection = _session_projection(self._session_registry, turn_input)

        selected_provider_name, selected_model, selection_projection = _run_provider_selection(
            self._provider_selection,
            turn_input,
            default_provider=self._provider_name,
            default_model=self._model,
        )
        if selected_provider_name != self._provider_name:
            self._provider = _ProviderWorkerProcessProvider(
                provider_name=selected_provider_name,
                base_url=self._base_url,
                timeout_seconds=self._timeout_seconds,
            )
        self._model = selected_model

        _emit_core_event(
            self._trace_reader,
            turn_input,
            TraceStage.TURN_RECEIVED,
            "Core agentic turn received.",
            {"status": "received"},
        )
        # Persist TURN_RECEIVED event to durable store (safe events only)
        _persist_trace_events(self._persistent_trace_store, self._trace_reader, turn_input.trace_id)
        try:
            intent_response = self._intent_classifier.classify(turn_input)
        except Exception:
            return _entrypoint_error_result(
                turn_input,
                reason="intent_worker_unavailable",
                message="Intent classification failed.",
            )
        intent_projection = dict(intent_response["classification"])
        intent_kind = str(
            dict(intent_projection.get("selected_intent", {})).get("intent_kind", "")
        )
        cognition = CognitionRuntime(
            intent_classifier=_fixed_intent_classifier(intent_response["classification"]),
            memory_store=self._memory_loop.memory_store if self._memory_loop is not None else None,
            memory_tree_runtime=self._memory_tree_runtime,
            web_search_provider=self._web_search_provider,
            skill_manifests=self._skill_manifests,
            skill_loader=self._skill_loader,
        ).assemble_turn(turn_input)
        loop = _AgenticLoopProjection(
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            max_steps=cognition.step_plan.max_steps,
        )
        metadata: dict[str, object] = {
            "intent_boundary": "intent_worker_process",
            "intent": intent_projection,
            "intent_backend": intent_response.get("backend_name"),
            "assistant_turn_spine": "used",
            "cognition": cognition.safe_projection().model_dump(mode="json"),
            "intent_plan": _intent_plan_projection(cognition.intent_plan),
            "session": session_projection,
            "provider_selection": selection_projection,
        }
        loop.step("plan")
        plan_intents = _intent_plan_kinds(cognition.intent_plan)
        route_intents = tuple(dict.fromkeys((intent_kind, *plan_intents)))
        if intent_projection.get("clarification_needed") == "needed" or intent_kind == "clarification":
            loop.step("clarify", stop_reason="finalized")
            return _entrypoint_text_result(
                turn_input,
                text="I need clarification before continuing.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
                stage_name="intent_preflight",
            )
        if intent_projection.get("risk_signal") == "unsafe_request" or intent_kind in {
            "unsafe_or_injection_suspected",
            "unsafe_risky",
        }:
            loop.step("block", stop_reason="blocked")
            return _entrypoint_error_result(
                turn_input,
                reason="unsafe_intent_blocked",
                message="Request blocked by intent safety preflight.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
            )
        if "capability_tool" in route_intents:
            loop.step("tool")
            return self._run_tool_path(
                turn_input,
                metadata=metadata,
                cognition=cognition,
                loop=loop,
                action="read",
                capability="read",
                resource_type="local_status",
                capability_id="builtin.calculator",
                arguments={"expression": _calculator_expression(turn_input.user_visible_input)},
            )
        if "risky_action" in route_intents:
            return self._run_approval_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)
        if "file_read_list_search" in route_intents:
            loop.step("tool")
            return self._run_file_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)
        if "mcp_needed" in route_intents or "mcp_skill" in route_intents:
            loop.step("tool")
            return self._run_mcp_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)
        if ("memory" in route_intents or "memory_tree_needed" in route_intents) and intent_kind not in {"grounded_answer", "web_search"}:
            loop.step("grounded_answer")
            return self._run_memory_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)
        if "skill_needed" in route_intents:
            loop.step("tool")
            return self._run_safe_projection_path(
                turn_input,
                metadata=metadata,
                loop=loop,
                route_name="skill",
                text="Skill instructions can be loaded only from configured local safe sources; install and launch remain disabled.",
                projection={
                    "local_skill_loader_available": self._skill_loader is not None,
                    "loaded_skill_contribution_count": _included_context_count(
                        cognition,
                        "skill_prompt_contribution",
                    ),
                    "install_launch_enabled": False,
                    "script_execution_allowed": False,
                    "remote_loading_allowed": False,
                    "raw_instruction_persisted": False,
                },
            )
        if "connector_account" in route_intents:
            loop.step("tool")
            return self._run_safe_projection_path(
                turn_input,
                metadata=metadata,
                loop=loop,
                route_name="connector",
                text="Connector account actions require explicit configuration and approval; live OAuth is not started.",
                projection={"live_oauth_started": False, "approval_required": True},
            )
        if "settings_control_plane" in route_intents:
            loop.step("tool")
            return self._run_safe_projection_path(
                turn_input,
                metadata=metadata,
                loop=loop,
                route_name="settings",
                text="Control-plane settings are available as safe status only from this turn path.",
                projection={"approval_resume_supported": True, "raw_payload_persisted": False},
            )
        if "browser_computer_use" in route_intents:
            loop.step("approval", stop_reason="waiting_for_human_approval")
            return self._run_safe_projection_path(
                turn_input,
                metadata=metadata,
                loop=loop,
                route_name="browser",
                text="Browser/computer-use execution is gated and not run in CI.",
                projection={"live_browser_executed": False, "approval_required": True},
                stop_reason="waiting_for_human_approval",
            )
        if "web_search" in route_intents or "grounded_answer" in route_intents:
            loop.step("web_search")
            loop.step("grounded_answer")
            return self._run_grounded_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)

        loop.step("provider")
        provider_turn_input, provider_instructions = _turn_input_with_prompt(turn_input, cognition)
        result = run_assistant_provider_stage_turn(
            provider_turn_input,
            provider=self._provider,
            model=self._model,
            instructions=provider_instructions,
            telemetry_sink=self._trace_reader,
        )
        memory_write = self._memory_loop.write_from_turn(turn_input) if self._memory_loop is not None else None
        loop.step("finalize", stop_reason="finalized")
        learning_projection = _run_learning_hook(
            self._learning_pipeline,
            turn_input,
            succeeded=result.error is None,
            intent_kind=intent_kind,
        )
        metadata = dict(result.metadata)
        metadata.update(
            {
                "intent_boundary": "intent_worker_process",
                "intent": intent_projection,
                "intent_backend": intent_response.get("backend_name"),
                "assistant_turn_spine": "used",
                "cognition": cognition.safe_projection().model_dump(mode="json"),
                "prompt_fidelity": _prompt_fidelity_projection(cognition, provider_turn_input, provider_instructions),
                "memory_loop": _memory_write_projection(memory_write),
                "session": session_projection,
                "provider_selection": selection_projection,
                "learning": learning_projection,
            }
        )
        metadata["provider_boundary"] = "provider_worker_process"
        metadata = _with_loop_metadata(metadata, loop, self._trace_reader, turn_input)
        _persist_trace_events(self._persistent_trace_store, self._trace_reader, turn_input.trace_id)
        return result.model_copy(update={"metadata": metadata})

    def _run_tool_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
        action: str,
        capability: str,
        resource_type: str,
        capability_id: str = "fake.status",
        arguments: dict[str, object] | None = None,
    ) -> AssistantTurnResult:
        try:
            tool_response = self._tool_executor.execute(
                turn_input,
                action=action,
                capability=capability,
                resource_type=resource_type,
                capability_id=capability_id,
                arguments=arguments,
            )
        except Exception:
            loop.step("finalize", stop_reason="failed")
            return _entrypoint_error_result(
                turn_input,
                reason="tool_worker_unavailable",
                message="Tool execution failed.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
            )
        combined_metadata = dict(metadata)
        combined_metadata["tool_boundary"] = "tool_worker_process"
        combined_metadata["tool"] = tool_response
        if tool_response.get("ok") is not True:
            loop.step("finalize", stop_reason="waiting_for_human_approval")
            return _entrypoint_error_result(
                turn_input,
                reason="tool_execution_blocked",
                message="Capability execution blocked by policy.",
                metadata=_with_loop_metadata(combined_metadata, loop, self._trace_reader, turn_input),
            )
        loop.step("finalize", stop_reason="finalized", executed=True)
        text = _tool_final_text(tool_response)
        return _entrypoint_text_result(
            turn_input,
            text=text,
            metadata=_with_loop_metadata(combined_metadata, loop, self._trace_reader, turn_input),
            stage_name="tool_execution",
            tool_result_refs=[
                ToolResultRef(
                    ref_type="tool_result",
                    ref_id=f"{turn_input.turn_id}:capability:result",
                )
            ],
        )

    def _run_grounded_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
    ) -> AssistantTurnResult:
        web_refs = tuple(cognition.web_evidence_refs)
        if not web_refs and not cognition.memory_evidence_refs:
            provider_result = self._run_provider_answer_path(
                turn_input,
                metadata={
                    **metadata,
                    "grounding": {
                        "web_search_executed": cognition.web_search_required,
                        "citation_validation": "citation.evidence_missing",
                        "fabricated": False,
                    },
                },
                cognition=cognition,
                loop=loop,
                stage_name="grounded_answer",
                provider_options={
                    "grounding_evidence_missing": True,
                    "raw_evidence_persisted": False,
                },
            )
            if provider_result.assistant_final_response is not None:
                return provider_result
            loop.step("finalize", stop_reason="finalized")
            grounded = {
                "web_search_executed": cognition.web_search_required,
                "citation_validation": "citation.evidence_missing",
                "fabricated": False,
            }
            metadata = {**metadata, "grounding": grounded}
            return _entrypoint_text_result(
                turn_input,
                text="Evidence is missing for this grounded answer, so I cannot answer without fabricating.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
                stage_name="grounded_answer",
            )
        memory_citation_ids = tuple(_memory_citation_id(ref) for ref in tuple(cognition.memory_evidence_refs)[:4])
        citation_ids = tuple(ref.evidence_id for ref in web_refs[:4]) + memory_citation_ids
        provider_result = self._run_provider_answer_path(
            turn_input,
            metadata=metadata,
            cognition=cognition,
            loop=loop,
            stage_name="grounded_answer",
            provider_options={
                "grounded_answer_required": True,
                "grounded_citation_ids": list(citation_ids[:4]),
                "raw_evidence_persisted": False,
            },
        )
        response_text = provider_result.assistant_final_response.text if provider_result.assistant_final_response is not None else ""
        draft = GroundedAnswerDraft(text=response_text or "Evidence is missing for this grounded answer.", citation_ids=_citation_ids_from_text(response_text, allowed=citation_ids))
        validation = validate_grounded_citations(
            draft,
            evidence_refs=web_refs,
            memory_evidence_refs=tuple(cognition.memory_evidence_refs),
            citations_required=True,
        )
        if not validation.valid:
            loop.step("finalize", stop_reason="finalized")
            metadata = {
                **provider_result.metadata,
                "grounding": {
                    "web_search_executed": cognition.web_search_required,
                    "citation_validation": validation.reason_code,
                    "fabricated": False,
                },
            }
            return _entrypoint_text_result(
                turn_input,
                text="Evidence is missing for this grounded answer, so I cannot answer without fabricating.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
                stage_name="grounded_answer",
            )
        metadata = {
            **provider_result.metadata,
            "grounding": {
                "web_search_executed": cognition.web_search_required,
                "citation_validation": validation.reason_code,
                "fabricated": False,
                "evidence_ref_count": len(cognition.evidence_refs),
            },
        }
        return provider_result.model_copy(update={"metadata": metadata})

    def _run_file_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
    ) -> AssistantTurnResult:
        if not self._file_capability_root:
            loop.step("finalize", stop_reason="blocked")
            return _entrypoint_error_result(
                turn_input,
                reason="file_capability_root_required",
                message="File read/list/search requires an explicit configured root.",
                metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
            )
        file_path = _file_path_from_input(turn_input.user_visible_input)
        result = self._run_tool_path(
            turn_input,
            metadata=metadata,
            cognition=cognition,
            loop=loop,
            action="read file",
            capability="file_read",
            resource_type="file",
            capability_id="file.read",
            arguments={"root": self._file_capability_root, "path": file_path, "max_preview_chars": 1200},
        )
        if result.error is not None or result.assistant_final_response is None:
            return result
        safe_result = dict(dict(result.metadata.get("tool", {})).get("result", {})).get("safe_result", {})
        preview = str(dict(safe_result).get("preview", ""))
        return result.model_copy(
            update={
                "assistant_final_response": result.assistant_final_response.model_copy(
                    update={"text": f"File preview from {file_path}: {preview}"}
                )
            }
        )

    def _run_mcp_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
    ) -> AssistantTurnResult:
        return self._run_tool_path(
            turn_input,
            metadata=metadata,
            cognition=cognition,
            loop=loop,
            action="call mcp tool echo",
            capability="mcp_execute",
            resource_type="mcp_tool",
            capability_id="mcp.local.echo",
            arguments={
                "server_id": "local",
                "tool_name": "echo",
                "allowed_server_ids": ["local"],
                "allowed_tool_names": ["echo"],
                "message": "bounded-local-mcp-fixture",
            },
        )

    def _run_memory_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
    ) -> AssistantTurnResult:
        if cognition.memory_evidence_refs:
            return self._run_grounded_path(turn_input, metadata=metadata, cognition=cognition, loop=loop)
        memory_projection = {
            "memory_records_recalled": _included_context_count(cognition, "memory_projection"),
            "memory_store_available": self._memory_loop is not None,
            "raw_memory_content_persisted": False,
        }
        return self._run_provider_answer_path(
            turn_input,
            metadata={**metadata, "memory": memory_projection},
            cognition=cognition,
            loop=loop,
            stage_name="memory",
            provider_options={"memory_context_requested": True, "raw_memory_persisted": False},
        )

    def _run_provider_answer_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
        stage_name: str,
        provider_options: dict[str, object] | None = None,
    ) -> AssistantTurnResult:
        provider_turn_input, provider_instructions = _turn_input_with_prompt(turn_input, cognition)
        effective_provider_options = _structured_provider_options(provider_options)
        result = run_assistant_provider_stage_turn(
            provider_turn_input,
            provider=self._provider,
            model=self._model,
            instructions=_structured_provider_instructions(provider_instructions),
            provider_options=effective_provider_options,
            telemetry_sink=self._trace_reader,
        )
        result = self._apply_structured_output_if_requested(
            result,
            target_contract=str(effective_provider_options.get("structured_output_target_contract") or ""),
        )
        memory_write = self._memory_loop.write_from_turn(turn_input) if self._memory_loop is not None else None
        if result.error is not None:
            loop.step("finalize", stop_reason="failed")
        else:
            loop.step("finalize", stop_reason="finalized")
        combined_metadata = dict(result.metadata)
        combined_metadata.update(
            {
                **metadata,
                "provider_boundary": "provider_worker_process",
                "prompt_fidelity": _prompt_fidelity_projection(cognition, provider_turn_input, provider_instructions),
                "model_answer_stage": stage_name,
                "memory_loop": _memory_write_projection(memory_write),
            }
        )
        return result.model_copy(update={"metadata": _with_loop_metadata(combined_metadata, loop, self._trace_reader, turn_input)})

    def _apply_structured_output_if_requested(
        self,
        result: AssistantTurnResult,
        *,
        target_contract: str,
    ) -> AssistantTurnResult:
        if target_contract != "AssistantFinalResponse" or result.assistant_final_response is None:
            return result
        raw_output_text = result.assistant_final_response.text
        structured = _map_structured_output(
            provider=self._provider,
            schema_version=result.schema_version,
            trace_id=result.trace_id,
            turn_id=result.turn_id,
            target_contract=target_contract,
            raw_output_text=raw_output_text,
        )
        projection = _structured_output_projection(structured)
        metadata = {**result.metadata, "structured_output": projection}
        if structured.get("state") == "valid_structured_result":
            payload = structured.get("parsed_payload")
            try:
                final_response = AssistantFinalResponse.model_validate(payload)
            except Exception:
                projection = {
                    **projection,
                    "state": "invalid_structured_output",
                    "validated": False,
                    "sanitized_error_code": "VALIDATION_FAILED",
                }
                return result.model_copy(
                    update={
                        "assistant_final_response": result.assistant_final_response.model_copy(
                            update={"text": "Provider output could not be validated as structured data."}
                        ),
                        "metadata": {**result.metadata, "structured_output": projection},
                    }
                )
            return result.model_copy(
                update={
                    "assistant_final_response": final_response,
                    "metadata": metadata,
                }
            )
        return result.model_copy(
            update={
                "assistant_final_response": result.assistant_final_response.model_copy(
                    update={"text": "Provider output could not be validated as structured data."}
                ),
                "metadata": metadata,
            }
        )

    def _run_safe_projection_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        loop: "_AgenticLoopProjection",
        route_name: str,
        text: str,
        projection: dict[str, object],
        stop_reason: str = "finalized",
    ) -> AssistantTurnResult:
        if loop.stop_reason == "not_stopped":
            loop.step("finalize", stop_reason=stop_reason)
        return _entrypoint_text_result(
            turn_input,
            text=text,
            metadata=_with_loop_metadata({**metadata, route_name: projection}, loop, self._trace_reader, turn_input),
            stage_name=route_name,
        )

    def _run_approval_path(
        self,
        turn_input: AssistantTurnInput,
        *,
        metadata: dict[str, object],
        cognition: CognitionTurnAssembly,
        loop: "_AgenticLoopProjection",
    ) -> AssistantTurnResult:
        approval_request = _approval_request(turn_input)
        decision = (self._approval_decision or "").strip().lower()
        if self._resume_approval:
            if self._resume_approval != approval_request.approval_request_id:
                loop.step("approval", stop_reason="blocked")
                return _entrypoint_error_result(
                    turn_input,
                    reason="approval_resume_mismatch",
                    message="Capability execution blocked because the approval request does not match this turn.",
                    metadata=_with_loop_metadata(
                        {
                            **metadata,
                            "approval": {
                                "approval_request_id": self._resume_approval,
                                "expected_approval_request_id": approval_request.approval_request_id,
                                "decision": "mismatched",
                            },
                        },
                        loop,
                        self._trace_reader,
                        turn_input,
                    ),
                )
            if decision == "approve":
                loop.step("approval")
                loop.step("tool")
                tool_response = self._tool_executor.execute(
                    turn_input,
                    action="approved risky action confirmation",
                    capability="read",
                    resource_type="approval_resume",
                    capability_id="fake.status",
                    arguments={"approved": True},
                )
                loop.step("finalize", stop_reason="finalized", executed=True)
                metadata = {
                    **metadata,
                    "approval": {"approval_request_id": self._resume_approval, "decision": "approved"},
                    "tool_boundary": "tool_worker_process",
                    "tool": tool_response,
                }
                return _entrypoint_text_result(
                    turn_input,
                    text="Action executed after approval through the policy-controlled worker boundary.",
                    metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
                    stage_name="approval_resume",
                    tool_result_refs=[ToolResultRef(ref_type="tool_result", ref_id=f"{turn_input.turn_id}:approval-resume:result")],
                )
            reason = "approval_cancelled" if decision == "cancel" else "approval_denied"
            loop.step("approval", stop_reason="blocked")
            return _entrypoint_error_result(
                turn_input,
                reason=reason,
                message="Capability execution blocked by approval decision.",
                metadata=_with_loop_metadata(
                    {
                        **metadata,
                        "approval": {
                            "approval_request_id": self._resume_approval,
                            "decision": "cancelled" if decision == "cancel" else "denied",
                        },
                    },
                    loop,
                    self._trace_reader,
                    turn_input,
                ),
            )
        loop.step("approval", stop_reason="waiting_for_human_approval")
        metadata = {
            **metadata,
            "approval_request": approval_request.model_dump(mode="json"),
        }
        return _entrypoint_text_result(
            turn_input,
            text=f"Approval required before continuing. approval_request_id={approval_request.approval_request_id}",
            metadata=_with_loop_metadata(metadata, loop, self._trace_reader, turn_input),
            stage_name="approval_pause",
        )


class _HealthOnlyTurnExecutor:
    def submit_turn(self, turn_input):
        return AssistantTurnResult(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            assistant_final_response=None,
            output_events=[],
            stage_summaries=[],
            provider_turn_refs=[],
            tool_result_refs=[],
            memory_result_refs=[],
            session_result_ref=None,
            error=ErrorEnvelope(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                error_id=f"{turn_input.turn_id}:core-service:turn-executor-unavailable",
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="Core service turn executor is unavailable in health-only mode.",
                recoverable=True,
                source="core_service_entrypoint",
                details={"reason": "health_only_mode"},
            ),
            metadata={},
        )


def _entrypoint_text_result(
    turn_input: AssistantTurnInput,
    *,
    text: str,
    metadata: dict[str, object],
    stage_name: str,
    tool_result_refs: list[ToolResultRef] | None = None,
) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=AssistantFinalResponse(
            schema_version=turn_input.schema_version,
            response_type=AssistantResponseType.TEXT,
            text=text,
            payload_ref=None,
            output_channel_intent=OutputChannelIntent.DEFAULT,
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason=AssistantFinishReason.STOP,
            metadata={},
        ),
        output_events=[],
        stage_summaries=[
            _stage_summary("input_normalization", StageStatus.COMPLETED),
            _stage_summary(stage_name, StageStatus.COMPLETED),
            _stage_summary("final_response_assembly", StageStatus.COMPLETED),
        ],
        provider_turn_refs=[],
        tool_result_refs=list(tool_result_refs or []),
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata=metadata,
    )


def _entrypoint_error_result(
    turn_input: AssistantTurnInput,
    *,
    reason: str,
    message: str,
    metadata: dict[str, object] | None = None,
) -> AssistantTurnResult:
    error_id = f"{turn_input.turn_id}:core-service-entrypoint:{reason}"
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[
            _stage_summary("input_normalization", StageStatus.COMPLETED),
            _stage_summary("intent_preflight", StageStatus.FAILED, error_ref=error_id),
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=ErrorEnvelope(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            error_id=error_id,
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            recoverable=False,
            source="core_service_entrypoint",
            details={"reason": reason},
        ),
        metadata=dict(metadata or {}),
    )


def _stage_summary(
    stage_name: str,
    status: StageStatus,
    *,
    error_ref: str | None = None,
) -> StageSummary:
    return StageSummary(
        stage_name=stage_name,
        status=status,
        started_at=None,
        completed_at=None,
        ref=None,
        error_ref=error_ref,
    )


@dataclass
class _AgenticLoopProjection:
    trace_id: str
    turn_id: str
    max_steps: int
    step_count: int = 0
    executed_count: int = 0
    stop_reason: str = "not_stopped"

    def step(self, _name: str, *, stop_reason: str | None = None, executed: bool = False) -> None:
        if self.step_count < self.max_steps:
            self.step_count += 1
        if executed:
            self.executed_count += 1
        if stop_reason is not None:
            self.stop_reason = stop_reason

    def safe_projection(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "turn_id": self.turn_id,
            "max_steps": self.max_steps,
            "step_count": self.step_count,
            "executed_count": self.executed_count,
            "stop_reason": self.stop_reason,
            "raw_payload_persisted": False,
        }


class _FakeCoreWebSearchProvider:
    provider_name = "fake_search"

    def search(self, query: WebSearchQuery) -> WebSearchGroundingBundle:
        result = WebSearchResult(
            title="Current browser-use release",
            url="local://fake-search/browser-use-release",
            domain="local.fake-search",
            snippet="Current browser-use release evidence.",
            freshness=query.freshness,
        )
        evidence = WebSearchEvidenceRef(
            evidence_id="web.evidence.1",
            source_url=result.url,
            domain=result.domain,
            title=result.title,
            snippet=result.snippet,
            freshness=query.freshness,
        )
        return WebSearchGroundingBundle(
            query=query,
            provider=self.provider_name,
            results=(result,),
            evidence_refs=(evidence,),
        )


class _DemoMemoryEvidenceLink:
    document_id = "demo-memory-doc"
    chunk_id = "chunk:demo:1"
    source_id = "demo-memory-source"
    quote_preview = "Demo memory evidence preview."


class _DemoMemoryNode:
    node_id = "node:demo-memory"
    evidence_links = (_DemoMemoryEvidenceLink(),)


class _DemoMemorySearch:
    results = (_DemoMemoryNode(),)


class _DemoMemoryTreeRuntime:
    def memory_query_with_evidence(self, _query: str) -> _DemoMemorySearch:
        return _DemoMemorySearch()


def _with_loop_metadata(
    metadata: dict[str, object],
    loop: _AgenticLoopProjection,
    trace_reader: InMemoryTraceReader,
    turn_input: AssistantTurnInput,
) -> dict[str, object]:
    _emit_core_event(
        trace_reader,
        turn_input,
        TraceStage.TURN_COMPLETED if loop.stop_reason == "finalized" else TraceStage.TURN_FAILED,
        "Core agentic turn finalized.",
        {"status": loop.stop_reason, "tool_status": "succeeded" if loop.executed_count else "not_executed"},
        level=TraceLevel.INFO if loop.stop_reason == "finalized" else TraceLevel.WARNING,
    )
    trace = trace_reader.read_trace(turn_input.trace_id)
    telemetry_event_count = int((trace or {}).get("event_count", 0) or 0)
    cognition = dict(metadata.get("cognition") or {})
    spine_projection = EndToEndAssistantTurnProjection(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        intent_kind=str(cognition.get("intent_kind", "unknown")),
        context_included_count=int(cognition.get("context_included_count", 0) or 0),
        prompt_section_count=int(cognition.get("prompt_section_count", 0) or 0),
        provider_continuation_ready=loop.stop_reason == "finalized",
        final_response_ready=loop.stop_reason in {"finalized", "waiting_for_human_approval"},
        pending_approval_count=1 if loop.stop_reason == "waiting_for_human_approval" else 0,
        executed_tool_count=loop.executed_count,
        telemetry_event_count=telemetry_event_count,
    )
    return {
        **metadata,
        "assistant_turn_spine_projection": spine_projection.model_dump(mode="json"),
        "agentic_loop": loop.safe_projection(),
        "telemetry": {
            "trace_id": turn_input.trace_id,
            "event_count": telemetry_event_count,
            "raw_payload_persisted": False,
        },
    }


def _emit_core_event(
    trace_reader: InMemoryTraceReader,
    turn_input: AssistantTurnInput,
    stage: TraceStage,
    message: str,
    data: dict[str, object],
    *,
    level: TraceLevel = TraceLevel.INFO,
) -> None:
    trace_reader.emit(
        make_trace_event(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            stage=stage,
            level=level,
            message=message,
            data={"turn_id": turn_input.turn_id, **data},
        )
    )


def _tool_final_text(tool_response: dict[str, object]) -> str:
    result = dict(tool_response.get("result") or {})
    safe_result = dict(result.get("safe_result") or {})
    if "result" in safe_result:
        return f"The calculator result is {safe_result['result']}."
    return "Capability completed with a safe result."


def _calculator_expression(text: str | None) -> str:
    match = re.search(r"\d+(?:\s*[+\-*/]\s*\d+)+", text or "")
    return match.group(0) if match else "0+0"


def _turn_input_with_prompt(
    turn_input: AssistantTurnInput,
    cognition: CognitionTurnAssembly,
) -> tuple[AssistantTurnInput, str | None]:
    system_text = "\n".join(
        section.safe_content
        for section in cognition.prompt_result.plan.sections
        if section.included and section.kind.value in {"system_policy", "approval_state"}
    )
    prompt_text = "\n".join(
        section.safe_content
        for section in cognition.prompt_result.plan.sections
        if section.included and section.kind.value not in {"system_policy", "approval_state"}
    )
    return turn_input.model_copy(update={"user_visible_input": prompt_text}), (system_text or None)


def _approval_request(turn_input: AssistantTurnInput) -> CapabilityApprovalRequest:
    capability_ref = CapabilityRef(kind=CapabilityKind.TOOL, identifier="builtin.approval_resume")
    prompt = ApprovalPrompt(
        schema_version=turn_input.schema_version,
        prompt_id=f"approval-prompt-{turn_input.turn_id}",
        capability_ref=capability_ref,
        user_visible_summary="Approval required for a risky local action.",
        risk_level=ToolRiskLevel.HIGH,
        side_effect_level=ToolSideEffectLevel.DESTRUCTIVE,
    )
    return CapabilityApprovalRequest(
        schema_version=turn_input.schema_version,
        approval_request_id=f"approval-{turn_input.turn_id}",
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        capability_ref=capability_ref,
        prompt=prompt,
    )


def _memory_citation_id(ref: object) -> str:
    chunk_id = str(getattr(ref, "chunk_id", "unknown"))
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", chunk_id).strip("-")
    return f"memory.evidence.{safe}"


def _citation_ids_from_text(text: str, *, allowed: tuple[str, ...]) -> tuple[str, ...]:
    allowed_set = set(allowed)
    found = tuple(re.findall(r"\[((?:web|memory)\.evidence\.[A-Za-z0-9_.:-]+)\]", text))
    return tuple(citation for citation in found if citation in allowed_set)


def _included_context_count(cognition: CognitionTurnAssembly, kind: str) -> int:
    return len(
        [
            source
            for source in cognition.context_projection.included_sources
            if str(dict(source).get("kind", "")) == kind
        ]
    )


def _web_search_provider_from_config(config: CoreServiceEntrypointConfig) -> object | None:
    if config.web_search == "none":
        return None
    if config.web_search == "ddgs":
        return DDGSWebSearchAdapter()
    if config.web_search == "searxng":
        if not config.web_base_url:
            raise ValueError("web_base_url is required for searxng web search")
        return SearXNGWebSearchAdapter(base_url=config.web_base_url)
    if config.web_search == "wikipedia":
        return WikipediaWebSearchAdapter()
    if config.web_search == "multi":
        # Ordered fallback: ddgs then wikipedia then searxng (if configured)
        ordered: list[object] = [DDGSWebSearchAdapter(), WikipediaWebSearchAdapter()]
        if config.web_base_url:
            ordered.append(SearXNGWebSearchAdapter(base_url=config.web_base_url))
        return MultiProviderWebSearch(providers=tuple(ordered))
    return _FakeCoreWebSearchProvider()


def _memory_tree_from_config(config: CoreServiceEntrypointConfig) -> object | None:
    return _DemoMemoryTreeRuntime() if config.demo_memory_evidence else None


def _memory_loop_from_config(config: CoreServiceEntrypointConfig) -> LocalMemoryLoop | None:
    if not config.memory_vault_root:
        return None
    return LocalMemoryLoop.open(vault_root=config.memory_vault_root)


def _skill_loader_from_config(config: CoreServiceEntrypointConfig) -> SkillInstructionLoader | None:
    if not config.skills_root:
        return None
    root = Path(config.skills_root)
    if not root.is_dir():
        return None
    return SkillInstructionLoader(local_skill_root=root)


def _skill_manifests_from_config(config: CoreServiceEntrypointConfig) -> tuple[SkillManifest, ...]:
    if not config.skills_root:
        return ()
    root = Path(config.skills_root)
    if not root.is_dir():
        return ()
    manifests: list[SkillManifest] = []
    for skill_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest = _skill_manifest_from_directory(root, skill_dir)
        if manifest is not None:
            manifests.append(manifest)
    return tuple(manifests)


def _skill_manifest_from_directory(root: Path, skill_dir: Path) -> SkillManifest | None:
    instruction_path = skill_dir / "SKILL.md"
    if not instruction_path.is_file():
        return None
    skill_id = _safe_skill_id(skill_dir.name)
    if not skill_id:
        return None
    try:
        instruction_path.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    description = _skill_description_from_file(instruction_path)
    return SkillManifest(
        schema_version="1",
        skill_ref=SkillRef(skill_id=skill_id),
        display_name=skill_id.replace("-", " ").replace("_", " ").title(),
        description=description,
        instruction_ref=SkillResourceRef(
            kind=SkillResourceKind.INSTRUCTION,
            uri=f"local://skills/{skill_id}/SKILL.md",
        ),
    )


def _skill_description_from_file(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace")[:600].splitlines():
            text = line.strip(" #\t")
            if text:
                return text[:240]
    except OSError:
        return "Local skill instruction."
    return "Local skill instruction."


def _safe_skill_id(value: str) -> str | None:
    if not value or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_" for character in value):
        return None
    return value


def _prompt_fidelity_projection(
    cognition: CognitionTurnAssembly,
    provider_turn_input: AssistantTurnInput,
    provider_instructions: str | None,
) -> dict[str, object]:
    sections = tuple(section.safe_content for section in cognition.prompt_result.plan.sections if section.included)
    joined = "\n".join(sections)
    return {
        "system_channel_used": bool(provider_instructions),
        "user_channel_used": bool(provider_turn_input.user_visible_input),
        "adaptive_budget": cognition.prompt_result.plan.route_profile.total_context_budget,
        "real_question_present": "User asked:" in joined,
        "memory_content_present": "Recalled memory" in joined,
        "evidence_content_present": "Evidence" in joined or "evidence" in joined,
        "raw_prompt_persisted": False,
    }


def _structured_provider_options(
    provider_options: dict[str, object] | None,
) -> dict[str, object]:
    options = dict(provider_options or {})
    options.setdefault("structured_output_target_contract", "AssistantFinalResponse")
    options.setdefault("structured_output_required", True)
    options.setdefault("raw_provider_output_persisted", False)
    return options


def _structured_provider_instructions(instructions: str | None) -> str:
    guidance = (
        "Return only a JSON object matching AssistantFinalResponse with fields: "
        "schema_version, response_type, text, payload_ref, output_channel_intent, "
        "safe_for_display, safe_for_speech, memory_write_candidate_hint, finish_reason, metadata. "
        "Do not wrap the JSON in markdown."
    )
    return f"{instructions}\n\n{guidance}" if instructions else guidance


def _map_structured_output(
    *,
    provider: object,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    raw_output_text: str,
) -> dict[str, object]:
    mapper = getattr(provider, "map_raw_output_to_structured_result", None)
    if callable(mapper):
        try:
            mapped = mapper(
                schema_version=schema_version,
                trace_id=trace_id,
                turn_id=turn_id,
                target_contract=target_contract,
                raw_output_text=raw_output_text,
            )
            if isinstance(mapped, dict):
                return dict(mapped)
            if hasattr(mapped, "model_dump"):
                return dict(mapped.model_dump(mode="json"))
        except Exception:
            pass
    result = validate_raw_structured_output(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        target_contract=target_contract,
        raw_output_text=raw_output_text,
        target_model=AssistantFinalResponse,
        include_raw_preview=False,
    )
    return dict(result.model_dump(mode="json"))


def _structured_output_projection(structured: dict[str, object]) -> dict[str, object]:
    state = str(structured.get("state") or "invalid_structured_output")
    return {
        "requested": True,
        "target_contract": str(structured.get("target_contract") or "AssistantFinalResponse"),
        "state": state,
        "validated": state == "valid_structured_result",
        "sanitized_error_code": structured.get("sanitized_error_code"),
        "raw_output_persisted": False,
        "raw_preview_present": bool(structured.get("raw_preview")),
    }


def _memory_write_projection(memory_write: object | None) -> dict[str, object]:
    if memory_write is None:
        return {"enabled": False, "raw_transcript_persisted": False}
    record = getattr(memory_write, "record", None)
    audit = getattr(memory_write, "policy_audit", None)
    return {
        "enabled": True,
        "written": bool(getattr(memory_write, "written", False)),
        "policy_decision": str(getattr(audit, "decision", "")),
        "memory_ref": getattr(getattr(record, "memory_ref", None), "ref_id", None),
        "revised_memory_ref": getattr(memory_write, "revised_memory_ref", None),
        "raw_transcript_persisted": False,
    }


def _intent_plan_kinds(intent_plan: object) -> tuple[str, ...]:
    steps = tuple(getattr(intent_plan, "steps", ()) or ())
    return tuple(
        str(getattr(getattr(step, "intent_kind", ""), "value", getattr(step, "intent_kind", "")))
        for step in steps
    )


def _intent_plan_projection(intent_plan: object) -> dict[str, object]:
    steps = tuple(getattr(intent_plan, "steps", ()) or ())
    return {
        "primary_intent": str(getattr(getattr(intent_plan, "primary_intent", ""), "value", getattr(intent_plan, "primary_intent", ""))),
        "step_count": len(steps),
        "step_kinds": [
            str(getattr(getattr(step, "intent_kind", ""), "value", getattr(step, "intent_kind", "")))
            for step in steps
        ],
        "raw_payload_persisted": False,
    }


def _file_path_from_input(text: str | None) -> str:
    value = (text or "").strip()
    match = re.search(r"(?:read|inspect)\s+file\s+(.+)$", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().strip("\"'")
    return value.strip().strip("\"'") or "."


def _fixed_intent_classifier(classification: object) -> Callable[[object], object]:
    projection = dict(classification)

    def classify(request: object) -> object:
        from packages.capability_runtime import ToolRiskLevel
        from packages.intent_runtime.models import IntentKind, IntentRiskSignal, classification_from_kind

        selected = dict(projection.get("selected_intent", {}))
        kind = IntentKind(str(selected.get("intent_kind", "provider_simple_chat")))
        risk = IntentRiskSignal(str(projection.get("risk_signal", "none")))
        score = {"high": 0.9, "medium": 0.6, "low": 0.3}.get(str(projection.get("confidence_bucket", "medium")), 0.6)
        risk_level = ToolRiskLevel.HIGH if risk == IntentRiskSignal.RISKY_ACTION_REQUESTED else ToolRiskLevel.SAFE
        return classification_from_kind(
            request,
            kind=kind,
            score=score,
            risk_signal=risk,
            risk_level=risk_level,
            reason_code=str(projection.get("route_reason_code", "intent.worker_projection")),
            backend_name="intent_worker_projection",
        )

    return classify


def _session_projection(
    registry: CurrentProcessSessionRegistry,
    turn_input: AssistantTurnInput,
) -> dict[str, object]:
    """Return safe session state for metadata; never includes transcript."""
    if turn_input.session_ref is None:
        return {"session_ref_present": False, "transcript_persisted": False}
    proj = registry.read_session_projection(turn_input.session_ref)
    if proj is None:
        return {
            "session_ref_present": True,
            "session_ref_id": turn_input.session_ref.ref_id,
            "turn_count": 0,
            "transcript_persisted": False,
        }
    return proj.safe_projection()


def _run_provider_selection(
    runtime: ProviderSelectionRuntime | None,
    turn_input: AssistantTurnInput,
    *,
    default_provider: str,
    default_model: str,
) -> tuple[str, str, dict[str, object]]:
    """Run provider selection; fall back to defaults if disabled or error."""
    if runtime is None:
        return default_provider, default_model, {"provider_selection_enabled": False}
    try:
        request = ProviderSelectionRequest(
            trace_id=turn_input.trace_id,
            requirement=ModelCapabilityRequirement(
                requested_capability="assistant_turn",
                tool_calling_required=False,
                min_context_length=0,
                local_preferred=True,
                cost_preference="balanced",
            ),
            autonomy_policy=_TURN_AUTONOMY_POLICY,
            fallback_policy=ProviderFallbackPolicy(
                provider_fallback_enabled=True,
                side_effect_retry_requires_policy=True,
            ),
            retry_policy=ProviderRetryPolicy(max_retries=1, retry_side_effect_tools=False),
        )
        decision = runtime.select(request)
        proj = decision.safe_projection().model_dump(mode="json")
        proj["provider_selection_enabled"] = True
        return decision.selected.provider_id, decision.selected.model, proj
    except Exception:
        return default_provider, default_model, {"provider_selection_enabled": False, "selection_error": True}


def _run_learning_hook(
    pipeline: LearningPipelineRunner | None,
    turn_input: AssistantTurnInput,
    *,
    succeeded: bool,
    intent_kind: str,
) -> dict[str, object]:
    """Record a safe post-turn feedback event; all candidates are review-required."""
    if pipeline is None:
        return {"learning_enabled": False}
    try:
        event = FeedbackEvent(
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            signal_kind=FeedbackSignalKind.TOOL_OUTCOME,
            payload=ToolOutcomeFeedback(
                tool_ref=f"intent.{intent_kind}",
                succeeded=succeeded,
                outcome_reason="turn_completed" if succeeded else "turn_failed",
            ),
        )
        summary = pipeline.ingest_and_run((event,))
        proj = summary.safe_projection().model_dump(mode="json")
        proj["learning_enabled"] = True
        return proj
    except Exception:
        return {"learning_enabled": False, "learning_error": True}


def _persist_trace_events(
    store: PersistentTraceStore | None,
    reader: InMemoryTraceReader,
    trace_id: str,
) -> None:
    """Write safe trace events from in-memory reader to persistent store."""
    if store is None:
        return
    try:
        raw_events = reader._events_by_trace_id.get(trace_id, ())  # type: ignore[attr-defined]
        for event in raw_events:
            try:
                store.emit(event)
            except Exception:
                pass
    except Exception:
        pass


def _create_foundation_turn_executor(
    *,
    trace_reader: InMemoryTraceReader,
) -> _CoreServiceFoundationTurnExecutor:
    from packages.runtime_composition import create_local_api_fake_turn_handler

    return _CoreServiceFoundationTurnExecutor(
        foundation_turn_handler=create_local_api_fake_turn_handler(
            telemetry_sink=trace_reader
        ),
        model=DEFAULT_FOUNDATION_MODEL,
    )


def create_core_service(
    *,
    trace_reader: InMemoryTraceReader | None = None,
    enable_foundation_turns: bool = True,
    config: CoreServiceEntrypointConfig | None = None,
) -> CoreService:
    effective_trace_reader = trace_reader or InMemoryTraceReader()
    effective_config = config or CoreServiceEntrypointConfig()
    executor = (
        _create_turn_executor(
            trace_reader=effective_trace_reader,
            config=effective_config,
        )
        if enable_foundation_turns
        else _HealthOnlyTurnExecutor()
    )
    return CoreService(turn_executor=executor)


def _create_turn_executor(
    *,
    trace_reader: InMemoryTraceReader,
    config: CoreServiceEntrypointConfig,
) -> object:
    # NOTE: intent preflight + Tool/Provider worker routing only runs when a
    # worker-backed provider is selected. The default "fake" provider uses the
    # in-process foundation executor and intentionally skips intent preflight.
    if config.provider == "fake":
        return _create_foundation_turn_executor(trace_reader=trace_reader)
    provider_name = (
        config.worker_provider
        if config.provider == "provider_worker"
        else config.provider
    )
    effective_name = provider_name or "fake"
    selection_runtime = ProviderSelectionRuntime(
        candidates=(
            ProviderCandidate(
                provider_id=effective_name,
                model=config.foundation_model,
                supports_tools=False,
                context_length=4096,
                locality="local",
                healthy=True,
                cost_tier="free",
            ),
        )
    )
    learning_store = LearningCandidateStore()
    learning_pipeline = LearningPipelineRunner(
        store=learning_store,
        autonomy_policy=_TURN_AUTONOMY_POLICY,
        loop=LearningLoop.default(),
    )
    persistent_store = _persistent_store_from_config(config)
    skill_loader = _skill_loader_from_config(config)
    return _CoreServiceProviderWorkerTurnExecutor(
        provider_name=effective_name,
        model=config.foundation_model,
        trace_reader=trace_reader,
        web_search_provider=_web_search_provider_from_config(config),
        memory_tree_runtime=_memory_tree_from_config(config),
        memory_loop=_memory_loop_from_config(config),
        file_capability_root=config.file_capability_root,
        resume_approval=config.resume_approval,
        approval_decision=config.approval_decision,
        base_url=config.base_url,
        timeout_seconds=config.timeout_seconds,
        session_registry=CurrentProcessSessionRegistry(),
        provider_selection_runtime=selection_runtime,
        learning_pipeline=learning_pipeline,
        persistent_trace_store=persistent_store,
        skill_manifests=_skill_manifests_from_config(config),
        skill_loader=skill_loader,
    )


def _persistent_store_from_config(
    config: CoreServiceEntrypointConfig,
) -> PersistentTraceStore | None:
    """Create PersistentTraceStore from config; returns None when path is empty."""
    raw_path = (config.telemetry_store_path or "").strip()
    if not raw_path:
        return None
    try:
        return PersistentTraceStore(trace_file_path=Path(raw_path))
    except Exception:
        return None


def create_core_service_app(
    *,
    config: CoreServiceEntrypointConfig,
    trace_reader: InMemoryTraceReader | None = None,
) -> tuple[Any, CoreService]:
    service = create_core_service(trace_reader=trace_reader, config=config)
    service.start()
    persistent_store = _persistent_store_from_config(config)
    effective_reader: Any = _CompositeTraceReader(
        in_memory=trace_reader or InMemoryTraceReader(),
        persistent=persistent_store,
    )
    app = create_health_version_api_app(
        service,
        turn_handler=lambda request: service.submit_turn(request.assistant_turn_input),
        trace_reader=effective_reader,
        local_auth_token=config.local_auth_token,
    )
    return app, service


class _CompositeTraceReader:
    """Reads traces from persistent store first, falling back to in-memory."""

    def __init__(
        self,
        *,
        in_memory: InMemoryTraceReader,
        persistent: PersistentTraceStore | None,
    ) -> None:
        self._in_memory = in_memory
        self._persistent = persistent

    def read_trace(self, trace_id: str) -> dict[str, Any] | None:
        if self._persistent is not None:
            try:
                result = self._persistent.read_trace(trace_id)
                if result is not None:
                    return result
            except Exception:
                pass
        return self._in_memory.read_trace(trace_id)


def health_once_payload() -> dict[str, object]:
    service = create_core_service(enable_foundation_turns=False)
    service.start()
    try:
        return {
            "health": service.get_health().model_dump(mode="json"),
            "version": service.get_version().model_dump(mode="json"),
        }
    finally:
        service.shutdown()


def run_health_once() -> int:
    print(json.dumps(health_once_payload(), sort_keys=True))
    return 0


def run_core_service(
    *,
    config: CoreServiceEntrypointConfig | None = None,
    server_factory: ServerFactory = make_server,
) -> int:
    effective_config = config or CoreServiceEntrypointConfig()
    if not effective_config.allow_remote:
        _validate_loopback(effective_config.host)
    local_api_config = effective_config.local_api_config()
    if not effective_config.local_auth_token or not effective_config.local_auth_token.strip():
        raise ValueError("local_auth_token is required for Core service startup")

    trace_reader = InMemoryTraceReader()
    app, service = create_core_service_app(
        config=effective_config,
        trace_reader=trace_reader,
    )
    httpd = server_factory(local_api_config.host, local_api_config.port, app)
    print(
        STARTUP_MESSAGE_PREFIX
        + json.dumps(
            {
                "base_url": f"http://{local_api_config.host}:{local_api_config.port}",
                "auth_required": True,
                "auth_token_present": True,
                "token_value_logged": False,
                "service": "marvex-core-service",
                "provider": effective_config.provider,
            },
            sort_keys=True,
        )
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        service.shutdown()
        httpd.server_close()
    return 0


def run_turn_once(
    *,
    text: str,
    config: CoreServiceEntrypointConfig,
    trace_id: str,
    turn_id: str,
    session_id: str | None = None,
) -> int:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id=f"{turn_id}:input",
        text=text,
        timestamp=datetime.now(UTC),
        session_id=session_id,
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id=turn_id,
        input_event=event,
    )
    trace_reader = InMemoryTraceReader()
    service = create_core_service(config=config, trace_reader=trace_reader)
    service.start()
    try:
        result = service.submit_turn(turn_input)
    finally:
        service.shutdown()
    print(result.model_dump_json())
    return 0


def _validate_loopback(host: str) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("host must be loopback-only")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Core service local entrypoint. Defaults to loopback 127.0.0.1; "
            "pass --allow-remote to bind a non-loopback host (bearer auth required)."
        )
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--health-once",
        action="store_true",
        help="Start CoreService in-process, print health/version JSON, then shut down.",
    )
    mode.add_argument(
        "--serve",
        action="store_true",
        help="Start the local Core service API on 127.0.0.1.",
    )
    mode.add_argument(
        "--turn-once",
        metavar="TEXT",
        help="Run one local Core turn and print an AssistantTurnResult JSON envelope.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help="Bind host. Defaults to 127.0.0.1. Use --allow-remote for non-loopback.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Permit binding a non-loopback host. Requires --local-auth-token.",
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        type=int,
        help="Loopback bind port. Defaults to 8765.",
    )
    parser.add_argument(
        "--local-auth-token",
        default=None,
        help="Bearer token required for protected local Core service endpoints.",
    )
    parser.add_argument(
        "--provider",
        choices=("fake", "lmstudio_responses", "litellm", "provider_worker"),
        default=DEFAULT_PROVIDER,
        help="Provider selection for turn execution. Defaults to fake.",
    )
    parser.add_argument(
        "--worker-provider",
        default=None,
        help="ProviderWorker target provider when --provider provider_worker is used.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_FOUNDATION_MODEL,
        help="Model name to place on provider requests.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL for local provider-compatible endpoints.",
    )
    parser.add_argument(
        "--web-search",
        choices=("fake", "none", "ddgs", "searxng", "wikipedia", "multi"),
        default="fake",
        help="Web search provider for grounded runtime turns. Defaults to deterministic fake. 'wikipedia' uses the free MediaWiki API (no key). 'multi' tries ddgs then wikipedia then searxng-if-configured.",
    )
    parser.add_argument(
        "--web-base-url",
        default=None,
        help="Base URL for SearXNG when --web-search searxng is selected.",
    )
    parser.add_argument(
        "--demo-memory-evidence",
        action="store_true",
        help="Inject deterministic safe memory-tree evidence for local runtime smokes.",
    )
    parser.add_argument(
        "--memory-vault-root",
        default=".marvex-memory",
        help="Local root for derived memory SQLite index and Obsidian-compatible wiki vault. Defaults to .marvex-memory so memory recall/write is on by default; pass an empty string to disable.",
    )
    parser.add_argument(
        "--file-capability-root",
        default=None,
        help="Explicit local root for read-only file read/list/search capabilities.",
    )
    parser.add_argument(
        "--skills-root",
        default=None,
        help="Optional local root containing safe skill directories with SKILL.md files.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Session id for --turn-once; threads session_ref through memory recall.",
    )
    parser.add_argument(
        "--telemetry-store-path",
        default=None,
        help=(
            "Path for safe persistent telemetry JSONL file "
            "(e.g. .marvex-telemetry/traces.jsonl; omit to disable persistence)."
        ),
    )
    parser.add_argument(
        "--resume-approval",
        default=None,
        help="Approval request id to resume for the same trace_id and turn_id.",
    )
    parser.add_argument(
        "--approval-decision",
        choices=("approve", "deny", "cancel"),
        default=None,
        help="Decision to apply with --resume-approval.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Provider request timeout in seconds.",
    )
    parser.add_argument(
        "--trace-id",
        default="trace-core-provider-worker-turn-once",
        help="Trace id for --turn-once.",
    )
    parser.add_argument(
        "--turn-id",
        default="turn-core-provider-worker-turn-once",
        help="Turn id for --turn-once.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.health_once:
        return run_health_once()
    config = CoreServiceEntrypointConfig(
        host=args.host,
        port=args.port,
        local_auth_token=args.local_auth_token,
        foundation_model=args.model,
        provider=args.provider,
        worker_provider=args.worker_provider,
        base_url=args.base_url,
        web_search=args.web_search,
        web_base_url=args.web_base_url,
        demo_memory_evidence=args.demo_memory_evidence,
        memory_vault_root=args.memory_vault_root,
        file_capability_root=args.file_capability_root,
        resume_approval=args.resume_approval,
        approval_decision=args.approval_decision,
        timeout_seconds=args.timeout,
        allow_remote=args.allow_remote,
        telemetry_store_path=args.telemetry_store_path or None,
        skills_root=args.skills_root,
    )
    if args.turn_once is not None:
        return run_turn_once(
            text=args.turn_once,
            config=config,
            trace_id=args.trace_id,
            turn_id=args.turn_id,
            session_id=args.session_id,
        )
    try:
        return run_core_service(
            config=config
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
