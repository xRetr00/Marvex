# Library Decision: Policy Engine and Structured Output Components

library name: PyCasbin, Pydantic AI, and Outlines

official source: https://github.com/apache/casbin-pycasbin, https://github.com/pydantic/pydantic-ai, https://ai.pydantic.dev/, https://dottxt.ai/, and https://docs.dottxt.ai/

maintenance status: Active as of April 29, 2026. PyPI latest versions observed as `pycasbin==2.8.0`, `pydantic-ai==1.88.0`, and `outlines==1.2.12`. PyCasbin documents ACL/RBAC/ABAC authorization support. Pydantic AI is maintained by the Pydantic team as an agent framework with structured outputs, tools, evals, and MCP capabilities. Outlines/dottxt documents constrained JSON and grammar output support.

why use it: PyCasbin is a good component candidate for capability and permission decisions once Marvex has policy contracts. Pydantic AI and Outlines are useful references or future components for typed structured outputs, but both carry too much framework/runtime gravity for Task 033.

why not custom code: Custom authorization logic tends to become scattered conditionals. Custom structured-output parsing tends to become prompt-specific recovery code. Marvex should use mature validation and constrained-generation components where they fit behind narrow boundaries.

fallback if abandoned: Keep policy decisions represented as Marvex contracts so PyCasbin can be replaced by explicit rule tables, OPA, Cedar, or another maintained policy engine. Keep structured-output validation on approved Pydantic contracts until a constrained generation component is approved.

pyproject dependency: none in Task 033

declared dependency: not declared; Task 033 must not edit pyproject.toml

verified date: 2026-04-29

verified by: Codex

scope: Candidate only. No policy runtime, agent runtime, tool runtime, or structured prompt framework is added in Task 033.

architecture fit: PyCasbin fits future policy checks such as capability, subject, object, action, and allow/deny/confirm decisions. Pydantic AI is too broad for the Marvex core spine because it wants to own agent execution. Outlines is better scoped as a future local constrained-output component, but only after model runtime choices are approved.

adopt / defer / reject decision: Adopt PyCasbin as the preferred lightweight policy-engine candidate for a future policy boundary. Defer Outlines for structured local constrained generation. Reject Pydantic AI as a central runtime for Marvex now; it may be reconsidered later for isolated typed agent experiments, but not for Core, intent routing, or policy ownership.

risks: PyCasbin policy files can become another hidden authority if not generated from explicit Marvex contracts. Pydantic AI can pull Marvex toward a framework-owned agent runtime. Outlines depends on compatible generation backends and may be unnecessary if provider-native structured outputs are sufficient.

comparison to custom routing: Policy engines should decide permissions, not infer user intent. Custom route policy remains rejected/deferred because it would mix intent, safety, and dispatch. Phrase-list routing is explicitly rejected as architecture.
