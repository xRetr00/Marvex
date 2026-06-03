from __future__ import annotations

import math
import os
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from packages.intent_runtime.hybrid import (
    FastEmbedIntentEncoder,
    SemanticEncoding,
    _configured_semantic_encoder,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_embed(texts: list[str]) -> Iterator[list[float]]:
    """Return a fixed-length unit vector so tests never touch the network."""
    dim = 8
    raw = [1.0] + [0.0] * (dim - 1)
    norm = math.sqrt(sum(v * v for v in raw))
    unit = [v / norm for v in raw]
    for _ in texts:
        yield unit


class _FakeTextEmbedding:
    """Drop-in stub for fastembed.TextEmbedding that never downloads a model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or "BAAI/bge-small-en-v1.5"

    def embed(self, texts: list[str]) -> Iterator[list[float]]:  # type: ignore[override]
        return _fake_embed(texts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fastembed_encoder_requires_fastembed_package() -> None:
    """FastEmbedIntentEncoder.__init__ raises RuntimeError when fastembed is absent."""
    with patch.dict("sys.modules", {"fastembed": None}):
        with pytest.raises(RuntimeError, match="fastembed is not installed"):
            FastEmbedIntentEncoder()


def test_fastembed_encoder_encode_returns_semantic_encoding() -> None:
    """FastEmbedIntentEncoder.encode returns a normalised SemanticEncoding."""
    fastembed = pytest.importorskip("fastembed")  # skip if not installed

    encoder = FastEmbedIntentEncoder.__new__(FastEmbedIntentEncoder)
    encoder._model = _FakeTextEmbedding()  # bypass __init__ / real model download

    result = encoder.encode("list MCP tools")

    assert isinstance(result, SemanticEncoding)
    assert result.backend_name == "fastembed_text_embedding"
    assert len(result.dimensions) > 0
    # Result must be a unit vector (norm ≈ 1.0)
    norm = math.sqrt(sum(v * v for v in result.dimensions))
    assert abs(norm - 1.0) < 1e-6


def test_fastembed_encoder_normalises_vector() -> None:
    """encode() normalises whatever the model returns to a unit vector."""
    pytest.importorskip("fastembed")

    encoder = FastEmbedIntentEncoder.__new__(FastEmbedIntentEncoder)
    encoder._model = _FakeTextEmbedding()

    # Encode two different strings; both should come back normalised
    for text in ("hello", "search latest version of Marvex"):
        result = encoder.encode(text)
        norm = math.sqrt(sum(v * v for v in result.dimensions))
        assert abs(norm - 1.0) < 1e-6, f"vector not normalised for {text!r}: norm={norm}"


def test_configured_encoder_selects_fastembed_via_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """MARVEX_INTENT_ENCODER=fastembed selects FastEmbedIntentEncoder."""
    pytest.importorskip("fastembed")

    monkeypatch.setenv("MARVEX_INTENT_ENCODER", "fastembed")
    # Patch TextEmbedding inside the hybrid module so no real download occurs
    with patch("packages.intent_runtime.hybrid.FastEmbedIntentEncoder.__init__") as mock_init:
        mock_init.return_value = None
        encoder = _configured_semantic_encoder()

    assert isinstance(encoder, FastEmbedIntentEncoder)


def test_configured_encoder_prefers_local_fastembed_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default intent routing should use local embeddings when fastembed exists."""

    monkeypatch.delenv("MARVEX_INTENT_ENCODER", raising=False)
    monkeypatch.setattr("packages.intent_runtime.hybrid.importlib.util.find_spec", lambda name: object() if name == "fastembed" else None)
    with patch("packages.intent_runtime.hybrid.FastEmbedIntentEncoder.__init__") as mock_init:
        mock_init.return_value = None
        encoder = _configured_semantic_encoder()

    assert isinstance(encoder, FastEmbedIntentEncoder)
    mock_init.assert_called_once_with(model_name=os.environ.get("MARVEX_INTENT_FASTEMBED_MODEL"))


def test_configured_encoder_selects_fastembed_with_model_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    """MARVEX_INTENT_FASTEMBED_MODEL is forwarded to FastEmbedIntentEncoder."""
    pytest.importorskip("fastembed")

    monkeypatch.setenv("MARVEX_INTENT_ENCODER", "fastembed")
    monkeypatch.setenv("MARVEX_INTENT_FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5")

    with patch("packages.intent_runtime.hybrid.FastEmbedIntentEncoder.__init__") as mock_init:
        mock_init.return_value = None
        encoder = _configured_semantic_encoder()

    assert isinstance(encoder, FastEmbedIntentEncoder)
    # Confirm model_name was passed (captured via call_args)
    mock_init.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5")


def test_fastembed_encoder_integrates_with_encoded_semantic_route_layer() -> None:
    """FastEmbedIntentEncoder plugs into EncodedSemanticRouteLayer without error."""
    pytest.importorskip("fastembed")

    import semantic_router

    from packages.intent_runtime.hybrid import EncodedSemanticRouteLayer, IntentKind

    encoder = FastEmbedIntentEncoder.__new__(FastEmbedIntentEncoder)
    encoder._model = _FakeTextEmbedding()

    routes = (
        semantic_router.Route(name=IntentKind.PROVIDER_SIMPLE_CHAT.value, utterances=("hello", "hi")),
        semantic_router.Route(name=IntentKind.WEB_SEARCH.value, utterances=("search latest", "current docs")),
    )
    layer = EncodedSemanticRouteLayer(encoder=encoder, routes=routes)

    kind, score = layer.select("hello there")

    # With a fake constant embedding every cosine score is identical → falls back to first winner or low-confidence
    assert isinstance(kind, IntentKind)
    assert 0.0 <= score <= 1.0
