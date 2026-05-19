# Semantic Memory Search

Marvex now has a local semantic memory search path in `packages.memory_tree_runtime.search`.

The implementation intentionally adds no paid, cloud, or model dependency. It uses a local token-vector scorer with synonym normalization, metadata boosts, and an FTS-like fallback. This satisfies the pre-Voice need for semantic-ish retrieval beyond exact keyword matching while avoiding OpenAI/provider embeddings, paid vector services, or a new heavyweight local embedding stack.

Supported filters:

- trust level
- recency / max age
- entity
- topic
- source
- source type
- score / hotness
- evidence availability

Result safety:

- Returned nodes remain source-grounded through `EvidenceLink`.
- Safe projections expose evidence refs and quote previews only.
- Raw memory content is not persisted by the search result.

Future dependency option:

A later goal may evaluate `fastembed` or `sentence-transformers` if real embedding quality becomes necessary. That adoption must use uv, stay local/free, and remain behind MemoryTreeRuntime search adapters.
