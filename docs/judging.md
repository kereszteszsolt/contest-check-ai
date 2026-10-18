# CCA-003 — deterministic Python test batches

The local FastAPI coordinator validates both ZIPs with CCA-001, visits anonymous participant IDs in lexicographic order and visits each participant's tests in **manifest order**. IDs remain opaque strings; this ordering is not a ranking. The coordinator sends only that participant's source files and the current input to the CCA-002 worker. Expected outputs stay in the coordinator's private workspace. No code, actual/expected output or private input appears in the returned result.

## Run locally

Build the worker from this checkout and qualify the existing reviewed profile as described in [judge-worker.md](judge-worker.md). The CCA-003 image tag is `contest-check-worker:cca003`; an old CCA-002 image cannot silently supply the new output-presence contract.

```bash
docker compose -f deploy/worker/compose.yaml build judge-worker
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml \
  run --rm --no-deps judge-worker --verify
JUDGE_EXECUTION_ENABLED=true JUDGE_REVIEWED_PROFILE=true \
  uv run --frozen uvicorn contest_check.api:app --host 127.0.0.1 --port 8000 --limit-concurrency 4
curl --fail --form task_zip=@task.zip --form submissions_zip=@submissions.zip \
  http://127.0.0.1:8000/api/judge
```

Both explicit environment settings are required. `.env` is not loaded automatically. `/health` reports the operator's execution configuration; it is **not** a sandbox qualification or a promise that Docker/image/prerequisites are available. The worker runs its full real qualification in its own process before every requested test. Missing settings return 503 `execution_disabled`; unavailable or failed infrastructure produces an incomplete batch, never a student failure.

