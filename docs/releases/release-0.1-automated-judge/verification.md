# Release 0.1 verification

**Status: CCA-001/002 locally verified, release incomplete.** Archive validation and a separately qualified offline worker exist. The recorded Docker/WSL2 worker passed sandbox integration; browser/API judging remains disabled until CCA-003. No unknown contestant programs have been run.

| Story | State | Unit / API checks | Sandbox / UI / export checks | Notes |
| --- | --- | --- | --- | --- |
| CCA-001 | Implemented | See dated evidence below | UI AppTest + local HTTP startup/upload checks; sandbox/export Not run | Execution hard-disabled; report endpoints are placeholders |
| CCA-002 | Implemented | Mocked worker/contract tests | Real Docker/NsJail qualification + six benign runtime cases | Host-specific evidence below; no unsafe fallback; web/API execution disabled |
| CCA-003 | Planned | Not run | Not run | No runner/verdicts implemented |
| CCA-004 | Planned | Not run | Not run | Only CCA-001 upload UI exists; no results UI, XLSX/PDF exporter or CI |

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
