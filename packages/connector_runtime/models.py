from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_SAFE_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_SECRET_TERMS = ("authorization", "bearer", "password", "secret", "token", "api_key", "apikey", "access_token")


class ConnectorRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=True)


class ConnectorCategory(StrEnum):
    GMAIL = "gmail"
    GOOGLE_CALENDAR = "google_calendar"
    GOOGLE_DRIVE = "google_drive"
    GITHUB = "github"
    SLACK = "slack"
    NOTION = "notion"
    GENERIC_OAUTH = "generic_oauth"


class SourceSyncMode(StrEnum):
    MANUAL = "manual"
    ON_DEMAND = "on_demand"
    SCHEDULED_AUTO_FETCH = "scheduled_auto_fetch"
    DISABLED = "disabled"


class SourceSyncInterval(StrEnum):
    MANUAL_ONLY = "manual_only"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class SourceLastSyncStatus(StrEnum):
    NEVER_SYNCED = "never_synced"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class OAuthConnectionStatus(StrEnum):
    NOT_CONNECTED = "not_connected"
    CONNECTED = "connected"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class ConnectorPermissionDecision(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    PENDING = "pending"


class ConnectorRef(ConnectorRuntimeModel):
    connector_id: str = Field(..., min_length=1)
    category: ConnectorCategory

    @field_validator("connector_id")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        return _validate_safe_id(value, "connector_id")


class ConnectorScope(ConnectorRuntimeModel):
    name: str = Field(..., min_length=1, max_length=120)
    purpose: str = Field(..., min_length=1, max_length=240)

    @field_validator("name")
    @classmethod
    def _safe_scope(cls, value: str) -> str:
        if value != value.strip() or any(part in value.lower() for part in _SECRET_TERMS):
            raise ValueError("connector scope name must be trimmed and non-secret")
        return value


class ConnectorManifest(ConnectorRuntimeModel):
    connector_ref: ConnectorRef
    display_name: str = Field(..., min_length=1, max_length=120)
    category: ConnectorCategory
    auth_kind: Literal["oauth2", "oauth1", "api_key_placeholder"]
    scopes: tuple[ConnectorScope, ...]
    account_action_allowed: Literal[False] = False
    auto_fetch_default_enabled: Literal[False] = False
    backend_kind: str = Field(..., min_length=1, max_length=80)

    def safe_projection(self) -> dict[str, object]:
        return {
            "connector_id": self.connector_ref.connector_id,
            "category": self.category,
            "display_name": self.display_name,
            "auth_kind": self.auth_kind,
            "scope_count": len(self.scopes),
            "account_action_allowed": False,
            "auto_fetch_default_enabled": False,
            "backend_kind": self.backend_kind,
        }


class OAuthConnectionRef(ConnectorRuntimeModel):
    connector_ref: ConnectorRef
    connection_id: str = Field(..., min_length=1)
    account_label: str = Field(..., min_length=1, max_length=160)
    status: OAuthConnectionStatus
    granted_scopes: tuple[ConnectorScope, ...] = ()
    token_storage: Literal["connector_auth_backend", "not_persisted"]
    connected_at: datetime | None = None
    expires_at: datetime | None = None
    raw_token_persisted: Literal[False] = False

    @field_validator("connection_id")
    @classmethod
    def _safe_connection_id(cls, value: str) -> str:
        return _validate_safe_id(value, "connection_id")

    def safe_projection(self) -> dict[str, object]:
        return {
            "connector_id": self.connector_ref.connector_id,
            "category": self.connector_ref.category,
            "connection_id": self.connection_id,
            "account_label": _safe_text(self.account_label),
            "status": self.status,
            "scope_count": len(self.granted_scopes),
            "token_storage": self.token_storage,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "raw_token_persisted": False,
        }


class SourceIngestionPolicy(ConnectorRuntimeModel):
    sync_mode: SourceSyncMode
    interval: SourceSyncInterval
    auto_fetch_enabled: bool = False
    human_approved: bool = False

    @model_validator(mode="after")
    def _validate_hidden_sync(self) -> SourceIngestionPolicy:
        if self.sync_mode == SourceSyncMode.SCHEDULED_AUTO_FETCH and not (self.auto_fetch_enabled and self.human_approved):
            raise ValueError("scheduled auto-fetch requires explicit enablement and approval")
        if self.sync_mode == SourceSyncMode.DISABLED and self.auto_fetch_enabled:
            raise ValueError("disabled source sync cannot enable auto-fetch")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "sync_mode": self.sync_mode,
            "interval": self.interval,
            "auto_fetch_enabled": self.auto_fetch_enabled,
            "human_approved": self.human_approved,
        }


class ConnectorSyncRequest(ConnectorRuntimeModel):
    request_id: str = Field(..., min_length=1)
    connector_ref: ConnectorRef
    sync_mode: SourceSyncMode
    permission_decision: ConnectorPermissionDecision
    requested_at: datetime
    raw_credentials_persisted: Literal[False] = False

    @field_validator("request_id")
    @classmethod
    def _safe_request_id(cls, value: str) -> str:
        return _validate_safe_id(value, "request_id")

    @model_validator(mode="after")
    def _validate_permission(self) -> ConnectorSyncRequest:
        if self.sync_mode != SourceSyncMode.DISABLED and self.permission_decision != ConnectorPermissionDecision.APPROVED:
            raise ValueError("connector sync requires an approved permission decision")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "connector_id": self.connector_ref.connector_id,
            "category": self.connector_ref.category,
            "sync_mode": self.sync_mode,
            "permission_decision": self.permission_decision,
            "requested_at": self.requested_at.isoformat(),
            "raw_credentials_persisted": False,
        }


