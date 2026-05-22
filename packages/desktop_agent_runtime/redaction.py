from __future__ import annotations

import re


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password|authorization|bearer)\b"),
    re.compile(r"(?i)\b(must-not-leak|sk-[a-z0-9_-]{8,})\b"),
)


def redact_and_bound_text(text: str, *, max_chars: int) -> str:
    safe = str(text or "").replace("\x00", " ")
    for pattern in _SECRET_PATTERNS:
        safe = pattern.sub("[REDACTED]", safe)
    safe = "\n".join(line.strip() for line in safe.splitlines() if line.strip())
    if len(safe) <= max_chars:
        return safe
    return safe[: max(0, max_chars - 15)].rstrip() + " [TRUNCATED]"
