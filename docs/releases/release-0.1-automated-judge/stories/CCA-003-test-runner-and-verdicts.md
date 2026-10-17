# CCA-003 — File-based tests, verdicts and timing

## Status

**Planned**.

## User story

As a teacher, I want every anonymous Python solution checked against the same private input/output test cases, so I can see which tests passed and how long they ran.

## Goal

Wire the validated task/archive manifest to the verified judge worker and produce consistent typed per-test/participant results.

## Dependencies

CCA-001 valid input contracts and a successfully verified **CCA-002 sandbox**.

## Acceptance criteria

- [ ] Tests run in deterministic manifest order, with fresh isolation and expected `.in` and `.out` filenames on every test.
- [ ] Output matching uses one documented and tested exact/text-normalization rule; unexpected output, missing file and oversized output have clear failure categories.
- [ ] Each test records `AC`, `WA`, `TLE`, `MLE` (when supportable), `RE` or `SYSTEM_ERROR` and measured runtime; missing metrics are `N/A`, never guessed.
- [ ] Participant summaries preserve anonymous folder IDs and list passed/failed test counts, with **no score, winner or ranking calculation**.
- [ ] Clear, objective configured policy violations can be recorded as `DQ` with reason; suspicious heuristic indicators use `REVIEW`, never automatic fraud/plagiarism guilt.
- [ ] A sandbox/system failure cannot become a student `WA`, `RE` or `DQ`, and the batch either pauses or reports incomplete results honestly.
- [ ] Mocked deterministic unit tests cover verdict mapping and edge cases; approved sandbox integration fixtures exercise success, wrong answer, timeout and file I/O.

## Out of scope

Reference-solution AI generation, custom executable checker programs, scoring-file imports, C/C++/Pascal and Big-O inference.

## Verification guidance

Run mocked verdict checks, then sandbox integration against known benign scripts. Record wall/CPU measurement behavior, output rule and any limits in verification. Never execute unknown contest submissions during development.
