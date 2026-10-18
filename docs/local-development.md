# Local development — Python judging and challenge authoring

Python **3.12.13**, `uv`, and a local Linux environment are used for the verified setup. `.python-version` selects the interpreter; direct dependencies are pinned and `uv.lock` records transitive versions and hashes. Dependency download happens during installation only. The application performs no runtime package/model downloads. Optional configured model calls require explicit teacher generation/revision. Uploaded programs execute only in separately qualified offline workers.

```bash
uv sync --locked
```

In two terminals, from the repository root:

```bash
uv run --frozen uvicorn contest_check.api:app --host 127.0.0.1 --port 8000 --limit-concurrency 4
```

```bash
uv run --frozen streamlit run streamlit_app.py --server.port 8501
```

Open <http://127.0.0.1:8501>. The UI calls the local API on port 8000. Streamlit binds to loopback, limits each file upload to 10 MiB and disables usage telemetry through `.streamlit/config.toml`. Its `client.toolbarMode = "viewer"` setting hides developer controls, including the Deploy button, in both native and Docker runs; the native System/Light/Dark theme choices, Print and browser-supported Record screen remain available. The app does not load `.env`. API judging is disabled by default; setting only `JUDGE_EXECUTION_ENABLED=true` is insufficient. Follow [judging.md](judging.md) to build/qualify the worker and explicitly configure both operator settings. After validation, the UI enables Run solutions; an unconfigured API refuses judging with a clear error. Review results, select Prepare PDF and XLSX and download the reports. The [UI/export contract](verdicts-and-reporting.md) explains state resets, N/A metrics and limits.

If port 8000 is occupied, use another local port for both processes. For example, start the API with `--port 18000`, and start the UI with `API_PORT=18000 uv run --frozen streamlit run streamlit_app.py --server.port 8501`. The UI accepts only a port number and always connects to `127.0.0.1`; no arbitrary API URL is accepted. `API_PORT` must be exported or provided on the command line; merely editing `.env` does not configure it.

Generate two known, inert example archives, then upload them using the UI or API:

```bash
uv run --frozen python scripts/make_demo_archives.py
curl --fail-with-body http://127.0.0.1:8000/api/validate \
  -F task_zip=@.runtime/demo/task.zip \
  -F submissions_zip=@.runtime/demo/submissions.zip
```

The response reports `validated`, the task ID, number of tests, opaque participant IDs, source-file count, total extracted bytes and `execution_enabled: false`. Files are removed before the response; no job or student data is persisted. Revalidation requires another upload. The demo `.py` files contain comments only.

| Endpoint | Behavior |
| --- | --- |
| `GET /health` | Health and operator execution configuration (false by default); not a sandbox qualification |
| `POST /api/validate` | Exactly two multipart files, `task_zip` and `submissions_zip`; 200 summary, 400 invalid upload, 413 size limit, 415 wrong media type, 503 unavailable workspace |
| `POST /api/judge` | 503 when disabled/busy; with explicit setup, two validated ZIPs produce typed completed/incomplete verdict batches; see [judging.md](judging.md) |
| `POST /api/reports/pdf` or `/xlsx` | Typed current BatchResult JSON, including ordered test_ids; bounded in-memory attachment, 422 invalid result, 413 size limit, 503 busy/failure. GET returns 405; no stored reports |
| `GET /docs` | Local OpenAPI documentation |

Errors have only `code` and `message`. Invalid global archives are upload errors with no contestant verdict or accusation. The [archive contract](archive-contracts.md) defines accepted filenames and limits.

```bash
uv run --frozen pytest -q tests/test_archives.py tests/test_api.py
uv run --frozen pytest -q tests/test_ui.py
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

The default tests use inert in-memory archives and mocked workers. API checks use in-process TestClient; Streamlit AppTest checks validation/judging/results/export/error states with mocked HTTP responses. Report tests inspect independently parsed PDF/XLSX files, deterministic output, formulas/links, limits and the maximum 10,000 test rows. These unit checks are distinct from actual browser and sandbox evidence. The optional [offline browser harness](verdicts-and-reporting.md#safe-verification-and-offline-mode) runs real local services with a fixed mocked worker. Restricted agent environments may require permission for TestClient's cross-thread event-loop sockets.

## Optional AI challenge authoring — CCA-005–008

Configure provider slots/credentials only on the API process using [model configuration](model-configuration.md), then choose **AI task draft** in the Streamlit Workspace sidebar. The judge screen does not invoke models. There is no default model choice, automatic retry, provider fallback, model discovery/download or automatic `.env` loading. Missing cloud credentials disable cloud choices. Credentials never enter the UI or worker.

Follow the [teacher workflow](authoring-workflow.md#streamlit-teacher-workflow): select model, topic/difficulty/instructions, generate, inspect public/private content and warnings, request bounded changes or explicitly approve/reject. Reference checks default off and require both operator flags plus fresh worker qualification. Approval leaves correctness unverified; independent teacher review is still required. Approved drafts offer separate [student/teacher ZIP downloads](challenge-packages.md); keep the latter private. After an uncertain HTTP response in the same connected session, use Refresh draft. Drafts and checkpoints are deleted when leaving the authoring workspace or when Streamlit detects the browser connection has closed (including page navigation, reload and browser/tab closure); new sessions start empty. There is no recovery ID/resume UI. Streamlit session retention is disabled with `server.disconnectedSessionTTL = 0`. A one-hour maximum/API restart still bounds backend state; already downloaded files remain on the teacher's device. There is no durable database or public account/sharing system.

Safe focused tests and the optional fixed-mock browser harness:

```bash
uv run --frozen pytest -q tests/test_workflow_api.py tests/test_authoring_workflow.py tests/test_authoring_ui.py tests/test_package_api.py
uv run --frozen python scripts/verify_authoring_ui.py --output .runtime/cca008-verification
```

The harness needs separately installed Node/Playwright/Chromium; it starts real loopback UI/API services with a fixed model mock and disabled worker. No live/paid call occurs. See [verification evidence](releases/release-0.2-ai-challenge-authoring/verification.md) for results and limits. A real model smoke requires separate approval; the shipped feature is not proof of model availability or challenge correctness.

## Docker deployment — CCA-009

The root `compose.yaml` builds Streamlit and FastAPI using the exact Python 3.12.13 / uv 0.11.29 image digests and existing lockfile. It uses separate non-root, read-only containers with bounded CPU/memory/processes and temporary scratch storage. The worker-specific build context is unchanged. The application Dockerfile has its own allowlist so `.env`, `.git`, uploads, runtime artifacts and local virtual environments never enter the build context/image.

From the repository root, create `.env` from `.env.example` only if it does not already exist; retain existing provider credentials/settings. Unlike native Python startup, **Docker Compose reads the root `.env` for interpolation**. Only explicitly listed provider settings/keys go to API; web receives only its internal API port. No model request occurs during startup or catalog/health lookup.

```bash
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

