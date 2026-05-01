# Schema Version Policy

The active v1 Provider Foundation schema version is `0.1.1-draft`.

Documentation-only assistant envelope drafts currently use `0.1.1-draft` for
examples and draft approval rows only. This does not approve assistant envelope
implementation.

A distinct assistant envelope schema version may be required before
implementation approval. No schema version split is approved by the current
draft docs.

`0.1-draft` is deprecated historical only. It may be mentioned only in this
policy document and in validation code that rejects deprecated active
references.

## Rules

- Active docs, examples, tests, CLI smoke requests, and contract approval rows
  must use `0.1.1-draft`.
- Contract models currently validate schema version as a non-empty string. Task
  018 does not change contract model runtime behavior.
- Future schema changes require an approved contract change, migration notes,
  rollback notes, and validation updates.
- New active references to `0.1-draft` fail validation.
