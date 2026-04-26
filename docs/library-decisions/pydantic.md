# Library Decision: Pydantic

library name: Pydantic

official source: https://docs.pydantic.dev/ and https://github.com/pydantic/pydantic

maintenance status: Active as of April 26, 2026. PyPI latest version observed as 2.13.3. Marvex currently installs 2.12.5 under the declared `>=2,<3` range.

why use it: Marvex needs strict, typed, JSON-compatible contract models with required-field validation, enum validation, extra-field rejection, and JSON schema generation.

why not custom code: Custom model validation and schema generation would duplicate mature validation behavior, increase compatibility risk, and weaken contract governance.

fallback if abandoned: Keep contract usage centralized in `packages/contracts/`; replace with another maintained validation library or approved hand-written validation only through an RFC and contract migration task.

pyproject dependency: pydantic

declared dependency: pydantic>=2,<3

verified date: 2026-04-26

verified by: Codex

scope: `packages/contracts/` contract models and schema generation. Consumers may use generated contract objects but must not add business logic to contract models.

risks: The declared range permits newer Pydantic 2.x releases. If a future 2.x release changes validation or schema output in a way that affects Marvex contracts, pinning to a narrower version requires a dependency-governance task and full contract test run.
