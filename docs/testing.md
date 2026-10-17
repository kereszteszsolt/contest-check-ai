# Test and verification strategy

## Current implementation

CCA-001–004 implement Release 0.1. Run `uv run --frozen pytest -q`, `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` after locked development setup. Default tests use inert archives and mocked workers/providers; they do not execute contestant/generated programs or call live models. [Release 0.1 evidence](releases/release-0.1-automated-judge/verification.md) separates unit/API/AppTest, real mocked-worker browser/download checks and the earlier real host-specific NsJail checks. [UI/report verification](verdicts-and-reporting.md#safe-verification-and-offline-mode) describes the optional browser harness. Hosted CI has not yet run. CCA-005 adds mocked LangChain/SDK, Pydantic, API and provider-selection AppTest checks; [Release 0.2 evidence](releases/release-0.2-ai-challenge-authoring/verification.md) records them. Subsequent Release 0.2 checks below remain planned.

## Release 0.1

1. Unit tests for ZIP central directory inspection, path normalization, archive caps, task manifests and invalid participant directory names.
2. Mock judge runner tests for `AC`, `WA`, `TLE`, `RE`, policy DQ, review flag and system error; exact/token byte comparison explicitly tested. `MLE` remains reserved because the worker lacks reliable per-test OOM evidence.
3. Hardened sandbox integration tests on a supported Linux environment using **benign fixtures only**, including network, filesystem, timing/memory limits and process cleanup. These checks **gate execution**.
4. API/UI tests for task upload, multiple participants, invalid archive feedback, per-test results and downloads.
5. PDF/XLSX checks for report shape, no private tests, escaped formula strings and repeatable ordering. Tests that require actual office/PDF readers may remain manual but must be disclosed.
6. CI runs safe unit/API/report checks with mocked judge; never runs untrusted student code automatically on hosted CI workers.

## Release 0.2

1. Pydantic validation of generated problem statement, public samples, hidden tests, starter and reference solution contracts.
2. LangGraph state/checkpoint/interrupt/resume tests with mocked providers and bounded tool-call budgets.
3. Provider allowlist, bad keys, timeouts, malformed JSON, explicit provider selection and no cloud fallback tests.
4. Teacher approve/reject/revise and separate ZIP privacy tests. No exports before approval.
5. Reference solution checks use the same verified sandbox. Never run generated code in the API process.
6. Real Ollama/OpenRouter smoke tests are manual, **opt-in** and must note the tested model and possible cloud cost.

## Documentation standard

Every test result in release `verification.md` requires the actual date, target environment, commands, observed output and remaining limitations. A `Not run` status is valid and honest. Story implementation and commit are **separate approval gates**.
