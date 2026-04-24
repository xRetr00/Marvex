# Architecture

## Executive Decision

Marvex is a hybrid, service-ready desktop system.

The first implementation target is:

- Python Core Service
- CLI Client
- Fake Provider
- LM Studio Responses Provider
- Telemetry

The later desktop target is:

- C++/Qt Shell
- Python Core Service
- Provider Worker
- Tool Worker
- Intent Worker
- Voice Worker
- Desktop Agent

This is not immediate microservices. It is a modular core designed so each major boundary can become a separate process without rewriting the product.

## V1 Scope

V1 includes only:

- Core Service
- CLI Client
- Fake Provider
- LM Studio Responses Provider
- Telemetry

V1 forbids:

- Intent
- Tools
- Memory
- UI
- Voice
- Desktop Context
- Proactive behavior
- Vision

These future modules may be documented, but they may not be implemented in v1.

## Core Principle

The Core Service owns turn orchestration only. It does not own provider-specific logic, UI behavior, tool execution, memory storage, voice capture, desktop observation, or policy decisions for modules that do not exist yet.

The Core talks through ports and stable JSON contracts.

## Service-Ready Modular Core

Every future module must be designed as if it may later run in a separate process:

- explicit input contract
- explicit output contract
- health check
- version field
- structured logs
- trace_id propagation
- error envelope
- startup and shutdown behavior

If a module cannot be separated without rewriting the Core, the module boundary is wrong.

## Provider Boundary

The Core sends `ProviderRequest` to a Provider Adapter through a port. The Core must not know whether the backend is LM Studio, OpenAI-compatible, local, remote, fake, or replaced later.

`previous_response_id` belongs in the provider contract and adapter behavior, not in hidden Core state.

## Anti-Spaghetti Rules

- No god files.
- No giant orchestrator.
- No hidden global state.
- No provider-specific code in Core.
- No UI logic in Core.
- No tool execution in UI.
- No features before contracts.
- No custom SDKs when maintained libraries exist.

