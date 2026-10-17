# Local development — validation and Python judging

Python **3.12.13**, `uv`, and a local Linux environment are used for the verified setup. `.python-version` selects the interpreter; direct dependencies are pinned and `uv.lock` records transitive versions and hashes. Dependency download happens during installation only. The application performs no runtime package downloads or model calls. Uploaded programs execute only in separately qualified offline workers.

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

Open <http://127.0.0.1:8501>. The UI calls the local API on port 8000. Streamlit binds to loopback, limits each file upload to 10 MiB and disables usage telemetry through `.streamlit/config.toml`. The app does not load `.env`. API judging is disabled by default; setting only `JUDGE_EXECUTION_ENABLED=true` is insufficient. Follow [judging.md](judging.md) to build/qualify the worker and explicitly configure both operator settings. The Streamlit Run button remains disabled pending CCA-004.

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
| `GET /api/reports/pdf` or `/xlsx` | Always 501 `reports_unavailable`; placeholder contract only |
| `GET /docs` | Local OpenAPI documentation |

Errors have only `code` and `message`. Invalid global archives are upload errors with no contestant verdict or accusation. The [archive contract](archive-contracts.md) defines accepted filenames and limits.

```bash
uv run --frozen pytest -q tests/test_archives.py tests/test_api.py
uv run --frozen pytest -q tests/test_ui.py
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

The tests use inert in-memory archives. API checks use Starlette's in-process TestClient; Streamlit AppTest checks startup and validation/error states with mocked uploads and HTTP responses. Neither constitutes browser-driven upload evidence or sandbox verification. Restricted agent environments may require permission for Python's cross-thread event-loop sockets even for TestClient.

## Docker layout

CCA-002 adds a separately deployed worker and scoped Docker files under `deploy/worker/`; see [the worker guide](judge-worker.md). Web/API containerization and Streamlit-triggered judging remain future work. The service boundaries are:

| Service | Responsibility and permitted access |
| --- | --- |
| `web` | Streamlit presentation; connects only to the internal API; no worker executable or model credentials |
| `api` | Archive validation and coordination; bounded private temporary filesystem; no contestant execution |
| `judge-worker` | Implemented one-shot worker with mandatory real NsJail qualification; no internet, secrets, Docker socket or unrelated application files; explicit isolated runtime/input/output only |

The worker uses a private bounded tmpfs, non-root user, read-only root, no network and no shared upload root with the web process. Every worker process qualifies the actual jail before accepting a program; the recorded host passed the isolation/negative checks. A plain container is never an execution fallback. The native trusted coordinator uses a fixed local Docker CLI command; it does not execute a solution itself or mount the daemon socket into workers. The startup commands above remain validation-only by default; API judging is an explicit separate setup documented in [judging.md](judging.md).
