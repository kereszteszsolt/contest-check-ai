# Roadmap

The project is planned in **two independently verifiable releases**. Both are **Planned**; a story plan is not proof of implementation or user permission to start.

## Release 0.1 — Automated Python Judge

Objective: upload valid task/submission ZIP files, safely and deterministically run **Python** solutions in a verified offline sandbox, and export pass/fail/time results as PDF and XLSX. No AI calls, numeric scoring, accounts, arbitrary language execution or public deployment.

| Story | Scope | Status |
| --- | --- | --- |
| [CCA-001](releases/release-0.1-automated-judge/stories/CCA-001-foundation-and-safe-archive-ingestion.md) | Python/Streamlit/FastAPI foundation and strict ZIP schemas | Planned |
| [CCA-002](releases/release-0.1-automated-judge/stories/CCA-002-isolated-python-judge-worker.md) | Offline hardened worker and fail-closed sandbox | Planned |
| [CCA-003](releases/release-0.1-automated-judge/stories/CCA-003-test-runner-and-verdicts.md) | Per-test verdicts, time and policy outcomes | Planned |
| [CCA-004](releases/release-0.1-automated-judge/stories/CCA-004-ui-reports-and-verification.md) | Judge UI, PDF/XLSX, CI and release evidence | Planned |

[Release overview](releases/release-0.1-automated-judge/README.md) · [Verification](releases/release-0.1-automated-judge/verification.md)

## Release 0.2 — AI Challenge Authoring

Objective: create a teacher-reviewed challenge draft from natural-language instructions using LangChain/LangGraph and explicitly configured Ollama/OpenRouter; validate sample/hidden tests with the safe judge; export two separate ZIPs.

| Story | Scope | Status |
| --- | --- | --- |
| [CCA-005](releases/release-0.2-ai-challenge-authoring/stories/CCA-005-configured-llm-providers.md) | Six allowed model slots, Pydantic and bounded LLM adapter | Planned |
| [CCA-006](releases/release-0.2-ai-challenge-authoring/stories/CCA-006-langgraph-generation-and-tools.md) | LangGraph state, generation tools, reference validation | Planned |
| [CCA-007](releases/release-0.2-ai-challenge-authoring/stories/CCA-007-student-teacher-artifact-packages.md) | PDF statement, samples/starters, separate private tests | Planned |
| [CCA-008](releases/release-0.2-ai-challenge-authoring/stories/CCA-008-teacher-approval-and-verification.md) | HITL UX, approval gating, tests, docs and evidence | Planned |

**Dependency:** Release 0.2 generated reference code cannot run until the Release 0.1 sandbox has been verified. An unsupported sandbox must block release acceptance, not induce a bypass.

[Release overview](releases/release-0.2-ai-challenge-authoring/README.md) · [Verification](releases/release-0.2-ai-challenge-authoring/verification.md)

## Uncommitted ideas

C / C++ / Free Pascal, scoring-rules upload, student practice portal, additional task/checker formats, durable persistence and similarity analysis are not assigned to releases. See [future.md](future.md). No story/acceptance criteria yet.