class ConnectorSyncResult(ConnectorRuntimeModel):
    request_id: str
    connector_ref: ConnectorRef
    status: Literal["completed", "failed", "skipped"]
    documents_seen: int = Field(..., ge=0)
    safe_summary: str = Field(..., min_length=1, max_length=500)
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "connector_id": self.connector_ref.connector_id,
            "status": self.status,
            "documents_seen": self.documents_seen,
            "safe_summary": _safe_text(self.safe_summary),
            "raw_payload_persisted": False,
        }


class ConnectorErrorEnvelope(ConnectorRuntimeModel):
    connector_ref: ConnectorRef
    reason_code: str
    safe_message: str
    recoverable: bool
    raw_error_persisted: Literal[False] = False


class ConnectorSafeProjection(ConnectorRuntimeModel):
    connector_id: str
    category: ConnectorCategory
    status: OAuthConnectionStatus
    auto_fetch_enabled: bool = False
    raw_token_persisted: Literal[False] = False


class AutoFetchJobRef(ConnectorRuntimeModel):
    job_id: str
    connector_ref: ConnectorRef


class AutoFetchSchedule(ConnectorRuntimeModel):
    interval: SourceSyncInterval
    next_run_at: datetime | None = None
    jitter_seconds: int = Field(default=0, ge=0, le=3600)


class AutoFetchPolicy(ConnectorRuntimeModel):
    connector_ref: ConnectorRef
    control_state: Literal["enabled", "disabled", "paused"] = "disabled"
    connector_enabled: bool = False
    source_enabled: bool = False
    schedule: AutoFetchSchedule
    control_plane_toggle_allowed: Literal[True] = True

    @classmethod
    def default_for_connector(cls, connector_ref: ConnectorRef) -> AutoFetchPolicy:
        return cls(
            connector_ref=connector_ref,
            schedule=AutoFetchSchedule(interval=SourceSyncInterval.MANUAL_ONLY),
        )

    @model_validator(mode="after")
    def _validate_enablement(self) -> AutoFetchPolicy:
        if self.control_state == "enabled" and not (self.connector_enabled and self.source_enabled):
            raise ValueError("enabled auto-fetch requires connector and source enablement")
        return self

    def safe_projection(self) -> dict[str, object]:
        return {
            "connector_id": self.connector_ref.connector_id,
            "category": self.connector_ref.category,
            "control_state": self.control_state,
            "connector_enabled": self.connector_enabled,
            "source_enabled": self.source_enabled,
            "interval": self.schedule.interval,
            "next_run_at": self.schedule.next_run_at.isoformat() if self.schedule.next_run_at else None,
            "control_plane_toggle_allowed": True,
        }


class AutoFetchRunSummary(ConnectorRuntimeModel):
    run_id: str
    connector_ref: ConnectorRef
    started_at: datetime
    completed_at: datetime | None
    status: Literal["completed", "failed", "skipped"]
    documents_seen: int = Field(..., ge=0)
    documents_canonicalized: int = Field(..., ge=0)
    chunks_created: int = Field(..., ge=0)
    raw_payload_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "connector_id": self.connector_ref.connector_id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "documents_seen": self.documents_seen,
            "documents_canonicalized": self.documents_canonicalized,
            "chunks_created": self.chunks_created,
            "raw_payload_persisted": False,
        }


def default_connector_manifests() -> tuple[ConnectorManifest, ...]:
    specs = (
        (ConnectorCategory.GMAIL, "Gmail", "gmail.readonly"),
        (ConnectorCategory.GOOGLE_CALENDAR, "Google Calendar", "calendar.events.readonly"),
        (ConnectorCategory.GOOGLE_DRIVE, "Google Drive", "drive.readonly"),
        (ConnectorCategory.GITHUB, "GitHub", "repo:read"),
        (ConnectorCategory.SLACK, "Slack", "channels:history.read"),
        (ConnectorCategory.NOTION, "Notion", "read_content"),
        (ConnectorCategory.GENERIC_OAUTH, "Generic OAuth", "read"),
    )
    return tuple(
        ConnectorManifest(
            connector_ref=ConnectorRef(connector_id=f"{category.value}-connector", category=category),
            display_name=display_name,
            category=category,
            auth_kind="oauth2",
            scopes=(ConnectorScope(name=scope, purpose="Read-only account-aware ingestion"),),
            backend_kind="direct_oauth_authlib",
        )
        for category, display_name, scope in specs
    )


def _validate_safe_id(value: str, field_name: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{field_name} must be non-empty and trimmed")
    if any(character not in _SAFE_CHARS for character in value):
        raise ValueError(f"{field_name} contains unsafe characters")
    if any(part in value.lower() for part in _SECRET_TERMS):
        raise ValueError(f"{field_name} must not contain secret-like terms")
    return value


def _safe_text(value: str) -> str:
    return "[redacted]" if any(part in value.lower() for part in _SECRET_TERMS) else value
