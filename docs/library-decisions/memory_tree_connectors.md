# Memory Tree and Connector Library Decisions

library name: Authlib

official source: https://docs.authlib.org/ and https://github.com/lepture/authlib

maintenance status: adopted. Resolver proof selected `Authlib==1.7.2` with `joserfc==1.6.5`; `python -m pip check` passed after installation on Python 3.12.0.

why use it: OAuth/OIDC mechanics are high-risk infrastructure and should come from a maintained Python library. Marvex uses it only behind `packages.adapters.connectors.authlib_oauth` for an import-backed OAuth backend seam.

why not custom code: Custom OAuth signing, authorization-code handling, token metadata parsing, and refresh behavior would increase security risk and duplicate maintained library work.

fallback if abandoned: Keep connector manifests and OAuth metadata contracts intact, disable the Authlib backend seam, and evaluate another free/open-source Python OAuth library behind the same ConnectorRuntime adapter boundary.

pyproject dependency: authlib

declared dependency: Authlib==1.7.2

verified date: 2026-05-18

verified by: dependency dry-run/install, adapter import proof, targeted tests, `python -m pip check`

scope: OAuth compatibility seam only. ConnectorRuntime remains policy owner; Control Plane never sees raw tokens; no token exchange or account sync starts from the import proof.

risks: OAuth libraries can encourage token handling in application code. Marvex limits Authlib to an adapter seam and models token storage as a future connector auth backend, not public metadata.

---

library name: Nango open-source integration platform

official source: https://www.nango.dev/ and https://github.com/NangoHQ/nango

maintenance status: adapter seam/reference for this checkpoint. The available `nango==0.1.2` Python package was not treated as an official maintained backend, and `nango-python` had no matching distribution in resolver checks.

why use it: Nango is a serious open-source integration/OAuth platform candidate for future connector auth and sync coordination.

why not custom code: A connector auth platform can centralize OAuth app setup, refresh, provider-specific integration behavior, and connector observability better than custom per-provider glue.

fallback if abandoned: Keep direct OAuth through Authlib and ConnectorRuntime contracts; add provider-specific adapters only after library decisions.

pyproject dependency: none

declared dependency: not declared; reference/deferred seam only

verified date: 2026-05-18

verified by: package availability dry-run and official project review

scope: Reference/deferred. No cloud/account service requirement and no runtime dependency in this checkpoint.

risks: Running Nango as a platform is heavier than a Python library seam and may own too much connector runtime behavior unless isolated as a backend service adapter.

---

library name: Airbyte CDK

official source: https://docs.airbyte.com/platform/connector-development/cdk-python and https://github.com/airbytehq/airbyte

maintenance status: reference/deferred. Resolver proof succeeded but pulled a broad connector platform surface and dependency set, including cloud secret-manager oriented dependencies and cryptography version pressure.

why use it: Airbyte has broad open-source connector coverage and mature connector development concepts that are useful for future ETL-style ingestion.

why not custom code: Building generic account ETL and connector normalization from scratch would be expensive and brittle.

fallback if abandoned: Continue with Marvex canonicalization/chunking contracts and direct provider-specific adapters through ConnectorRuntime.

pyproject dependency: none

declared dependency: not declared; reference/deferred seam only

verified date: 2026-05-18

verified by: resolver dry-run and dependency audit

scope: Reference only for connector design and future adapter backend evaluation.

risks: Too broad for this foundation; could pressure connector runtime ownership, dependency size, and secret-management assumptions.

---

library name: Meltano / Singer SDK

official source: https://sdk.meltano.com/ and https://github.com/meltano/sdk

maintenance status: reference/deferred. `singer-sdk==0.54.2` resolved but was not needed for the current connector proof; `Meltano==4.2.0` resolved as a much heavier CLI/platform dependency.

why use it: Singer-style taps are a useful free/open-source connector pattern for later ingestion backends.

why not custom code: Singer taps can reduce custom connector extraction logic when a specific source tap is adopted.

fallback if abandoned: Keep ConnectorRuntime sync contracts and implement source-specific adapter seams only when a source backend is selected.

pyproject dependency: none

declared dependency: not declared; reference/deferred seam only

verified date: 2026-05-18

verified by: resolver dry-run and dependency audit

scope: Reference/deferred. Not adopted until a concrete tap backend is needed.

risks: Meltano is too platform-sized for the current local foundation; Singer SDK is narrower but still unnecessary until a real tap is selected.

---

library name: Pipedream components / Connect SDK

official source: https://github.com/PipedreamHQ/pipedream and https://pipedream.com/docs/connect

maintenance status: reference/deferred. `pipedream==2.0.2` resolved lightly, but the product model is cloud/account-service oriented.

why use it: Pipedream components are useful reference material for provider integration shapes and account-aware connector UX.

why not custom code: Provider-specific component ecosystems can avoid bespoke integration code if a backend is appropriate.

fallback if abandoned: Keep local Authlib OAuth seam and Marvex-owned connector contracts.

pyproject dependency: none

declared dependency: not declared; reference/deferred seam only

verified date: 2026-05-18

verified by: resolver dry-run and official docs/source review

scope: Reference/deferred only. No cloud-only requirement in Marvex runtime.

risks: Cloud account dependency and runtime ownership risk make it unsuitable as a required local-first backend in this checkpoint.

---

library name: Markdown/frontmatter libraries

official source: https://markdown-it-py.readthedocs.io/ and https://github.com/eyeseast/python-frontmatter

maintenance status: deferred. `markdown-it-py==4.0.0` is already present transitively; `python-frontmatter==1.2.0` resolved. Neither is required for the current deterministic vault projection.

why use it: If Marvex later needs rich Markdown AST parsing or round-trip frontmatter editing, maintained parsers should be preferred over ad hoc parsing.

why not custom code: Markdown parsing and frontmatter round-tripping have edge cases that should not be custom-built once full vault editing is needed.

fallback if abandoned: Keep the current deterministic Markdown projection and add parser-specific adapters later.

pyproject dependency: none

declared dependency: not declared; deferred until needed

verified date: 2026-05-18

verified by: resolver dry-run and installed package inspection

scope: Deferred. The current foundation writes safe projection strings and does not need parser ownership.

risks: Adding parser dependencies before a real parsing need would widen the runtime surface without improving current behavior.
