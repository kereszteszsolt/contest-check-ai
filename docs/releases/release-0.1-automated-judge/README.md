# Release 0.1 — Automated Python Judge

**Status: Implemented and locally verified — CCA-001–004.** Streamlit supports upload, validation, judging, anonymous per-test results and PDF/XLSX downloads through the explicitly configured local API and a separately qualified offline NsJail worker. Real Docker/WSL2 integration and fixed mocked-worker browser/report checks are recorded separately. Streamlit/API run natively; only the worker is supplied as a Compose service. Hosted CI and public deployment are not claimed verified.

## Goal

A local teacher can upload one valid task package and an anonymous multi-participant submission archive, run Python solutions only in a **verified offline sandbox**, view per-test pass/fail/time, and download PDF/XLSX reports. The release is about **deterministic judging, not AI**.

## Safety requirement

The sandbox and archive validation are release-blocking requirements. If they cannot be validated on the target Linux/Docker setup, code execution must remain disabled. Do not replace with host `subprocess` or Docker-only execution to satisfy acceptance criteria.

## Stories (in order)

| Story | Goal | Status |
| --- | --- | --- |
| [CCA-001](stories/CCA-001-foundation-and-safe-archive-ingestion.md) | UI/API foundation + safe archive contract | Implemented; see verification evidence |
| [CCA-002](stories/CCA-002-isolated-python-judge-worker.md) | Verified offline Python worker / resource limits | Implemented; host-specific sandbox evidence recorded |
| [CCA-003](stories/CCA-003-test-runner-and-verdicts.md) | Per-test verdicts, timings, policy handling | Implemented; fixed-fixture API/Docker integration recorded |
| [CCA-004](stories/CCA-004-ui-reports-and-verification.md) | Streamlit UI, PDF/XLSX, tests, CI and docs | Implemented; browser/report evidence recorded, hosted CI Not run |

No scoring, student profiles, AI generation or C/C++/Pascal in this release. [verification.md](verification.md) records exact checks, corrected failures, artifacts and limitations. Sandbox evidence applies to the recorded host and every new worker must qualify again; local verification does not establish production/public safety.
