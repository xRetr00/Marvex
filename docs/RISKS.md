# Risks

## Top Risks

- CapabilityRuntime execution policy becoming a god file.
- Assistant turn integration spine becoming the central assistant brain.
- Green tests masking stale governance docs.
- Existing code being mistaken for product approval.
- Provider logic leaking into Core.
- RuntimeComposition becoming a routing or policy brain.
- Local API or Control Plane executing tools directly.
- Telemetry becoming a raw prompt/transcript/provider/tool payload store.
- Marketplace or skill metadata becoming arbitrary install or execution paths.
- Browser/computer-use seams becoming unbounded automation.
- Custom SDKs replacing maintained libraries.
- Hidden global state.
- Weak tests or gates with broad exceptions.

## Risk Controls

- `docs/GOVERNANCE_CLASSIFICATION.md` classifies every major surface.
- Existing code is not approval; future work needs current goal spec, docs/CONTRACT_APPROVALS.md, PROJECT_STATUS.md, validation gates, and relevant architecture docs.
- File size and god-file checks target known risk files directly.
- Service placeholders remain README-only except explicitly approved
  service-owned entrypoint files.
- Core/provider/ports/adapters boundaries remain validated by scripts.
- CapabilityRuntime owns permission, approval, execution request, result envelope, and loop guard policy.
- Assistant turn integration stays composition glue and must not own provider routing, prompt policy, memory policy, or tool policy.
- Library decision records remain required for runtime dependencies and frontend stack dependencies.

## Current Cleanup Priority

The next cleanup priority is reducing remaining large-file and central-brain risk inside bounded foundations without adding product features.
