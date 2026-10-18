# CCA-008 — Teacher approval UI and AI authoring verification

## Status

**Implemented and locally verified with mocked providers/workers and synthetic teacher decisions.** Actual Streamlit/API/LangGraph/checkpoint/download behavior is exercised. Live provider/reference execution and independent teacher correctness review are Not run; see [release evidence](../verification.md).

## User story

As a teacher, I want to review, edit or reject generated tasks before downloading student material, so I remain accountable for problem quality and private test validity.

## Goal

Complete the Streamlit challenge-generation mode, integrate human-in-the-loop review within the active browser session and publish verified local usage instructions and automated tests.

## Dependencies

CCA-005–007 and proven Release 0.1 sandbox. This story must not bypass missing generation or security checks.

## Acceptance criteria

- [x] Streamlit has a dedicated challenge-generation workflow with model choice, natural-language task instructions, loading/status, draft preview and bounded revision inputs.
- [x] Teacher can **approve, request changes or reject**; rejection produces no final downloadable student package. Approval action is explicit and resumes the correct persisted LangGraph state.
- [x] Student ZIP and teacher ZIP are separate downloads after approval. UI prominently warns that generated reference/test correctness requires independent teacher review.
- [x] Mock-based tests cover teacher checkpoint decisions and double-click/retry behavior, missing keys, broken outputs and artifact privacy; no surprise OpenRouter billing in CI.
- [x] Later user correction: no cross-session resume UI or displayed recovery ID. Leaving the workspace, closing/navigating away from the browser page or disconnecting deletes the temporary draft/checkpoints and cached packages. In-flight results cannot restore a deleted draft; a fresh session starts empty.
- [x] Teacher-provided input and generated source cannot trigger arbitrary filesystem, network, shell, GitHub or unsafe judge operations; reference checks use only the vetted sandbox.
- [x] README diagrams, model-selection docs, safe setup instructions and actual dependency lists match shipped behavior; record manual PDF/ZIP/UI smoke checks if done.
- [x] Release 0.2 verification contains exact observed test commands, real/mocked provider details, teacher decision paths and known limitations; nothing falsely marked complete.

## Out of scope

Public accounts, scoring, C/C++/Pascal, automatic student assessment with AI, publishing to GitHub, MCP integration or broader web access.

## Verification guidance

Run focused graph, model, API, UI and artifact tests; perform an approved manual teacher approval/rejection demo. Record observed output and ask for separate commit approval.
