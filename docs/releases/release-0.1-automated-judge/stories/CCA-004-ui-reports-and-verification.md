# CCA-004 — Judge UI, PDF/XLSX results and MVP verification

## Status

**Planned**.

## User story

As a teacher, I want a simple page to upload the task and submissions, inspect every test and download a clear report without identifying students by name.

## Goal

Complete Streamlit judge flow, PDF/XLSX exports, safe automated tests, local Docker documentation and **honest release evidence**.

## Dependencies

CCA-001–003, especially verified CCA-002 sandbox. Refer to [report contract](../../../verdicts-and-reporting.md).

## Acceptance criteria

- [ ] Streamlit shows task ZIP/submission ZIP uploads, clear validation errors, run progress, per-test pass/fail table, timings and anonymous participant IDs; no accounts or scoring UI.
- [ ] PDF summary contains per-student/per-test outcomes, measurement units, configured limits and separately labelled `Disqualified / Rejected` and `Requires Review` sections.
- [ ] XLSX contains summary and detailed test sheets, separate DQ and review sheets, and protection against spreadsheet formula injection.
- [ ] Downloaded files omit private expected outputs and student source code; temporary workspaces and export artifacts are bounded and cleaned.
- [ ] Unit/API/UI/report tests use mocked worker results by default; CI never executes unknown submissions, performs real cloud calls or enables the judge insecurely.
- [ ] Local deployment docs explain actual worker prerequisites, Docker Compose services, non-public judge API, offline test mode and how to check isolation; **no false claim of safety**.
- [ ] README and Release 0.1 verification reflect actual implemented features, commands, failures, sandbox evidence, environment and `Not run` entries; no planned functionality represented as complete.

## Out of scope

AI challenge generation, numeric scores, student logins, a public URL and additional languages.

## Verification guidance

Run safe unit/integration tests and browser/manual report checks; inspect PDF/XLSX output and link validity. The release is not complete without CCA-002 sandbox evidence. Obtain separate commit approval.
