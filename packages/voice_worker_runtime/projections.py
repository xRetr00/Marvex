from __future__ import annotations

from typing import Any

from .audio import PlaybackAdapterResult
from .models import VoiceWorkerEvent


class VoiceWorkerTurnRunResult:
    def __init__(
        self,
        *,
        turn: Any,
        events: tuple[VoiceWorkerEvent, ...],
        playback: PlaybackAdapterResult,
        capture_summary: dict[str, object] | None = None,
    ) -> None:
        self.turn = turn
        self.events = events
        self.playback = playback
        self.capture_summary = capture_summary or {}

    def safe_projection(self) -> dict[str, object]:
        return {
            "turn_status": self.turn.status if self.turn is not None else "not_started",
            "event_count": len(self.events),
            "playback_status": self.playback.status,
            **self.capture_summary,
            "raw_audio_persisted": False,
            "raw_transcript_persisted": False,
        }


def transcription_summary(result: Any) -> dict[str, object]:
    summary: dict[str, object] = {
        "backend_id": result.backend_id,
        "status": result.status,
        "duration_ms": result.duration_ms,
        "language": result.language,
        "confidence_present": result.confidence is not None,
        "segment_count": len(result.segments),
        "text_present": bool(result.text),
        "raw_audio_persisted": False,
        "raw_transcript_persisted": False,
    }
    if result.safe_error is not None:
        summary["exact_blocker"] = result.safe_error.details.get("reason_code")
    return summary


def synthesis_summary(result: Any) -> dict[str, object]:
    summary: dict[str, object] = {
        "backend_id": result.backend_id,
        "voice_id": result.voice_id,
        "status": result.status,
        "format": result.format,
        "sample_rate": result.sample_rate,
        "duration_ms": result.duration_ms,
        "audio_ref_present": bool(result.audio_ref),
        "raw_audio_persisted": False,
    }
    if result.safe_error is not None:
        summary["exact_blocker"] = result.safe_error.details.get("reason_code")
    return summary
