# Grounded Answer Evidence

Grounded answers may combine safe web evidence and Memory Tree evidence, but citations must map to concrete evidence refs.

Implemented behavior:

- `packages.grounded_answer_runtime.validate_grounded_citations` validates that every declared citation ID maps to a provided `WebSearchEvidenceRef`.
- Bracketed citation markers such as `[web.evidence.1]` are checked against the same evidence set.
- Missing evidence returns `citation.evidence_missing`.
- Hallucinated or unknown citation refs return `citation.evidence_ref_missing`.
- Web evidence can be converted into a `ContextCandidate` with `ContextSourceKind.WEB_SEARCH_EVIDENCE` for PromptHarnessRuntime.

Safety rules:

- No citation is accepted unless it maps to evidence.
- Snippets are treated as untrusted summaries, not raw page truth.
- Raw pages, raw provider payloads, raw browser DOM, screenshots, secrets, tokens, and transcripts are not persisted by default.
- If no evidence exists, Marvex must say evidence is missing or trigger web search when the route and provider are available.
