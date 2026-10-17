# Release 0.1 verification

**Status: Release 0.1 / CCA-001–004 implemented and locally verified.** Archive validation, separately qualified offline workers, typed batch results, Streamlit judging/results and PDF/XLSX exports exist. The configured local API passed fixed-fixture Docker/WSL2 integration in CCA-003; CCA-004 browser/report checks use a fixed mocked worker and are separate evidence. No unknown contestant programs have been run. Hosted CI/public deployment are not claimed verified.

| Story | State | Unit / API checks | Sandbox / UI / export checks | Notes |
| --- | --- | --- | --- | --- |
| CCA-001 | Implemented | See dated evidence below | UI AppTest + local HTTP startup/upload checks | Safe archive boundary retained |
| CCA-002 | Implemented | Mocked worker/contract tests | Real Docker/NsJail qualification + six benign runtime cases | Host-specific evidence below; no unsafe fallback |
| CCA-003 | Implemented | Deterministic mapping/order/policy/transport/API checks | Real API-service-to-NsJail fixed-fixture batch; 38-check startup qualification | Configured local API only; metrics unavailable honestly; no scores |
| CCA-004 | Implemented | Final suite: 330 passed; lint/format passed | Real local browser with mocked worker, PDF visual review, independent XLSX parsing and 100 × 100 report tests | Safe CI configured; hosted CI Not run; worker unchanged |

## Evidence instructions

After approval, append dated commands, observed outputs, OS/kernel/runner details for security tests, failures, constraints, and whether check used harmless known fixtures, mocks or real sandbox runs. Never mark a sandbox as safe based only on unit tests. Add actual commit hash only after user-approved commit.

## 2026-10-17 — CCA-001 foundation and safe ingestion

Authorization: the user explicitly requested implementation of CCA-001 and subsequently gave separate approval for a local commit. Only this story was implemented. No push was requested.

Environment: Linux/WSL2, `Linux 6.6.87.2-microsoft-standard-WSL2 x86_64 GNU/Linux`; CPython **3.12.13**, uv **0.11.29**. The default host `python3` was 3.14.4 and was not used for application verification. Python, package cache and verification environment were placed under `/tmp/cca001-python`, `/tmp/cca001-uv-cache` and `/tmp/cca001-venv` to avoid changing host installations.

### Installation and contract checks

Commands below used these temporary verification locations; ordinary developer setup uses `uv sync --locked` as documented in [local-development.md](../../local-development.md).

```bash
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python uv python install 3.12
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --bounds exact fastapi pydantic streamlit httpx python-multipart uvicorn
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --dev --bounds exact pytest ruff
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv sync --locked --offline
```

Observed: Python 3.12.13 installed; 51 lockfile packages resolved; the final offline locked sync checked 49 installed packages successfully. All direct dependency versions are exact; transitive hashes and versions are in `uv.lock`. Installation required an approved unrestricted tool run because restricted DNS could not resolve the download hosts. This was development setup, not application runtime network traffic.

```bash
timeout 60s /tmp/cca001-venv/bin/pytest -q tests/test_archives.py tests/test_api.py tests/test_ui.py -o faulthandler_timeout=15
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
git -c core.whitespace=cr-at-eol diff --check
/tmp/cca001-venv/bin/python scripts/make_demo_archives.py
```

Final observed results: **136 passed, 1 warning in 2.18s**; Ruff **All checks passed**; formatting **42 files already formatted**; `git diff --check` exited 0; demo generation succeeded. The warning is the documented Starlette adapter deprecation below. The final added ZIP64-specific archive test also passed in the focused archive-only run (**105 passed in 0.60s**).

Coverage uses known inert data/comment-only `.py` files: valid stored/deflated task/submission ZIPs; numeric IDs and optional sibling modules; strict typed manifest, JSON Schema/example consistency and all resource bounds; traversal/absolute/drive/backslash/NUL/Unicode/control paths; symlinks/devices/FIFOs/sockets; duplicate/case-ambiguous names; unsupported/nested/renamed archives; dishonest central entry counts and forged expansion sizes; CRC/local-header corruption; encryption/split/ZIP64/unsupported compression; compressed/expanded/per-file/file-count/participant limits; exact declared test pairs; cleanup after success, consumer error and partial extraction failure; no extraction directory before both inputs pass; safe API errors and private-source non-disclosure; actual body size limits with missing/dishonest length; disabled judge and placeholder reports. Source fixtures are never imported or executed.

Streamlit AppTest checks startup and disabled controls, success/upload-error/offline states, and local-only API port configuration. Upload values and HTTP responses are mocked for UI state tests; API tests use the real validation service through in-process TestClient.

Dependency review: inspected installed distribution license metadata for all 48 external packages and license notices for direct dependencies/build backend and selected bundled/MPL components. Inventory and redistribution boundaries are recorded in [dependency-licenses.md](../../dependency-licenses.md). Upstream notices were retained; no dependencies were vendored or modified.

### Corrected failures and environment limits

