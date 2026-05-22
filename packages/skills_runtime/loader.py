from __future__ import annotations

from pathlib import Path

from packages.skills_runtime.models import SkillManifest, SkillPromptContribution


_FORBIDDEN_INSTRUCTION_TERMS = (
    "api_key",
    "authorization",
    "bearer",
    "ignore previous instructions",
    "ignore system instructions",
    "override marvex policy",
    "override system prompt",
    "password",
    "raw prompt",
    "secret",
    "system prompt",
    "token",
    "transcript",
)


class SkillInstructionLoader:
    def __init__(self, *, local_skill_root: Path | str, max_instruction_chars: int = 800) -> None:
        self._root = Path(local_skill_root).resolve()
        self._max_instruction_chars = max(1, min(max_instruction_chars, 1200))

    def load_prompt_contributions(
        self,
        manifest: SkillManifest,
    ) -> tuple[SkillPromptContribution, ...]:
        text = self._read_local_instruction(manifest)
        summary = _safe_instruction_summary(text, max_chars=self._max_instruction_chars)
        base_contributions = manifest.prompt_contributions or (
            SkillPromptContribution(
                schema_version=manifest.schema_version,
                contribution_id=f"{manifest.skill_ref.skill_id}.instruction",
                skill_ref=manifest.skill_ref,
                summary=manifest.description[:600],
                when_to_use="When this local skill is explicitly selected.",
                max_context_chars=min(self._max_instruction_chars, 1200),
            ),
        )
        loaded: list[SkillPromptContribution] = []
        for contribution in base_contributions:
            max_chars = min(contribution.max_context_chars, self._max_instruction_chars)
            loaded.append(
                SkillPromptContribution(
                    schema_version=contribution.schema_version,
                    contribution_id=f"{contribution.contribution_id}.loaded",
                    skill_ref=contribution.skill_ref,
                    summary=f"{contribution.summary} Local instruction: {summary}"[:600],
                    when_to_use=contribution.when_to_use,
                    max_context_chars=max_chars,
                )
            )
        return tuple(loaded)

    def _read_local_instruction(self, manifest: SkillManifest) -> str:
        relative = manifest.instruction_ref.uri.removeprefix("local://skills/")
        target = (self._root / relative).resolve()
        try:
            target.relative_to(self._root)
        except ValueError as exc:
            raise ValueError("skill instruction path escapes local skill root") from exc
        if not target.is_file():
            raise ValueError("skill instruction file is missing")
        return target.read_text(encoding="utf-8", errors="replace")


def _safe_instruction_summary(text: str, *, max_chars: int) -> str:
    lines = [line.strip(" #\t") for line in text.splitlines() if line.strip()]
    summary = " ".join(lines)[:max_chars].strip()
    if not summary:
        raise ValueError("skill instruction is empty")
    lowered = summary.lower()
    if any(term in lowered for term in _FORBIDDEN_INSTRUCTION_TERMS):
        raise ValueError("skill instruction contains policy override or unsafe text")
    return summary
