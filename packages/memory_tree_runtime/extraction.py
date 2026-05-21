"""Deterministic, offline extraction of derived memory artefacts from canonicalized chunks.

Extracts entities (people/projects/repos), facts, user preferences, entity relations,
and daily-digest material from MemoryChunk content — all derived-safe with full provenance.

No embeddings, no network, no LLM call required.  Every result carries a provenance
reference (chunk_id + document_id + source_id) back to the originating chunk so the
tree can content-address and trace every derived fact.

file size justification: extraction logic spans five distinct extraction categories
(entities, facts, preferences, relations, daily digest) each requiring independent
regex/heuristics, plus bounded scoring and safe-model construction — splitting would
add cross-file coupling for no structural benefit.
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import Field

from packages.memory_tree_runtime.models import (
    ChunkId,
    EvidenceLink,
    MemoryChunk,
    MemoryTreeModel,
    MemoryTreeNode,
    _SECRET_TERMS,
    _sha256,
)


def _is_safe_text(text: str) -> bool:
    lower = text.lower()
    return not any(term in lower for term in _SECRET_TERMS)


def _sanitize(text: str, max_chars: int = 200) -> str:
    """Trim, cap length, redact if secret-like."""
    trimmed = text.strip()[:max_chars]
    return "[redacted]" if any(term in trimmed.lower() for term in _SECRET_TERMS) else trimmed


# ---------------------------------------------------------------------------
# Derived models — all carry raw_content_persisted: Literal[False]
# ---------------------------------------------------------------------------


class ExtractedEntity(MemoryTreeModel):
    """A named entity derived from a chunk — people, projects, or repos."""

    entity_id: str
    label: str
    kind: Literal["person", "project", "repo", "generic"]
    chunk_id: ChunkId
    document_id: str
    source_id: str
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "entity_id": self.entity_id,
            "label": self.label,
            "kind": self.kind,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "raw_content_persisted": False,
        }


class ExtractedFact(MemoryTreeModel):
    """A short derived fact statement from a chunk."""

    fact_id: str
    text: str = Field(..., min_length=1, max_length=300)
    chunk_id: ChunkId
    document_id: str
    source_id: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "text": self.text,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "confidence": self.confidence,
            "raw_content_persisted": False,
        }


class ExtractedPreference(MemoryTreeModel):
    """A user preference signal derived from a chunk."""

    preference_id: str
    subject: str = Field(..., min_length=1, max_length=160)
    preference_text: str = Field(..., min_length=1, max_length=300)
    polarity: Literal["positive", "negative", "neutral"]
    chunk_id: ChunkId
    document_id: str
    source_id: str
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "preference_id": self.preference_id,
            "subject": self.subject,
            "preference_text": self.preference_text,
            "polarity": self.polarity,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "raw_content_persisted": False,
        }


class ExtractedRelation(MemoryTreeModel):
    """A directed relation between two extracted entities."""

    relation_id: str
    subject_entity_id: str
    predicate: str = Field(..., min_length=1, max_length=80)
    object_entity_id: str
    chunk_id: ChunkId
    document_id: str
    source_id: str
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "relation_id": self.relation_id,
            "subject_entity_id": self.subject_entity_id,
            "predicate": self.predicate,
            "object_entity_id": self.object_entity_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "raw_content_persisted": False,
        }


class ChunkExtractionResult(MemoryTreeModel):
    """All derived extraction results for a single chunk, with full provenance."""

    chunk_id: ChunkId
    document_id: str
    source_id: str
    entities: tuple[ExtractedEntity, ...] = ()
    facts: tuple[ExtractedFact, ...] = ()
    preferences: tuple[ExtractedPreference, ...] = ()
    relations: tuple[ExtractedRelation, ...] = ()
    hotness_boost: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "entity_count": len(self.entities),
            "fact_count": len(self.facts),
            "preference_count": len(self.preferences),
            "relation_count": len(self.relations),
            "hotness_boost": self.hotness_boost,
            "raw_content_persisted": False,
        }


class DailyDigestEntry(MemoryTreeModel):
    """A single daily-digest entry derived from a chunk."""

    entry_id: str
    date_label: str = Field(..., min_length=1, max_length=10)
    headline: str = Field(..., min_length=1, max_length=160)
    chunk_id: ChunkId
    document_id: str
    source_id: str
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "date_label": self.date_label,
            "headline": self.headline,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "source_id": self.source_id,
            "raw_content_persisted": False,
        }


# ---------------------------------------------------------------------------
# Regex patterns (deterministic, no network/embedding dependency)
# ---------------------------------------------------------------------------

# Capitalised multi-word proper names: "Alice Smith", "Marvex AI"
_PERSON_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")

# GitHub-style repo references: "org/repo" or "owner/project-name"
_REPO_RE = re.compile(r"\b([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)\b")

# Quoted or backtick project names, e.g. "Marvex", `memory_tree_runtime`
_PROJECT_QUOTED_RE = re.compile(r'["`]([A-Za-z][A-Za-z0-9_\-]{2,40})["`]')

# Fact-like sentences: short declarative sentences with a subject + verb
_FACT_SENTENCE_RE = re.compile(r"([A-Z][^.!?]{15,180}[.!?])")

# Preference signals
_PREF_POSITIVE_RE = re.compile(
    r"\b(?:prefer(?:s|red)?|like(?:s|d)?|want(?:s|ed)?|care(?:s|d)? about|love(?:s|d)?|rely\s+on|use(?:s|d)?)\b",
    re.IGNORECASE,
)
_PREF_NEGATIVE_RE = re.compile(
    r"\b(?:dislike(?:s|d)?|avoid(?:s|ed)?|hate(?:s|d)?|not\s+want|don'?t\s+(?:like|use|want)|never\s+use)\b",
    re.IGNORECASE,
)

# Relation cues: "X uses Y", "X depends on Y", "X owns Y"
_RELATION_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_\-]{1,40})\s+(uses|depends\s+on|owns|manages|implements|extends|calls|invokes|integrates\s+with)\s+([A-Za-z][A-Za-z0-9_\-]{1,40})\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _entity_id(label: str, kind: str) -> str:
    return f"entity:{kind}:{_sha256(f'{kind}:{label.strip().lower()}')[:12]}"


def _fact_id(chunk_id: str, ordinal: int) -> str:
    return f"fact:{_sha256(f'{chunk_id}:fact:{ordinal}')[:12]}"


def _pref_id(chunk_id: str, ordinal: int) -> str:
    return f"pref:{_sha256(f'{chunk_id}:pref:{ordinal}')[:12]}"


def _relation_id(subj: str, pred: str, obj: str, chunk_id: str) -> str:
    return f"rel:{_sha256(f'{subj}|{pred}|{obj}|{chunk_id}')[:12]}"


def _entry_id(chunk_id: str, date_label: str) -> str:
    return f"digest:{_sha256(f'{chunk_id}:{date_label}')[:12]}"


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------


def extract_entities(chunk: MemoryChunk) -> tuple[ExtractedEntity, ...]:
    """Extract people, repos, and project names from a chunk (derived-safe, deterministic)."""
    text = chunk.markdown
    if not _is_safe_text(text):
        return ()

    seen: set[str] = set()
    entities: list[ExtractedEntity] = []

    # People: capitalised multi-word names
    for match in _PERSON_RE.finditer(text):
        label = _sanitize(match.group(1))
        if label and label not in seen:
            seen.add(label)
            entities.append(
                ExtractedEntity(
                    entity_id=_entity_id(label, "person"),
                    label=label,
                    kind="person",
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                )
            )

    # Repos: org/repo pattern
    for match in _REPO_RE.finditer(text):
        label = _sanitize(match.group(1))
        if label and label not in seen and "/" in label:
            seen.add(label)
            entities.append(
                ExtractedEntity(
                    entity_id=_entity_id(label, "repo"),
                    label=label,
                    kind="repo",
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                )
            )

    # Projects: quoted names
    for match in _PROJECT_QUOTED_RE.finditer(text):
        label = _sanitize(match.group(1))
        if label and label not in seen:
            seen.add(label)
            entities.append(
                ExtractedEntity(
                    entity_id=_entity_id(label, "project"),
                    label=label,
                    kind="project",
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                )
            )

    return tuple(entities[:20])  # bounded: max 20 per chunk


def extract_facts(chunk: MemoryChunk) -> tuple[ExtractedFact, ...]:
    """Extract short declarative facts from a chunk (derived-safe, deterministic)."""
    text = chunk.markdown
    if not _is_safe_text(text):
        return ()

    facts: list[ExtractedFact] = []
    for ordinal, match in enumerate(_FACT_SENTENCE_RE.finditer(text)):
        sentence = _sanitize(match.group(1), max_chars=300)
        if len(sentence) < 20:
            continue
        # Simple confidence heuristic: longer sentences with verbs score higher
        verb_count = len(re.findall(r"\b(?:is|are|was|were|has|have|will|should|can|must)\b", sentence, re.IGNORECASE))
        confidence = min(0.9, 0.4 + verb_count * 0.1 + min(len(sentence) / 600, 0.3))
        facts.append(
            ExtractedFact(
                fact_id=_fact_id(chunk.chunk_id, ordinal),
                text=sentence,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_id=chunk.source_id,
                confidence=round(confidence, 2),
            )
        )
        if len(facts) >= 10:  # bounded: max 10 per chunk
            break

    return tuple(facts)


def extract_preferences(chunk: MemoryChunk) -> tuple[ExtractedPreference, ...]:
    """Extract user preference signals from a chunk (derived-safe, deterministic)."""
    text = chunk.markdown
    if not _is_safe_text(text):
        return ()

    prefs: list[ExtractedPreference] = []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for ordinal, sentence in enumerate(sentences):
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
        is_positive = bool(_PREF_POSITIVE_RE.search(sentence))
        is_negative = bool(_PREF_NEGATIVE_RE.search(sentence))
        if not (is_positive or is_negative):
            continue
        polarity: Literal["positive", "negative", "neutral"] = (
            "negative" if is_negative else "positive"
        )
        words = sentence.split()
        subject = _sanitize(" ".join(words[:3]), max_chars=160) if words else "user"
        pref_text = _sanitize(sentence, max_chars=300)
        if not pref_text:
            continue
        prefs.append(
            ExtractedPreference(
                preference_id=_pref_id(chunk.chunk_id, ordinal),
                subject=subject or "user",
                preference_text=pref_text,
                polarity=polarity,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_id=chunk.source_id,
            )
        )
        if len(prefs) >= 5:  # bounded: max 5 per chunk
            break

    return tuple(prefs)


def extract_relations(
    chunk: MemoryChunk,
    entities: tuple[ExtractedEntity, ...],
) -> tuple[ExtractedRelation, ...]:
    """Extract directed relations between entities found in a chunk (derived-safe, deterministic)."""
    text = chunk.markdown
    if not _is_safe_text(text):
        return ()

    entity_map = {e.label.lower(): e.entity_id for e in entities}
    relations: list[ExtractedRelation] = []

    for match in _RELATION_RE.finditer(text):
        subj_raw = match.group(1)
        pred_raw = re.sub(r"\s+", " ", match.group(2)).strip().lower()
        obj_raw = match.group(3)

        subj_id = entity_map.get(subj_raw.lower()) or _entity_id(subj_raw, "generic")
        obj_id = entity_map.get(obj_raw.lower()) or _entity_id(obj_raw, "generic")

        rel = ExtractedRelation(
            relation_id=_relation_id(subj_id, pred_raw, obj_id, chunk.chunk_id),
            subject_entity_id=subj_id,
            predicate=_sanitize(pred_raw, max_chars=80),
            object_entity_id=obj_id,
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            source_id=chunk.source_id,
        )
        relations.append(rel)
        if len(relations) >= 10:  # bounded: max 10 per chunk
            break

    return tuple(relations)


def compute_hotness_boost(
    entities: tuple[ExtractedEntity, ...],
    facts: tuple[ExtractedFact, ...],
    preferences: tuple[ExtractedPreference, ...],
) -> float:
    """Compute an entity-topic hotness boost (0–1) from extraction richness."""
    entity_signal = min(len(entities) * 0.05, 0.3)
    fact_signal = min(len(facts) * 0.04, 0.2)
    pref_signal = min(len(preferences) * 0.06, 0.2)
    high_conf_facts = sum(1 for f in facts if f.confidence >= 0.7)
    conf_signal = min(high_conf_facts * 0.05, 0.15)
    return round(min(entity_signal + fact_signal + pref_signal + conf_signal, 1.0), 3)


def extract_chunk(chunk: MemoryChunk) -> ChunkExtractionResult:
    """Run full extraction pipeline on a single chunk.

    Returns derived-safe, bounded, provenance-linked results.
    Deterministic — no network, no embeddings, no LLM call.
    """
    entities = extract_entities(chunk)
    facts = extract_facts(chunk)
    preferences = extract_preferences(chunk)
    relations = extract_relations(chunk, entities)
    hotness_boost = compute_hotness_boost(entities, facts, preferences)

    return ChunkExtractionResult(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        source_id=chunk.source_id,
        entities=entities,
        facts=facts,
        preferences=preferences,
        relations=relations,
        hotness_boost=hotness_boost,
    )


def extract_chunks(chunks: tuple[MemoryChunk, ...]) -> tuple[ChunkExtractionResult, ...]:
    """Run extraction on all chunks, returning a bounded tuple of results."""
    return tuple(extract_chunk(chunk) for chunk in chunks)


# ---------------------------------------------------------------------------
# Daily digest builder
# ---------------------------------------------------------------------------


def build_daily_digest_entries(
    chunks: tuple[MemoryChunk, ...],
    *,
    date_label: str,
) -> tuple[DailyDigestEntry, ...]:
    """Build daily digest entries from chunks for a given date label.

    Each entry is a headline derived from the chunk's first sentence — derived-safe,
    content-addressed, with full provenance.
    """
    entries: list[DailyDigestEntry] = []
    for chunk in chunks:
        if not _is_safe_text(chunk.markdown):
            continue
        headline = _first_sentence(chunk.markdown)
        if not headline:
            continue
        entries.append(
            DailyDigestEntry(
                entry_id=_entry_id(chunk.chunk_id, date_label),
                date_label=date_label,
                headline=headline,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                source_id=chunk.source_id,
            )
        )
    return tuple(entries)


def build_daily_digest_node(
    entries: tuple[DailyDigestEntry, ...],
    *,
    date_label: str,
) -> MemoryTreeNode | None:
    """Build a MemoryTreeNode daily digest from DailyDigestEntry objects.

    Returns None if no safe entries are available.
    """
    if not entries:
        return None

    evidence_links = tuple(
        EvidenceLink(
            document_id=entry.document_id,
            chunk_id=entry.chunk_id,
            source_id=entry.source_id,
            quote_preview=entry.headline[:120],
        )
        for entry in entries[:10]  # bounded evidence
    )
    if not evidence_links:
        return None

    headlines = "; ".join(e.headline[:60] for e in entries[:5])
    summary = f"Daily digest {date_label}: {headlines}"[:400]

    return MemoryTreeNode(
        node_id=f"daily:{date_label}",
        title=f"Daily digest {date_label}",
        summary=summary,
        node_kind="daily_digest",
        evidence_links=evidence_links,
    )


# ---------------------------------------------------------------------------
# Topic hotness updater
# ---------------------------------------------------------------------------


def compute_topic_hotness(
    extraction_results: tuple[ChunkExtractionResult, ...],
    *,
    topic_label: str,
) -> float:
    """Compute aggregate topic hotness from extraction results for a topic label.

    Returns a bounded float in [0, 1].
    """
    if not extraction_results:
        return 0.0

    topic_lower = topic_label.lower()
    relevant = [
        r for r in extraction_results
        if any(e.label.lower() in topic_lower or topic_lower in e.label.lower() for e in r.entities)
        or any(topic_lower in f.text.lower() for f in r.facts)
    ]

    if not relevant:
        base = sum(r.hotness_boost for r in extraction_results) / len(extraction_results)
        return round(min(base * 0.5, 1.0), 3)

    avg_boost = sum(r.hotness_boost for r in relevant) / len(relevant)
    coverage = min(len(relevant) / max(len(extraction_results), 1), 1.0)
    return round(min(avg_boost * 0.7 + coverage * 0.3, 1.0), 3)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _first_sentence(text: str) -> str:
    """Extract and sanitize the first sentence from text (max 160 chars)."""
    match = re.search(r"([A-Z][^.!?]{10,160}[.!?])", text)
    if match:
        return _sanitize(match.group(1), max_chars=160)
    # Fallback: first 160 chars of stripped text
    stripped = text.strip()[:160]
    return _sanitize(stripped) if stripped else ""