- Initial `uv python install 3.12` failed with DNS resolution errors in the restricted environment. Re-running with tool approval installed the pinned interpreter.
- Initial `/tmp/cca001-venv/bin/pytest -q tests/test_archives.py tests/test_api.py` and the subsequent combined suite stalled entering TestClient and were interrupted. `timeout 20s /tmp/cca001-venv/bin/pytest -vv tests/test_api.py::test_validation_returns_summary_only -o faulthandler_timeout=8` exited 124; its trace showed the cross-thread event-loop portal waiting. The approved unrestricted run completed API tests without a code workaround.
- The first unrestricted combined suite reported **126 passed, 4 failed**: Streamlit 1.66 resolves AppTest relative paths against the test file, so the test looked in `tests/`. Fixed by using the absolute application path. Later complete runs passed, including the expanded suite below.
- Initial Ruff checks found line lengths/unused imports; a later ZIP64 fixture briefly lacked an `io` import. Corrected before final verification.
- The first `/tmp/cca001-venv/bin/python /tmp/cca001-live-smoke.py` failed because loopback port 8000 was already occupied (`Errno 98`). That existing service was not modified. The test was rerun on 18000 and the UI was configured with `API_PORT=18000`.
- Starlette 1.8 emits one deprecation warning for its HTTPX TestClient adapter (suggesting `httpx2`). This does not fail the tests; HTTPX 0.28.1 remains pinned and no warnings are suppressed.

### Live local service checks

`/tmp/cca001-venv/bin/python /tmp/cca001-live-smoke.py` launched the following trusted application commands with the temporary uv locations above and `JUDGE_EXECUTION_ENABLED=true`; it sent requests with an HTTPX client using `trust_env=False`, then stopped only its own process groups:

```bash
uv run --frozen uvicorn contest_check.api:app --host 127.0.0.1 --port 18000 --limit-concurrency 4
API_PORT=18000 uv run --frozen streamlit run streamlit_app.py --server.port 8501
```

Observed over actual loopback HTTP:

- `GET :18000/health`: **200**, `{"status":"ok","execution_enabled":false}`.
- `GET :8501/_stcore/health`: **200**, `ok`; Streamlit root HTML: **200**.
- `POST :18000/api/validate` with the generated demo task/submissions: **200**, task `addition`, 1 test, participant IDs `1001`/`1002`, 3 source files, 492 extracted bytes, `execution_enabled: false`.
- Replacing submissions with inert invalid ZIP data: **400**, code `invalid_zip`, fixed upload-error message.
- `POST :18000/api/judge` despite enabling environment flag: **503**, `execution_disabled`.
- `GET :18000/api/reports/pdf` and `/xlsx`: **501**, placeholder contracts only.
- Both temporary service processes stopped at the end. Temporary API logs: `/tmp/cca001-live-smoke-api.log`; UI logs: `/tmp/cca001-live-smoke-ui.log`. These are local verification artifacts, not committed assets.

### Not run / remaining boundaries

**Not run:** browser-driven file upload/screenshots; sandbox/namespaces/seccomp/security integration; student-program execution; verdicts; PDF/XLSX generation; model calls; Docker builds/deployment; public-host checks; Windows-native permission verification; CI. These are outside CCA-001. A private temporary extraction directory is not an execution sandbox. No claim of safe worker execution is made. Normal context-manager cleanup is tested; abrupt process/host crashes may leave temporary files for OS/operator cleanup.

## 2026-10-17 — CCA-002 isolated Python worker

Authorization: the user requested CCA-002 implementation and separately approved testing the scoped worker-only syscall profile after the default Docker namespace probe failed. The [security review](../../worker-security-review.md) describes the final concrete profile and setup corrections. Implementation and verification initially ended without a commit; the user subsequently approved committing CCA-002, including the timeout/cleanup follow-up. No push was requested. No other story was implemented; the web/API judge route still returns 503.

### Environment, pins and licensing

Observed target: **Docker Desktop 4.82.0 (233772), Docker Engine 29.6.1**, Linux **6.6.87.2-microsoft-standard-WSL2**, x86-64, cgroup v2; built-in Docker seccomp and cgroup namespaces present. The host's non-container namespace probe succeeded, but the same trusted user/mount/network namespace probe in a non-root, capability-free default-profile container failed with `PermissionError: Operation not permitted`. Native agent `python -m contest_check.judge.cli --check` also exited 78 and failed required environment/resource/runtime checks; it ran no jail or submission.

Pinned NsJail **3.5** commit `402e2b4c13c79731c632c2add4c3884dd1afc25f`; Kafel submodule `b4241da9f3d17e786387280fc6e4965634fdf45b`; official CPython **3.12.13** image digest `sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`. Both sandbox components were inspected from upstream source and their Apache-2.0 LICENSE files; no binary was blindly vendored and no upstream patches were applied. Build-time Git/package downloads are separate from the offline runtime.

Actual final tested worker image: **`sha256:b8c8359a54ee49ace54330494e9c1db254f0de79305f75afdd39c459ef8627e1`**. The checked-in [JSON evidence](evidence/cca002-docker-verification.json) contains this image ID, actual inspected container settings, both profile outcomes, runtime results, source pins and hashes of the tested configuration files.

Observed native runtime package versions (`dpkg-query` in the image):

| Package | Version |
| --- | --- |
| libc6 | `2.36-9+deb12u14` |
| libgcc-s1 / libstdc++6 | `12.2.0-14+deb12u1` |
| libnl-3-200 / libnl-route-3-200 | `3.7.0-0.2+b1` |
| libprotobuf32 | `3.21.12-3+deb12u1` |

