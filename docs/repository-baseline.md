# Repository inventory — original baseline and CCA-001

The original documentation baseline was a **plan for Codex**, with no runnable Python application. CCA-001 now adds a Python 3.12 Streamlit/FastAPI foundation, pinned `uv` packaging, typed task schema, bounded safe ZIP ingestion, private temporary extraction/cleanup, inert demo archives and unit/API/UI tests. See [local development](local-development.md) and [Release 0.1 evidence](releases/release-0.1-automated-judge/verification.md).

Original documentation retained:

- README with Mermaid architecture / user flow diagrams, license summary, Ways to Support and status warnings.
- Full unchanged Apache-2.0 `LICENSE` plus imported support image.
- `AGENTS.md`, one optional worker agent, three narrowly triggered technical skills, environment example.
- Architecture, archive contracts, security, verdicts, models, testing and story workflow documentation.
- Release 0.1 and Release 0.2 plans; only CCA-001 has implementation evidence.

Still deliberately absent: sandbox config/binary, execution worker, judge/verdicts, AI generation, report exporters, Dockerfile/Compose YAML, public deployment and CI executing submissions. The application cannot execute student code, including when an enabling environment flag is present.

When implementation starts, validate actual dependency licenses and host sandbox capabilities before enabling code execution. A local-operator-only proof of concept must not be described as production safe or opened to the public without explicit extra safeguards.
