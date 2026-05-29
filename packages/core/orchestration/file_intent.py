"""File-capability intent parsing for natural-language user input.

Pulled out of ``services.core.main`` so the heuristic can be unit-tested
without booting the full Core service (FastAPI, intent/tool workers, etc.).

The previous routing in this module silently fell through to ``file.read``
on a directory path for question-form queries like
"what is the PDF files on my desktop?", which the tool worker then rejected
with a generic policy-block. We now treat any plural-"files" phrasing
referring to a known directory shorthand as a list intent, while preserving
the original behaviour for explicit "read file"/"open file" verbs.
"""

from __future__ import annotations

import re
from typing import Mapping


__all__ = [
    "file_path_from_input",
    "file_request_from_input",
    "file_rg_query",
    "file_search_query",
    "file_write_request_from_input",
    "file_write_topic",
]


_FILE_WRITE_GENERATIVE_MARKERS: tuple[str, ...] = (
    "what is",
    "what are",
    "what the",
    "what does",
    "explain",
    "definition of",
    "meaning of",
    "means",
    "write about",
    "summary of",
    "describe",
)


def file_write_topic(text: str | None) -> str:
    """Strip write/destination scaffolding to leave the topic to compose."""

    value = (text or "").strip()
    cleaned = re.sub(
        r"\b(write|save|create|make|in|into|to|that|the|this|a|an|file|on|my|please|for\s+me|desktop|documents|downloads)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"[A-Za-z0-9_.-]+\.(?:txt|md|json|csv|log)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or value.strip()


def file_write_request_from_input(text: str | None) -> dict[str, object] | None:
    value = (text or "").strip()
    lowered = value.lower()
    if not any(action in lowered for action in ("write", "create", "save", "make")):
        return None
    filename = "output.txt"
    match = re.search(r"(?:^|\s)([A-Za-z0-9_.-]+\.(?:txt|md|json|csv|log))", value)
    if match:
        filename = match.group(1).strip()
    path = filename
    if "desktop" in lowered:
        path = f"Desktop/{filename}"

    content = ""
    content_prompt: str | None = None

    # 1. Quoted literal content is unambiguous and always wins.
    quoted = re.search(r"[\"'“‘](.+?)[\"'”’]", value)
    if quoted and quoted.group(1).strip():
        content = quoted.group(1).strip()
    else:
        # 2. "write <literal content> to/into/in <destination>".
        content_match = re.search(
            r"(?:write|save)\s+(.+?)\s+(?:to|into|in)\s+", value, flags=re.IGNORECASE
        )
        literal = content_match.group(1).strip().strip("\"'") if content_match else ""
        if literal and not any(marker in literal.lower() for marker in _FILE_WRITE_GENERATIVE_MARKERS):
            content = literal
        elif filename.lower() == "test.txt" and re.search(r"\btest\b", lowered):
            content = "test"
        # 3. Generative intent - capture the topic so the caller can ask the
        #    provider to compose the body instead of writing an empty file.
        if not content and any(marker in lowered for marker in _FILE_WRITE_GENERATIVE_MARKERS):
            content_prompt = file_write_topic(value)

    request: dict[str, object] = {"path": path, "content": content, "overwrite": False}
    if content_prompt:
        request["content_prompt"] = content_prompt
    return request


_DIRECTORY_MARKERS: tuple[str, ...] = (
    "desktop",
    "documents",
    "downloads",
    "pictures",
    "videos",
    "music",
)


_LIST_MARKERS: tuple[str, ...] = (
    "list",
    "names",
    "filenames",
    "show me",
    "what is the",
    "what are the",
    "what files",
    "which files",
    "files on my",
    "files in",
    "files at",
)


_EXPLICIT_READ_VERBS: tuple[str, ...] = (
    "read file",
    "read the file",
    "open file",
    "open the file",
    "inspect file",
)


def file_path_from_input(text: str | None) -> str:
    value = (text or "").strip()
    match = re.search(r"(?:read|inspect)\s+file\s+(.+)$", value, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip().strip("\"'")
    if re.search(r"\bdesktop\b", value, flags=re.IGNORECASE):
        return "Desktop"
    return value.strip().strip("\"'") or "."


def file_search_query(text: str | None) -> str:
    value = (text or "").strip()
    match = re.search(r"search\s+(?:files?\s+)?(?:for\s+)?(.+)$", value, flags=re.IGNORECASE)
    return (match.group(1) if match else value).strip().strip("\"'") or value


def file_rg_query(text: str | None) -> str:
    value = (text or "").strip()
    cleaned = re.sub(
        r"\b(i\s+need|find|search|look\s+for|where\s+is|on|in|the|my|desktop|folder|directory|drive|disk)\b",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or value


def file_request_from_input(text: str | None) -> Mapping[str, object]:
    lowered = (text or "").lower()
    path = file_path_from_input(text)
    if any(marker in lowered for marker in ("report", "document", "docx", "pptx", "xlsx")) and any(
        location in lowered for location in ("desktop", "folder", "directory", "drive", "disk")
    ):
        return {
            "action": "find files with ripgrep",
            "capability": "search",
            "capability_id": "file.rg",
            "arguments": {"path": path, "query": file_rg_query(text), "max_matches": 50},
            "extension": None,
        }
    is_list_intent = any(marker in lowered for marker in _LIST_MARKERS) or (
        "files" in lowered and any(loc in lowered for loc in _DIRECTORY_MARKERS)
    )
    explicit_read = any(verb in lowered for verb in _EXPLICIT_READ_VERBS)
    if is_list_intent and not explicit_read:
        for known in _DIRECTORY_MARKERS:
            if known in lowered:
                path = "Desktop" if known == "desktop" else known.capitalize()
                break
        extension = ".pdf" if "pdf" in lowered else None
        return {
            "action": "list files",
            "capability": "list",
            "capability_id": "file.list",
            "arguments": {"path": path, "max_entries": 200},
            "extension": extension,
        }
    if "search" in lowered:
        return {
            "action": "search files",
            "capability": "search",
            "capability_id": "file.search",
            "arguments": {"path": path, "query": file_search_query(text), "max_matches": 50},
            "extension": None,
        }
    return {
        "action": "read file",
        "capability": "read",
        "capability_id": "file.read",
        "arguments": {"path": path, "max_preview_chars": 1200},
        "extension": None,
    }
