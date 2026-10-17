# Release 0.1 — Automated Python Judge

**Status: In progress.** CCA-001 provides local Streamlit/FastAPI archive validation; CCA-002 adds a separate NsJail worker verified on the recorded Docker/WSL2 environment. Browser/API judging remains disabled. Per-test orchestration/verdicts, reports and web/API deployment remain planned.

## Goal

A local teacher can upload one valid task package and an anonymous multi-participant submission archive, run Python solutions only in a **verified offline sandbox**, view per-test pass/fail/time, and download PDF/XLSX reports. The release is about **deterministic judging, not AI**.

## Safety requirement

The sandbox and archive validation are release-blocking requirements. If they cannot be validated on the target Linux/Docker setup, code execution must remain disabled. Do not replace with host `subprocess` or Docker-only execution to satisfy acceptance criteria.

## Stories (in order)

| Story | Goal | Status |
| --- | --- | --- |
| [CCA-001](stories/CCA-001-foundation-and-safe-archive-ingestion.md) | UI/API foundation + safe archive contract | Implemented; see verification evidence |
| [CCA-002](stories/CCA-002-isolated-python-judge-worker.md) | Verified offline Python worker / resource limits | Implemented; host-specific sandbox evidence recorded |
| [CCA-003](stories/CCA-003-test-runner-and-verdicts.md) | Per-test verdicts, timings, policy handling | Planned |
| [CCA-004](stories/CCA-004-ui-reports-and-verification.md) | Streamlit UI, PDF/XLSX, tests, CI and docs | Planned |

No scoring, student profiles, AI generation or C/C++/Pascal in this release. Actual evidence belongs to [verification.md](verification.md) and must not be prefilled as successful.
