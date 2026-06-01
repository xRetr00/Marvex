"""Dependency + feature detection for runtime-downloadable heavy deps.

Each heavy dep group (tts, stt, wakeword, browser, mcp, computer_use, embeddings) is checked
with importlib.util.find_spec (no import attempted) plus optional model-file
presence.  Features degrade gracefully: missing dep → feature disabled.
No network, no pip, no side-effects in this module.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Safe asset/model root — resolved from this file's location so it works in
# any working directory.  Actual model files live under assets/models/ at
# the repo root (or user data dir if relocated in production).
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MODEL_ROOT = _REPO_ROOT / "assets" / "models"


class DepInfo(BaseModel):
    """Safe projection of a single dependency's status."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    group: str = Field(..., min_length=1)
    installed: bool
    feature: str = Field(..., min_length=1)


class DepGroup(BaseModel):
    """A logical group of packages that together enable one feature."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    feature: str = Field(..., min_length=1)
    packages: tuple[str, ...]
    # Relative paths under _MODEL_ROOT that must exist for the feature to work
    model_paths: tuple[str, ...] = ()
    # pip-installable specifier(s) for runtime install (may differ from import name)
    install_specs: tuple[str, ...] = ()
    # Some features need every listed import, while others are alternatives.
    require_all_packages: bool = False


# ---------------------------------------------------------------------------
# Registry of all heavy dep groups mapped to features
# ---------------------------------------------------------------------------

DEP_GROUPS: tuple[DepGroup, ...] = (
    DepGroup(
        id="tts",
        label="Text-to-Speech",
        feature="tts",
        packages=("kokoro_onnx", "piper"),
        install_specs=("kokoro-onnx", "piper-tts"),
    ),
    DepGroup(
        id="stt",
        label="Speech-to-Text",
        feature="stt",
        packages=("moonshine", "funasr", "sherpa_onnx"),
        install_specs=("moonshine-voice", "funasr", "sherpa-onnx"),
    ),
    DepGroup(
        id="wakeword",
        label="Wake-word detection",
        feature="wakeword",
        packages=("sherpa_onnx",),
        install_specs=("sherpa-onnx", "sherpa-onnx-core"),
    ),
    DepGroup(
        id="web_search",
        label="Web search (DDGS)",
        feature="web_search",
        packages=("ddgs",),
        install_specs=("ddgs",),
    ),
    DepGroup(
        id="browser",
        label="Browser automation",
        feature="browser",
        packages=("playwright", "browser_use"),
        install_specs=("playwright", "browser-use"),
        require_all_packages=True,
    ),
    DepGroup(
        id="mcp",
        label="MCP Python SDK",
        feature="mcp",
        packages=("mcp",),
        install_specs=("mcp",),
    ),
    DepGroup(
        id="computer_use",
        label="Windows computer use",
        feature="computer_use",
        packages=("mcp", "uiautomation"),
        install_specs=("mcp", "uiautomation"),
        require_all_packages=True,
    ),
    DepGroup(
        id="embeddings",
        label="Local embeddings (fastembed)",
        feature="embeddings",
        packages=("fastembed",),
        install_specs=("fastembed",),
    ),
)


class FeatureAvailability(BaseModel):
    """Per-feature boolean availability map — safe projection only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tts: bool = False
    stt: bool = False
    wakeword: bool = False
    web_search: bool = False
    browser: bool = False
    mcp: bool = False
    computer_use: bool = False
    embeddings: bool = False


def _spec_present(package_import_name: str) -> bool:
    """Return True if importlib can find the package without importing it."""
    try:
        return importlib.util.find_spec(package_import_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _model_files_present(group: DepGroup) -> bool:
    """Return True if all required model files exist under the safe model root."""
    if not group.model_paths:
        return True
    for rel in group.model_paths:
        if not (_MODEL_ROOT / rel).exists():
            return False
    return True


def detect_dep(group: DepGroup) -> DepInfo:
    """Check whether a single dep group is installed (no import, no network)."""
    package_results = tuple(_spec_present(pkg) for pkg in group.packages)
    pkg_ok = all(package_results) if group.require_all_packages else any(package_results)
    models_ok = _model_files_present(group)
    installed = pkg_ok and models_ok
    return DepInfo(
        id=group.id,
        label=group.label,
        group=group.id,
        installed=installed,
        feature=group.feature,
    )


def detect_all() -> tuple[DepInfo, ...]:
    """Detect all dep groups.  No side-effects; CI-safe."""
    return tuple(detect_dep(g) for g in DEP_GROUPS)


def detect_features() -> FeatureAvailability:
    """Map dep detection results to a per-feature availability dict."""
    infos = {info.feature: info.installed for info in detect_all()}
    return FeatureAvailability(
        tts=infos.get("tts", False),
        stt=infos.get("stt", False),
        wakeword=infos.get("wakeword", False),
        web_search=infos.get("web_search", False),
        browser=infos.get("browser", False),
        mcp=infos.get("mcp", False),
        computer_use=infos.get("computer_use", False),
        embeddings=infos.get("embeddings", False),
    )
