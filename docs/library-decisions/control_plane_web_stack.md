# Library Decision: Control Plane Web Stack

library name: React, TypeScript, Vite, TanStack Query, Tailwind CSS, shadcn/ui-style local components, Zod, Vitest

official source: https://react.dev/, https://www.typescriptlang.org/, https://vite.dev/, https://tanstack.com/query/latest, https://tailwindcss.com/, https://ui.shadcn.com/, https://zod.dev/, https://vitest.dev/

maintenance status: Active as of May 18, 2026. These are widely maintained frontend foundations with current package releases installed through npm for the isolated `apps/control_plane_web` package.

why use it: The Control Plane needs a local admin dashboard with typed API boundaries, deterministic builds, component tests, data loading states, and maintainable UI primitives. React plus TypeScript and Vite gives a small, well-supported frontend app boundary. TanStack Query handles local API fetch lifecycle. Zod validates JSON from Control Plane endpoints. Tailwind and shadcn/ui-style local components provide a practical UI system without a large opaque application framework.

why not custom code: Custom frontend state/query/runtime code would recreate maintained browser app mechanics and increase safety risk around validation, loading/error states, and API handling. Marvex should own safe contracts and policy boundaries, not reinvent frontend build tooling or query orchestration.

fallback if abandoned: Keep the frontend isolated under `apps/control_plane_web` and accessed only through HTTP/JSON endpoints. If a library is abandoned, replace it inside that app without changing Core, CapabilityRuntime, AssistantRuntime, ProviderRuntime, Local API, Control Plane API policy authority, or backend adapters.

pyproject dependency: none

declared dependency: npm package dependencies in `apps/control_plane_web/package.json`

verified date: 2026-05-18

verified by: Codex

scope: Frontend-only local Control Plane app. It must never import Python internals, execute tools directly, render secrets, or render raw prompts/transcripts/tool/browser/computer/provider payloads by default.

architecture fit: Good. The stack is isolated in `apps/control_plane_web`, uses typed client helpers and Zod validation, and talks only to approved local Control Plane / Local API endpoints.

adopt / defer / reject decision: Adopt for Control Plane frontend foundation. Defer Orb, desktop overlay, voice UI, final assistant shell, remote access, and direct tool execution.

risks: Frontend apps can accidentally render secrets or become an execution surface. Mitigations are typed safe projection schemas, no direct Python imports, no direct tool execution, restrictive boundary checks, no token rendering, and backend approval policy remaining in CapabilityRuntime.