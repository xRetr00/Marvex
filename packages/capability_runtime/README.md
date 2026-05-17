# CapabilityRuntime

CapabilityRuntime owns capability manifests, selection readiness, permission decisions, human approval requirements, context delivery and compaction policy, execution envelopes, safe summaries, loop guards, planning readiness, and verification hooks.

This package does not talk to providers, MCP servers, local APIs, memory, sessions, telemetry stores, or adapters. Adapter packages may translate external protocol shapes into CapabilityRuntime proposals, but adapters cannot bypass CapabilityRuntime policy.
