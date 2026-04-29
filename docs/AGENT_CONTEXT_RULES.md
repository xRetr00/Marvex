# Agent Context Rules

Context window usage is an architectural resource. Treat it like CPU, memory,
dependency risk, and file size: budget it deliberately and avoid waste.

## Required Orientation

- Read `docs/SYSTEM_MAP.md` before source discovery.
- Read `docs/MODULE_INDEX.md` before source discovery.
- Use the task spec Context Pack before reading source files.
- Start with the files named by the Context Pack and the user's allowed scope.

## Search Budget

- Do not scan the full repository by default.
- Do not run broad `rg` without a target folder.
- Do not run repo-wide `rg --files` unless the task is explicitly repo-wide.
- Prefer targeted search inside the allowed task scope.
- If a targeted search fails, widen one boundary at a time and explain why.
- Ask for approval before widening read scope outside the Context Pack or
  allowed task files.

## File Read Budget

- Do not read whole large files unless necessary for the current task.
- Large file reads require a short justification before the read.
- Prefer focused snippets, targeted search matches, and relevant sections.
- Avoid repeated reads of the same file in one task.
- Summarize findings instead of dumping full file contents into the conversation.

## Prompt Discipline

- Do not use "review the entire codebase" prompts unless the task is an approved
  audit.
- Do not rediscover architecture that is already summarized in the system map or
  module index.
- Do not use broad repo discovery to compensate for an incomplete task spec.
- Stop and ask when the Context Pack is missing required scope decisions.

## Approved Repo-Wide Reads

Repo-wide scans are allowed only when:

- the task is explicitly an approved repo-wide audit,
- a validation failure requires locating all instances of a specific pattern, or
- the user explicitly approves widening scope.

Even then, summarize results and avoid dumping unnecessary output.
