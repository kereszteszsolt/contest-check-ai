# Codex engineering guide — ContestCheck AI

## Current repository status

**Release 0.1 / CCA-001–004 implemented and locally verified.** Streamlit supports upload, validation, judging, per-test results and PDF/XLSX downloads through the local API. The API can judge only with both explicit operator settings; every separate offline worker must qualify in its own process. Existing Docker/WSL2 sandbox evidence and CCA-004 mocked-worker browser/report checks are distinct. CI runs safe mocked tests only; hosted CI/public deployment are not claimed verified. Release 0.2 and LangGraph remain **Planned**. Implement one approved `CCA-*` story at a time; do not mark features complete from documentation alone.

## Target scope and boundaries

- **Release 0.1 — Python Automated Judge:** teacher uploads a task package and an anonymous submissions ZIP. Validate, safely judge Python code with offline sandbox, report per-test Pass/Fail/runtime/errors, and export PDF/XLSX. **No numeric score**, accounts, external repository calls, or model calls in this release.
- **Release 0.2 — AI Challenge Authoring:** teachers write instructions and choose one of at most three configured Ollama / three OpenRouter models. LangChain + LangGraph drafts the problem, starters, examples, reference solution and private tests. The teacher reviews; the application exports distinct student and teacher ZIPs only after approval.
- C, C++ and Free Pascal are candidates for a later release, not automatic MVP scope. No relational application database is required. Temporary job workspaces and optional checkpoint storage are not student profile systems.
- Streamlit is presentation; FastAPI coordinates uploads, workflows and reports. A **separate isolated judge worker** is the only place untrusted code may execute. Never run uploaded programs in the web/API process.

## Context discipline

1. Read `AGENTS.md`, **one approved active story**, and its release README. Use only the related technical document and skill.
2. Load `python-web-artifacts` for UI/APIs/ZIP/PDF/XLSX, `isolated-judge-runtime` for runner isolation and verdicts, or `langgraph-ai-authoring` for optional model workflows. Multiple skills only for genuine cross-cutting work.
3. Do not scan the whole repository or load historical logs/other stories by default. Business requirements live in active stories, not duplicated across skills.
4. Use the main Codex session by default. An optional `implementation_worker` may be the sole writer for one story; no duplicate parallel coding, redundant reviewers or unnecessary token use.

## Safety must not be bypassed

- No arbitrary remote integrations. Runtime model traffic may go only to explicitly configured Ollama or OpenRouter. Judge worker must have **no network**, secrets, Docker socket or access to application/system files except isolated input/output.
- No student code execution until hardened Linux sandbox requirements and negative tests are demonstrated on the real execution environment. If impossible, **fail closed** and mark verification blocked; never silently fall back to unsandboxed `subprocess`, host execution or a plain Docker shell.
- Archive ingestion is untrusted. Reject traversal, symlinks, duplicate normalized names, expansion bombs, unsupported extensions, excessive file counts and oversized data before extraction/execution.
- Disqualify only for objectively proven configured contest-policy violations; record reason/evidence. Static suspicion (possible plagiarism or evasion) requires human review, not automatic DQ. LLM output never changes official test verdicts.
- Hidden tests and reference source stay teacher-only. No browsing, package fetching or arbitrary URL calls at application runtime.

## Story approval and evidence

1. Summarize one story, touched areas, risks, and focused verification; ask for explicit **implementation approval**.
2. Implement acceptance criteria only; consult technology docs when needed. Do not add new releases, broad frameworks or feature scope without approval.
3. Run focused tests before broader checks. No unapproved paid OpenRouter calls, live unknown contestant code, or CI executing untrusted samples.
4. Record exact commands/results, environment, failures and `Not run` in the active release `verification.md`. No invented success, screenshots, score or benchmarks.
5. Review the diff and request **separate commit approval**. Never auto-commit/push, force-push, or start another story.

## Short SPDX license headers

Use **exactly** the following two SPDX lines on **new hand-written application source** with the language's native comment syntax:

```text
SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
SPDX-License-Identifier: Apache-2.0
```

For Python/shell use `#`, for JS/TS use `//`, for HTML use `<!-- ... -->`, etc. **Do not** add headers to generic or generated configuration, e.g. `.env.example`, JSON, YAML, TOML, Markdown, lockfiles, dependency metadata, Compose/Dockerfiles and generated sources. The full license remains in `LICENSE`. Preserve upstream notices and review third-party licenses separately; do not paste the full Apache text into each file.

## Baseline and implementation boundary

`docs/repository-baseline.md` distinguishes the original baseline from CCA-001–004. README diagrams include the planned AI system. `.env` is not loaded automatically; an environment flag never bypasses worker qualification. Local setup is in `docs/local-development.md`, deployment in `docs/judge-worker.md`, batch/policy in `docs/judging.md`, and UI/export contracts in `docs/verdicts-and-reporting.md`. Consult the active release verification record for actual evidence and limitations.
