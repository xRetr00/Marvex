# Control Plane Foundation

Status: foundation in progress; API and web frontend scaffold are implemented.

The Control Plane is Marvex's protected local admin/control surface. It is not the Orb, not a desktop assistant face, not voice UI, and not the final user-facing assistant shell.

## Backend Boundary

Control Plane API must not own policy. It owns local HTTP/auth/JSON projection and command envelopes only. CapabilityRuntime remains authoritative for approval state, permission decisions, risk classification, execution modes, approved execution requests, dispatch policy, and loop guards.

The Human Approval API foundation exposes safe list/read/approve/deny flows for pending approval requests. Approving or denying transitions pending approval state and creates a backend approval decision record only; it does not execute tools. Execution remains blocked until a separate backend runtime path consumes an approved `CapabilityExecutionRequest` under CapabilityRuntime policy.

## Frontend Boundary

Web frontend must never import Python internals. It talks only to approved local Control Plane / Local API endpoints through typed client helpers and safe JSON contracts. The frontend is isolated in `apps/control_plane_web` and uses React, TypeScript, Vite, TanStack Query, Tailwind, shadcn/ui-style local components, and Zod validation. It must not execute tools directly, render secrets, render raw transcripts, render raw browser/computer payloads, or display auth tokens.

## Safe Views

The Control Plane API foundation exposes safe projections for approvals, providers, capabilities/tools, MCP, skills, telemetry/traces, memory/session refs, agent loops, and settings. Provider credentials, API keys, environment variables, raw prompts, raw transcripts, screenshots, DOM, browser/computer payloads, and raw tool inputs/outputs are blocked by default.

## Local Security

Control Plane endpoints require the local bearer-token flow and are intended for loopback-only local operation. Public readiness endpoints in Local API remain separate unless a future task explicitly changes them.