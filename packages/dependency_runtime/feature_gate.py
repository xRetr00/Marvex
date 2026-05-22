"""Feature gate helpers for lazy-guarded heavy dep paths.

Usage pattern in any module with a heavy dep:

    from packages.dependency_runtime.feature_gate import require_feature, FeatureUnavailableError

    def run_tts(text: str) -> dict:
        if not require_feature("tts"):
            return {"status": "unavailable", "reason": "tts_feature_disabled", "feature": "tts"}
        # ... actual TTS code here

All callers should check the returned dict/error rather than crash when the dep
is missing.  No import of the heavy dep happens here.
"""
from __future__ import annotations

from packages.dependency_runtime.detection import detect_features


class FeatureUnavailableError(RuntimeError):
    """Raised when a feature is explicitly required but its dep is missing."""

    def __init__(self, feature: str) -> None:
        super().__init__(f"feature '{feature}' is unavailable: dep/model not installed")
        self.feature = feature


def is_feature_available(feature: str) -> bool:
    """Return True if all deps for the given feature are present.

    Callers should return a safe "feature unavailable" projection on False.
    Does NOT raise by default — callers decide how to degrade.
    """
    features = detect_features()
    return bool(getattr(features, feature, False))


# Alias: require_feature is intentionally the same check — kept for call-site readability.
require_feature = is_feature_available


def unavailable_projection(feature: str) -> dict[str, object]:
    """Safe projection for when a feature is disabled due to missing dep."""
    return {
        "status": "unavailable",
        "reason": "feature_dep_not_installed",
        "feature": feature,
        "raw_payload_persisted": False,
    }
