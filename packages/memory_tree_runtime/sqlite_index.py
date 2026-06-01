from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import CanonicalMemoryDocument, MemoryChunk, MemoryTreeNode, ScoringExplanation
from .summaries import MemoryTreeForgetSummary


class SQLiteMemoryTreeIndex:
    def __init__(self, *, memory_db_path: str | Path, local_user_root: str | Path | None = None) -> None:
        root = Path(local_user_root).expanduser().resolve() if local_user_root else None
        path = Path(memory_db_path).expanduser().resolve()
        if root is not None and not _is_relative_to(path, root):
            raise ValueError("memory_db_path must be local-user scoped")
        self._path = path
        self._ensure_schema()

    def upsert_document(self, document: CanonicalMemoryDocument) -> None:
        payload = document.model_dump(mode="json")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_tree_documents(document_id, source_id, external_id, title, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (document.document_id, document.metadata.source_id, document.metadata.external_id, document.metadata.title, _json(payload)),
            )

    def upsert_chunks(self, chunks: tuple[MemoryChunk, ...]) -> None:
        with self._connect() as connection:
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO memory_tree_chunks(chunk_id, document_id, source_id, ordinal, content_hash, char_count, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chunk.chunk_id, chunk.document_id, chunk.source_id, chunk.ordinal, chunk.content_hash, chunk.char_count, _json(chunk.model_dump(mode="json"))),
                )

    def upsert_score(self, score: ScoringExplanation) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_tree_scores(chunk_id, importance, decision, payload_json)
                VALUES (?, ?, ?, ?)
                """,
                (score.chunk_id, score.importance.value, score.keep_drop_decision.decision, _json(score.model_dump(mode="json"))),
            )

    def upsert_node(self, node: MemoryTreeNode, *, tree_kind: str, tree_key: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memory_tree_nodes(node_id, tree_kind, tree_key, title, evidence_count, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (node.node_id, tree_kind, tree_key, node.title, len(node.evidence_links), _json(node.model_dump(mode="json"))),
            )

    def forget_source(self, source_id: str) -> MemoryTreeForgetSummary:
        with self._connect() as connection:
            document_ids = [row[0] for row in connection.execute("SELECT document_id FROM memory_tree_documents WHERE source_id = ?", (source_id,)).fetchall()]
            chunk_ids = [row[0] for row in connection.execute("SELECT chunk_id FROM memory_tree_chunks WHERE source_id = ?", (source_id,)).fetchall()]
            node_ids = [
                row[0]
                for row in connection.execute("SELECT node_id, payload_json FROM memory_tree_nodes").fetchall()
                if _node_references_source(row[1], source_id)
            ]
            documents_deleted = _delete_many(connection, "memory_tree_documents", "document_id", document_ids)
            chunks_deleted = _delete_many(connection, "memory_tree_chunks", "chunk_id", chunk_ids)
            scores_deleted = _delete_many(connection, "memory_tree_scores", "chunk_id", chunk_ids)
            tree_nodes_deleted = _delete_many(connection, "memory_tree_nodes", "node_id", node_ids)
        return MemoryTreeForgetSummary(
            subject_id=source_id,
            subject_kind="source",
            documents_deleted=documents_deleted,
            chunks_deleted=chunks_deleted,
            scores_deleted=scores_deleted,
            tree_nodes_deleted=tree_nodes_deleted,
        )

    def safe_sources(self) -> tuple[dict[str, object], ...]:
        rows = self._rows("SELECT DISTINCT source_id FROM memory_tree_documents ORDER BY source_id", ())
        return tuple({"source_id": row[0], "raw_credentials_persisted": False} for row in rows)

    def safe_documents(self) -> tuple[dict[str, object], ...]:
        rows = self._rows("SELECT document_id, source_id, external_id, title FROM memory_tree_documents ORDER BY document_id", ())
        return tuple({"document_id": row[0], "source_id": row[1], "external_id": row[2], "title": row[3], "raw_secret_persisted": False} for row in rows)

    def safe_chunks(self) -> tuple[dict[str, object], ...]:
        rows = self._rows("SELECT chunk_id, document_id, source_id, ordinal, char_count FROM memory_tree_chunks ORDER BY ordinal, chunk_id", ())
        return tuple({"chunk_id": row[0], "document_id": row[1], "source_id": row[2], "ordinal": row[3], "char_count": row[4], "raw_secret_persisted": False} for row in rows)

    def documents(self) -> tuple[CanonicalMemoryDocument, ...]:
        rows = self._rows("SELECT payload_json FROM memory_tree_documents ORDER BY document_id", ())
        return tuple(CanonicalMemoryDocument.model_validate(json.loads(row[0])) for row in rows)

    def chunks(self) -> tuple[MemoryChunk, ...]:
        rows = self._rows("SELECT payload_json FROM memory_tree_chunks ORDER BY ordinal, chunk_id", ())
        return tuple(MemoryChunk.model_validate(json.loads(row[0])) for row in rows)

    def safe_scores(self) -> tuple[dict[str, object], ...]:
        rows = self._rows("SELECT chunk_id, importance, decision, payload_json FROM memory_tree_scores ORDER BY chunk_id", ())
        return tuple(_score_projection(row) for row in rows)

    def safe_tree_nodes(self, *, tree_kind: str, tree_key: str) -> tuple[dict[str, object], ...]:
        rows = self._rows(
            "SELECT node_id, title, evidence_count, payload_json FROM memory_tree_nodes WHERE tree_kind = ? AND tree_key = ? ORDER BY node_id",
            (tree_kind, tree_key),
        )
        return tuple(_node_projection(row) for row in rows)

    def _ensure_schema(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS memory_tree_documents(document_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, external_id TEXT NOT NULL, title TEXT NOT NULL, payload_json TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS memory_tree_chunks(chunk_id TEXT PRIMARY KEY, document_id TEXT NOT NULL, source_id TEXT NOT NULL, ordinal INTEGER NOT NULL, content_hash TEXT NOT NULL, char_count INTEGER NOT NULL, payload_json TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS memory_tree_scores(chunk_id TEXT PRIMARY KEY, importance REAL NOT NULL, decision TEXT NOT NULL, payload_json TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS memory_tree_nodes(node_id TEXT PRIMARY KEY, tree_kind TEXT NOT NULL, tree_key TEXT NOT NULL, title TEXT NOT NULL, evidence_count INTEGER NOT NULL, payload_json TEXT NOT NULL)")

    def _rows(self, query: str, params: tuple[Any, ...]) -> list[tuple[Any, ...]]:
        with self._connect() as connection:
            return connection.execute(query, params).fetchall()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _score_projection(row: tuple[Any, ...]) -> dict[str, object]:
    payload = json.loads(row[3])
    return {
        "chunk_id": row[0],
        "source_weight": payload["source_weight"]["value"],
        "recency": payload["recency"]["value"],
        "interaction": payload["interaction"]["value"],
        "entity_topic_boost": payload["entity_topic_boost"]["value"],
        "importance": row[1],
        "decision": row[2],
        "raw_content_persisted": False,
    }


def _node_projection(row: tuple[Any, ...]) -> dict[str, object]:
    payload = json.loads(row[3])
    evidence_links = tuple(_safe_evidence_link(link) for link in payload.get("evidence_links", ()))
    return {
        "node_id": row[0],
        "title": row[1],
        "node_kind": payload.get("node_kind", "summary"),
        "parent_node_id": payload.get("parent_node_id"),
        "child_node_count": len(payload.get("child_node_ids", ())),
        "evidence_count": row[2],
        "evidence_links": evidence_links,
        "raw_content_persisted": False,
    }


def _safe_evidence_link(link: dict[str, Any]) -> dict[str, object]:
    return {
        "document_id": str(link.get("document_id", "")),
        "chunk_id": str(link.get("chunk_id", "")),
        "source_id": str(link.get("source_id", "")),
        "quote_preview": str(link.get("quote_preview", ""))[:160],
    }


def _node_references_source(payload_json: str, source_id: str) -> bool:
    payload = json.loads(payload_json)
    return any(str(link.get("source_id")) == source_id for link in payload.get("evidence_links", ()))


def _delete_many(connection: sqlite3.Connection, table: str, column: str, values: list[str]) -> int:
    if not values:
        return 0
    placeholders = ",".join("?" for _ in values)
    cursor = connection.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", values)
    return int(cursor.rowcount if cursor.rowcount is not None else 0)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