The image retains NsJail/Kafel licenses, package copyright files and common-license texts. libnl's LGPL-2.1 and GCC runtime exceptions/component notices were inspected, alongside protobuf's package notices. The image is a collection of differently licensed components, not exclusively Apache-2.0. ContestCheck's own source remains Apache-2.0. Full redistribution/source obligations are documented in [judge-worker.md](../../judge-worker.md#licensing-and-distribution); no image was published. Apt resolution is recorded, not claimed to be byte-for-byte reproducible.

### Exact build and verification commands

Python unit verification reused `/tmp/cca001-venv` (CPython 3.12.13, pytest 9.1.1, Ruff 0.17.1) and the CCA-001 temporary uv locations. Adding the optional worker group did not upgrade existing dependencies.

```bash
git ls-remote https://github.com/google/nsjail.git refs/tags/3.4 refs/tags/3.5 refs/heads/master
git clone --depth 1 --branch 3.5 --recurse-submodules --shallow-submodules https://github.com/google/nsjail.git /tmp/cca002-nsjail-source
docker version --format '{{json .}}'
docker info --format 'Kernel={{.KernelVersion}} OS={{.OperatingSystem}} Cgroups={{.CgroupVersion}} Security={{json .SecurityOptions}}'
docker pull python:3.12.13-slim-bookworm
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --offline --group worker --bounds exact pydantic
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv export --frozen --only-group worker --no-emit-project --format requirements-txt --output-file deploy/worker/requirements.txt
docker compose -f deploy/worker/compose.yaml build judge-worker > /tmp/cca002-build.log 2>&1
docker compose -f deploy/worker/compose.yaml run --rm --no-deps judge-worker --check
docker compose -f deploy/worker/compose.yaml run --rm --no-deps judge-worker --verify > /tmp/cca002-default-verification.json
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml config --format json
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml run --rm --no-deps judge-worker --verify > /tmp/cca002-reviewed-verification.json
/tmp/cca001-venv/bin/python scripts/verify_worker_deployment.py --reviewed-profile > /tmp/cca002-deployment-evidence.json
/tmp/cca001-venv/bin/pytest -q tests/test_worker.py
timeout 60s /tmp/cca001-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
git -c core.whitespace=cr-at-eol diff --check
```

Docker access and the full TestClient suite used approved tool execution; the restricted tool environment could not access the daemon and previously stalled TestClient's cross-thread loop. No sandbox restriction was bypassed inside a worker to work around the agent-tool restrictions.

Final observed Python results: focused worker tests **59 passed in 0.53s**; complete suite **195 passed, 1 warning in 2.38s**. The warning remains Starlette's already documented HTTPX TestClient adapter deprecation; none was suppressed. Ruff reported **All checks passed**, formatting **55 files already formatted**, and whitespace checks exited 0. The final offline `uv sync --locked --offline` resolved 51 lock packages and checked 49 installed packages without changes.

### Observed security and runtime results

- The final default-profile verification returned **78**, `execution_ready: false`, with all outer checks passing and the first real jail attestation failing. No submitted source ran.
- The reviewed-profile verification returned **0**, `execution_ready: true`, with **35/35 checks passing** on actual NsJail executions. This includes seven separate namespaces, UID/GID 65534, zero capability sets, no-new-privileges, at least two seccomp layers, read-only root/work mounts, one writable output mount, clean descriptors/environment, hard limits, restricted filesystem and sockets/DNS/fork/namespace/symlink/ptrace, bounded memory/output/CPU/wall/FDs, sibling modules, reaping and workspace cleanup.
- Docker inspect confirmed **network `none`, read-only root, no privileges/capabilities, no host binds or published ports, 384 MiB memory with the same memory+swap total, one CPU, 16 outer processes**. Private scratch is a 96 MiB noexec/nosuid/nodev tmpfs. No Docker socket, application secrets, public endpoint or host-cgroup write mount was supplied.
- The integration harness ran **six known, controlled protocol cases** only after each worker completed its own qualification. It removed all of its named test containers in `finally`. Success returns only the expected file; failure returns no partial output payload or raw source diagnostics.

| Protocol fixture | Observed result |
| --- | --- |
| Named `challenge.in` / `answer.out`, sibling `helper.py` | `success` / `completed`, exact output bytes `3\n` (2 bytes) |
| Runtime exception carrying a private marker | `crash` / `program_exit`; marker absent from stdout/stderr diagnostics |
| Sleep with 0.5-second wall limit | `timeout` / `wall_limit`, returned after about 0.508 seconds including cleanup |
| Repeated output writes, 4,096-byte limit | `resource` / `output_or_exit`, actual output exactly 4,096 bytes |
| Bounded allocation probe, 64 MiB address-space limit | `resource` / `memory_or_exit` |
| IPv4 socket attempt | `crash` / `program_exit`, SIGSYS-style status; no connection |

Elapsed times are one observed run including jail setup/termination, not algorithm benchmarks. Exit/signal encodings and 70/71 resource markers are hints, not proof of intent; no DQ/scoring exists. Raw program stdout/stderr and NsJail logs are discarded in production paths. Debugging below used only the fixed trusted probes and temporarily exposed their own NsJail setup diagnostics, never unknown contestant source.

