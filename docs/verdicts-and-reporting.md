# Test verdicts and result exports

## Initial comparison and metrics

CCA-003 compares task-defined file outputs using the manifest's tested rule: `exact` means identical bytes; `tokens` means identical ordered `bytes.split()` tokens (ASCII whitespace only). There is no implicit CRLF/final-newline normalization, numeric tolerance or output sorting. Full lifecycle, mappings, policy and API contract are in [judging.md](judging.md).

| Code | Meaning |
| --- | --- |
| `AC` | Output matched expected result for this test |
| `WA` | Completed but produced a different output |
| `TLE` | Exceeded configured wall/CPU time limit |
| `MLE` | Exceeded memory limit (only if reliably observable) |
| `RE` | Runtime error/non-zero exit or expected output absent |
| `CE` | Compilation error (reserved for a future compiled language) |
| `DQ` | Proven configured policy violation, with recorded rule/reason |
| `REVIEW` | Suspicious behavior needs teacher review; **not a verdict of cheating** |
| `SYSTEM_ERROR` | Judge/sandbox failure; do not attribute to the participant |

The current worker emits no reliable per-test OOM evidence, so CCA-003 reserves but does not emit `MLE`. Memory/output/signal exit encodings are ambiguous hints and produce `RE` with explicit `*_or_exit` reasons; only the supervisor's observed wall deadline produces `TLE`. Missing output is `RE`; malformed/oversized capture violating the sandbox contract is `SYSTEM_ERROR`. A system failure stops the batch, retaining prior results and explicitly counting all remaining tests as not run. None becomes a participant failure or DQ.

## Measurement honesty

Track wall time and CPU time separately where available; do not present measured timings from different hosts/languages as directly comparable, or infer asymptotic Big-O. Note the host/limits, exclude infrastructure retries from solution runtime, and retain per-test measurements. Some memory metrics may be unavailable and must be shown as `N/A`, never invented.

CCA-003 records wall time including jail setup and bounded termination/reaping, excluding Docker startup and qualification. There are no retries. CPU time, peak memory and unavailable wall metrics serialize as `null` (N/A). Per-participant summaries preserve opaque IDs and distinguish passed, failed, system-error and not-run counts. Optional total-source-byte policy provides objective DQ evidence; configured static import indicators produce REVIEW only and do not change official test results.

## Implemented PDF/XLSX reports — CCA-004

- **XLSX:** summary sheet with opaque participant IDs, test counts and outcomes; detailed test sheet; separate `Disqualified / Rejected` and `Requires Review` sheets. Escape Excel formula prefixes in all untrusted fields.
- **PDF:** compact summary with test pass/fail counts, timings, environment/limits and separate lists of proven DQ cases and review flags. Sanitized error summaries only; no arbitrary embedded code.
- CCA-003/004 supply a typed local-operator JSON response from `POST /api/judge` and the Streamlit result screen; these are not Internet-facing public services.
- Only anonymized IDs. Do not expose teacher private test content or student source in exported reports by default.

**No score, points, ranking or winner declaration in Release 0.1**. A later score/weight rules file is only a future idea.

### Streamlit workflow

Upload both ZIPs, select **Validate archives**, then **Run solutions**. Validation errors are separate from participant verdicts. The running status is deliberately indeterminate: it shows the real batch stage and declared participant/test counts, with no fabricated percentage or unobserved per-test progress. Results appear when the synchronous batch returns. Large batches include worker qualification overhead; each program still has its own short manifest deadline.

The screen shows anonymous summary counts, every declared test (including explicitly not-run rows), limits and units, and separate DQ/review sections. System errors are not participant failures. CPU/memory and unavailable wall measurements display N/A. UI/PDF timings use six significant digits; XLSX retains numeric values with a six-decimal display format. Tables preserve participant IDs as text and scroll internally on narrow screens.

Select **Prepare PDF and XLSX**, then download either format. Download clicks do not rerun judging. Upload changes, revalidation and new runs clear old results/downloads; report-service errors preserve the current results so report preparation can be retried. There are no accounts, shared result cache or stored report URLs.

