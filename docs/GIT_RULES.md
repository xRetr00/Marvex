# Git Rules

This document is the authoritative Git workflow policy for Marvex.

## Default Workflow

Normal small and medium Marvex tasks must be implemented directly on `main`.

The standard task flow is:

1. The agent produces a plan.
2. The user approves the plan.
3. The agent implements the approved task.
4. The agent runs required validation.
5. The agent commits changes to `main`.
6. The agent pushes `main`.
7. The agent may move to the next task only after the push is complete.

Plan-only responses do not require commits unless files are changed.

## Branch Rules

Agents must not create branches automatically.

Branches are allowed only for:

- large subsystems
- risky refactors
- explicitly user-approved cases

Before creating any branch, the agent must ask the user first.

## Task Continuity

Agents must not leave task changes uncommitted before starting another task.

Agents must not start Task N+1 while Task N has uncommitted changes.

If validation fails, the agent must fix the current task or report the blocker.
The agent must not switch to unrelated work to bypass the failure.

## Tags

Tags may be created only after validation passes and either:

- the user approves the tag, or
- the milestone clearly requires the tag.

## Final Reports

Implementation final reports must include:

- validation result
- commit hash or explicit no-commit reason
- push status
- current Git status summary
