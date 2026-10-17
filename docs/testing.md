# Test and verification strategy

## Baseline

Documentation-only: **no application source, dependencies, judge implementation or test suite exists yet**. The test commands will be added during approved stories and evidence recorded in the active verification file.

## Release 0.1

1. Unit tests for ZIP central directory inspection, path normalization, archive caps, task manifests and invalid participant directory names.
2. Mock judge runner tests for `AC`, `WA`, `TLE`, `MLE`, `RE`, policy DQ, review flag, and system error; output comparison normalization explicitly tested.
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