### Corrected failures and retained boundaries

- Docker access initially returned permission denied in the restricted tool sandbox; an approved read-only daemon query established the actual target capabilities.
- Default-profile trusted `os.unshare(USER|MOUNT|NET)` probe failed EPERM. The user explicitly approved the documented worker-only profile test. All final runs retained non-root UID, zero capabilities, no-new-privileges, network `none`, read-only root and all resource caps.
- Compose rejected the initial override list syntax; using one `seccomp:./docker-seccomp.json` entry lets the base no-new-privileges setting merge correctly.
- The Windows-mounted checkout copied a writable policy mode into the first image; runtime integrity rejected it. The build now explicitly sets the policy to 0444. The expected read-only Docker init mount was added to the exact mount allowlist; arbitrary mounts, including extra paths under `/proc`, `/sys` and `/dev`, are rejected.
- The first outer profile omitted Docker init's specific fork/signal/group operations. These were added as trusted supervisor setup calls, still under the outer process cap and denied by the inner jail policy.
- Kafel uses `newstat`/`newfstat`/`newlstat`/`newuname` names on x86-64. Unsupported initial aliases failed policy compilation, so the pinned table names were used; the permitted syscall operations were not broadened by those renames.
- NsJail's parent performs a Netlink route query even without interfaces to move. The outer profile permits AF_UNIX and only AF_NETLINK/NETLINK_ROUTE for setup; AF_INET/AF_INET6 remain denied, and the inner jail denies all socket families. No egress or network capability was added.
- The legacy mount path failed read-only remount with EPERM. The new upstream mount API plus an initial bind over `/` then failed remount with EINVAL. The selected configuration instead starts with an empty private root and mounts only the minimal runtime subtrees/bootstrap individually. It uses the pinned upstream new mount API, retains read-only boundaries and verifies the actual mount flags before allowing a request. There is no runtime fallback between mount implementations.
- PID-namespace PID 1 ignores many default signal dispositions: the first output test hit kernel EFBIG and returned a crash rather than a signal classification. The bootstrap now has an explicit SIGXFSZ handler, and the supervisor checks the actual output file size on every outcome. The hard kernel byte cap was retained throughout.
- Initial Ruff line-length/import findings and exact-text patch mismatches were corrected before final verification. No failed security check was marked successful or skipped.

### Not run / remaining scope

**Not run:** unknown contestant programs or malware; browser-triggered judging; CCA-003 comparison/official verdicts; report generation; model calls; CI sandbox execution; public deployment/image publication; other kernels/architectures/Windows-native execution; independent exploit audit. Runtime syscalls required by this pinned CPython are allowlisted; threads/processes, network-dependent modules and third-party student packages are intentionally unsupported. Host/kernel vulnerabilities remain a residual risk. The current host-specific evidence is not a universal safety guarantee, and every new worker/image/profile/host must qualify again before accepting programs.

## 2026-10-17 — CCA-002 per-test timeout and cleanup follow-up

The user explicitly requested a short configurable execution limit that restarts for each tested program and automatic deletion of generated test data before proceeding. Inspection confirmed both were already implemented: `task.limits.time_seconds` is passed afresh to each execution's watchdog, and the per-test `TemporaryDirectory` context exits before the backend returns. No application/runtime source, dependency, image or security-profile change was needed. The active story and worker guide now explicitly state the lifecycle, including the requirement for the future CCA-003 coordinator.

Added five regression cases in `tests/test_worker.py`:

- Four sequential-execution cases use the same backend after success, crash, resource failure or timeout. They assert the old directory (including nested temporary data) is deleted before the next launch, the next input/source are current, the next output starts empty, each wait receives a full 0.5-second budget, and elapsed time starts afresh despite a simulated gap between runs.
- An injected directory-cleanup failure leaves temporary files, produces only safe `system_error` metadata and revokes qualification; the next request cannot launch a program. The test removes its own deliberately retained fixture directory afterwards.

Verification commands:

```bash
/tmp/cca001-venv/bin/pytest -q tests/test_worker.py
timeout 60s /tmp/cca001-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
/tmp/cca001-venv/bin/ruff check tests/test_worker.py
/tmp/cca001-venv/bin/ruff format --check tests/test_worker.py
git -c core.whitespace=cr-at-eol diff --check
```

Observed results: focused tests **64 passed in 0.66s**; full suite **200 passed, 1 warning in 2.47s**. Ruff checks passed, formatting reported **55 files already formatted**, and whitespace checks exited 0. The existing Starlette deprecation warning remains unchanged. The final focused run followed a test-only refinement to advance a simulated clock independently of how often the backend reads it. The full suite again used approved execution because of the previously documented restricted-environment TestClient issue.

These new cases mock NsJail and time; no fixture program executes on the host. **Not rerun:** Docker build and sandbox integration, because deployed worker source and configuration are unchanged. The earlier actual 0.5-second timeout, termination/reaping and workspace-cleanup evidence above remains applicable; the added sequential and cleanup-failure assertions are unit evidence, not a new live sandbox claim. No commit or push was performed.

## 2026-10-17 — CCA-003 deterministic batches, verdicts and policy

