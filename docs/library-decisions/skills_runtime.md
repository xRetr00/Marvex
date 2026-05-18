# Library Decision: Skills Runtime Foundation

library name: none adopted

official source: No single maintained Python Skills SDK/spec is adopted for this foundation. Anthropic Agent Skills documentation and Claude Code SDK Skills documentation were reviewed as official ecosystem references, but they describe filesystem discovery, autonomous model invocation, code execution, and platform-specific Skill tools that do not fit this Marvex foundation boundary.

maintenance status: Not applicable because no dependency is added. The reviewed official references are active product/platform documentation, not a neutral Marvex runtime dependency.

why use it: No maintained library was adopted because this task needs Marvex-owned safety primitives for local skill metadata, validation, bounded prompt contribution, and CapabilityRuntime context delivery. A broad external skill ecosystem would add install/execution semantics that are explicitly out of scope.

why not custom code: A full custom skill ecosystem would be too much surface area. This foundation implements only small Pydantic boundary models and deterministic test fixtures. It does not build registries, installers, script execution, remote loading, UI, or package management.

fallback if abandoned: Keep SkillsRuntime behind `packages.skills_runtime` and the capability adapter seam so future maintained skill package formats can be mapped into these models or replace the adapter without changing Core or CapabilityRuntime policy ownership.

pyproject dependency: none

declared dependency: not declared

verified date: 2026-05-18

verified by: Codex

scope: Foundation-only. SkillsRuntime may represent local skill refs/manifests/resources, validate policy-safe prompt contributions, produce safe projections, and feed CapabilityRuntime eligibility/context delivery. It must not execute skill scripts, install skills, load remote skills, route providers, select models, or own assistant runtime behavior.

architecture fit: Good as a Marvex-owned boundary because CapabilityRuntime remains authoritative for permission and context delivery policy, while SkillsRuntime owns only skill package safety and projection.

adopt / defer / reject decision: Defer dependency adoption. Implement the narrow Marvex skill boundary now.

risks: Skill instructions can become prompt injection, hidden policy override, or unbounded context bloat. Mitigations in this phase are local-only refs, `Literal[False]` execution/install/remote flags, policy-override phrase rejection, bounded `SkillPromptContribution`, safe projections, and boundary gates.

comparison to custom routing: Skills are not routers, tools, provider selectors, MCP clients, or integrations. They are validated local context packages selected through CapabilityRuntime eligibility.
