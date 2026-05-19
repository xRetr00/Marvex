# Adaptive Context, Evidence, Memory Learning, and Governance

This checkpoint makes pre-Voice context delivery adaptive instead of static.

Implemented runtime behavior:

- `packages.prompt_harness_runtime.adaptive` builds route-specific context policy, budgets, prompt ordering, citation guidance, and safe tool-schema candidates.
- Grounded lookup routes have non-zero evidence budget and inject web evidence before the response contract.
- Memory query routes have non-zero memory budget and inject memory evidence before the response contract.
- Tool, browser, and MCP routes prioritize eligible capability schemas plus approval policy before continuation/answer instructions.
- Clarification routes keep context minimal and suppress unnecessary evidence/tool blocks.
- Prompt block suppression is explicit through `PromptBlockSuppression`, not accidental global omission.

Safety boundaries:

- No all-tools or all-memory dumping.
- Tool schema injection uses eligible `CapabilityManifest` safe summaries only.
- Evidence and memory sections use safe refs/excerpts only.
- Citation guidance is included only when evidence exists.
- Provider tool calls remain proposals; CapabilityRuntime still owns approval and dispatch.
