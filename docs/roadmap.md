# Roadmap

The project has two independently verifiable releases. CCA-001–004 are implemented with local host-specific judge evidence; CCA-005–008 have mocked authoring/real graph/UI/artifact evidence. CCA-009 local Docker deployment is explicitly requested and in progress. A story plan is not proof of implementation or authorization; linked verification records state actual results and limitations.

## Release 0.1 — Automated Python Judge

Objective: upload valid task/submission ZIP files, safely and deterministically run **Python** solutions in a verified offline sandbox, and export pass/fail/time results as PDF and XLSX. No AI calls, numeric scoring, accounts, arbitrary language execution or public deployment.

| Story | Scope | Status |
| --- | --- | --- |
| [CCA-001](releases/release-0.1-automated-judge/stories/CCA-001-foundation-and-safe-archive-ingestion.md) | Python/Streamlit/FastAPI foundation and strict ZIP schemas | Implemented; locally verified |
| [CCA-002](releases/release-0.1-automated-judge/stories/CCA-002-isolated-python-judge-worker.md) | Offline hardened worker and fail-closed sandbox | Implemented; host-specific sandbox evidence |
| [CCA-003](releases/release-0.1-automated-judge/stories/CCA-003-test-runner-and-verdicts.md) | Per-test verdicts, time and policy outcomes | Implemented; fixed-fixture integration verified |
| [CCA-004](releases/release-0.1-automated-judge/stories/CCA-004-ui-reports-and-verification.md) | Judge UI, PDF/XLSX, CI and release evidence | Implemented; browser/report checks passed, hosted CI Not run |

[Release overview](releases/release-0.1-automated-judge/README.md) · [Verification](releases/release-0.1-automated-judge/verification.md)

## Release 0.2 — AI Challenge Authoring

Objective: create a teacher-reviewed challenge draft from natural-language instructions using LangChain/LangGraph and explicitly configured Ollama/OpenRouter; validate sample/hidden tests with the safe judge; export two separate ZIPs.

| Story | Scope | Status |
| --- | --- | --- |
| [CCA-005](releases/release-0.2-ai-challenge-authoring/stories/CCA-005-configured-llm-providers.md) | Six allowed model slots, Pydantic and bounded LLM adapter | Implemented; mocked provider/API/UI evidence |
| [CCA-006](releases/release-0.2-ai-challenge-authoring/stories/CCA-006-langgraph-generation-and-tools.md) | LangGraph state, generation tools, reference validation | Implemented; mocked models/workers and actual graph |
| [CCA-007](releases/release-0.2-ai-challenge-authoring/stories/CCA-007-student-teacher-artifact-packages.md) | PDF statement, samples/starters, separate private tests | Implemented; synthetic ZIP/PDF/API checks |
| [CCA-008](releases/release-0.2-ai-challenge-authoring/stories/CCA-008-teacher-approval-and-verification.md) | HITL UX, approval gating, tests, docs and evidence | Implemented; mocked providers, actual UI/API and local browser |
| [CCA-009](releases/release-0.2-ai-challenge-authoring/stories/CCA-009-local-docker-deployment.md) | Local Docker UI/API and isolated Linux judge execution | In progress; base mode runs, API socket approval pending |

**Dependency:** Release 0.2 generated reference code cannot run until the Release 0.1 sandbox has been verified. An unsupported sandbox must block release acceptance, not induce a bypass.

[Release overview](releases/release-0.2-ai-challenge-authoring/README.md) · [Verification](releases/release-0.2-ai-challenge-authoring/verification.md)

## Uncommitted ideas

C / C++ / Free Pascal, scoring-rules upload, student practice portal, additional task/checker formats, durable persistence and similarity analysis are not assigned to releases. See [future.md](future.md). No story/acceptance criteria yet.
