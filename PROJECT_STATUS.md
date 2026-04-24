# Project Status

current_phase: planning_only

implementation_status: not_started

accepted_docs: false

allowed_current_work:

- documentation
- templates
- validation scripts
- README-only placeholder folders

forbidden_current_work:

- Marvex product implementation
- provider implementation before contract approval
- core service implementation before contract approval
- UI implementation
- tools
- memory
- voice
- desktop context
- proactive behavior
- vision

status_rule:

Until `accepted_docs` is changed to `true` through an explicit accepted documentation review, agents may not create product code. Governance validation scripts are allowed because they protect the workspace.

acceptance_rule:

Docs may be accepted only after all planning blockers are fixed, `python scripts/run_all_checks.py` passes, and the user explicitly approves the updated planning set.