### Export API and bounds

`POST /api/reports/pdf` or `/api/reports/xlsx` accepts the current `BatchResult` JSON from `POST /api/judge`. It formats provided results; it does not execute or rejudge code. The response is an attachment with the appropriate MIME type, `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`. GET on these paths returns 405 because no report is persisted. This local operator API has no public/authenticated hosting mode.

The result contract includes ordered `test_ids` for every declared test. Unique anonymous IDs, manifest-order prefixes, counts, completion states and configured DQ evidence are validated, so absent tests cannot be invented as failures. Unknown fields, source code, private expected outputs, free-form diagnostics, inconsistent counts and unsafe identifiers are rejected with a fixed 422 message without echoing their contents.

JSON report bodies are bounded to **8 MiB before parsing**, including missing/dishonest Content-Length. Each output is capped at **8 MiB**. At most 100 participants x 100 tests are represented, and one export is built at a time per API process. Busy generation returns 503 `report_busy`; size overflow returns 413 `report_size`; unexpected failures return fixed 503 `report_failed`. A failed generation releases the export slot.

ReportLab builds escaped text with built-in Helvetica, no user-supplied HTML, fonts, images, links or templates. XlsxWriter uses `in_memory: true`; formulas/URL detection are disabled, every string is explicitly written as text, and formula-leading/control characters are neutralized. No macros or external workbook links are generated. Runtime export never opens an uploaded PDF/XLSX, and no temporary export file is created. A bounded memory sink discards overflow until the library closes cleanly, then refuses to return the artifact.

The XLSX sheets are `Summary`, `Tests`, `Disqualified - Rejected` (Excel forbids `/` in a sheet name), and `Requires Review`. Summary metadata contains task/status/comparison and configured per-test limits; detailed rows include all declared tests. Invalid ZIP uploads have no participant verdict and are described by a separate rejection note, not fabricated DQ rows. PDF policy sections use the exact labels **Disqualified / Rejected** and **Requires Review**.

PDF has repeated table headers and page numbers; exports preserve input order. Binary output is deterministic for the same result/dependency versions: metadata uses a fixed date and does not claim an execution date. No private input, expected/actual output or student source is present. The UI retains at most one result and two capped report payloads per session; replacing uploads clears them. Existing temporary judge workspaces still clean up per test and batch. Abrupt host/API crashes retain the previously documented cleanup limitation.

### Safe verification and offline mode

```bash
uv run --frozen pytest -q tests/test_reports.py tests/test_report_api.py tests/test_ui.py
uv run --frozen pytest -q
```

These tests use mocked workers and inert sources by default, with no Docker, model/provider traffic or submitted-program execution. The report tests independently read the generated files with pypdf/openpyxl, verify formulas/links are absent, exercise size limits and the maximum 10,000-test batch, and check unavailable metrics and policy separation. CI runs this safe suite and lint/format checks with execution flags disabled, no provider keys and action revisions pinned to full commit hashes. Operator sandbox/browser verification scripts are never CI steps.

An explicit optional browser check starts actual loopback FastAPI and Streamlit services with a **fixed mocked worker**, uploads only its own inert ZIPs and checks downloads/desktop/mobile/error/reset states. It is verification tooling, not a worker fallback or a mode for real contests. It requires Node, Playwright 1.62.1 and its Chromium/shared-library prerequisites, in addition to the development Python environment. For example, after installing those optional tools outside the repository:

```bash
CCA_PLAYWRIGHT_MODULE=/tmp/cca004-browser-tools/node_modules/playwright \
  uv run --frozen python scripts/verify_ui_reports.py
```

`CCA_BROWSER_NODE` can select an installed Node executable. Artifacts default to ignored `.runtime/cca004-verification/`; fixture ZIPs are temporary and its own service processes stop in `finally`. No external source file is accepted by this harness. Its fake timings/verdicts are test data, not sandbox/algorithm evidence. The separately recorded CCA-002/003 real NsJail qualification remains the execution evidence. See [release verification](releases/release-0.1-automated-judge/verification.md) for exact observed commands, screenshots, PDF inspection and limitations.