Authorization: the user explicitly requested implementing CCA-003. The earlier explicit approval of the scoped worker-only profile remained applicable: neither the outer Docker syscall profile nor the inner Kafel policy was relaxed or changed. Only fixed benign fixture programs were used. Implementation and verification initially ended without a commit. The user subsequently approved committing CCA-003 after checking that only appropriate project files are included. No push was requested; no other story was implemented.

### Implemented behavior and boundaries

- Validated ZIPs feed a deterministic coordinator: participant IDs stay opaque strings in lexicographic order; tests run in the manifest's declared order. Each test gets a fresh private worker/jail and a fresh manifest time budget. The runtime files and then the test container are removed before proceeding. Expected answers stay coordinator-only; responses contain no uploaded source, private input or actual/expected output.
- `exact` means identical bytes, including CRLF, BOM and final newline; `tokens` means ordered `bytes.split()` tokens with ASCII whitespace only, without numeric coercion. Extra output is WA. Untouched output is RE/missing-output; deliberately empty/truncated output can be AC. The output's initial epoch mtime and denied timestamp setters distinguish the latter cases; three new real startup probes verify this contract.
- Official outcomes are typed AC/WA/TLE/RE/SYSTEM_ERROR. MLE is reserved but not emitted because the backend cannot reliably distinguish per-test OOM from a deliberately chosen exit/signal encoding. Memory/output/resource markers produce explicit `*_or_exit` reasons. Only the supervisor's observed wall deadline produces TLE. CPU and peak memory are N/A (`null`); unavailable wall time is also null. Wall time includes jail startup and bounded termination/reaping, excluding Docker startup/qualification. No retries or Big-O claims.
- Optional teacher policy permits an objective total-source-byte DQ with observed/configured byte evidence. Static configured import indicators produce REVIEW only and never change official test verdicts. Neither invalid uploads nor sandbox failures become DQ. Defaults enable no policy checks; existing manifests remain valid. The generated schema matches the typed manifest.
- A system/transport/protocol/cleanup failure stops the whole batch and retains prior results with separate passed, failed, system-error and not-run counts. Remaining participants are explicitly not run. No score, ranking, winner, accounts or database exists.
- `POST /api/judge` uses the same bounded two-ZIP multipart contract as validation and admits one batch per API process. Both explicit operator settings are required; environment flags never bypass worker qualification. The trusted native coordinator uses a fixed local Docker daemon address and fixed offline, non-root, capability-free image command with no shell, image pull, host binds, secrets or public worker port. The coordinator has trusted local Docker administration access; no daemon socket enters a worker. Setup, limits and result contracts are in [judging.md](../../judging.md).

### Environment and exact commands

The same CPython 3.12.13, temporary uv environment and qualified Docker/WSL2 host were used: Docker Engine **29.6.1**, Linux **6.6.87.2-microsoft-standard-WSL2**, x86-64, cgroup v2. Upstream NsJail/Kafel/base-image pins and licenses are unchanged. No Python dependency was added or upgraded; the offline lock check resolved the existing 51 packages. The CCA-003 image tag prevents silently using the old output-presence protocol.

Actual tested image: **`contest-check-worker:cca003`**, **`sha256:61c28046ff9e657c00339d5771cfb5fa0f2c8b940778c2587b08518920eb54e9`**. The checked-in [batch evidence](evidence/cca003-batch-verification.json) records both qualification outcomes, inspected container limits, typed API results, cleanup, host properties and hashes of tested configuration/coordinator files. The earlier CCA-002 artifact remains historical evidence for its own image/configuration.

```bash
docker --host unix:///var/run/docker.sock version --format '{{.Server.Version}}'
docker --host unix:///var/run/docker.sock compose -f deploy/worker/compose.yaml build judge-worker > /tmp/cca003-build.log 2>&1
docker --host unix:///var/run/docker.sock compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml run --rm --no-deps judge-worker --verify > /tmp/cca003-reviewed-verification.json
/tmp/cca001-venv/bin/pytest -q tests/test_judging.py tests/test_worker_transport.py tests/test_worker.py
timeout 60s /tmp/cca001-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca001-venv/bin/python scripts/verify_judge_batch.py --reviewed-profile > /tmp/cca003-batch-evidence.json
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python uv lock --check --offline
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
git -c core.whitespace=cr-at-eol diff --check
```

Docker calls and the full TestClient suite used approved tool execution for the same daemon/socket and restricted-environment TestClient reasons documented for CCA-001/002. The new focused tests use mocked executors and trusted pipe helpers; they execute no fixture program on the host and do not call a model or external service.

Final observed results: focused **136 passed in 0.90s**; full suite **278 passed, 1 warning in 3.09s**. Ruff reported **All checks passed** and **62 files already formatted**; whitespace checks exited 0. The only warning remains the existing Starlette HTTPX TestClient deprecation, unsuppressed. The offline lock check passed without a dependency change.

Final diff/artifact review confirmed the exact SPDX headers on all 6 new Python files, 74 valid local documentation links, all 8 recorded evidence hashes matching the current files, and no whitespace defects in new text files. Both syscall policies are byte-for-byte unchanged from the CCA-002 baseline. A final Docker listing found no remaining `cca-judge-*` or `cca003-qualification-*` containers. At the end of implementation review, the Git index was empty and CCA-003 changes were uncommitted. The subsequent commit review checked all 32 changed/new files, found no credential-shaped content or unexpected runtime artifacts, confirmed the example API key is blank, and verified that the evidence contains no uploaded source/input/output fields.

