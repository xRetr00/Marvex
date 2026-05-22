# Library Decision: FastEmbed Offline Embedding Backend

library name: fastembed

official source: https://github.com/qdrant/fastembed and https://qdrant.github.io/fastembed/

maintenance status: Active as of May 22, 2026. fastembed is maintained by Qdrant. Version 0.4.x is the current stable series; the library targets Python 3.8+ and ships pre-quantised ONNX models so no GPU or heavy runtime is required.

why use it: Marvex intent routing needs an optional real offline embedding backend for `FastEmbedIntentEncoder` in `packages/intent_runtime/hybrid.py`. fastembed is free, open-source (Apache 2.0), downloads ONNX models on first runtime use, and needs no LM Studio server, no GPU, and no paid API. It fills the gap between the always-available `DeterministicLocalIntentEncoder` (heuristic, no model) and the `OpenAICompatibleEmbeddingIntentEncoder` (requires a running LM Studio instance).

why not custom code: Custom ONNX model loading would recreate model discovery, quantisation handling, batching, and tokenisation that fastembed already handles. The deterministic encoder is already the zero-dependency fallback; a custom embedding path would add that complexity without the community maintenance benefit.

fallback if abandoned: Switch to another maintained ONNX embedding library (e.g. sentence-transformers behind the same encoder seam) or revert to the deterministic encoder. The encoder boundary in `_configured_semantic_encoder()` is a single selection point; no routing logic, contracts, or tests need to change.

pyproject dependency: none

declared dependency: not in default/runtime deps; optional only. Install with `uv sync --extra embeddings` or `pip install "marvex[embeddings]"`. The declared optional spec is `fastembed>=0.4.0,<1` in `[project.optional-dependencies] embeddings`.

verified date: 2026-05-22

verified by: Claude (agent-a08fa15a0ebd04221)

scope: Optional offline embedding backend for `FastEmbedIntentEncoder` in `packages/intent_runtime/hybrid.py` only. Selected at runtime when `MARVEX_INTENT_ENCODER=fastembed`. Must not be imported at module level; the import is guarded inside `FastEmbedIntentEncoder.__init__`. CI must not download models; tests that exercise this backend must use `pytest.importorskip("fastembed")` and inject a fake model to avoid network calls.

architecture fit: Good as a thin replaceable backend behind the `_configured_semantic_encoder()` seam. fastembed stays entirely inside `FastEmbedIntentEncoder`; it does not touch routing policy, contracts, memory, tools, or Core.

adopt / defer / reject decision: Adopt as optional extra. The package is declared as an optional dependency in `pyproject.toml [project.optional-dependencies] embeddings`. Default install and CI remain light (no model download, no network). The encoder is only active when `MARVEX_INTENT_ENCODER=fastembed` is set and `fastembed` is installed. Offline production deployments that need real vector embeddings without LM Studio can opt in.

risks: Model download happens on first use at runtime, not at install time. CI must not set `MARVEX_INTENT_ENCODER=fastembed` or it will attempt a network download. The ONNX runtime pulls in native binaries; on some platforms the wheel may be large. Route quality depends on the chosen model; the default `BAAI/bge-small-en-v1.5` is a well-tested compact model but thresholds may need re-tuning if the model is changed.

comparison to sentence-transformers: fastembed is lighter than sentence-transformers (ONNX vs PyTorch), ships quantised models, and has no torch dependency. sentence-transformers remains a viable alternative behind the same encoder seam if fastembed is abandoned.
