# Library Decision: Tiny Intent Validator

library name: LiquidAI LFM2.5-350M

official source: https://www.liquid.ai/blog/lfm2-5-350m-no-size-left-behind and https://huggingface.co/LiquidAI/LFM2.5-350M

maintenance status: Active as of April 29, 2026. Liquid AI announced LFM2.5-350M on March 31, 2026 and describes it as a 350M parameter model improved with more pre-training and reinforcement learning. Liquid says it is strong at tool use, data extraction, and structured outputs at the edge, but not recommended for math, code, or creative writing.

why use it: Marvex needs a cheap validator for route confidence, ambiguity, and structured intent sanity checks. A tiny model is a better fit than sending every turn to a large LLM or writing a custom intent framework.

why not custom code: A custom intent validator would invite Vaxil-style cue lists, confidence hacks, and special cases. A small maintained model can be evaluated as a replaceable validator with measurable fixtures.

fallback if abandoned: Evaluate another tiny local model with strong structured-output behavior, or use provider-native structured classification behind the same validator boundary. If no maintained model is good enough, keep deterministic validation minimal and require a new RFC before custom training or custom framework work.

pyproject dependency: none in Task 033

declared dependency: not declared; Task 033 must not edit pyproject.toml

verified date: 2026-04-29

verified by: Codex

scope: Candidate only. Future use may validate intent JSON, ambiguity, and route confidence. It must not answer user questions, dispatch tools, build prompts, or own policy.

architecture fit: Good as a validator after Semantic Router and before policy/context construction. It should receive compact normalized input and candidate route metadata, then return a bounded validation result.

adopt / defer / reject decision: Defer. LFM2.5-350M is promising, but Task 033 does not add inference dependencies or model runtime. Task 034 may leave the validator boundary empty or mocked until a separate model-runtime decision approves how to run the model.

risks: Model availability and runtime backend selection are unresolved. Tiny models can be overconfident on ambiguous input. Validation quality must be measured on Marvex replay fixtures before adoption. It must never become a hidden router or answer generator.

comparison to custom routing: Tiny-model validation is preferred over homegrown confidence heuristics once a runtime path is approved. Custom confidence scoring is deferred and limited to tests until real evaluation data proves it is necessary.

structured output comparison: Pydantic validation remains the immediate schema guard because it is already approved. Pydantic AI and Outlines are compared in `policy_engine.md` for future structured prompt contracts, but neither is adopted as a central runtime in Task 033.
