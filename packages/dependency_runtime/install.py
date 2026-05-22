"""Bounded runtime install/download for heavy dep groups.

Rules:
- Explicit/user-initiated only (install_request.explicit_user_triggered must be True).
- Packages are installed into the running user site via pip (--user, --quiet).
- Model files are downloaded to the safe model root only.
- No silent/background installs; no secret/raw persistence.
- No subprocess calls to shell; subprocess.run with a fixed argv only.
- All operations are logged to stderr via the stdlib logging module.
"""
from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.dependency_runtime.detection import DEP_GROUPS, DepGroup, detect_dep

logger = logging.getLogger("dependency_runtime.install")

_SCHEMA_VERSION = "1"

# Injectable pip runner for tests: (argv: list[str]) -> (success, detail)
PipRunner = Callable[[list[str]], tuple[bool, str]]


class InstallStatus(str, Enum):
    INSTALLING = "installing"
    INSTALLED = "installed"
    ERROR = "error"
    BLOCKED = "blocked"


class InstallRequest(BaseModel):
    """A user-initiated install/download request for a single dep group."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., min_length=1)
    # Must be True — no silent installs
    explicit_user_triggered: Literal[True] = True


class InstallResult(BaseModel):
    """Safe projection returned to the caller/UI."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = _SCHEMA_VERSION
    id: str
    status: InstallStatus
    detail: str = ""
    raw_payload_persisted: Literal[False] = False


def _find_group(dep_id: str) -> DepGroup | None:
    for group in DEP_GROUPS:
        if group.id == dep_id:
            return group
    return None


def _pip_install(specs: tuple[str, ...], *, pip_runner: PipRunner | None = None) -> tuple[bool, str]:
    """Install packages via pip into user site.  Returns (success, detail)."""
    if not specs:
        return True, "no_packages_to_install"
    argv = [sys.executable, "-m", "pip", "install", "--user", "--quiet", *specs]
    logger.info("dependency_runtime.install: pip install %s", specs)
    if pip_runner is not None:
        return pip_runner(argv)
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, no shell=True
            argv,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown pip error")[:500]
            logger.warning("dependency_runtime.install: pip failed: %s", detail)
            return False, detail
        return True, "pip_install_succeeded"
    except Exception as exc:  # noqa: BLE001
        logger.error("dependency_runtime.install: pip exception: %s", exc)
        return False, str(exc)[:300]


def runtime_install(
    request: InstallRequest,
    *,
    pip_runner: PipRunner | None = None,
) -> InstallResult:
    """Perform a bounded, user-initiated install for the given dep group.

    - Validates the request is explicit_user_triggered.
    - Looks up the group in DEP_GROUPS.
    - Runs pip install --user for the group's install_specs.
    - Re-checks detection and returns the result.
    - No secret/raw persistence; no shell=True.
    """
    group = _find_group(request.id)
    if group is None:
        return InstallResult(
            id=request.id,
            status=InstallStatus.BLOCKED,
            detail="dep_group_not_found",
        )

    # Check if already installed
    info = detect_dep(group)
    if info.installed:
        return InstallResult(
            id=request.id,
            status=InstallStatus.INSTALLED,
            detail="already_installed",
        )

    # Run pip install
    success, detail = _pip_install(group.install_specs, pip_runner=pip_runner)
    if not success:
        return InstallResult(id=request.id, status=InstallStatus.ERROR, detail=detail)

    # Re-detect after install
    updated_info = detect_dep(group)
    final_status = InstallStatus.INSTALLED if updated_info.installed else InstallStatus.INSTALLING
    return InstallResult(id=request.id, status=final_status, detail=detail)
