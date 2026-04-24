# Core Rules

The Core Service owns turn orchestration. It does not own every decision in the product.

## Hard Rules

- Core cannot import UI.
- Core cannot import LM Studio directly.
- Core cannot import tools directly.
- Core cannot own provider-specific logic.
- Core only talks to ports and interfaces.
- Core must not use hidden global state.
- No god files.
- No file over 500 lines without explicit justification.
- No feature before contract.
- No provider-specific branches in the orchestrator.

## Refactor Safety

Core changes require:

- task spec
- contract diff if contracts change
- fake adapter tests
- replay tests when behavior changes
- migration plan
- rollback plan

## Ownership

Core owns:

- turn lifecycle
- provider port call
- final response normalization
- trace lifecycle emission

Core does not own:

- provider protocol details
- memory
- tools
- UI
- voice
- desktop context
- proactive behavior
- intent classification

