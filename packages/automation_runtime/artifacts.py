from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_ARTIFACT_DIR = ".marvex-automation/artifacts"


@dataclass(frozen=True)
class AutomationArtifactRecord:
    artifact_id: str
    artifact_kind: str
    path: str
    bytes_written: int
    raw_payload_persisted: bool = True

    def safe_projection(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "path": self.path,
            "bytes_written": self.bytes_written,
            "raw_payload_persisted": self.raw_payload_persisted,
        }


def persist_automation_artifacts(
    *,
    trace_id: str,
    turn_id: str,
    capability_id: str,
    payloads: dict[str, Any],
    root: str | Path | None = None,
) -> dict[str, AutomationArtifactRecord]:
    base = Path(root or os.environ.get("MARVEX_AUTOMATION_ARTIFACT_DIR") or DEFAULT_ARTIFACT_DIR)
    base.mkdir(parents=True, exist_ok=True)
    records: dict[str, AutomationArtifactRecord] = {}
    for artifact_kind, payload in payloads.items():
        safe_kind = _safe_name(artifact_kind)
        artifact_id = f"{_safe_name(trace_id)}-{_safe_name(turn_id)}-{_safe_name(capability_id)}-{safe_kind}"
        path = base / f"{artifact_id}.json"
        envelope = {
            "schema_version": "1",
            "artifact_id": artifact_id,
            "artifact_kind": artifact_kind,
            "trace_id": trace_id,
            "turn_id": turn_id,
            "capability_id": capability_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "raw_payload": payload,
            "raw_payload_persisted": True,
        }
        data = json.dumps(envelope, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        path.write_bytes(data)
        records[artifact_kind] = AutomationArtifactRecord(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            path=str(path),
            bytes_written=len(data),
        )
    return records


def _safe_name(value: str) -> str:
    text = "".join(character if character.isalnum() or character in "._-" else "-" for character in str(value))
    return text.strip(".-_") or "artifact"