Open <http://127.0.0.1:8501>. `APP_PORT` and `API_PORT` in `.env` change the two published host ports; container ports remain 8501/8000. Both published ports bind only to `127.0.0.1`. Web shares API's Docker network namespace (`network_mode: service:api`) so the existing UI always calls `127.0.0.1:8000`; their filesystems, process namespaces and environment remain separate. Port mappings therefore appear on the API container. Compose manages both services together.

**Default mode intentionally returns `execution_enabled: false`.** Validation, authoring/catalog/review and packaging work without a Docker socket. Run solutions is refused; requested reference checks remain blocked. This default cannot execute a submission even if the root `.env` contains judge flags. The explicit judge override below is required. No Docker-in-Docker daemon or worker network server is added.

To stop/restart default mode:

```bash
docker compose stop
docker compose up -d --wait
```

Uploads/reports/checkpoints are temporary; API restart loses process-local authoring checkpoints. No application data volume/database is added. Images and the root `.env` remain. Model availability and challenge correctness still require their own checks.

### Explicit judge-enabled mode

Read [worker prerequisites](judge-worker.md) and the [concrete reviewed worker profile](worker-security-review.md). **The trusted API coordinator needs Docker administration access through the local Unix socket.** `compose.judge.yaml` grants that access only to API, using the socket's actual group ID. This is broad daemon/host control, not a narrowly scoped worker-only permission. Enable it only for the trusted local operator deployment with explicit approval. Web and every code-executing worker receive no socket or model credentials.

Build/qualify the worker before enabling execution:

```bash
docker compose -f deploy/worker/compose.yaml build judge-worker
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml run --rm --no-deps judge-worker --verify
stat -c '%g' /var/run/docker.sock
```

Set `DOCKER_GID` in the ignored root `.env` to the last command's number. After reviewing and approving the trusted API socket exposure:

```bash
docker compose -f compose.yaml -f compose.judge.yaml config --quiet
docker compose -f compose.yaml -f compose.judge.yaml up -d --build --wait
```

Use this same file pair for subsequent updates/restarts. The override selects the `judge-api` image target with a digest-pinned Docker CLI 29.6.1 and the exact reviewed seccomp profile at the installed package's fixed lookup path; no application-source change or user-supplied profile/command is introduced. No host checkout/uploads are mounted. The socket bind refuses to create a missing host path. `/health` reports the operator flags, **not qualification**. Every program/test still creates a fresh Linux worker with no network, host mounts, socket or model environment and must pass all real NsJail startup checks in that process. The API never imports/executes contestant/reference source. Failed qualification/cleanup stops execution; no host or plain-container fallback exists.

The current local judge-enabled startup is **awaiting explicit approval**: automatic approval review rejected the API socket exposure. The optional image builds and worker qualification pass; an API-container-to-worker execution result is not yet claimed. See [CCA-009](releases/release-0.2-ai-challenge-authoring/stories/CCA-009-local-docker-deployment.md) and [observed evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

### Operator verification

```bash
uv run --frozen python scripts/verify_docker_app.py
# Only after approved judge mode and real worker qualification:
uv run --frozen python scripts/verify_docker_app.py --reviewed-profile
```

This optional operator script uses fixed benign CCA-003 fixtures and a loopback API only. Without the explicit flag it never submits executable fixtures to an enabled judge. In default mode it checks health, catalog, valid/invalid archives and the expected 503 execution-disabled response. In enabled mode it checks observed AC/WA/TLE/RE, objective DQ/REVIEW and PDF/XLSX exports through the actual running API. It never calls a model or runs program source on the host. It is not run by pytest/CI.

Docker/uv references: [Compose networking](https://docs.docker.com/compose/how-tos/networking/), [Dockerfile-specific context allowlists](https://docs.docker.com/build/concepts/context/#dockerignore-files), [uv multi-stage locked installs](https://docs.astral.sh/uv/guides/integration/docker/).