### Actual sandbox and API-service results

The default Docker profile still fails closed: exit 78, `execution_ready: false`, first real jail attestation failed. With the approved profile, the updated worker passed **38/38 real checks**, including the original isolation/limits and new empty-written, untouched and denied timestamp-reset probes. Every requested fixture test qualified again in its own process before execution. Inspected settings retained network `none`, read-only root, no capabilities/host binds/ports, 384 MiB memory/no additional swap, one CPU and 16 outer processes.

The operator-only integration script submitted fixed ZIPs to the **real FastAPI service through in-process TestClient**, using production configuration and the actual local Docker transport. Archive validation, policy evaluation, protocol exchange, all NsJail execution, comparison, counts and cleanup are real; the HTTP socket/server and browser are not exercised. A temporary directory override allows the harness to verify that all upload/job files are gone afterwards. The three test IDs are deliberately ordered `b`, `a`, `empty` to detect sorting mistakes.

| Participant fixture | Observed per-test results | Summary |
| --- | --- | --- |
| `1001`, named file I/O and sibling helper, including deliberately empty output | AC, AC, AC | 3 passed; REVIEW for an unreachable static import indicator; official results unchanged |
| `1002`, wrong file contents | WA, WA, WA | 3 failed |
| `1003`, sleep with a fresh 0.5-second deadline | TLE, TLE, TLE | 3 failed; measured about 0.508–0.569 seconds including startup/termination; no cumulative deadline |
| `1004`, no output write | RE, RE, RE / `missing_output` | 3 failed, including the empty-expected test |
| `1005`, 1,025 source bytes under explicit 1,024-byte policy | No program launched | DQ with observed/allowed byte evidence; 3 not-run tests |

The batch returned `completed`, with no system errors, 12 actual program runs and no new leftover test containers or job-workspace files. Each success fixture also verifies that the new output starts empty. The harness removes its own qualification container in `finally`. These timings are one observed run, not algorithm benchmarks.

Mocked checks additionally cover malformed/oversized/unsupported worker responses, lost Docker access, transport deadline/cleanup/reaping failures, first and later system failures with retained prior results, N/A metrics, schema/policy boundaries, unchanged REVIEW verdicts, archive rejection before execution, source/expected-output privacy, request-size enforcement and batch-slot release. A cleanup exception in the local CLI still attempts daemon-side container removal; an uncertain stop never permits the next test.

### Corrected failures and Not run

- Initial focused collection failed because pytest reserves the fixture name `request`; renamed it before running tests. An instance-level Pydantic metadata warning in a new test was corrected to class-level access. Initial import/line-length/format findings were fixed; final lint and formatting checks pass.
- The first complete integration harness exited 1 on its positive-fixture verdict assertion. A separate controlled request of that fixture returned RE/crash, SIGSYS 31, about 0.215 seconds: its executable network-module import was incompatible with the existing restrictive runtime. The positive fixture now uses an unreachable static import indicator, proving that a REVIEW flag can coexist with AC. No syscall, mount, network or privilege restriction was weakened. The final full harness exited 0 and its checked-in artifact has `verified: true`.
- The test harness now retains safe partial result metadata if an assertion fails; it never prints source or private expected outputs. The initial failed run returned no success artifact and was not represented as passing evidence.

**Not run:** unknown contestant programs/malware; browser-driven judging/results; actual HTTP socket/uvicorn judging; PDF/XLSX; model calls; CI sandbox execution; public deployment/image publication; other kernels/architectures/Windows-native execution; host/API crash recovery or a persistent queue; independent exploit audit. Full runtime qualification per one-shot test adds startup overhead; large batches are synchronous. Missing CPU/memory metrics and reserved MLE are explicit limits. The Streamlit screen remains validation-only with its Run button disabled. CCA-004 and Release 0.2 were not implemented. No commit or push was performed during implementation/verification.

## 2026-10-17 — CCA-004 UI, reports and MVP verification

Authorization: the user explicitly requested implementation of CCA-004. Implementation and verification completed without a commit; the user subsequently gave separate approval to commit the reviewed changes. This work completes that story only. No push, public deployment or model call was requested or performed.

### Implemented scope and dependency review

Streamlit now supports validation, an honest indeterminate running stage, anonymous summary/per-test tables, separate DQ/review tables, incomplete batches, report preparation and PDF/XLSX downloads. Changing an upload, revalidating or starting a new run clears previous results/downloads. Report errors retain results. Downloads do not rerun judging.

The report API accepts only bounded typed result JSON, including ordered test IDs, with coherent counts and policy evidence. Unknown/private fields and untrusted diagnostics are refused without echoing them. Each JSON body and artifact is capped at 8 MiB; one report generation is admitted per API process. Both exporters operate in memory, preserve not-run tests and unavailable measurements, and omit source and private test contents. PDF uses built-in Helvetica and repeated table headers. XLSX writes identifiers as text, disables formulas/URL detection, neutralizes unsafe prefixes/control characters and uses four distinct sheets.

