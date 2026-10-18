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

Open <http://127.0.0.1:8501>. The UI calls the local API on port 8000. Streamlit binds to loopback, limits each file upload to 10 MiB and disables usage telemetry through `.streamlit/config.toml`. The app does not load `.env`. API judging is disabled by default; setting only `JUDGE_EXECUTION_ENABLED=true` is insufficient. Follow [judging.md](judging.md) to build/qualify the worker and explicitly configure both operator settings. After validation, the UI enables Run solutions; an unconfigured API refuses judging with a clear error. Review results, select Prepare PDF and XLSX and download the reports. The [UI/export contract](verdicts-and-reporting.md) explains state resets, N/A metrics and limits.

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

Follow the [teacher workflow](authoring-workflow.md#streamlit-teacher-workflow): select model, topic/difficulty/instructions, generate, inspect public/private content and warnings, request bounded changes or explicitly approve/reject. Reference checks default off and require both operator flags plus fresh worker qualification. Approval leaves correctness unverified; independent teacher review is still required. Approved drafts offer separate [student/teacher ZIP downloads](challenge-packages.md); keep the latter private. After a lost response use Refresh workflow, or reconnect by private workflow ID in a fresh browser session. Checkpoints expire after one hour and disappear on API restart. There is no durable database or public account/sharing system.

Safe focused tests and the optional fixed-mock browser harness:

```bash
uv run --frozen pytest -q tests/test_workflow_api.py tests/test_authoring_workflow.py tests/test_authoring_ui.py tests/test_package_api.py
uv run --frozen python scripts/verify_authoring_ui.py --output .runtime/cca008-verification
```

The harness needs separately installed Node/Playwright/Chromium; it starts real loopback UI/API services with a fixed model mock and disabled worker. No live/paid call occurs. See [verification evidence](releases/release-0.2-ai-challenge-authoring/verification.md) for results and limits. A real model smoke requires separate approval; the shipped feature is not proof of model availability or challenge correctness.

## Docker layout (worker only)

CCA-002 adds a separately deployed worker and scoped Docker files under `deploy/worker/`; see [the worker guide](judge-worker.md). Only the worker is a Compose service. Streamlit/API run natively with the commands above; no web/API containers or daemon-socket mounts are supplied. The service boundaries are:

| Service | Responsibility and permitted access |
| --- | --- |
| `web` | Streamlit presentation; connects only to the internal API; no worker executable or model credentials |
| `api` | Archive validation and coordination; bounded private temporary filesystem; no contestant execution |
| `judge-worker` | Implemented one-shot worker with mandatory real NsJail qualification; no internet, secrets, Docker socket or unrelated application files; explicit isolated runtime/input/output only |

The worker uses a private bounded tmpfs, non-root user, read-only root, no network and no shared upload root with the web process. Every worker process qualifies the actual jail before accepting a program; the recorded host passed the isolation/negative checks. A plain container is never an execution fallback. The native trusted coordinator uses a fixed local Docker CLI command; it does not execute a solution itself or mount the daemon socket into workers. The startup commands above leave judging disabled by default; explicit worker/API setup is documented in [judging.md](judging.md). Never make a failed qualification green with privileged mode, broad syscall overrides or public worker ports. Normal upload/runtime workspaces are cleaned automatically; report creation is capped and memory-only.
