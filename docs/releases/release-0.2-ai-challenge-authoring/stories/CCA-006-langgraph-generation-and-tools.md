# CCA-006 — LangGraph draft generation and bounded tools

## Status

**Planned**.

## User story

As a teacher, I want challenge drafts refined and checked step by step, so I can inspect potentially incorrect AI-generated statements and test cases before publishing anything.

## Goal

Create an explicit LangGraph workflow with bounded read/generate/check tools and Pydantic state, including teacher-interrupt points.

## Dependencies

CCA-005 providers and an actually verified Release 0.1 judge sandbox for reference solution checks.

## Acceptance criteria

- [ ] Workflow accepts bounded natural-language instructions, topic/difficulty and chosen configured model, and produces typed problem statement, candidate reference solution, public examples and teacher-private test draft.
- [ ] Graph state tracks draft, warnings, attempts, tool results, approval state and errors across nodes; no uncontrolled agent loop or unrestricted OS/shell tool access.
- [ ] Agent tools have a minimal allowlist (e.g., `validate_draft`, `run_reference_tests`); only the approved judge worker can execute the candidate reference source.
- [ ] Reference tests report observed output mismatches and resource limits; generated tests/reference are labelled **unverified** unless independent review has occurred.
- [ ] LangGraph `interrupt`/checkpoint can pause with a reviewable preview and resume on explicit teacher approval/revision/rejection; resume does not duplicate side effects.
- [ ] Enforce maximum model/tool calls; reject unsafe output requests or unapproved file paths; uploaded instructions and model-generated content are treated as untrusted data.
- [ ] Mocked graph/tool tests cover pass, mismatch, malformed state, timeout, rejection and resume; no test executes untrusted source outside verified isolation.

## Out of scope

PDF/XLSX final packaging and polished Streamlit authoring UI (handled by next stories), autonomous publishing or multi-agent swarm.

## Verification guidance

Run deterministic mocked LangGraph tests, then teacher-approved local smoke tests only after sandbox verification. Record real human interrupt/resume behavior and residual uncertainty about challenge correctness.
