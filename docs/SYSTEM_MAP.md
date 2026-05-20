# System Map

Use this file for first-pass orientation before reading source. It is a map,
not a substitute for the task spec Context Pack.

## Provider Foundation

- Responsibility: Stable provider-facing turn flow through contracts, ports,
  adapters, ProviderRuntime, Core orchestration, CLI, and telemetry.
- Allowed dependencies: Contracts, ProviderPort, documented adapters,
  ProviderRuntime, Core, CLI, telemetry as documented by each boundary.
- Forbidden dependencies: UI, tools, memory, voice, desktop context, service
  workers, and runtime behavior outside the documented surface map.
- Important files: `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
  `packages/core/orchestration/turn_orchestrator.py`,
  `packages/provider_runtime/provider_runtime.py`.
- Do not read unless required: concrete provider adapter internals for non-provider
  tasks; full contract docs when only one contract is involved.

## Process Readiness

- Responsibility: Health/version contracts, local ProcessRuntime object
  construction, future HTTP endpoint planning, and CLI health/version exposure.
- Allowed dependencies: Contracts, local ProcessRuntime, CLI's narrow
  ProcessRuntime integration.
- Disallowed dependencies: HTTP server, daemon, subprocess runtime, service mode,
  provider probing, config loading, Core integration, ProviderRuntime integration.
- Important files: `docs/PROCESS_MODEL.md`, `docs/IPC_API.md`,
  `packages/process_runtime/process_runtime.py`, `apps/cli/main.py`.
- Do not read unless required: service placeholders, future worker docs, or Core
  internals for local health/version tasks.

## CLI

- Responsibility: One-shot text turn client plus local health/version command
  output.
- Allowed dependencies: Public Core orchestration, ProviderRuntime, and
  ProcessRuntime only from `apps/cli/main.py` for approved health/version commands.
- Disallowed dependencies: provider SDKs, services, HTTP servers, config files,
  environment reads, provider health checks, telemetry implementation.
- Important files: `apps/cli/main.py`, `apps/cli/README.md`,
  `tests/api/test_cli.py`.
- Do not read unless required: provider adapter code or Core internals when
  testing CLI argument/output behavior.

## Core

- Responsibility: Turn lifecycle orchestration through contracts, ports, and
  telemetry sink contracts.
- Allowed dependencies: Contracts, ports, telemetry sink contracts.
- Disallowed dependencies: adapters, CLI, services, ProviderRuntime,
  ProcessRuntime, provider-specific behavior.
- Important files: `packages/core/orchestration/turn_orchestrator.py`,
  `packages/core/README.md`, `tests/core/test_turn_orchestrator.py`.
- Do not read unless required: provider adapter internals or CLI files for pure
  Core behavior tasks.

## Contracts

- Responsibility: Implementation-neutral Pydantic models and JSON schemas.
- Allowed dependencies: Pydantic and Python standard library.
- Forbidden dependencies: Core, ports, adapters, CLI, telemetry implementation,
  services, runtime side effects.
- Important files: `packages/contracts/models.py`, `packages/contracts/enums.py`,
  `packages/contracts/schema.py`, `docs/CONTRACTS.md`.
- Do not read unless required: all contract tests when a task touches only docs
  or a single unrelated boundary.

## Ports

- Responsibility: Minimal interface contracts.
- Allowed dependencies: contracts listed in `docs/CONTRACT_APPROVALS.md` only.
- Disallowed dependencies: Core, adapters, CLI, telemetry implementation,
  provider SDKs, concrete provider names.
- Important files: `packages/ports/provider/provider_port.py`,
  `packages/ports/provider/README.md`, `scripts/check_port_boundaries.py`.
- Do not read unless required: adapter implementations for port-only changes.

## Adapters

- Responsibility: Concrete provider integrations behind ports.
- Allowed dependencies: contracts listed in `docs/CONTRACT_APPROVALS.md` and
  documented external SDKs inside adapter boundaries.
- Disallowed dependencies: Core, ports importing adapters, CLI, telemetry,
  services, business policy.
- Important files: `packages/adapters/providers/fake/fake_provider.py`,
  `packages/adapters/providers/litellm/litellm_provider.py`,
  `packages/adapters/providers/lmstudio_responses/lmstudio_responses_provider.py`.
- Do not read unless required: all adapters for a task scoped to one provider.

## ProviderRuntime

- Responsibility: Minimal provider creation boundary for documented provider names.
- Allowed dependencies: ProviderPort and provider adapters listed in `docs/CONTRACT_APPROVALS.md`.
- Disallowed dependencies: Core, CLI, telemetry implementation, services,
  ProcessRuntime, provider policy, fallback/retry/session behavior.
- Important files: `packages/provider_runtime/provider_runtime.py`,
  `packages/provider_runtime/README.md`,
  `scripts/check_provider_runtime_boundaries.py`.
- Do not read unless required: adapter internals beyond constructor names for
  factory-only tasks.

## ProcessRuntime

- Responsibility: Build `HealthCheck` and `VersionInfo` from explicit in-memory
  configuration.
- Allowed dependencies: contracts listed in `docs/CONTRACT_APPROVALS.md` and standard-library modules.
- Disallowed dependencies: Core, adapters, ProviderRuntime, telemetry, apps,
  services, HTTP, sockets, subprocesses, files, environment, provider probing.
- Important files: `packages/process_runtime/process_runtime.py`,
  `packages/process_runtime/README.md`,
  `scripts/check_process_runtime_boundaries.py`.
- Do not read unless required: CLI implementation unless the task is the approved
  local health/version integration.

## Telemetry

- Responsibility: Minimal trace event construction and sink contracts for the
  turn lifecycle.
- Allowed dependencies: contracts listed in `docs/CONTRACT_APPROVALS.md`.
- Disallowed dependencies: adapters, CLI, services, persistent storage, secrets,
  provider behavior.
- Important files: `packages/telemetry/sinks.py`,
  `packages/telemetry/README.md`, `tests/telemetry/test_telemetry_sinks.py`.
- Do not read unless required: provider adapter or CLI code for telemetry-only
  tasks.

## Manual Smoke Scripts

- Responsibility: Developer-only provider path verification.
- Allowed dependencies: CLI/Core/provider runtime paths needed for smoke checks.
- Disallowed dependencies: CI-only assumptions, product runtime behavior,
  service workers.
- Important files: `scripts/smoke_providers.py`, `docs/SMOKE_TESTING.md`.
- Do not read unless required: smoke scripts during normal unit-test or docs-only
  tasks.

## Governance And Validation

- Responsibility: Enforce architecture, dependency, schema, task, status, and
  placeholder rules.
- Allowed dependencies: repository text files and Python standard library.
- Disallowed dependencies: product runtime behavior, SDK calls, service startup,
  external systems.
- Important files: `scripts/run_all_checks.py`, `docs/VALIDATION_GATES.md`,
  `docs/AI_AGENT_RULES.md`, `templates/TASK_SPEC.md`.
- Do not read unless required: every validation script for a task touching one
  documented gate; start with the named gate script.