New runtime packages: ReportLab **5.0.1**, XlsxWriter **3.2.9**. Development-only independent readers: openpyxl **3.1.5**, pypdf **6.21.1**, with et-xmlfile **2.0.0**. Existing dependency versions and the worker group/requirements were preserved. Installed notices were inspected: ReportLab toolkit BSD-3-Clause, XlsxWriter BSD-2-Clause, openpyxl/et-xmlfile MIT and pypdf BSD-3-Clause. ReportLab also bundles separately licensed Vera/DarkGarden font resources; those notices are retained and these exports do not embed those fonts. See [dependency inventory](../../dependency-licenses.md) for the exact redistribution boundary. No dependency was vendored or modified and no new image was published.

### Environment and exact automated commands

Linux/WSL2 environment and Python locations are the same as the preceding evidence: CPython **3.12.13**, uv **0.11.29**, pytest **9.1.1**, Ruff **0.17.1** in `/tmp/cca001-venv`. Installation required authorized development network access, separate from application runtime.

```bash
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --bounds exact reportlab xlsxwriter
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --dev --bounds exact openpyxl pypdf
/tmp/cca001-venv/bin/pytest -q tests/test_reports.py tests/test_judging.py
/tmp/cca001-venv/bin/pytest -q tests/test_reports.py
/tmp/cca001-venv/bin/pytest -q tests/test_reports.py tests/test_ui.py
/tmp/cca001-venv/bin/pytest -q tests/test_reports.py -k maximum
timeout 60s /tmp/cca001-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv sync --locked --offline
git diff HEAD --exit-code -- src/contest_check/judge src/contest_check/models.py deploy/worker
```

Observed results, in order: initial report/judging checks **80 passed, 3 warnings**; after the warning corrections below, report-only **26 passed in 1.27s** without warnings; report/UI **40 passed in 5.45s**. The two subsequently added maximum-batch cases passed (**2 passed in 20.41s**): both formats represent **100 participants × 100 tests** within the output cap, including the last declared participant/test. The final complete suite passed **330 tests, 1 warning in 21.69s**. The remaining warning is the existing Starlette HTTPX TestClient deprecation, not suppressed. The suite uses inert archive fixtures and mocked workers, with no contestant execution, Docker or model traffic. API/TestClient checks used the authorized environment because of the restricted cross-thread socket limitation already recorded for CCA-001.

Final Ruff: **All checks passed**; format: **67 files already formatted**. Final locked offline sync: **56 packages resolved, 54 checked**, no lockfile change. A direct comparison of `HEAD:uv.lock` with the new lock confirmed all existing versions unchanged. The worker/source/config diff command exited **0**: judge modules, task/resource schema, worker Dockerfiles/profiles/requirements and deployment are unchanged.

CI is defined in [check.yml](../../../.github/workflows/check.yml), with read-only contents permission, no persisted checkout credentials, execution flags false, empty provider settings and only locked install/lint/format/mocked pytest steps. Action revisions were resolved from the upstream repositories:

```bash
git ls-remote https://github.com/actions/checkout.git refs/tags/v7
git ls-remote https://github.com/astral-sh/setup-uv.git refs/tags/v7
```

Pinned revisions: checkout `3d3c42e5aac5ba805825da76410c181273ba90b1`, setup-uv `94527f2e458b27549849d47d273a16bec83a01e9`. Python 3.12.13 and uv 0.11.29 are explicit. The workflow was manually reviewed; hosted GitHub Actions has **not run** in this task.

### Actual browser and downloaded report checks

The optional checked-in operator harness starts real loopback FastAPI/Streamlit services, supplies only its own inert archives and overrides the worker with fixed responses. It accepts no external source file. Browser versions: Node **24.18.0**, Playwright **1.62.1**, Chromium **151.0.7922.34**. Existing extracted browser libraries were used under `/tmp`; no system or worker sandbox configuration was changed.

Successful command:

```bash
LD_LIBRARY_PATH=/tmp/task-flow-svg-check/browser-libs/extracted/usr/lib/x86_64-linux-gnu CCA_BROWSER_NODE=/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node CCA_PLAYWRIGHT_MODULE=/tmp/open-nook-onk001-browser/node_modules/playwright /tmp/cca001-venv/bin/python scripts/verify_ui_reports.py --output /tmp/cca004-ui-verification
```

Observed: **exit 0**, desktop **1440 × 1000**, mobile **390 × 844**, invalid upload rejection, real running-stage visibility, completed results, both attachment downloads, upload-change stale-result/download removal and an incomplete system-error batch all passed. No browser page errors, unexpected external requests or page-level horizontal overflow were observed. The tables retain internal horizontal scrolling on narrow screens. Only the harness's own service process groups were stopped in `finally`; fixture ZIPs were removed with its temporary directory.

Fixture metadata: task `offline-ui-fixture`, manifest tests `z`, `a`; anonymous participants `1001` (synthetic AC/AC), `1002` (synthetic WA/WA plus static REVIEW), `1003` (synthetic TLE/TLE), `1004` (objective 1,025-byte/1,024-byte policy DQ, no worker call). A separate fixed system-error response proves incomplete/not-run presentation. These verdicts and timings are **test data**, not observed student execution or algorithm benchmarks.

