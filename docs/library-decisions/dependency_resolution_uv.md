# Library Decision: uv Dependency Resolution Workflow

library name: uv

official source: https://docs.astral.sh/uv/ and https://github.com/astral-sh/uv

maintenance status: Active as of May 18, 2026. Local audit found `uv 0.11.3` available on this workstation.

why use it: Marvex has multiple SDK-backed runtime adapters with tight transitive dependency constraints. `uv lock`, `uv sync`, and `uv run` give Marvex a repeatable resolver path for OpenAI, LiteLLM, MCP, Playwright, Semantic Router, Authlib, Browser-use, and future dependency work.

why not custom code: Custom dependency scripts would duplicate resolver behavior and would not provide a reliable lockfile. One-off `pip install` commands already risk drifting the local environment away from declared dependencies.

fallback if abandoned: Keep `pyproject.toml` as the source of truth and fall back to standard pip in a clean virtual environment only after documenting the blocker. Do not hand-edit lockfiles.

pyproject dependency: none

declared dependency: not a runtime dependency

verified date: 2026-05-18

verified by: Codex

scope: Development dependency workflow only. `uv.lock` records resolved packages, `.venv/` is local and ignored, and project validation should run through `uv run` when uv is available.

architecture fit: Good. The resolver does not own Marvex runtime behavior, policy, routing, memory, tools, or provider execution. It only standardizes dependency installation and validation.

adopt / defer / reject decision: Adopt `uv` as the preferred dependency workflow when available. Required commands are `uv lock`, `uv sync`, `uv run python -m pip check`, `uv run python -m pytest -q`, and `uv run python scripts/run_all_checks.py`.

safe update workflow: Change dependency declarations in `pyproject.toml`, run `uv lock`, run `uv sync`, then run `uv run python -m pip check`, targeted tests for touched adapter families, full pytest, and `scripts/run_all_checks.py`. Avoid one-off pip installs and never edit `uv.lock` manually.

risks: Resolver behavior can expose conflicts across supported Python ranges. Treat a failed `uv lock` as a real dependency blocker until the conflict is documented or the supported Python range is intentionally changed.

comparison to custom routing: `uv` is not a runtime dependency manager inside Marvex. It is a development and validation tool only.
