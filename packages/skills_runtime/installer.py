from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Literal

import yaml

from packages.skills_runtime.models import (
    SkillManifest,
    SkillPromptContribution,
    SkillRef,
    SkillResourceKind,
    SkillResourceRef,
)

_SAFE_SKILL_ID = re.compile(r"[^a-zA-Z0-9.:-]+")
_POLICY_OVERRIDE = (
    "ignore previous instructions",
    "ignore system instructions",
    "override marvex policy",
    "override system prompt",
    "system prompt",
)


class SkillInstallResult:
    def __init__(
        self,
        *,
        installed: bool,
        manifest: SkillManifest | None,
        reason_code: str,
    ) -> None:
        self.installed = installed
        self.manifest = manifest
        self.reason_code = reason_code
        self.raw_instruction_persisted = False

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "installed": self.installed,
            "skill_id": self.manifest.skill_ref.skill_id if self.manifest is not None else "",
            "reason_code": self.reason_code,
            "raw_instruction_persisted": False,
            "script_execution_allowed": False,
            "arbitrary_install_allowed": False,
        }


class SkillPackageInstaller:
    def __init__(self, *, managed_root: str | Path) -> None:
        self._managed_root = Path(managed_root).resolve()

    def install_from_directory(self, source: str | Path, *, source_label: str) -> SkillInstallResult:
        source_path = Path(source).resolve()
        skill_file = source_path / "SKILL.md"
        if not skill_file.is_file():
            return SkillInstallResult(installed=False, manifest=None, reason_code="skill_md_missing")
        try:
            manifest = manifest_from_skill_md(skill_file, managed_root=self._managed_root)
            target = (self._managed_root / manifest.skill_ref.skill_id).resolve()
            target.relative_to(self._managed_root)
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_path, target)
            return SkillInstallResult(installed=True, manifest=manifest, reason_code=f"installed:{source_label}")
        except Exception:
            return SkillInstallResult(installed=False, manifest=None, reason_code="skill_validation_failed")


def scan_installed_skill_manifests(managed_root: str | Path) -> tuple[SkillManifest, ...]:
    root = Path(managed_root).resolve()
    if not root.is_dir():
        return ()
    manifests: list[SkillManifest] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        try:
            manifests.append(manifest_from_skill_md(skill_file, managed_root=root))
        except Exception:
            continue
    return tuple(manifests)


def manifest_from_skill_md(skill_file: str | Path, *, managed_root: str | Path) -> SkillManifest:
    path = Path(skill_file).resolve()
    text = path.read_text(encoding="utf-8", errors="replace")
    metadata, body = _parse_frontmatter(text)
    name = _safe_skill_id(str(metadata.get("name") or path.parent.name))
    description = str(metadata.get("description") or _first_heading(body) or name).strip()
    _reject_policy_override(name)
    _reject_policy_override(description)
    _reject_policy_override(body[:1200])
    skill_ref = SkillRef(skill_id=name)
    root = Path(managed_root).resolve()
    relative = path.relative_to(root) if _is_relative_to(path, root) else Path(name) / "SKILL.md"
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return SkillManifest(
        schema_version="1",
        skill_ref=skill_ref,
        display_name=name,
        description=description,
        instruction_ref=SkillResourceRef(
            kind=SkillResourceKind.INSTRUCTION,
            uri=f"local://skills/{relative.as_posix()}",
            content_digest=f"sha256:{digest}",
        ),
        prompt_contributions=(
            SkillPromptContribution(
                schema_version="1",
                contribution_id=f"{name}.context",
                skill_ref=skill_ref,
                summary=description[:600],
                when_to_use=str(metadata.get("when_to_use") or description)[:400],
                max_context_chars=800,
            ),
        ),
    )


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    loaded = yaml.safe_load(parts[1]) or {}
    return dict(loaded) if isinstance(loaded, dict) else {}, parts[2]


def _safe_skill_id(value: str) -> str:
    cleaned = _SAFE_SKILL_ID.sub("-", value.strip()).strip(".-:_")
    if not cleaned:
        raise ValueError("skill id is empty")
    return cleaned


def _first_heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.strip("# ").strip()
    return ""


def _reject_policy_override(value: str) -> None:
    lowered = value.lower()
    if any(marker in lowered for marker in _POLICY_OVERRIDE):
        raise ValueError("skill package cannot override policy")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


__all__ = [
    "SkillInstallResult",
    "SkillPackageInstaller",
    "manifest_from_skill_md",
    "scan_installed_skill_manifests",
]

