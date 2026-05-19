# Risk-Based Governance

Marvex governance now distinguishes safe read/list/search from actions that require confirmation and actions that must be hard-blocked.

Allowed by default:

- read
- list
- search
- inspect
- summarize
- safe public web search
- safe public page read/extract
- safe memory tree traversal
- safe trace/control summaries
- safe capability/tool/MCP/skill listing

Requires user confirmation:

- write
- delete
- send
- post
- upload
- export outside the local boundary
- install package
- enable connector
- enable auto-fetch
- submit form
- risky browser click/type
- type sensitive data
- start long browser/computer task
- run command
- connect OAuth account
- access private account data beyond granted scope

Hard-block only:

- malware
- credential theft or extraction
- prompt-injection exploitation
- command-injection exploitation
- data exfiltration
- unauthorized account abuse
- CAPTCHA or anti-bot bypass
- stealth abuse
- destructive action without consent
- payment/checkout without explicit approval
- policy override attempts

Implementation:

- `packages.capability_runtime.risk_governance.RiskGovernancePolicy` returns safe decisions with risk level, side-effect level, execution mode, confirmation flag, hard-block flag, and reason code.
- The validation gate proves read/list/search are not hard-blocked, risky write/delete/send/install/run actions require approval, and abuse categories hard-block.
- This policy does not execute tools. CapabilityRuntime remains authoritative for approval and dispatch.