The supported coordinator runs natively from the source checkout on the qualified Linux/WSL2 host, with a Docker CLI and access to **only the fixed local daemon address** `unix:///var/run/docker.sock`. The operator/coordinator is trusted and has Docker administration access. No Docker socket is mounted into any worker. Inherited Docker hosts, contexts and credentials cannot redirect the transport. The command is fixed, uses no shell and permits no upload-supplied argument, image, volume, environment or URL. Images are built explicitly beforehand; runtime uses `--pull=never` and never builds or downloads packages. Public exposure and containerizing the API were outside CCA-003. CCA-009 adds an optional [local containerized coordinator](local-development.md#explicit-judge-enabled-mode) with the same fixed transport and explicit Docker administration permission; its integrated activation is awaiting approval. Worker isolation is unchanged.

`POST /api/judge` takes the same two bounded multipart ZIP fields as `/api/validate`. Only one batch is admitted per API process; concurrent attempts return 503 `judge_busy`. Use one API process. A batch is synchronous and performs no retries. CCA-004 now provides the Streamlit validation/run/result flow and PDF/XLSX downloads; see [the UI/export contract](verdicts-and-reporting.md). The result includes ordered `test_ids`, allowing reports to list every not-run test without inventing identifiers.

## Per-test lifecycle

Each test gets a fresh hardened worker container, private 96 MiB tmpfs and NsJail workspace. `task.limits.time_seconds` starts again for every test, including after a prior timeout. The deadline counts jail startup and the program; the reported wall metric also includes bounded termination/reaping. Docker startup, qualification, policy parsing and comparison are excluded from this metric. CPU time and peak memory are unavailable and serialize as `null` (**N/A**), never zero estimates. No Big-O inference is made.

The worker removes its temporary source/input/output/configuration files before returning. The coordinator then removes that test's container before starting the next test. The transport bounds request/response data and has a separate 45-second infrastructure deadline plus bounded stop/removal time. That infrastructure deadline does not extend the program's configured limit. Cleanup failure returns `SYSTEM_ERROR` and stops the batch. The validated originals/private expected outputs remain available only until the batch workspace is automatically removed on completion or failure; generated runtime files never carry into a later test.

Normal cleanup does not guarantee cleanup after an abrupt host/API crash or daemon outage. A container has hard CPU/memory/process/tmpfs limits regardless of coordinator availability. The operator must remove a stranded `cca-judge-*` container after such an outage. There is no persistent job database or crash-recovery service in CCA-003.

## Comparison rules

The manifest chooses exactly one of these implemented modes:

| Mode | Rule |
| --- | --- |
| `exact` | Identical bytes. CRLF differs from LF; a final newline, trailing space, BOM and non-UTF-8 byte all matter. No decoding or normalization. |
| `tokens` | Compare ordered lists from Python `bytes.split()`. Only ASCII space, tab, LF, CR, vertical tab and form feed separate tokens. No Unicode-whitespace normalization, token sorting, numeric coercion or tolerance. |

Extra output/tokens fail comparison. An intentionally empty file can pass an empty expected output. An untouched pre-created output is `RE` / `missing_output`, even when the expected output is empty. To distinguish these cases, the supervisor sets the output's mtime to epoch zero before launch; writing or truncating it changes mtime. All timestamp-setting syscalls are denied inside the jail, and startup qualification verifies empty-written, untouched and denied timestamp-reset cases. The output remains the only writable file. Unexpected physical removal/symlinking or a capture larger than the hard bound violates the sandbox contract and is a system failure.

## Verdicts and incomplete results

| Runtime observation | Verdict / reason |
| --- | --- |
| Successful capture matches | `AC` / `output_matched` |
| Successful capture differs | `WA` / `output_mismatch` |
| Successful execution leaves output untouched | `RE` / `missing_output` |
| Supervisor's measured wall deadline expires | `TLE` / `time_limit` |
| Program exit/crash | `RE` / `program_exit` |
| Memory marker 70 | `RE` / `memory_limit_or_exit` |
| Output marker 71, including the hard output-byte cap | `RE` / `output_limit_or_exit` |
| Other resource signal/exit encoding | `RE` / `resource_limit_or_exit` |
| Sandbox, transport, invalid protocol, cleanup or workspace failure | `SYSTEM_ERROR`; wall/CPU/memory metrics are N/A |

`MLE` is reserved in the typed result, but **this backend does not emit it**: RLIMIT_AS failure and NsJail's exit/signal encoding are not trustworthy per-test OOM evidence. A program can deliberately choose 70/71 or a signal-like exit code. These hints never justify DQ or claims of intent; ambiguous CPU signal codes are likewise not asserted to be a proven timeout.

Successful API handling returns HTTP 200 with batch `status: completed` or `incomplete`. An incomplete response retains prior results, explicitly records the system failure, marks remaining tests as not run and never calls the worker again. Participants have separate passed, failed, system-error and not-run counts. A system failure contributes no failed test. Participants not reached after a system failure have `status: not_run`. No score, points, ordering by performance, winner or ranking is calculated.

## Optional contest policy

Existing manifests need no changes. An optional teacher configuration is:

```json
"policy": {
  "max_source_bytes": 4096,
  "review_imports": ["socket", "subprocess", "ctypes"]
}
```

`max_source_bytes` is the total byte size of all that participant's Python sources, bounded from 1 to 30 MiB. Exceeding an explicitly configured limit produces `DQ` with the rule, fixed reason and observed/allowed byte counts; no tests run for that participant. Equality is allowed. By default this policy is absent (`null`), so archive limits alone do not become a DQ. Invalid archives remain upload rejections before judging, never DQ.

`review_imports` is empty by default and accepts only the three names above, without duplicates. A bounded static AST inspection records matching import statements as `REVIEW`; it never imports or executes the source. The solution still receives its ordinary official test results. Failed static parsing becomes a review notice, never proof of misconduct. Comments/string mentions are not imports, dynamic imports can be missed, and an import can be harmless. This is a teacher-review aid, not fraud or plagiarism detection. Reasons are fixed codes; raw source and exception diagnostics are not returned.

## Verification

```bash
uv run --frozen pytest -q tests/test_judging.py tests/test_worker_transport.py tests/test_worker.py
uv run --frozen python scripts/verify_judge_batch.py --reviewed-profile
```

The first command mocks execution and exercises pipe transport without executing a program. The second is an operator-only, explicitly invoked integration suite. It accepts no external source and submits only fixed benign ZIPs through the real API service to qualified NsJail workers. It checks successful sibling-module file I/O, intentionally empty output, wrong answers, fresh timeouts, missing output, objective DQ, REVIEW without verdict changes and cleanup. It is not a CI task. Actual outcomes, commands, host/image IDs and limitations belong in [Release 0.1 verification](releases/release-0.1-automated-judge/verification.md).
