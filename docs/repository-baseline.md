# Repository inventory — original baseline and CCA-001–006

The original documentation baseline was a **plan for Codex**, with no runnable Python application. CCA-001 now adds a Python 3.12 Streamlit/FastAPI foundation, pinned `uv` packaging, typed task schema, bounded safe ZIP ingestion, private temporary extraction/cleanup, inert demo archives and unit/API/UI tests. See [local development](local-development.md) and [Release 0.1 evidence](releases/release-0.1-automated-judge/verification.md).

CCA-002 adds a separately built one-shot NsJail worker, worker-only Compose configuration, inner/outer syscall policies, strict bounded JSON protocol, real startup qualification, mocked unit tests and operator-only benign Docker integration checks. See [judge-worker.md](judge-worker.md). Only its recorded Docker/WSL2 environment is qualified by the checked-in evidence; every worker start must qualify again.

CCA-003 connects validated ZIPs to fresh qualified workers through a fixed local Docker transport and an explicitly configured FastAPI route. It implements deterministic manifest-order tests, exact/token byte comparisons, honest metrics and incomplete batches, anonymous counts, optional objective DQ and static REVIEW indicators. See [judging.md](judging.md). Real fixed-fixture integration and focused unit evidence are recorded.

CCA-004 completes Streamlit validation/judging/results and bounded in-memory PDF/XLSX downloads, with separate policy/review sections, safe spreadsheet text, mocked tests and a safe CI workflow. Real local browser checks use fixed mocked worker results; they do not replace the earlier real sandbox evidence. See [UI/report contracts](verdicts-and-reporting.md) and the release verification artifacts. Hosted CI has not been run.

Original documentation retained:

- README with Mermaid architecture / user flow diagrams, license summary, Ways to Support and status warnings.
- Full unchanged Apache-2.0 `LICENSE` plus imported support image.
- `AGENTS.md`, one optional worker agent, three narrowly triggered technical skills, environment example.
- Architecture, archive contracts, security, verdicts, models, testing and story workflow documentation.
- Release 0.1 and Release 0.2 plans; CCA-001–004 have implementation evidence.

CCA-005 adds backend-only configured Ollama/OpenRouter slots, bounded LangChain adapters, strict unverified task drafts and an explicit teacher selection/preview screen. Only mocked provider/API/AppTest checks are recorded; no live model is verified. See [model configuration](model-configuration.md) and [Release 0.2 evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

CCA-006 adds a bounded Pydantic LangGraph workflow, two fixed checking tools, opt-in reference checks through the existing qualified worker transport, expiring in-memory checkpoints and backend teacher approve/revise/reject. Actual graph/interrupt/API tests use mocked models/workers; live model/reference execution and manual teacher smoke are Not run. Approval leaves correctness unverified. See [authoring workflow](authoring-workflow.md).

Still deliberately absent: polished authoring/review UI, final independent teacher verification, student/teacher package export, web/API containers, public deployment and CI executing submissions. Only the explicitly configured native coordinator can request judging; a separate worker accepts a program only after its real sandbox checks pass. API/Streamlit never execute uploaded/generated programs themselves.

Validate actual dependency licenses and host sandbox capabilities before enabling code execution on another installation. This local-operator-only implementation is not a universal safety guarantee or a public deployment.
