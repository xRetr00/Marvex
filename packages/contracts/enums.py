from enum import Enum


class Source(str, Enum):
    CLI = "cli"


class ResponseType(str, Enum):
    TEXT = "text"
    ERROR = "error"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"
    UNKNOWN = "unknown"


class TraceStage(str, Enum):
    TURN_RECEIVED = "turn_received"
    PROVIDER_REQUEST_CREATED = "provider_request_created"
    PROVIDER_REQUEST_SENT = "provider_request_sent"
    PROVIDER_RESPONSE_RECEIVED = "provider_response_received"
    FINAL_RESPONSE_CREATED = "final_response_created"
    TURN_COMPLETED = "turn_completed"
    TURN_AWAITING_APPROVAL = "turn_awaiting_approval"
    TURN_FAILED = "turn_failed"


class TraceLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    STARTING = "starting"
    STOPPING = "stopping"
    ERROR = "error"


class ErrorCode(str, Enum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    TELEMETRY_WRITE_FAILED = "TELEMETRY_WRITE_FAILED"
    SERVICE_UNHEALTHY = "SERVICE_UNHEALTHY"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AssistantInputSource(str, Enum):
    CLI = "cli"
    SHELL = "shell"
    VOICE = "voice"
    DESKTOP = "desktop"
    PROACTIVE = "proactive"
    SYSTEM = "system"


class InputModality(str, Enum):
    TEXT = "text"
    SPEECH = "speech"
    DESKTOP_EVENT = "desktop_event"
    SYSTEM_EVENT = "system_event"


class AssistantMode(str, Enum):
    DEFAULT = "default"
    DIAGNOSTIC = "diagnostic"


class AssistantResponseType(str, Enum):
    TEXT = "text"
    ERROR = "error"
    PAYLOAD_REF = "payload_ref"


class OutputChannelIntent(str, Enum):
    DEFAULT = "default"
    DISPLAY = "display"
    SPEECH = "speech"
    BOTH = "both"


class AssistantFinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    CANCELLED = "cancelled"
    ERROR = "error"
    UNKNOWN = "unknown"


class StageStatus(str, Enum):
    PENDING = "pending"
    SKIPPED = "skipped"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Sensitivity(str, Enum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"
    SECRET = "secret"
