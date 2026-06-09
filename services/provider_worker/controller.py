from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from packages.capability_runtime import AutonomyMode, AutonomyPolicy
from packages.contracts import (
    AssistantFinalResponse,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    HealthCheck,
    HealthStatus,
    ProviderRequest,
    ProviderResponse,
    VersionInfo,
)
from packages.provider_runtime import ProviderRuntimeConfig, create_provider
from packages.provider_runtime.provider_runtime import map_provider_raw_output_to_structured_result
from packages.provider_structured_output import validate_raw_structured_output
from packages.provider_selection_runtime import (
    ModelCapabilityRequirement,
    ProviderCandidate,
    ProviderFallbackPolicy,
    ProviderRetryPolicy,
    ProviderSelectionRequest,
    ProviderSelectionRuntime,
)

from .models import (
    SCHEMA_VERSION,
    SERVICE_NAME,
    SERVICE_VERSION,
    ProviderWorkerCommandResult,
    ProviderWorkerConfig,
    ProviderWorkerSelectionProjection,
)


ProviderFactory = Callable[[ProviderRuntimeConfig], object]
_CONCRETE_PROVIDER_IDS = frozenset({"fake", "lmstudio_responses", "litellm", "openrouter"})


class ProviderWorkerState(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class ProviderWorkerController:
    config: ProviderWorkerConfig = field(default_factory=ProviderWorkerConfig)
    provider_factory: ProviderFactory = create_provider

    def __post_init__(self) -> None:
        self._state = ProviderWorkerState.INITIALIZED
        self._started_at = datetime.now(UTC)

    def start(self, *, trace_id: str = "provider-worker-start") -> ProviderWorkerCommandResult:
        self._state = ProviderWorkerState.RUNNING
        return self._result(command="start", ok=True, trace_id=trace_id)

    def stop(self, *, trace_id: str = "provider-worker-stop") -> ProviderWorkerCommandResult:
        self._state = ProviderWorkerState.STOPPING
        return self._result(command="stop", ok=True, trace_id=trace_id)

    def status(self, *, trace_id: str = "provider-worker-status") -> ProviderWorkerCommandResult:
        return self._result(command="status", ok=True, trace_id=trace_id)

    def health(self) -> HealthCheck:
        return HealthCheck(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            status=HealthStatus.OK
            if self._state != ProviderWorkerState.STOPPING
            else HealthStatus.STOPPING,
            version=SERVICE_VERSION,
            uptime_seconds=max(0.0, (datetime.now(UTC) - self._started_at).total_seconds()),
            dependencies={
                "provider_runtime": {"configured": True},
                "accepted_providers": list(self.config.provider_candidates),
            },
        )

    def version(self) -> VersionInfo:
        return VersionInfo(
            schema_version=SCHEMA_VERSION,
            service=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            contract_versions={
                "ProviderWorker": SCHEMA_VERSION,
                "ProviderRequest": SCHEMA_VERSION,
                "ProviderResponse": SCHEMA_VERSION,
                "ErrorEnvelope": SCHEMA_VERSION,
                "HealthCheck": SCHEMA_VERSION,
                "VersionInfo": SCHEMA_VERSION,
            },
            build={},
        )

    def send(
        self,
        *,
        provider_name: str,
        request: ProviderRequest,
        base_url: str | None = None,
        provider_mode: str | None = None,
        timeout_seconds: float | None = None,
        lmstudio_responses_api_key: str | None = None,
        litellm_api_key: str | None = None,
        openrouter_api_key: str | None = None,
    ) -> ProviderWorkerCommandResult:
        decision_projection: ProviderWorkerSelectionProjection | None = None
        try:
            provider_ids, decision_projection, retry_allowed = self._selected_provider_ids(
                requested_provider=provider_name,
                request=request,
            )
        except Exception:
            return self._error_result(
                command="send",
                trace_id=request.trace_id,
                error=self._error(
                    request,
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                    reason="provider_unavailable",
                    message="Provider unavailable.",
                    recoverable=True,
                ),
            )

        last_response: ProviderResponse | None = None
        last_error: ErrorEnvelope | None = None
        retry_count = self.config.max_retries if retry_allowed else 0
        for candidate in provider_ids:
            for _attempt in range(retry_count + 1):
                try:
                    provider = self.provider_factory(
                        _provider_runtime_config(
                            provider_name=candidate,
                            base_url=base_url,
                            provider_mode=provider_mode,
                            timeout_seconds=timeout_seconds,
                            lmstudio_responses_api_key=lmstudio_responses_api_key,
                            litellm_api_key=litellm_api_key,
                            openrouter_api_key=openrouter_api_key,
                        )
                    )
                    response = provider.send(request)  # type: ignore[attr-defined]
                except Exception as exc:
                    last_error = self._exception_error(request, exc)
                    if last_error.code in {
                        ErrorCode.PROVIDER_TIMEOUT,
                        ErrorCode.PROVIDER_UNAVAILABLE,
                    }:
                        break
                    continue

                safe_response = self._safe_response(response)
                if self._is_success(safe_response):
                    return self._result(
                        command="send",
                        ok=True,
                        trace_id=request.trace_id,
                        response=safe_response,
                        selection=decision_projection,
                        metadata={"payload_persisted": False},
                    )
                last_response = safe_response
                last_error = safe_response.error or self._error(
                    request,
                    code=ErrorCode.PROVIDER_ERROR,
                    reason="provider_error",
                    message="Provider failed.",
                    recoverable=True,
                )

        if last_response is not None and last_response.error is not None:
            return self._error_result(
                command="send",
                trace_id=request.trace_id,
                error=last_response.error,
                response=last_response,
                selection=decision_projection,
            )
        return self._error_result(
            command="send",
            trace_id=request.trace_id,
            error=last_error
            or self._error(
                request,
                code=ErrorCode.PROVIDER_UNAVAILABLE,
                reason="provider_unavailable",
                message="Provider unavailable.",
                recoverable=True,
            ),
            response=last_response,
            selection=decision_projection,
        )

    def stream(
        self,
        *,
        provider_name: str,
        request: ProviderRequest,
        base_url: str | None = None,
        provider_mode: str | None = None,
        timeout_seconds: float | None = None,
        lmstudio_responses_api_key: str | None = None,
        litellm_api_key: str | None = None,
        openrouter_api_key: str | None = None,
    ):
        """Drive a provider stream, yielding frame dicts for the JSONL transport.

        Yields ``{"type":"delta","text":...}`` per token, then a terminal
        ``{"type":"final","response":<ProviderResponse json>}`` (carrying the
        authoritative text + any tool calls) or ``{"type":"error","message":...}``.
        Best-effort: any failure yields an error frame so the caller falls back
        to the non-streaming ``send`` path.
        """

        from packages.contracts.streaming_models import (
            StreamCompleted,
            StreamError,
            StreamStarted,
            StreamTextDelta,
        )

        try:
            provider = self.provider_factory(
                _provider_runtime_config(
                    provider_name=provider_name,
                    base_url=base_url,
                    provider_mode=provider_mode,
                    timeout_seconds=timeout_seconds,
                    lmstudio_responses_api_key=lmstudio_responses_api_key,
                    litellm_api_key=litellm_api_key,
                    openrouter_api_key=openrouter_api_key,
                )
            )
            stream_send = getattr(provider, "stream_send", None)
            if stream_send is None:
                yield {"type": "error", "message": "Provider does not support streaming."}
                return
            accumulated: list[str] = []
            for event in stream_send(request):
                if isinstance(event, StreamStarted):
                    yield {"type": "response", "response_id": event.response_id}
                elif isinstance(event, StreamTextDelta):
                    if event.text:
                        accumulated.append(event.text)
                        yield {"type": "delta", "text": event.text}
                elif isinstance(event, StreamCompleted):
                    joined = "".join(accumulated)
                    text = event.output_text if len(event.output_text) >= len(joined) else joined
                    response = self._safe_response(
                        ProviderResponse(
                            schema_version=request.schema_version,
                            trace_id=request.trace_id,
                            turn_id=request.turn_id,
                            provider_name=provider_name,
                            response_id=event.response_id,
                            output_text=text,
                            finish_reason=_stream_finish_reason(event.finish_reason),
                            usage=dict(event.usage),
                            raw_metadata=dict(event.raw_metadata),
                            error=None,
                            tool_calls=event.tool_calls,
                        )
                    )
                    yield {"type": "final", "response": response.model_dump(mode="json")}
                    return
                elif isinstance(event, StreamError):
                    yield {"type": "error", "message": "Provider stream failed."}
                    return
            # Stream ended without a terminal event: treat accumulated as final.
            response = self._safe_response(
                ProviderResponse(
                    schema_version=request.schema_version,
                    trace_id=request.trace_id,
                    turn_id=request.turn_id,
                    provider_name=provider_name,
                    response_id=None,
                    output_text="".join(accumulated),
                    finish_reason=FinishReason.STOP,
                    usage={},
                    raw_metadata={},
                    error=None,
                )
            )
            yield {"type": "final", "response": response.model_dump(mode="json")}
        except Exception:
            yield {"type": "error", "message": "Provider stream failed."}

    def cancel_response(
        self,
        *,
        provider_name: str,
        trace_id: str,
        response_id: str,
        base_url: str | None = None,
        provider_mode: str | None = None,
        timeout_seconds: float | None = None,
        lmstudio_responses_api_key: str | None = None,
        litellm_api_key: str | None = None,
        openrouter_api_key: str | None = None,
    ) -> ProviderWorkerCommandResult:
        return self._response_control(
            command="cancel_response",
            provider_name=provider_name,
            trace_id=trace_id,
            response_id=response_id,
            base_url=base_url,
            provider_mode=provider_mode,
            timeout_seconds=timeout_seconds,
            lmstudio_responses_api_key=lmstudio_responses_api_key,
            litellm_api_key=litellm_api_key,
            openrouter_api_key=openrouter_api_key,
        )

    def delete_response(
        self,
        *,
        provider_name: str,
        trace_id: str,
        response_id: str,
        base_url: str | None = None,
        provider_mode: str | None = None,
        timeout_seconds: float | None = None,
        lmstudio_responses_api_key: str | None = None,
        litellm_api_key: str | None = None,
        openrouter_api_key: str | None = None,
    ) -> ProviderWorkerCommandResult:
        return self._response_control(
            command="delete_response",
            provider_name=provider_name,
            trace_id=trace_id,
            response_id=response_id,
            base_url=base_url,
            provider_mode=provider_mode,
            timeout_seconds=timeout_seconds,
            lmstudio_responses_api_key=lmstudio_responses_api_key,
            litellm_api_key=litellm_api_key,
            openrouter_api_key=openrouter_api_key,
        )

    def _response_control(
        self,
        *,
        command: str,
        provider_name: str,
        trace_id: str,
        response_id: str,
        base_url: str | None,
        provider_mode: str | None,
        timeout_seconds: float | None,
        lmstudio_responses_api_key: str | None,
        litellm_api_key: str | None,
        openrouter_api_key: str | None,
    ) -> ProviderWorkerCommandResult:
        cleaned = response_id.strip()
        if not cleaned:
            return self._error_result(
                command=command,
                trace_id=trace_id,
                error=ErrorEnvelope(
                    schema_version=SCHEMA_VERSION,
                    trace_id=trace_id,
                    error_id=f"{trace_id}:provider-worker:invalid_response_id",
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Provider response id is required.",
                    recoverable=False,
                    source="provider_worker",
                    details={"reason": "invalid_response_id"},
                ),
            )
        try:
            provider = self.provider_factory(
                _provider_runtime_config(
                    provider_name=provider_name,
                    base_url=base_url,
                    provider_mode=provider_mode,
                    timeout_seconds=timeout_seconds,
                    lmstudio_responses_api_key=lmstudio_responses_api_key,
                    litellm_api_key=litellm_api_key,
                    openrouter_api_key=openrouter_api_key,
                )
            )
            method_name = "cancel_response" if command == "cancel_response" else "delete_response"
            method = getattr(provider, method_name)
            result = method(cleaned)
        except Exception:
            return self._error_result(
                command=command,
                trace_id=trace_id,
                error=ErrorEnvelope(
                    schema_version=SCHEMA_VERSION,
                    trace_id=trace_id,
                    error_id=f"{trace_id}:provider-worker:{command}_failed",
                    code=ErrorCode.PROVIDER_ERROR,
                    message="Provider response control request failed.",
                    recoverable=True,
                    source="provider_worker",
                    details={"reason": f"{command}_failed"},
                ),
            )
        return self._result(
            command=command,
            ok=True,
            trace_id=trace_id,
            metadata={
                "response_control": result if isinstance(result, dict) else {},
                "response_id": cleaned,
                "payload_persisted": False,
            },
        )

    def _selected_provider_ids(
        self,
        *,
        requested_provider: str,
        request: ProviderRequest,
    ) -> tuple[list[str], ProviderWorkerSelectionProjection, bool]:
        candidates = self._candidate_ids(requested_provider)
        runtime = ProviderSelectionRuntime(
            candidates=tuple(self._candidate(provider_id, request) for provider_id in candidates)
        )
        decision = runtime.select(
            ProviderSelectionRequest(
                trace_id=request.trace_id,
                requirement=ModelCapabilityRequirement(
                    requested_capability="provider_send",
                    min_context_length=1,
                    local_preferred=True,
                ),
                autonomy_policy=AutonomyPolicy.for_mode(AutonomyMode.AUTO_MARVEX),
                fallback_policy=ProviderFallbackPolicy(
                    provider_fallback_enabled=self.config.fallback_enabled
                ),
                retry_policy=ProviderRetryPolicy(max_retries=self.config.max_retries),
            )
        )
        selected = [decision.selected.provider_id]
        selected.extend(candidate.provider_id for candidate in decision.fallback_candidates)
        projection = decision.safe_projection()
        return (
            selected,
            ProviderWorkerSelectionProjection(
                selected_provider_id=projection.selected_provider_id,
                fallback_provider_ids=projection.fallback_provider_ids,
                rejected_provider_ids=projection.rejected_provider_ids,
                fallback_allowed=projection.fallback_allowed,
                retry_allowed=projection.retry_allowed,
            ),
            decision.retry_allowed,
        )

    def _candidate_ids(self, requested_provider: str) -> tuple[str, ...]:
        if requested_provider in _CONCRETE_PROVIDER_IDS:
            return (requested_provider,)
        if requested_provider in self.config.provider_candidates:
            return tuple(
                [requested_provider]
                + [
                    candidate
                    for candidate in self.config.provider_candidates
                    if candidate != requested_provider
                ]
            )
        return (requested_provider,)

    def _candidate(self, provider_id: str, request: ProviderRequest) -> ProviderCandidate:
        return ProviderCandidate(
            provider_id=provider_id,
            model=request.model,
            supports_tools=provider_id in {"litellm", "lmstudio_responses", "openrouter"},
            context_length=128000,
            locality="cloud" if provider_id in {"litellm", "openrouter"} else "local",
            healthy=provider_id not in self.config.unavailable_provider_ids,
            cost_tier="low" if provider_id in {"litellm", "openrouter"} else "free",
        )

    def _is_success(self, response: ProviderResponse) -> bool:
        return (
            response.error is None
            and response.finish_reason != FinishReason.ERROR
            and (bool(response.output_text.strip()) or bool(response.tool_calls))
        )

    def _safe_response(self, response: ProviderResponse) -> ProviderResponse:
        return response.model_copy(
            update={"raw_metadata": self._safe_metadata(response.raw_metadata)}
        )

    def _safe_metadata(self, metadata: dict[str, object]) -> dict[str, object]:
        safe: dict[str, object] = {}
        for key, value in metadata.items():
            lowered = key.lower()
            if any(token in lowered for token in ("raw", "secret", "token", "key")):
                continue
            if isinstance(value, str) and "must-not-leak" in value:
                continue
            safe[key] = value
        return safe

    def _exception_error(
        self,
        request: ProviderRequest,
        exc: Exception,
    ) -> ErrorEnvelope:
        if isinstance(exc, TimeoutError):
            return self._error(
                request,
                code=ErrorCode.PROVIDER_TIMEOUT,
                reason="provider_timeout",
                message="Provider request timed out.",
                recoverable=True,
            )
        if isinstance(exc, (ConnectionError, ValueError)):
            return self._error(
                request,
                code=ErrorCode.PROVIDER_UNAVAILABLE,
                reason="provider_unavailable",
                message="Provider unavailable.",
                recoverable=True,
            )
        return self._error(
            request,
            code=ErrorCode.PROVIDER_ERROR,
            reason="provider_error",
            message="Provider failed.",
            recoverable=True,
        )

    def _error(
        self,
        request: ProviderRequest,
        *,
        code: ErrorCode,
        reason: str,
        message: str,
        recoverable: bool,
    ) -> ErrorEnvelope:
        return ErrorEnvelope(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            error_id=f"{request.turn_id}:provider-worker:{reason}",
            code=code,
            message=message,
            recoverable=recoverable,
            source="provider_worker",
            details={"reason": reason},
        )

    def _result(
        self,
        *,
        command: str,
        ok: bool,
        trace_id: str,
        response: ProviderResponse | None = None,
        selection: ProviderWorkerSelectionProjection | None = None,
        metadata: dict[str, object] | None = None,
    ) -> ProviderWorkerCommandResult:
        return ProviderWorkerCommandResult(
            command=command,
            ok=ok,
            trace_id=trace_id,
            state=self._state.value,
            response=response,
            selection=selection,
            metadata=dict(metadata or {}),
        )

    def _error_result(
        self,
        *,
        command: str,
        trace_id: str,
        error: ErrorEnvelope,
        response: ProviderResponse | None = None,
        selection: ProviderWorkerSelectionProjection | None = None,
    ) -> ProviderWorkerCommandResult:
        return ProviderWorkerCommandResult(
            command=command,
            ok=False,
            trace_id=trace_id,
            state=self._state.value,
            response=response,
            error=error,
            selection=selection,
            metadata={"payload_persisted": False},
        )

    def map_structured_output(
        self,
        *,
        provider_name: str,
        schema_version: str,
        trace_id: str,
        turn_id: str,
        target_contract: str,
        raw_output_text: str,
        base_url: str | None = None,
        provider_mode: str | None = None,
        timeout_seconds: float | None = None,
        lmstudio_responses_api_key: str | None = None,
        litellm_api_key: str | None = None,
        openrouter_api_key: str | None = None,
    ) -> ProviderWorkerCommandResult:
        if target_contract != "AssistantFinalResponse":
            return self._error_result(
                command="structured_output",
                trace_id=trace_id,
                error=ErrorEnvelope(
                    schema_version=schema_version,
                    trace_id=trace_id,
                    error_id=f"{turn_id}:provider-worker:unsupported-structured-target",
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Structured output target is unsupported.",
                    recoverable=False,
                    source="provider_worker",
                    details={"reason": "unsupported_structured_target"},
                ),
            )
        try:
            if provider_name == "fake":
                structured = validate_raw_structured_output(
                    schema_version=schema_version,
                    trace_id=trace_id,
                    turn_id=turn_id,
                    target_contract=target_contract,
                    raw_output_text=raw_output_text,
                    target_model=AssistantFinalResponse,
                    include_raw_preview=False,
                )
            else:
                structured = map_provider_raw_output_to_structured_result(
                    config=ProviderRuntimeConfig(
                        provider_name=provider_name,
                        lmstudio_responses_api_key=lmstudio_responses_api_key,
                        litellm_api_key=litellm_api_key,
                        openrouter_api_key=openrouter_api_key,
                        base_url=base_url,
                        provider_mode=provider_mode,
                        timeout_seconds=timeout_seconds,
                    ),
                    schema_version=schema_version,
                    trace_id=trace_id,
                    turn_id=turn_id,
                    target_contract=target_contract,
                    raw_output_text=raw_output_text,
                    target_model=AssistantFinalResponse,
                    include_raw_preview=False,
                )
        except TimeoutError:
            structured = None
            error_code = ErrorCode.PROVIDER_TIMEOUT
            reason = "provider_timeout"
            message = "Provider structured output mapping timed out."
        except Exception:
            structured = None
            error_code = ErrorCode.PROVIDER_ERROR
            reason = "provider_error"
            message = "Provider structured output mapping failed."
        else:
            return self._result(
                command="structured_output",
                ok=True,
                trace_id=trace_id,
                metadata={
                    "structured_output": structured.model_dump(mode="json"),
                    "raw_output_persisted": False,
                },
            )

        return self._error_result(
            command="structured_output",
            trace_id=trace_id,
            error=ErrorEnvelope(
                schema_version=schema_version,
                trace_id=trace_id,
                error_id=f"{turn_id}:provider-worker:{reason}",
                code=error_code,
                message=message,
                recoverable=True,
                source="provider_worker",
                details={"reason": reason},
            ),
        )


def _stream_finish_reason(value: str | None) -> FinishReason:
    mapping = {
        "stop": FinishReason.STOP,
        "completed": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "incomplete": FinishReason.LENGTH,
        "error": FinishReason.ERROR,
        "failed": FinishReason.ERROR,
    }
    return mapping.get(str(value or "stop"), FinishReason.STOP)


def _provider_runtime_config(
    *,
    provider_name: str,
    base_url: str | None = None,
    provider_mode: str | None = None,
    timeout_seconds: float | None = None,
    lmstudio_responses_api_key: str | None = None,
    litellm_api_key: str | None = None,
    openrouter_api_key: str | None = None,
) -> ProviderRuntimeConfig:
    if provider_name == "fake":
        return ProviderRuntimeConfig(provider_name=provider_name)
    return ProviderRuntimeConfig(
        provider_name=provider_name,
        lmstudio_responses_api_key=lmstudio_responses_api_key,
        litellm_api_key=litellm_api_key,
        openrouter_api_key=openrouter_api_key,
        base_url=base_url,
        provider_mode=provider_mode,
        timeout_seconds=timeout_seconds,
    )
