# Release 0.1 verification

**Status: CCA-001 locally verified, release incomplete.** Archive validation and the UI/API foundation exist. No sandbox or student-code execution has been verified or enabled.

| Story | State | Unit / API checks | Sandbox / UI / export checks | Notes |
| --- | --- | --- | --- | --- |
| CCA-001 | Implemented | See dated evidence below | UI AppTest + local HTTP startup/upload checks; sandbox/export Not run | Execution hard-disabled; report endpoints are placeholders |
| CCA-002 | Planned | Not run | Not run | No sandbox; execution must stay disabled |
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
