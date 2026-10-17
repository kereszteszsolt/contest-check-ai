# Test verdicts and result exports

## Initial comparison and metrics

The judge takes task-defined `.in` inputs and compares the solution's task-defined `.out` file with expected text using one documented, deterministic normalization rule (for example, CRLF normalization and trailing newline handling; exact rule is specified/tested during CCA-003). Do **not** silently ignore arbitrary whitespace or reorder outputs unless an approved task checker explicitly allows it.

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

## Measurement honesty

Track wall time and CPU time separately where available; do not present measured timings from different hosts/languages as directly comparable, or infer asymptotic Big-O. Note the host/limits, exclude infrastructure retries from solution runtime, and retain per-test measurements. Some memory metrics may be unavailable and must be shown as `N/A`, never invented.

## Export plan

- **XLSX:** summary sheet with opaque participant IDs, test counts and outcomes; detailed test sheet; separate `Disqualified / Rejected` and `Requires Review` sheets. Escape Excel formula prefixes in all untrusted fields.
- **PDF:** compact summary with test pass/fail counts, timings, environment/limits and separate lists of proven DQ cases and review flags. Sanitized error summaries only; no arbitrary embedded code.
- JSON test results can be kept internally for reproducible programmatic testing; they are not an advertised public API until the release story verifies them.
- Only anonymized IDs. Do not expose teacher private test content or student source in exported reports by default.

**No score, points, ranking or winner declaration in Release 0.1**. A later score/weight rules file is only a future idea.
