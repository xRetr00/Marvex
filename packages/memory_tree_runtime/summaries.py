from __future__ import annotations

from typing import Literal

from pydantic import Field

from .models import MemoryTreeModel


class MemoryTreeForgetSummary(MemoryTreeModel):
    subject_id: str
    subject_kind: Literal["source", "chunk", "topic"]
    documents_deleted: int = Field(..., ge=0)
    chunks_deleted: int = Field(..., ge=0)
    scores_deleted: int = Field(..., ge=0)
    tree_nodes_deleted: int = Field(..., ge=0)
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "subject_id": self.subject_id,
            "subject_kind": self.subject_kind,
            "documents_deleted": self.documents_deleted,
            "chunks_deleted": self.chunks_deleted,
            "scores_deleted": self.scores_deleted,
            "tree_nodes_deleted": self.tree_nodes_deleted,
            "raw_content_persisted": False,
        }


class MemoryTreeTelemetrySummary(MemoryTreeModel):
    event_kind: Literal["canonicalized", "chunked", "scored", "tree_updated", "traversed", "forgotten"]
    documents_canonicalized: int = Field(default=0, ge=0)
    chunks_created: int = Field(default=0, ge=0)
    scores_created: int = Field(default=0, ge=0)
    tree_nodes_updated: int = Field(default=0, ge=0)
    traversal_results: int = Field(default=0, ge=0)
    raw_content_persisted: Literal[False] = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "event_kind": self.event_kind,
            "documents_canonicalized": self.documents_canonicalized,
            "chunks_created": self.chunks_created,
            "scores_created": self.scores_created,
            "tree_nodes_updated": self.tree_nodes_updated,
            "traversal_results": self.traversal_results,
            "raw_content_persisted": False,
        }