The PDF downloaded through the actual UI was **4,318 bytes**, SHA-256 `6075395b54ff727dbe22fb81937641372ec4a2803c7ea5d5e8471e4f64ade389`; XLSX **9,558 bytes**, SHA-256 `92d2baeb68bf9d4e62193fe34036e0121015fd4c62313afb0fb2bfb413bcb616`. pypdf read the PDF text; openpyxl independently read all **8** detailed test rows and confirmed no formulas. Unit tests additionally inspect sheet names, IDs, policies, numeric values, links/macros, deterministic bytes, privacy and maximum-batch output.

Both PDF pages were rendered with an optional temporary tool environment and visually inspected alongside desktop/mobile UI screenshots:

```bash
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python uv run --no-project --python /tmp/cca001-venv/bin/python --with pypdfium2 --with pillow python - <<'PY'
from pathlib import Path
import pypdfium2 as pdfium

folder = Path("/tmp/cca004-ui-verification")
document = pdfium.PdfDocument(folder / "download.pdf")
for index in range(len(document)):
    page = document[index]
    bitmap = page.render(scale=1.5)
    bitmap.to_pil().save(folder / f"report-page-{index + 1}.png")
    bitmap.close()
    page.close()
document.close()
PY
```

Renderer: **pypdfium2 5.14.0**, Pillow **12.3.0**, **2 pages**. PDF tables/units fit the page, headers and page numbers are readable, and DQ/review are distinct. These optional rendering tools were not added to application or worker dependencies.

Checked-in evidence contains only fixed-fixture metadata and six real captures, with source/artifact hashes in [verification.json](evidence/cca004/verification.json):

- [Desktop results](evidence/cca004/results-desktop.png), [mobile results](evidence/cca004/results-mobile.png), [mobile uploads](evidence/cca004/uploads-mobile.png).
- [Incomplete batch](evidence/cca004/incomplete-desktop.png).
- [PDF page 1](evidence/cca004/report-page-1.png), [PDF page 2](evidence/cca004/report-page-2.png).

Raw downloaded reports, ZIPs, browser logs and intermediate captures stay outside version control. Default harness output is ignored `.runtime/cca004-verification/`.

### Sandbox evidence retained separately

No worker code, syscall profile, runtime limits, mounts, privilege or transport configuration was changed. The real **38-check startup qualification and 12 fixed-fixture program runs** in the preceding CCA-003 section remain the sandbox/integration evidence for image `sha256:61c28046ff9e657c00339d5771cfb5fa0f2c8b940778c2587b08518920eb54e9`, tag `contest-check-worker:cca003`. They were **not rerun or counted as new CCA-004 checks**. Browser-to-real-worker execution was not tested as one combined path. Every newly launched production worker still qualifies itself; a mock never qualifies a deployment. Native web/API plus worker-only Compose prerequisites and non-public access are documented in [local setup](../../local-development.md), [judging](../../judging.md) and [worker deployment](../../judge-worker.md).

### Corrected failures and Not run

- Initial lint/format findings were corrected before the final checks.
- Initial PDF/XLSX checks exposed an Excel footer parser warning and a ZIP finalizer warning on deliberate output overflow. Added the proper center footer prefix and changed the capped sink to discard overflow while allowing clean writer closure, then reject the artifact. Final report checks have no such warnings.
- The first restricted browser launch failed with `sandbox_host_linux.cc` / shutdown `EPERM`. The authorized local-browser run used existing temporary NSS/NSPR/ASound libraries. No judge restriction was weakened.
- The first browser upload-replacement check clicked Validate before the widget's upload-change callback completed. The harness now waits for the old error to disappear before validating the new upload; the subsequent complete run passed.
- Initial screenshots showed only the bottom of Streamlit's internal scroll container. The harness now scrolls the real view to the relevant sections before capturing; no page contents or styles were fabricated.
- An optional ad hoc YAML-parser check failed with `ModuleNotFoundError: No module named 'yaml'`. No dependency was added solely for that check; the small workflow was manually reviewed. This is not automated YAML validation or hosted-CI evidence.
- uv normalized an upstream invalid `>=3.6,` package specifier to `>=3.6` during resolution; installation and final locked offline sync completed.

Final diff/artifact review: `git -c core.whitespace=cr-at-eol diff --check` exited **0** after removing an extra documentation EOF blank line. A Python standard-library audit of all **36 changed/new files** found **0 errors**: six new source files have the exact SPDX headers, **100 local Markdown links** resolve, six PNG hashes/nine implementation hashes/two downloaded report hashes and sizes match the evidence, and no generated runtime directories or credential-pattern matches were found. At the end of implementation review the Git index was empty and no commit had been made. Before the subsequently approved commit, all nine implementation hashes and six evidence hashes matched again, all 36 files passed the artifact/credential-pattern/whitespace check, and the staged diff was reviewed separately.

**Not run:** hosted GitHub CI; an Excel/LibreOffice GUI (independent openpyxl parsing was run); browser-to-real-NsJail judging as a combined path; new Docker builds or sandbox runs in this story; unknown contestant programs/malware; live Ollama/OpenRouter or other Release 0.2 workflows; public deployment/image publication; other kernels/architectures/Windows-native execution; host/API crash recovery or persistent queues; independent security/exploit audit. Existing synchronous-batch overhead, unavailable CPU/memory measurements, reserved MLE and abrupt-crash cleanup limits remain documented. These local results establish the recorded behavior, not universal safety.
