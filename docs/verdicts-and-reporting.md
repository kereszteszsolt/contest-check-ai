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

## Export plan

- **XLSX:** summary sheet with opaque participant IDs, test counts and outcomes; detailed test sheet; separate `Disqualified / Rejected` and `Requires Review` sheets. Escape Excel formula prefixes in all untrusted fields.
- **PDF:** compact summary with test pass/fail counts, timings, environment/limits and separate lists of proven DQ cases and review flags. Sanitized error summaries only; no arbitrary embedded code.
- CCA-003 supplies a typed local-operator JSON response from `POST /api/judge`; this is not an Internet-facing public API. PDF/XLSX and the Streamlit result screen remain CCA-004 work.
- Only anonymized IDs. Do not expose teacher private test content or student source in exported reports by default.

**No score, points, ranking or winner declaration in Release 0.1**. A later score/weight rules file is only a future idea.
