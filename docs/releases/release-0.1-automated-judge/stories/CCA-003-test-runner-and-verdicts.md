# CCA-003 — File-based tests, verdicts and timing

## Status

**Implemented and locally verified (2026-10-17).** The configured local API connects validated ZIPs to qualified offline workers and returns typed results. Unit checks and the fixed-fixture Docker/WSL2 integration passed; see [verification.md](../verification.md) and [judging.md](../../../judging.md). Streamlit results and exports remain CCA-004 work.

## User story

As a teacher, I want every anonymous Python solution checked against the same private input/output test cases, so I can see which tests passed and how long they ran.

## Goal

Wire the validated task/archive manifest to the verified judge worker and produce consistent typed per-test/participant results.

## Dependencies

CCA-001 valid input contracts and a successfully verified **CCA-002 sandbox**.

## Acceptance criteria

- [x] Tests run in deterministic manifest order, with fresh isolation and expected `.in` and `.out` filenames on every test.
- [x] Output matching uses the documented and tested manifest rules (`exact` bytes or ordered `tokens`); unexpected output, missing file and oversized output have clear failure categories.
- [x] Each test records `AC`, `WA`, `TLE`, `RE` or `SYSTEM_ERROR` and measured wall time. `MLE` is reserved but not emitted without reliable evidence; unavailable wall/CPU/memory metrics are N/A (`null`), never guessed.
- [x] Participant summaries preserve anonymous folder IDs and list passed/failed test counts, with **no score, winner or ranking calculation**.
- [x] Clear, objective configured policy violations can be recorded as `DQ` with byte-count evidence; configured static import indicators use `REVIEW` without altering official test verdicts, never automatic fraud/plagiarism guilt.
- [x] A sandbox/system failure cannot become a student `WA`, `RE` or `DQ`; the batch stops, retains prior results and explicitly counts remaining tests/participants as not run.
- [x] Mocked deterministic unit tests cover verdict mapping and edge cases; approved sandbox integration fixtures exercise success, wrong answer, timeout, missing/empty output, file I/O and cleanup.

The configured time budget restarts per test. Generated runtime files and the test container are removed before the next test; uncertain cleanup stops the batch. Expected outputs remain coordinator-only.

## Out of scope

Reference-solution AI generation, custom executable checker programs, scoring-file imports, C/C++/Pascal and Big-O inference.

## Verification guidance

Run mocked verdict checks, then sandbox integration against known benign scripts. Record wall/CPU measurement behavior, output rule and any limits in verification. Never execute unknown contest submissions during development.
