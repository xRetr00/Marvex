# V1 Process Map

```mermaid
sequenceDiagram
  participant Client as Local Client
  participant API as Local API
  participant RuntimeComposition as RuntimeComposition
  participant Core as Core helper
  participant AssistantRuntime as AssistantRuntime
  participant ProviderRuntime as ProviderRuntime
  participant Provider as Fake Provider
  participant Telemetry as Telemetry

  Client->>API: POST /v1/turns envelope + bearer token
  API->>API: authenticate and validate JSON
  API->>RuntimeComposition: injected fake turn handler
  RuntimeComposition->>ProviderRuntime: create fake provider
  RuntimeComposition->>Core: run assistant-provider-stage helper
  Core->>AssistantRuntime: run provider stage
  AssistantRuntime->>Telemetry: provider_request_created
  AssistantRuntime->>Telemetry: provider_request_sent
  AssistantRuntime->>Provider: ProviderRequest
  Provider-->>AssistantRuntime: ProviderResponse
  AssistantRuntime->>Telemetry: provider_response_received
  AssistantRuntime->>Telemetry: final_response_created
  AssistantRuntime->>Telemetry: turn_completed
  AssistantRuntime-->>Core: AssistantTurnResult
  Core-->>RuntimeComposition: AssistantTurnResult
  RuntimeComposition-->>API: AssistantTurnResult
  API-->>Client: AssistantTurnResult JSON
```

Failure path: Local API auth/request failures return top-level `ErrorEnvelope`.
Provider-stage failures returned by the injected handler remain inside
`AssistantTurnResult.error`.
