# Process Runtime Package

Status: minimal local health/version runtime provider.

Ownership: Process-readiness object construction boundary.

Responsibility: Build `HealthCheck` and `VersionInfo` contract objects from
explicit in-memory configuration.

Forbidden responsibilities:

- HTTP endpoints.
- Daemon mode.
- Subprocess management.
- Process supervision.
- Service loops or background threads.
- Filesystem, environment, or network access.
- Provider behavior or provider health probing.
- CLI behavior.
- Tool execution, memory, intent, UI, voice, or desktop context.

Dependency direction:

- May depend on approved contracts only.
- Must not depend on Core, ports, adapters, ProviderRuntime, telemetry, apps, or
  services.
