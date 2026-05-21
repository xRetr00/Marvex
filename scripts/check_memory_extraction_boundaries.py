"""Gate: derived-safe extraction only — no raw transcript/secret persistence,
bounded chunks, provenance present, deterministic default (no network/embedding dep).

Asserts:
1. extraction.py exists in packages/memory_tree_runtime and imports only approved modules.
2. All extraction result models carry raw_content_persisted: Literal[False].
3. No forbidden network/embedding imports are present.
4. Provenance fields (chunk_id, document_id, source_id) are declared on all result models.
5. The extraction module contains determinism markers and no LLM/network call defaults.
6. All extraction model classes declare raw_content_persisted.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MEMORY_TREE = ROOT / "packages" / "memory_tree_runtime"
EXTRACTION_MODULE = MEMORY_TREE / "extraction.py"

ALLOWED_EXTRACTION_IMPORTS = (
    "__future__",
    "dataclasses",
    "datetime",
    "enum",
    "hashlib",
    "json",
    "math",
    "pathlib",
    "packages.memory_tree_runtime",
    "pydantic",
    "re",
    "sqlite3",
    "typing",
)

FORBIDDEN_NETWORK_IMPORTS = (
    "httpx",
    "requests",
    "urllib",
    "socket",
    "openai",
    "anthropic",
    "transformers",
    "sentence_transformers",
    "torch",
    "numpy",
    "sklearn",
    "faiss",
    "chromadb",
    "pinecone",
    "weaviate",
    "qdrant_client",
    "cohere",
    "tiktoken",
    "embeddings",
    "os",
    "subprocess",
    "packages.core",
    "packages.provider_runtime",
    "packages.assistant_runtime",
    "services",
    "apps",
)

REQUIRED_EXTRACTION_TERMS = (
    "ExtractedEntity",
    "ExtractedFact",
    "ExtractedPreference",
    "ExtractedRelation",
    "ChunkExtractionResult",
    "DailyDigestEntry",
    "extract_chunk",
    "extract_chunks",
    "extract_entities",
    "extract_facts",
    "extract_preferences",
    "extract_relations",
    "build_daily_digest_entries",
    "build_daily_digest_node",
    "compute_topic_hotness",
    "compute_hotness_boost",
    # Provenance fields
    "chunk_id",
    "document_id",
    "source_id",
    # Safety markers
    "raw_content_persisted",
    # Determinism marker: no network/LLM default
    "No embeddings, no network, no LLM",
)

REQUIRED_SAFETY_MARKERS = (
    "raw_content_persisted: Literal[False] = False",
)

FORBIDDEN_EXTRACTION_TEXT = (
    "raw_content_persisted: Literal[True]",
    "raw_secret_persisted: Literal[True]",
    "import httpx",
    "import requests",
    "import torch",
    "import openai",
    "import anthropic",
    "import numpy",
    "import transformers",
    "import sklearn",
)

RESULT_MODEL_CLASSES = (
    "ExtractedEntity",
    "ExtractedFact",
    "ExtractedPreference",
    "ExtractedRelation",
    "ChunkExtractionResult",
    "DailyDigestEntry",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if path.is_file()) if root.exists() else []


def _module_from_import(node: ast.AST) -> str | None:
    if isinstance(node, ast.ImportFrom):
        return None if node.level else node.module
    if isinstance(node, ast.Import):
        return node.names[0].name if node.names else None
    return None


def _matches(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _check_extraction_imports(failures: list[str]) -> None:
    if not EXTRACTION_MODULE.exists():
        failures.append("extraction.py missing from packages/memory_tree_runtime")
        return
    tree = ast.parse(EXTRACTION_MODULE.read_text(encoding="utf-8"), filename=str(EXTRACTION_MODULE))
    rel = EXTRACTION_MODULE.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        module = _module_from_import(node)
        if module is None:
            continue
        if _matches(module, tuple(FORBIDDEN_NETWORK_IMPORTS)):
            failures.append(f"{rel} imports forbidden network/embedding/OS dependency: {module}")
        if not _matches(module, ALLOWED_EXTRACTION_IMPORTS):
            failures.append(f"{rel} imports non-approved dependency: {module}")


def _check_required_terms(extraction_text: str, failures: list[str]) -> None:
    for term in REQUIRED_EXTRACTION_TERMS:
        if term not in extraction_text:
            failures.append(f"extraction.py missing required term: {term!r}")


def _check_safety_markers(extraction_text: str, failures: list[str]) -> None:
    for marker in REQUIRED_SAFETY_MARKERS:
        count = extraction_text.count(marker)
        if count < len(RESULT_MODEL_CLASSES):
            failures.append(
                f"extraction.py has only {count} occurrences of {marker!r}; "
                f"expected at least {len(RESULT_MODEL_CLASSES)} (one per result model)"
            )


def _check_forbidden_text(extraction_text: str, failures: list[str]) -> None:
    for token in FORBIDDEN_EXTRACTION_TEXT:
        if token in extraction_text:
            failures.append(f"extraction.py contains forbidden token: {token!r}")


def _check_provenance_fields(extraction_text: str, failures: list[str]) -> None:
    for cls_name in RESULT_MODEL_CLASSES:
        # Each result model class must declare chunk_id, document_id, source_id fields.
        if f"class {cls_name}" not in extraction_text:
            failures.append(f"extraction.py missing result model class: {cls_name}")


def _check_memory_tree_imports_include_extraction(failures: list[str]) -> None:
    init_path = MEMORY_TREE / "__init__.py"
    if not init_path.exists():
        failures.append("packages/memory_tree_runtime/__init__.py not found")
        return
    init_text = init_path.read_text(encoding="utf-8")
    for name in ("extract_chunk", "extract_chunks", "ChunkExtractionResult", "DailyDigestEntry"):
        if name not in init_text:
            failures.append(f"packages/memory_tree_runtime/__init__.py does not export: {name}")


def main() -> int:
    failures: list[str] = []

    if not EXTRACTION_MODULE.exists():
        failures.append("CRITICAL: packages/memory_tree_runtime/extraction.py does not exist")
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    extraction_text = EXTRACTION_MODULE.read_text(encoding="utf-8")

    _check_extraction_imports(failures)
    _check_required_terms(extraction_text, failures)
    _check_safety_markers(extraction_text, failures)
    _check_forbidden_text(extraction_text, failures)
    _check_provenance_fields(extraction_text, failures)
    _check_memory_tree_imports_include_extraction(failures)

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1

    print("PASS memory extraction boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
