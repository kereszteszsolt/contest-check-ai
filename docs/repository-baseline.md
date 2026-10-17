# Repository inventory — original baseline and CCA-001/002/003

The original documentation baseline was a **plan for Codex**, with no runnable Python application. CCA-001 now adds a Python 3.12 Streamlit/FastAPI foundation, pinned `uv` packaging, typed task schema, bounded safe ZIP ingestion, private temporary extraction/cleanup, inert demo archives and unit/API/UI tests. See [local development](local-development.md) and [Release 0.1 evidence](releases/release-0.1-automated-judge/verification.md).

CCA-002 adds a separately built one-shot NsJail worker, worker-only Compose configuration, inner/outer syscall policies, strict bounded JSON protocol, real startup qualification, mocked unit tests and operator-only benign Docker integration checks. See [judge-worker.md](judge-worker.md). Only its recorded Docker/WSL2 environment is qualified by the checked-in evidence; every worker start must qualify again.

CCA-003 connects validated ZIPs to fresh qualified workers through a fixed local Docker transport and an explicitly configured FastAPI route. It implements deterministic manifest-order tests, exact/token byte comparisons, honest metrics and incomplete batches, anonymous counts, optional objective DQ and static REVIEW indicators. See [judging.md](judging.md). Real fixed-fixture integration and focused unit evidence are recorded; the Streamlit Run button remains disabled.

Original documentation retained:

- README with Mermaid architecture / user flow diagrams, license summary, Ways to Support and status warnings.
- Full unchanged Apache-2.0 `LICENSE` plus imported support image.
- `AGENTS.md`, one optional worker agent, three narrowly triggered technical skills, environment example.
- Architecture, archive contracts, security, verdicts, models, testing and story workflow documentation.
- Release 0.1 and Release 0.2 plans; CCA-001/002/003 have implementation evidence.

Still deliberately absent: Streamlit results UI, AI generation, report exporters, web/API containers, public deployment and CI executing submissions. Only the explicitly configured native coordinator can request judging; a separate worker accepts a program only after its real sandbox checks pass. API/Streamlit never execute uploaded programs themselves.

When implementation starts, validate actual dependency licenses and host sandbox capabilities before enabling code execution. A local-operator-only proof of concept must not be described as production safe or opened to the public without explicit extra safeguards.
