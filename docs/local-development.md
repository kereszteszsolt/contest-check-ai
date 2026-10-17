# CCA-001 local development

Python **3.12.13**, `uv`, and a local Linux environment are used for the verified setup. `.python-version` selects the interpreter; direct dependencies are pinned and `uv.lock` records transitive versions and hashes. Dependency download happens during installation only. The application performs no package downloads, model calls or contestant execution.

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

Open <http://127.0.0.1:8501>. The UI calls the local API on port 8000. Streamlit binds to loopback, limits each file upload to 10 MiB and disables usage telemetry through `.streamlit/config.toml`. `.env.example` documents later configuration; CCA-001 does not load `.env`. Execution is hard-disabled even if `JUDGE_EXECUTION_ENABLED=true` exists in the environment.

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
| `GET /health` | Health and `execution_enabled: false` |
| `POST /api/validate` | Exactly two multipart files, `task_zip` and `submissions_zip`; 200 summary, 400 invalid upload, 413 size limit, 415 wrong media type, 503 unavailable workspace |
| `POST /api/judge` | Always 503 `execution_disabled` |
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

## Docker layout — design only

CCA-001 intentionally supplies no Dockerfile, Compose service or runnable worker. A later container layout should keep these boundaries:

| Service | Responsibility and permitted access |
| --- | --- |
| `web` | Streamlit presentation; connects only to the internal API; no worker executable or model credentials |
| `api` | Archive validation and coordination; bounded private temporary filesystem; no contestant execution |
| `judge-worker` | Future separately verified Linux sandbox worker; no internet, secrets, Docker socket, or unrelated application/system files; narrow isolated input/output only |

Use separate writable temporary filesystems with quotas, unprivileged users and no shared upload root with the web process. Bind local ports to loopback. A dedicated temp filesystem also discards artifacts on container teardown. A plain container does not establish safe execution: CCA-002 must prove isolation and negative tests on the real host before any worker is enabled. There is no `docker compose up` command for this story.
