# Skills Runtime Foundation

## Status

Skills Runtime Foundation is implemented as a safe representation, validation, selection, and context-delivery layer. It is not a script runner, package installer, plugin host, MCP server, tool runtime, prompt engine, or assistant brain.

## Definition

Skill is bounded capability context: a locally referenced package of instructions, resources, and optional script metadata that can help shape a future assistant turn only after validation and CapabilityRuntime eligibility. A skill contributes bounded context. It does not execute actions, call tools, override policy, install dependencies, fetch remote content, or rewrite the whole prompt.

Skills differ from adjacent surfaces:

- Tool: a callable action with arguments and side effects. A skill is guidance/context and has no execution path.
- MCP tool: a protocol-discovered callable tool mediated by the MCP adapter and CapabilityRuntime execution requests. A skill is not MCP protocol machinery.
- Plugin: a packaged extension surface that may contain connectors or app integration metadata. A skill is narrower instruction/resource context.
- Connector: an authenticated external account or service link. A skill stores no credentials and performs no external access.
- Integration: a configured relationship between plugin/connector capability and Marvex. A skill is local context, not account integration.

## Ownership

`packages.skills_runtime` owns `SkillRef`, `SkillResourceRef`, `SkillManifest`, `SkillValidationResult`, `SkillEligibilityDecision`, `SkillPromptContribution`, `SafeSkillProjection`, and the deterministic fake skill package used by tests.

CapabilityRuntime remains authoritative for capability refs, manifests, eligibility decisions, context delivery policy, compaction policy, and context packs. SkillsRuntime can project skills into CapabilityRuntime-owned models, but skills cannot override Marvex policy.

`packages.adapters.capabilities.skills` is now a thin compatibility adapter surface that delegates to `packages.skills_runtime` instead of owning skill primitives.

## Safety Invariants

- Skill resources are local `local://skills/...` references only.
- Remote skill loading is blocked.
- Arbitrary skill install is blocked.
- Skill scripts are metadata only and are never executed.
- Prompt contributions are bounded and validated for policy-override language.
- Raw prompts, raw instructions, raw transcripts, tool payloads, credentials, and provider payloads are not persisted by default.
- Core, Local API, RuntimeComposition, ProviderRuntime, Telemetry, AssistantRuntime, MemoryRuntime, SessionRuntime, local service startup, MCP adapter, CLI, and services do not own skill runtime behavior.

## Validation

`tests/skills_runtime` covers manifest projection, local-resource validation, policy-override rejection, bounded prompt contribution delivery through CapabilityRuntime context packs, and deterministic fake skill packages.

`scripts/check_skills_runtime_boundaries.py` enforces SkillsRuntime isolation and is included in `python scripts/run_all_checks.py`.
