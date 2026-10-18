# Release 0.2 verification

**Status: CCA-009 Docker deployment is in progress with socket approval pending; CCA-005–008 implemented and locally verified with mocked providers/workers and synthetic artifacts/teacher decisions.** Actual graph approval/resume, Streamlit API integration, separate ZIP/PDF exports and fresh-browser-session checkpoint recovery are exercised. The teacher ZIP passes judge validation. Hungarian sample PDFs were parsed, rendered and visually inspected by Codex. No live model, generated-reference execution, independent teacher correctness review, hosted CI or public deployment is claimed. Historical sections below describe the scope at their respective story boundaries; CCA-008 supersedes earlier planned-UI status.

| Story | State | Mock/Pydantic tests | Approved model / sandbox / HITL | Notes |
| --- | --- | --- | --- | --- |
| CCA-005 | Implemented | 78 focused checks; 408 full-suite tests; lint/format passed | Live model / generated-code sandbox / HITL Not run | Actual LangChain/SDK serialization and parsing over mocked HTTP; API/AppTest mocks |
| CCA-006 | Implemented | 72 new checks; 150 focused authoring checks; 480 full-suite tests; lint/format passed | Actual graph/checkpoint/approve-revise-reject with synthetic decisions; live model/reference/manual teacher smoke Not run | Strict state, fixed tools, bounded call ledgers, private local API |
| CCA-007 | Implemented | 42 new checks; 173 focused checks; 522 full-suite tests; lint/format passed | Mocked graph/API decisions; real ZIP/PDF parsing and Codex visual PDF inspection; live reference Not run | Separate public/private projections, fixed starter, direct teacher-ZIP judge ingestion |
| CCA-008 | Implemented | 80 focused checks; 542 full-suite tests; lint/format passed | Actual UI/API/graph, synthetic browser approve/revise/reject and resume; live provider/reference/manual independent review Not run | Lost-response recovery, checkpoint-bound controls, bounded creation ledger, separate audience-validated downloads |
| CCA-009 | In progress | Docker build, health/API/browser/ZIP smoke passed; 38 real worker checks | Default UI/API active without socket; integrated judge activation awaits explicit permission | Automatic review rejected broad API Docker-socket access; no bypass |

## Evidence instructions

Record exact test commands, model IDs **actually** used (if any), whether Ollama/OpenRouter was real or mocked, output validation outcomes, sandbox host capability proof and observed approve/revise/reject behavior. Billable OpenRouter smoke tests require separate approval. An AI-generated reference passing generated tests is not independent proof of challenge correctness.

## 2026-10-17 — CCA-005 configured Ollama/OpenRouter providers

Authorization: the user requested continuing with CCA-005. Only this story was implemented. Implementation and verification ended without a commit; the user subsequently gave separate approval to commit the reviewed changes. No live Ollama/OpenRouter smoke, paid/model call, generated-code execution or push was performed.

### Scope and environment

The backend loads up to three distinct non-empty slots per provider, exposes a sanitized catalog and resolves only those slots. Missing cloud credentials/invalid provider URLs hide affected choices with safe UI issues. Invalid numeric limits disable all models. Dynamic OpenRouter routes/search variants and Ollama cloud variants are rejected. No discovery or model download occurs.

The Streamlit Workspace selector preserves the existing judge screen and adds explicit model selection, teacher instructions, a cloud cost/data-transfer notice and one-call unverified draft preview. The selection starts empty. New selection/instructions/configuration clear old drafts. Strict Pydantic output includes public examples, starter/candidate reference source, private tests and warnings, with manifest-compatible filenames/limits. Drafts are explicitly `approved: false`, `executed: false`; no approval/export or LangGraph flow was added.

Adapter transport permits only a non-streaming POST to the selected endpoint, with no redirect/proxy, tool/plugin, tracing, model/provider fallback, response repair or retry. The shared generation-session budget counts actual attempts, including failures. Input is capped at 8,000 characters, API bodies at 64 KiB, wire responses at 256 KiB, drafts at 128 KiB, output at 256–8,192 tokens and absolute per-call time at 1–120 seconds. The current route makes one call; later orchestration can reuse the same 1–6-call session. Privacy boundaries and exact error codes are in [model configuration](../../model-configuration.md).

Environment: branch `dev_r0.2`, Linux/WSL2 x86-64, CPython **3.12.13**, uv **0.11.29**, pytest **9.1.1**, Ruff **0.17.1**, using `/tmp/cca001-venv`, `/tmp/cca001-python` and `/tmp/cca001-uv-cache`. At entry, 90 tracked files already differed only in CRLF line endings: `git diff --ignore-cr-at-eol --stat` was empty. Their starting byte hashes were saved in `/tmp/cca005-baseline.json`; pre-existing changes were retained, with CRLF preserved in edited existing files. No unrelated normalization/reset was performed.

### Dependencies and exact commands

```bash
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --bounds exact langchain-ollama langchain-openrouter
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv add --offline --bounds exact langchain-core langsmith
UV_CACHE_DIR=/tmp/cca001-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca001-python UV_PROJECT_ENVIRONMENT=/tmp/cca001-venv uv sync --locked --offline
```

Observed: LangChain core **1.6.12**, Ollama integration **1.1.0**, OpenRouter integration **0.2.9**, LangSmith **0.14.11**. Resolved SDKs: Ollama **0.6.3**, OpenRouter **0.10.8**. Final offline sync resolved **79 packages** and checked **76 installed packages**. A `tomllib` comparison against `HEAD:uv.lock` confirmed every existing package version unchanged; only new package/marker entries were added. The worker dependency group/requirements are unchanged. Development package installation used authorized network access; it made no model call.

Installed distribution metadata/license files for the 22 new Linux packages were inspected, including the orjson **MPL-2.0 AND (Apache-2.0 OR MIT)** expression and all three retained license texts. The Emscripten-only `httpx2-jsfetch==1.0` lock entry is not installed; its installed notices were not reviewed. [License inventory](../../dependency-licenses.md) records all versions/notices and the unsupported WASM boundary. No dependency is vendored/modified and no image is published. ContestCheck's own source remains Apache-2.0.

Primary docs consulted: [LangChain Ollama](https://docs.langchain.com/oss/python/integrations/chat/ollama), [LangChain OpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter), [OpenRouter structured output](https://openrouter.ai/docs/guides/features/structured-outputs), [routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Ollama chat](https://docs.ollama.com/api/chat). Pinned installed SDK source was inspected for endpoint behavior, client ownership, environment credentials, debug logging and retries. Explicit SDK `retry_config=None` and request `retries=None` are necessary in addition to wrapper `max_retries=0`. Ollama's inherited `OLLAMA_API_KEY` is removed before network transmission; tracing/debug output is disabled explicitly.

### Mocked verification

```bash
timeout 60s /tmp/cca001-venv/bin/pytest -q tests/test_providers.py -o faulthandler_timeout=15
/tmp/cca001-venv/bin/pytest -q tests/test_providers.py -k 'roundtrip or shared_session'
timeout 60s /tmp/cca001-venv/bin/pytest -q tests/test_providers.py tests/test_authoring_api.py tests/test_authoring_ui.py -o faulthandler_timeout=15
timeout 60s /tmp/cca001-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca001-venv/bin/ruff check .
/tmp/cca001-venv/bin/ruff format --check .
```

Final focused result: **78 passed in 3.29s**. Final full result: **408 passed in 24.52s**, no pytest warnings reported. Ruff: **All checks passed**; formatting: **74 files already formatted**. The earlier full run before the final unfinished-response cases passed **406 tests in 25.99s**. TestClient/AppTest checks used authorized execution because of the existing restricted cross-thread socket constraint; no model/judge permission was relaxed.

The provider tests exercise the actual pinned LangChain/SDK request serialization and response parsing through `httpx.MockTransport`. Model labels `fixture:1` and `test/fixture` are synthetic identifiers, **not downloaded or contacted models**. The sample starter/reference files contain inert comments and are never imported/executed. Checked cases include:

- Valid shared draft/schema for both providers; exact endpoint/model, JSON schema, token caps, no tools/plugins, no provider fallback and no ambient Ollama key in the request.
- Blank/duplicate/invalid slots, missing cloud key, invalid endpoint/limit settings, unknown selections and rejected arbitrary model/URL/key/upload fields.
- Malformed/fenced/duplicate-key/extra-field, truncated/unfinished and oversized outputs; actual response-stream bounds/closure, including compressed responses.
- Timeout/cancellation, connection failures, authentication/rate/server errors and redirects, each with one attempt; shared session-budget exhaustion without another outbound call.
- Inherited `LANGSMITH_TRACING`/`LANGCHAIN_TRACING_V2`/`OPENROUTER_DEBUG` enabled in a test, while external tracing creation/update are forbidden and no provider debug body is logged.
- Safe API error/response contracts, no-store success responses, body limits with missing/dishonest Content-Length, occupied generation slot and release after error.
- AppTest empty initial selection, explicit cloud cost notice, draft preview, stale-draft clearing and missing-key/offline error states. UI requests contain only the selected slot and teacher instructions.

No actual provider response, served model version, charge, performance result or algorithm-correctness claim is recorded. AppTest is **not browser-driven evidence**. Default judge/report tests continue to pass without contacting a model or executing generated/contestant programs.

The existing CI workflow still runs locked install/lint/format/mocked pytest only; explicit disabled tracing/empty Ollama-key settings were added. YAML syntax and expected execution/key/tracing settings were checked with PyYAML 6.0.3 using `yaml.BaseLoader`. This validates local syntax/settings, not hosted GitHub Actions execution.

### Corrected failures and Not run

- Initial Ruff findings were import ordering, line length and compact test formatting; corrected before final lint/format checks.
- First provider-only run: **47 passed, 2 failed**. A direct fixed-fixture adapter diagnostic showed the pinned OpenRouter SDK requires `system_fingerprint`; the fixture now includes its nullable field. A focused roundtrip/budget rerun passed **4 tests**. The bounded response also preserves the content-type header for SDK parsing; no parser or security requirement was relaxed.
- First combined provider/API/UI run: **61 passed, 1 failed, 2 setup errors**. The mocked catalog responses lacked the HTTPX Request required by `raise_for_status()`. Added the fixed loopback request to test fixtures; the expanded suite then passed **76 tests in 3.19s**. Final unfinished-output cases bring it to 78.
- The initial dependency-notice script assumed every conditional lock entry was installed and stopped at `httpx2-jsfetch`. It now records the Emscripten-only/uninstalled entry separately; Linux-installed notices were reviewed.

Final review: a standard-library audit confirmed **18 edited existing files**, **7 new Python files with exact SPDX headers**, **72 pre-existing files preserved byte-for-byte**, **78 resolving local Markdown links**, no credential-pattern matches and no extra runtime artifacts. Existing edited files retain CRLF. `git -c core.whitespace=cr-at-eol diff --ignore-cr-at-eol --check` exited **0**. The whole-tree check without ignoring CRLF reported the pre-existing two-space Markdown hard breaks in untouched `docs/github-metadata.md:3–4`; they were preserved. At the end of implementation review the Git index was empty and no commit had been made. Before the separately approved commit, the 25-file scope and 72 untouched baseline files were verified again. Only the story's 25 paths were staged with command-scoped `core.autocrlf=input`, retaining the repository's existing LF blobs and excluding unrelated CRLF-only changes; working-tree file bytes were preserved.

**Not run:** live Ollama or OpenRouter smoke/model compatibility, provider billing or output quality, browser-driven CCA-005 UI checks/screenshots, LangGraph/tool/checkpoint workflow, candidate-reference execution, teacher approve/revise/reject behavior, student/teacher ZIP export, new Docker builds or real sandbox qualification, public deployment, hosted CI, other OS/architectures/WASM, independent security/legal audit. Existing Release 0.1 sandbox evidence remains historical and separate; this story does not alter worker isolation or prove any new execution environment safe.


## 2026-10-18 — CCA-006 bounded LangGraph and reference tools

Authorization: the user explicitly requested continuing implementation with CCA-006. The story scope, risks and mocked verification were summarized before implementation; this request supplied implementation approval. No other story was started. Implementation ended without a commit; the user subsequently gave separate approval to commit the reviewed CCA-006 changes. No push, live provider request or generated/contestant-code execution was performed.

### Implemented scope and environment

A Pydantic `WorkflowState` drives the actual LangGraph sequence: generate, validate draft, check reference, prepare preview, teacher interrupt. Safe provider errors produce a reviewable pause without automatic retry. Explicit approve/revise/reject resumes the current checkpoint; revisions carry bounded teacher feedback and the prior draft to the same selected provider. Approval remains `verification: unverified` and enables neither packaging nor official test acceptance.

The two fixed tools revalidate the strict draft and, only on explicit reference opt-in, send the candidate through the existing worker protocol. Public/private results reuse existing verdict comparison, report observed mismatches and resource hints, cap observed output previews, and halt on worker infrastructure/protocol failure. Expected outputs never enter worker requests. Missing operator configuration blocks execution; every real worker still qualifies its own sandbox. Neither the transport, worker sources/profile nor worker dependencies changed.

Budgets are cumulative across teacher revisions: at most three generation attempts, the configured one-to-six model-call allowance, six tool invocations and twenty worker cases. Unrun tests are counted. Actual LangGraph interrupts/checkpoints are exercised with synthetic teacher decisions. Review IDs bind decisions to the current preview; duplicate/stale/concurrent resumes do not repeat model/worker effects. Unexpected checkpoint failure invalidates the session rather than replaying an uncertain effect. The local API adds create/preview/review/delete, bounded bodies, fixed errors, no-store responses, shared model/judge admission, and at most eight in-memory workflows with one-hour expiry. Process restart loses this storage; it is not durable crash recovery. The CCA-005 Streamlit flow retains its one-call behavior.

Environment: clean starting worktree/index on branch `dev_r0.2`, HEAD `3d8b469`, Linux **6.6.87.2-microsoft-standard-WSL2**, x86-64, CPython **3.12.13**, uv **0.11.29**, pytest **9.1.1**, Ruff **0.17.1**. The host default Python is 3.14.4, so a separate required Python 3.12 environment was created at `/tmp/cca006-venv`, with `/tmp/cca006-python` and `/tmp/cca006-uv-cache`. Dependencies were downloaded during development only; no model was contacted.

### Dependency commands and review

```bash
UV_CACHE_DIR=/tmp/cca006-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca006-python UV_PROJECT_ENVIRONMENT=/tmp/cca006-venv uv add --bounds exact langgraph
UV_CACHE_DIR=/tmp/cca006-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca006-python UV_PROJECT_ENVIRONMENT=/tmp/cca006-venv uv sync --locked --offline --group dev
UV_CACHE_DIR=/tmp/cca006-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca006-python UV_PROJECT_ENVIRONMENT=/tmp/cca006-venv uv sync --locked --group dev
UV_CACHE_DIR=/tmp/cca006-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca006-python UV_PROJECT_ENVIRONMENT=/tmp/cca006-venv uv sync --locked --offline --group dev
```

The first add required authorized network access after the restricted attempt failed DNS resolution while downloading Python. The first offline dev sync could not find the pinned Ruff wheel in the fresh cache; the authorized online dev sync populated it. Final offline locked sync resolved **84 packages**, checked **81 packages** and exited 0.

New locked components: **langgraph 1.2.16**, **langgraph-checkpoint 4.3.0**, **langgraph-prebuilt 1.1.1**, **langgraph-sdk 0.4.8**, **ormsgpack 1.13.0**. A `tomllib` comparison against `git show HEAD:uv.lock` found exactly these five additions and one required version change: **websockets 17.2 to 16.1.1**, because installed SDK metadata requires `websockets>=14,<17`. All other existing locked versions, dependency groups and worker requirements/transport are unchanged. Installed metadata and retained license files were inspected; exact component notices and the downgrade are recorded in [license inventory](../../dependency-licenses.md). No dependency was vendored/modified or image published.

Primary technology references: [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), and the installed pinned graph/checkpoint serializer source. Checkpoint pickle fallback and arbitrary MessagePack class restoration are disabled; application checkpoint values are JSON data. Tracing is disabled around the entire graph even when inherited tracing variables are enabled.

### Exact mocked verification commands and results

```bash
timeout 60s /tmp/cca006-venv/bin/pytest -q tests/test_authoring_tools.py tests/test_authoring_workflow.py -o faulthandler_timeout=15
timeout 60s /tmp/cca006-venv/bin/pytest -q tests/test_authoring_tools.py tests/test_authoring_workflow.py tests/test_workflow_api.py tests/test_providers.py tests/test_authoring_api.py tests/test_authoring_ui.py -o faulthandler_timeout=15
timeout 60s /tmp/cca006-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca006-venv/bin/ruff check .
/tmp/cca006-venv/bin/ruff format --check .
```

Final authoring result: **150 passed in 4.24s**, including **72 new checks** over the CCA-005 baseline. Final full result: **480 passed in 24.79s**, no pytest warnings. Ruff: **All checks passed**; formatting: **81 files already formatted**. The preceding full run passed 480 in 26.28s; the final run also verifies the no-store middleware addition for authoring errors and successful responses.

The first restricted run completed the 22 initial tool tests but hung during the first graph's cross-thread asyncio wakeup; faulthandler reported the event loop waiting in `selectors.select`, and the external deadline exited **124**. The same tests were run with authorized host execution, preserving all model/worker mocks: **37 passed in 1.20s**, with one intentional malformed-model serialization warning. That test now explicitly captures its expected warning. Subsequent expanded runs passed **146 in 5.35s**, then **150 in 4.54s**. No execution/isolation requirement was relaxed to pass tests. Initial Ruff findings were import ordering and long lines; corrected before final checks.

Coverage includes:

- Actual StateGraph transitions, Pydantic state/progress checks, stored interrupt payload/response schema, checkpoint inspection, and terminal approval/rejection.
- Explicit revision with prior draft/context, fresh review IDs, retained error history, model/tool/worker budgets across revisions, and lower operator call budgets.
- Model timeout, malformed/oversized output and credential errors with no automatic retry or invalid-draft approval; real adapter/SDK serialization of workflow context over mocked HTTP for both providers.
- Reference pass/mismatch, wall timeout, ambiguous memory/output resource hints, crashes, missing/unqualified worker, malformed responses/metrics, safe failure without fallback, public/private ordering and bounded observed output.
- Strict unsafe filename/path refusal, nested draft mutation, invalid run budgets and malformed requests/state; expected outputs absent from worker protocol payloads.
- Duplicate/stale/terminal/concurrent review decisions, checkpoint-write failure after a model effect, preview mutation isolation, capacity, expiry and checkpoint deletion.
- Disabled inherited LangSmith tracing and no backend key in checkpoints; safe API errors, no-store headers, honest/dishonest/missing Content-Length handling and shared admission slots.
- Existing provider/API/AppTest and Release 0.1 ingestion/judge/report regressions.

All generated-source fixtures are inert comments and are never imported or executed. Worker outputs are synthetic metadata, not proof of a reference algorithm or real sandbox behavior. The actual graph/interrupt protocol is exercised; teacher actions in tests are synthetic, not a manual human review session. The current Streamlit UI is unchanged and no new UI/browser evidence is claimed.

### Review and limitations

The diff was reviewed against the approved story, including generated-code and private-test boundaries, shared budget retention, resume effects, dependency/version changes and compatibility with the existing preview. Existing CRLF/LF styles are retained; new handwritten Python source/tests have the exact required SPDX lines. No worker permissions, sandbox profile, official verdicts, CI runtime execution or unrelated staged work were changed. Final audit confirmed 15 edited tracked paths, 7 new paths, exact SPDX headers in all 6 new Python source/test files, 75 resolving local Markdown links and preserved CRLF in 12 edited existing files. The credential-pattern check found no matches. `git -c core.whitespace=cr-at-eol diff --check` exited 0. The implementation review ended with an empty index. After separate user commit approval, the 22-path scope, SPDX headers, worktree credential-pattern audit, lint and formatting were checked again before staging. Only these intended paths are included in the commit; no push is authorized.

**Not run:** live Ollama/OpenRouter or paid calls, real generated-reference execution, new Docker builds/sandbox qualification, manual teacher/model/sandbox smoke, independent challenge/test correctness review, polished workflow/review UI, student/teacher artifact packaging/export, durable/multi-process checkpoint recovery, hosted CI, public deployment, other OS/architectures, independent security/legal audit. Historical Release 0.1 sandbox evidence remains separate and does not qualify a new process/host. CCA-007/008 remain Planned.


## 2026-10-18 — CCA-007 student and teacher packages

Authorization: the user requested continuing implementation with CCA-007. This supplied implementation approval after the story scope/risks were summarized. Only this story was implemented. Implementation ended without a commit; the user subsequently provided separate approval to commit the reviewed CCA-007 changes. No push, live model request or generated/contestant-code execution occurred.

### Scope and environment

The backend builds separate student/teacher ZIPs from a revalidated copy of the stored current approved workflow. Student output is an explicit public projection: statement/examples, resource/file-I/O constraints, public manifest, a fixed application-owned minimal starter and a printable PDF. Model-generated starter/reference code, private tests, warnings, prompts and check logs are excluded from public artifacts. Student bytes remain identical when only private source/warnings change. Approval is required but never changes correctness from `unverified`.

Teacher ZIPs contain the unchanged strict judge manifest and private test pairs, plus the exact `teacher/README.md` / `teacher/checks.json` metadata pair and an optional `teacher/reference/main.py` on explicit teacher review assertion. This narrow ingestion-layout extension lets the complete teacher ZIP pass the existing judge validation route directly. Extra metadata never affects qualification/verdicts and is never executed or sent to a worker. All shared path/type/duplicate/CRC/size/compression/nested-archive checks remain in force; the worker/transport and dependency pins are unchanged.

Reference evidence comes from existing workflow checks, including skipped/blocked/partial/not-run gaps. Export starts no worker/model call and does not infer independent correctness from generated reference/test agreement. The new local API refuses client-supplied drafts/approval/source/paths, rejects unapproved/rejected downloads, bounds option bodies, serializes exports, returns fixed safe errors and serves no-store ZIP attachments with an explicit unverified header. Existing teacher preview remains available for unapproved/rejected drafts. The Streamlit workflow/download UI and final independent verification remain CCA-008 scope.

PDFs render escaped plain text with packaged DejaVu Sans/Mono 2.37 fonts, Hungarian long accents, file/resource constraints, samples and explanations. Unsupported glyphs/control/bidi text fails explicitly. Limits: 1 MiB PDF, 60 pages, 2,400 rendered line units, and the shared archive/file/manifest limits. No remote image/font fetch, active PDF action/form/attachment, external template or temporary export workspace is added. Exact sample bytes are preserved separately from printable wrapping/tab expansion. ZIP_STORED, fixed timestamps/modes, stable JSON and invariant PDF output are deterministic in the pinned environment.

Environment: clean starting worktree on `dev_r0.2`, HEAD `2aaab75`, Linux/WSL2 x86-64, CPython 3.12.13, uv 0.11.29, pytest 9.1.1, Ruff 0.17.1; reused `/tmp/cca006-venv`, `/tmp/cca006-python` and `/tmp/cca006-uv-cache`. `pyproject.toml`, `uv.lock`, worker requirements/transport and sandbox profiles are unchanged. No application/test dependency was added.

### Exact automated checks

```bash
timeout 60s /tmp/cca006-venv/bin/pytest -q tests/test_challenge_packages.py tests/test_archives.py -o faulthandler_timeout=15
timeout 60s /tmp/cca006-venv/bin/pytest -q tests/test_package_api.py tests/test_workflow_api.py -o faulthandler_timeout=15
timeout 60s /tmp/cca006-venv/bin/pytest -q tests/test_challenge_packages.py tests/test_package_api.py tests/test_archives.py tests/test_workflow_api.py -o faulthandler_timeout=15
timeout 60s /tmp/cca006-venv/bin/pytest -q -o faulthandler_timeout=15
/tmp/cca006-venv/bin/ruff check .
/tmp/cca006-venv/bin/ruff format --check .
UV_CACHE_DIR=/tmp/cca006-uv-cache UV_PYTHON_INSTALL_DIR=/tmp/cca006-python uv build --offline --wheel --out-dir /tmp/cca007-dist
```

Final focused result: **173 passed in 3.05s**. Final full result: **522 passed in 24.61s**, including **42 new tests**, with no pytest warnings. The preceding expanded checks passed 172 in 3.12s / 521 in 25.09s and 172 in 2.96s / 521 in 25.27s. Earlier standalone archive/package checks passed **132 in 1.44s**; workflow/export API checks passed **40 in 2.49s**. TestClient/LangGraph checks used authorized host execution for the previously established restricted cross-thread asyncio limitation; all provider/worker calls stayed mocked. Ruff passed; final formatting check reports **87 files already formatted** (including supported Markdown code blocks).

Coverage includes exact public/private ZIP membership, unchanged student output under private-source/warning changes, fixed starter without model code, teacher-only reviewed-reference opt-in, exact/empty/Unicode/CRLF examples, deterministic bytes/timestamps/modes, public manifest/PDF parsing, Hungarian glyph extraction/embedded fonts, escaped HTML-like text and inactive PDF content, line/page/byte caps, maximum-length task-ID footer abbreviation with complete manifest ID, unsupported control/glyph handling, expected-output byte limits, unsafe paths/nested payloads/teacher metadata allowlists, judge-ready ingestion and extraction cleanup, approval/rejection/expiry/body/option/error/concurrency API boundaries, and no extra provider/worker calls during export.

An offline Python wheel was built successfully. A ZIP inspection of the final wheel compared the three new application modules, both TTF files and the notice byte-for-byte with current source; all matched. Font binaries match `/usr/share/fonts/truetype/dejavu/` originals from `fonts-dejavu-core 2.37-8build1`. The retained full applicable Bitstream Vera/public-domain DejaVu notice is packaged and copied into the student ZIP. Exact hashes/terms are recorded in [license inventory](../../dependency-licenses.md); no upstream font binary was modified and no unrelated Debian packaging code was copied.

### Rendered synthetic artifact inspection

A trusted fixture helper constructed the approved, explicitly unverified Hungarian task **Két szám összege**, with two public examples and inert comment-only starter/reference model fields. The actual fixed application starter was exported. Files were written only under `/tmp/cca007-artifacts/`; no new repository runtime artifacts were retained:

- `addition-student.zip`: **47,787 bytes**, nine members (two example pairs).
- `addition-teacher.zip`: **3,284 bytes**, six members including the explicitly requested inert reviewed-reference fixture.
- `problem.pdf`: **42,636 bytes**, **one A4 page**, SHA-256 `83e7cb6f8a48e9088048d422511bdda726103bf840b9d0a88333256cbfcc723a`.
- `problem-page-1.png`: rendered from that actual PDF using PDFium, opened with the image viewer and visually read through by Codex. Hungarian accents, statement/input constraints, file/resource limits, both sample I/O pairs, unverified notice and footer are readable; no clipping or private data was observed. This is Codex inspection of a synthetic PDF, not manual teacher correctness approval or browser/UI proof.

Temporary render tools were installed separately:

```bash
UV_CACHE_DIR=/tmp/cca006-uv-cache uv venv --python /tmp/cca006-venv/bin/python /tmp/cca007-pdf-review
UV_CACHE_DIR=/tmp/cca006-uv-cache uv pip install --python /tmp/cca007-pdf-review/bin/python pypdfium2==5.14.0 pillow==12.3.0
```

The fixture generation used `PYTHONPATH=tests:src /tmp/cca006-venv/bin/python` with the trusted `draft_data`/`approved_challenge` fixture factories and `build_challenge_package`; the two example inputs were `1 2` and `-5 3`, outputs `3` and `-2`. `/tmp/cca007-pdf-review/bin/python` rendered every PDF page with `document[index].render(scale=1.4)`. The template and fixture code are trusted application/test code; generated source was never imported/executed. PDFium/Pillow are external inspection tools, not added dependencies or shipped renderer code.

### Corrected failures and limits

- The initial package/archive run passed **129**, failed **1** because a PDF assertion expected the literal status `unverified` while the initial text said `not independently verified`. The PDF now prints explicit `Status: unverified` to match the manifest/header and avoid ambiguity.
- The first page-cap regression run passed **131**, failed **1**: ReportLab annotates exceptions by constructing another instance with a message, which is incompatible with the fixed-code `PackageError` constructor. The page hook now raises a compatible internal `PageLimit` and translates it to the fixed `package_size` at the document boundary. Both page and byte cap tests pass; no bound was relaxed.
- Initial Ruff findings were import order/long literal formatting; fixed before final checks. Missing Hungarian long-accent glyphs in ReportLab's bundled Vera font were observed before implementation, so supported packaged DejaVu fonts were chosen instead of silently substituting glyphs.
- The public/student manifest now uses the same 64 KiB manifest cap as the judge manifest. Expected outputs in both public/private tests must satisfy the declared byte bound. Unexpected export exceptions never echo source, key, path or PDF content.

The final diff is restricted to CCA-007 implementation/contracts, its tests/font notices and current status/evidence documentation. Final audit confirmed 12 edited tracked paths, 9 new paths, exact SPDX headers in 5 new Python source/test files, 90 resolving local Markdown links and preserved CRLF in 11 edited existing files. The worktree credential-pattern scan found no matches; the Git index is empty. `git -c core.whitespace=cr-at-eol diff HEAD --check` exited 0. Final wheel application/font/notice bytes match current sources, and upstream font binaries are unchanged. The implementation review ended without a commit. After separate user commit approval, the exact 21-path scope, SPDX/font notices, worktree credential-pattern scan, wheel/source equality, lint and formatting were checked again before staging. Only these intended paths are included in the approved commit; no push is authorized.

**Not run:** live Ollama/OpenRouter or billable calls, actual generated-reference/contestant execution, new sandbox qualification/Docker build, independent challenge correctness review, manual teacher UI/download flow, polished Streamlit authoring/review integration, complex-script shaping/universal Unicode, durable/multi-process workflow recovery, hosted CI/public deployment, independent security/legal audit. Existing Release 0.1 sandbox evidence remains historical and separate. CCA-008 remains Planned.

## 2026-10-18 — CCA-008 teacher approval UI and verification

Authorization: the user requested continuing implementation with CCA-008. This is implementation approval for this story only. The worktree was clean on `dev_r0.2` at `ea3c537` (CCA-007). No live provider/paid call, generated-source execution or push was authorized/performed. Implementation ended without a commit; the user subsequently gave separate approval to commit the reviewed CCA-008 changes.

### Implemented behavior and boundaries

Streamlit **AI task draft** now uses the actual workflow API: explicit configured model selection, topic/difficulty/instructions, loading/status, inert public/private previews, cumulative checks/warnings, bounded revision text and explicit approve/revise/reject. Current-checkpoint widget keys and review IDs prevent delayed old clicks from approving a revision; every new checkpoint resets its acknowledgment. The UI requires the teacher's review acknowledgment for approval and prominently keeps correctness **unverified**. Rejection provides no final packages. Reference checks default off, use only the existing qualified-worker path when enabled, and remain visibly skipped/blocked otherwise.

Creation stores a cryptographically random private workflow ID before POST using the optional typed `Idempotency-Key` header. Repeating an admitted identical request reads the stored checkpoint without another model call; changed payloads conflict. A bounded ledger retains up to 64 creation IDs, including failed/deleted entries, until one hour after creation. The existing active-workflow cap remains eight. These guarantees are process-local and expire; API restart loses them. Clients must not automatically repost missing workflows. The UI never retries generation/revision automatically: timeouts, malformed previews or unexpected IDs/models hide decisions/downloads until explicit GET refresh. A fresh browser session can resume by private workflow ID. Inputs stay fixed within the workflow.

Approved workflows offer separate student/teacher ZIP preparation and downloads; a separate default-off assertion includes an independently reviewed reference only in the teacher ZIP. The UI validates bounded response bytes, attachment/type, both audience layouts and the student manifest against the reviewed draft before offering either download. Reference-option changes, mutations, refresh and new workflows clear cached archives. Downloads use `on_click="ignore"` and do not call a provider/worker. The backend approval gate remains authoritative.

Untrusted instructions, statements, explanations, warnings and source display as `st.text`/`st.code`, never active Markdown/HTML or executable source. Negative tests include an external-image URL, script markup and an `os.system` source string, treated only as data. No filesystem/shell/GitHub/web tool, new execution path or permission bypass is introduced. Existing generation limits, two fixed graph checking tools, worker qualification and official judge verdicts retain their contracts. CI explicitly clears all six provider slots as well as credentials/worker flags and runs mocked pytest only. No runtime dependency or lockfile changed. README diagrams/dependency/deployment descriptions and teacher/setup/package documentation now match this shipped UI.

### Environment, commands and observed results

Linux/WSL2 `6.6.87.2-microsoft-standard-WSL2`, x86-64; CPython **3.12.13**, uv **0.11.29**, pytest **9.1.1**, Ruff **0.17.1**, Streamlit **1.66.0**, FastAPI **0.143.3**, LangGraph **1.2.16**. Existing pinned environment: `/tmp/cca006-venv`, `/tmp/cca006-python`, `/tmp/cca006-uv-cache`. TestClient/LangGraph tests used authorized host execution for the previously recorded restricted cross-thread event-loop limitation; provider/worker behavior remained mocked.

```bash
/tmp/cca006-venv/bin/pytest -q tests/test_workflow_api.py tests/test_authoring_workflow.py tests/test_authoring_ui.py tests/test_package_api.py
/tmp/cca006-venv/bin/pytest -q
/tmp/cca006-venv/bin/ruff check .
/tmp/cca006-venv/bin/ruff format --check .
/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node --check scripts/verify_authoring_ui.cjs
git -c core.whitespace=cr-at-eol diff HEAD --check
```

Final focused result: **80 passed in 9.22s**. Final full result: **542 passed in 30.46s**, a net increase of **20** over CCA-007's 522. No pytest warnings. Ruff passed; formatting reports **88 files already formatted**. JavaScript syntax and whitespace checks exited 0. The earlier complete run passed **536 in 29.04s** before the additional response/budget/stale-widget cases. Current UI-only checks also passed **16 in 7.62s**.

Tests exercise actual LangGraph interrupt/checkpoint/resume through FastAPI and Streamlit AppTest, with mocked generation/worker outputs: explicit/no-default selection, cloud cost notice, missing keys/catalog failure, approved/revised/rejected paths, exhausted budget, late prior-checkpoint approval events, lost creation/revision/approval responses followed by GET recovery without another call, malformed model/HTTP previews, wrong workflow/model responses, swapped teacher-as-student ZIP rejection, optional reference/download cache resets, and bounded proxy-free preview reads. API tests cover identical creation replay, conflicting payloads, invalid IDs, failed/deleted ID retirement and ledger capacity/expiry; existing tests cover stale/concurrent decisions and sandbox-only reference delegation.

Initial focused failures were incorrect test expectations for the existing `challenge/tests/` / `teacher/reference/` archive prefixes and explicit empty model selection after starting over. They were corrected without changing export behavior. The first stale-click test reused an obsolete AppTest element tree and failed on a removed checkbox key; the final test submits the old trigger ID alongside the current widget state. Initial lint found an unused import/long fixture line, corrected. All final checks above passed.

### Real local browser, ZIP/PDF and visual checks

The new operator-only `scripts/verify_authoring_ui.py` / `.cjs` harness starts the real loopback API and Streamlit, overrides generation with a fixed mock, disables the worker and refuses provider transport. It is outside pytest/CI. Verification tooling was installed only under `/tmp`: Playwright **1.61.1** with Node **24.18.0**, explicitly selecting the already installed Chromium **151.0.7922.34** and temporary Linux libraries. The application's dependencies are unchanged.

```bash
PATH=/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin:$PATH npm install --prefix /tmp/cca008-browser --no-audit --no-fund playwright@1.61.1
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu CCA_BROWSER_NODE=/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node CCA_PLAYWRIGHT_MODULE=/tmp/cca008-browser/node_modules/playwright CCA_BROWSER_EXECUTABLE=/home/zsolti-wsl/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome /tmp/cca006-venv/bin/python scripts/verify_authoring_ui.py --output /tmp/cca008-ui-evidence
```

Final harness exited 0. Evidence: `/tmp/cca008-ui-evidence/verification.json`, initial/approved/rejected/invalid-output desktop screenshots, review/review-controls mobile screenshots, downloaded `student.zip`, `teacher.zip` and extracted `problem.pdf`. It exercised explicit selection and the cloud notice without a provider call, generation, read-only refresh, revision, acknowledgment/approval, separate downloads, new-browser-session resume by ID without regeneration, rejection with no downloads and safe malformed output. **Four fixed mock generation attempts**, including one revision and one malformed response; **zero actual provider/worker calls**, **zero page errors**, **zero attempted external browser requests** despite generated image markup. The final retained fixture workflow was rejected. Viewports: **1440×1000** and **390×844**, with no document horizontal overflow. Child services were stopped by the harness.

Browser fixture model labels are `ollama / offline-fixture:1` and `openrouter / offline/fixture`; these are **mock labels**, not verified model versions. The cloud model was only selected to inspect the cost notice; it was never contacted. Source in the browser fixture is comment-only and never imported or executed. Decisions were synthetic browser actions, not independent human teacher review.

Initial browser runs exposed harness interaction issues: native radio/checkbox input overlays required clicking their visible labels; Streamlit text areas required Ctrl+Enter before disabled actions could enable; sidebar resize animation and persisted collapsed state required native collapse/expand handling and waiting for the animation. These were harness fixes; no application CSS or forced-click bypass was added. The final fresh output directory contains successful evidence only. Codex visually inspected the final mobile header/warnings and decision controls, desktop approval/download view and rendered PDF.

The actual downloaded archives passed `validate_export_archive`; pypdf independently extracted the Hungarian title/statement and found no private fixture marker. Teacher ZIP contains hidden tests and omits the reference by default. The **one-page** PDF was rendered using the existing temporary **pypdfium2 5.14.0** environment (`/tmp/cca007-pdf-review/bin/python`), scale 1.5, and saved as `/tmp/cca008-ui-evidence/problem-page-1.png`. Visual inspection found legible Hungarian long accents, statement, constraints/examples and the explicit approved/unverified notice; the image URL remains literal text. The fixture is not an algorithm-correctness benchmark.

| Downloaded artifact | SHA-256 |
| --- | --- |
| `student.zip` | `6c84bc1ef74bc8a9bc2fbbfbb82d8e7c517c4a2ae40add6d57af2f46fafddcf5` |
| `teacher.zip` | `9a0b3c0ec90be87bf8c2d88ea4ec10c64cbf88a507ebf0d52b027143f571f9b2` |
| `problem.pdf` | `3e5207a70e8f86c75058e3672dd83f7276192c66e2fa67db520b6dc6c906112d` |

### Review and limitations

Final scope: 17 edited tracked paths and two new operator harness sources; no unrelated changes. Both new source files have the exact two-line SPDX header. The final audit found 84 resolving local Markdown links, consistent CRLF in 10 edited existing files, zero credential-pattern matches in the changed/new files and zero staged paths. `git -c core.whitespace=cr-at-eol diff HEAD --check` exited 0; final Ruff/format/JavaScript syntax checks passed. The implementation review ended without a commit. After separate user commit approval, the 19-path scope, SPDX headers, credential-pattern scan, local links, lint, formatting, JavaScript syntax and whitespace checks were verified again. Only the intended CCA-008 paths are included in the approved commit; no push is authorized.

**Not run:** live Ollama/OpenRouter or paid calls, real generated-reference/contestant execution, fresh sandbox qualification/Docker build, independent challenge/reference/private-test correctness review by a teacher, a live teacher/model/sandbox demo, durable or multi-process checkpoint recovery, hosted CI/public deployment, other browser/OS/architectures or independent security/legal audit. Historical Release 0.1 sandbox evidence is separate and does not qualify a new worker process/host. Approval and generated reference/test agreement cannot establish independent correctness. The UI/API are for a local teacher/operator, not a public account service; the process-local ID ledger is not crash-proof exactly-once billing protection.

## 2026-10-18 — CCA-009 local Docker deployment (in progress)

Authorization: the user requested starting the application in Docker, explicitly requested a user story for this capability and clarified that submitted/reference code must execute in Linux Docker containers. CCA-009 was added to Release 0.2. Implementation began from the clean `dev_r0.2` / `fbf802b` CCA-008 commit. Implementation initially ended without commit approval. The user subsequently authorized committing the reviewed CCA-009 state. This approval covers the repository changes, not the previously rejected API socket activation; CCA-009 remains In progress until that separate permission and integrated runtime verification. No push is authorized.

### Scope, configuration and observed state

Root `compose.yaml` and `deploy/app/Dockerfile` now build separate non-root, read-only UI/API containers with the unchanged Python lockfile, resource limits and tmpfs scratch. The Dockerfile-specific context allowlist excludes local `.env`, Git data, virtual environments, uploads and runtime evidence; runtime COPY statements also name only explicit application/notice files. Models/keys reach only API from the root `.env`. All published ports bind to 127.0.0.1: **8501 UI**, **8000 API**. Web shares API's network namespace so the existing loopback client works; filesystems/process environments remain separate. No database/data volume, public hosting, model fetch or runtime package installation is added.

The root default runs with **execution disabled and no Docker socket in either container**, irrespective of native judge flags in `.env`. The optional `compose.judge.yaml` is prepared with a separate `judge-api` image, exact Docker CLI 29.6.1 digest, fixed packaged seccomp location, socket GID and an explicit host socket bind for the trusted coordinator only. This is broad Docker administration permission; it is not a worker-restricted API. No application source/worker transport, sandbox policy, official verdict or dependency/lockfile changes were needed. Docker CLI retains its original Apache license/copyright notice. Native launch remains supported.

The ignored root `.env` retained its existing bytes/credentials; only the local socket group setting `DOCKER_GID=65534` was appended. It remains ignored/untracked and is excluded from image builds. No key values or resolved secret-bearing Compose/inspect output were printed. Native Python still does not load `.env`; Docker Compose performs interpolation explicitly.

### Automatic approval boundary — judge activation not performed

Automatic approval review **rejected** `docker compose -f compose.yaml -f compose.judge.yaml up -d --build --wait --wait-timeout 120` before it ran. Stated reason: mounting the host Docker socket into the API grants broad host/container control and persistently enables judge execution; the user's general request for Docker execution did not explicitly authorize that socket exposure. The rejection was not bypassed through another container, proxy, host coordinator or indirect launch. The default socket-free services stayed active; their health reports `execution_enabled: false`.

Unaffected work was completed: the optional image builds successfully without mounting a socket, its CLI version and exact profile lookup are checked, real offline worker qualification succeeds, safe default-mode HTTP/browser/package checks pass, and documentation describes both modes. **Explicit user approval of trusted API Docker-socket access is still required before activation and the real API-container-to-worker batch/export checks.** CCA-009 remains In progress; no successful integrated judge result is claimed.

### Environment, commands and results

Observed host: Docker Desktop **4.82.0 (233772)**, Engine **29.6.1**, Compose **v5.3.0**, Linux/WSL2 x86-64 `6.6.87.2-microsoft-standard-WSL2`. Application Python **3.12.13**; build-only uv **0.11.29**. Digest pins:

- Python base: `python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2`.
- uv build tool: `ghcr.io/astral-sh/uv@sha256:78923b1c11ab847cc275c5706c70debc9eac743f935d7ad11966c1c983236aa3`.
- Optional CLI source: `docker:29.6.1-cli@sha256:862099ada15c669000bef53aa4cb9d821262829f45b0dda2159ccb276443043b`.

Exact principal commands:

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 120
docker compose -f compose.yaml up -d --build --wait --wait-timeout 120
docker compose -f deploy/worker/compose.yaml -f deploy/worker/compose.reviewed.yaml run --rm --no-deps judge-worker --verify
docker compose -f deploy/worker/compose.yaml run --rm --no-deps judge-worker --verify
docker compose -f compose.yaml -f compose.judge.yaml config --quiet
docker compose -f compose.yaml -f compose.judge.yaml build api
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges:true --entrypoint docker contest-check-api-judge:local --version
/tmp/cca006-venv/bin/python scripts/verify_docker_app.py
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu /home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node .runtime/cca009-verification/browser.cjs
/tmp/cca006-venv/bin/ruff check .
/tmp/cca006-venv/bin/ruff format --check .
git -c core.whitespace=cr-at-eol diff HEAD --check
```

Base build/start and later rebuild/start: **exit 0, both services healthy**. The initial non-elevated Docker read was denied by the sandbox; authorized Docker access succeeded. Default worker `--verify`: **exit 78**, `execution_ready: false`, failing `jail_namespaces_privileges_limits` under the ordinary Docker syscall profile. Reviewed worker `--verify`: **exit 0, all 38 checks passed**, `execution_ready: true`; the one-shot qualification container was removed. This proves the observed host/profile only; every actual test worker must qualify again in its own process. No worker security restriction was relaxed or new profile introduced.

Optional API build: **exit 0**, installed-package lookup assertion finds the exact reviewed profile, CLI reports **Docker 29.6.1, build 8900f1d** in a socket-free network-disabled one-off container. It has not been started with daemon access. Final observed runtime IDs:

| Component | Image ID |
| --- | --- |
| Running UI/API base image | `sha256:81362dfcb30fb6f05e5ef891955d2074159ae6e6b66d621f40f26866c04485af` |
| Built optional judge API image | `sha256:38fbd2a4ce8fb5b7d2a51d346ab378d9710f0cb20789758d2a57e5a8bd0c5e63` |
| Existing freshly qualified worker | `sha256:61c28046ff9e657c00339d5771cfb5fa0f2c8b940778c2587b08518920eb54e9` |

Container audit: user **1000:1000**, read-only roots, all capabilities dropped, no Docker socket on either running service, credentials present only on API, correct loopback published ports and shared network mode. All **26 installed application Python source files** match checkout SHA-256 bytes exactly. The optional image contains no model key. Seccomp profile SHA-256: `18cd477aa05c34d4211c0c907a7fb071701bdb3470357d20edebc130616d7c8b`.

`verify_docker_app.py`: **exit 0** against real services. API and Streamlit health return 200; configured model catalog has **five choices, zero issues**, no-store; valid known ZIPs validate, malformed ZIP returns 400 `invalid_zip`; judging returns the expected 503 `execution_disabled`. No source runs and no provider call is made. The operator-only script also has an explicit `--reviewed-profile` path for later fixed AC/WA/TLE/RE/DQ/REVIEW and PDF/XLSX checks against the enabled deployment; this path is **Not run** pending permission. The script is not in CI and never runs program source locally.

Browser smoke: real Docker Streamlit/API with Chromium **151.0.7922.34** / temporary Playwright **1.61.1**, desktop **1440×1000** and mobile **390×844**; successful upload/validation, visible safe execution-disabled error, explicit model selection/cloud cost notice and enabled-but-never-clicked Generate button. **Zero page errors and external browser requests**, no horizontal document overflow. No generation was requested. Codex visually inspected the judge/authoring desktop and authoring mobile screenshots. Final rebuild HTTP/browser smoke repeated successfully.

A separate one-off base-image container with **network none, read-only root and no Docker socket/credentials** exercised actual installed LangGraph start/interrupt/approval and both ZIP/PDF exports using a fixed mocked generator and comment-only draft sources. Result: `approved`, correctness `unverified`, **zero real model calls, zero reference runs**. Both generated archives passed the strict audience validators; pypdf found the public Addition statement without private markers; the student ZIP retains the font license. This validates packaging/fonts in the container, not independent challenge correctness or real contestant execution.

Local evidence stays ignored under `.runtime/cca009-verification/`: `app-smoke.json`, `browser.json`, desktop/mobile screenshots, `worker-qualification.json`, `container-audit.json`, `offline-packages.json`, synthetic exported ZIPs and the temporary fixed verification helpers. Nothing contains real student data or model keys. Ruff passed, format reports **90 files already formatted**, whitespace check exited 0. Application code/dependency locks are unchanged; the CCA-008 full **542-test** result remains prior evidence, not a newly rerun CCA-009 test count. Verification here is the actual Docker build/runtime smoke, not documentation alone.

**Not run / pending:** explicit authorization and activation of the API Docker socket; real API-container-to-worker submission/reference execution, enabled-mode judge/export smoke and its cleanup proof; live Ollama/OpenRouter generation or paid calls; fresh worker rebuild (existing unchanged image requalified); independent teacher correctness review; hosted CI/public deployment; different OS/CPU/browser combinations; external image publication or independent security/license audit. The UI/API remain available at localhost while this approval is pending.

### CCA-009 commit review

After explicit user commit approval, the 18-path scope, source/license headers, ignored local `.env`, credential patterns, local documentation links and empty pre-stage index were rechecked. Ruff and format passed again. Both Compose configurations validate without printing resolved secrets. The default-mode HTTP smoke was repeated with `/tmp/cca006-venv/bin/python scripts/verify_docker_app.py --output /tmp/cca009-commit-verification`: healthy API/UI, five configured models without issues, successful valid/invalid upload checks and the expected disabled-judge response. No new container, model call or program execution was started. Story acceptance items for integrated code execution remain unchecked; the commit does not enable the optional socket profile.

### CCA-009 teacher toolbar follow-up — 2026-10-18

Authorization: the user requested removing Streamlit's Deploy UI and recording the change, then clarified that the three-dot menu should retain System/Light/Dark themes, Print and a working Record screen. Rerun is a Streamlit UI script refresh, not submission judging; it and the other developer controls are hidden.

Added `[client] toolbarMode = "viewer"` to the existing `.streamlit/config.toml`. This native setting hides Deploy, Rerun, Clear cache and auto rerun while retaining the native theme choices, Print and browser-supported Record screen. No custom menu, CSS, JavaScript injection or application/dependency change was added. Native and Docker startup use the same config. Local setup and the CCA-009 acceptance record now describe this behavior; integrated judge acceptance remains pending.

Rebuilt and recreated only the socket-free base deployment. Exact verification commands:

```bash
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build --wait --wait-timeout 120
docker compose -f compose.yaml exec -T web python -c 'from streamlit import config; import json; print(json.dumps({"toolbar_mode": config.get_option("client.toolbarMode")}))'
/tmp/cca006-venv/bin/python scripts/verify_docker_app.py --output .runtime/cca009-toolbar-verification
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu /home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node .runtime/cca009-toolbar-verification/browser.cjs
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu /home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node .runtime/cca009-toolbar-verification/record.cjs
git -c core.whitespace=cr-at-eol diff HEAD --check
```

Build/start exited 0; both services healthy; running web config reports `viewer`. Real Docker HTTP smoke passed: healthy API/UI, five configured model choices without issues, valid/invalid ZIP handling and expected disabled-judge response. No provider call or program execution was requested.

Chromium **151.0.7922.34**, Playwright **1.61.1**: desktop **1440×1000** judge/authoring and mobile **390×844** authoring views all passed. Deploy button/menu are absent. The menu has exactly two action items, **Print** and **Record screen**, plus three native theme radio choices. All three choices update their native checked state; Print invokes the browser print handler (observed using a test-browser spy, not an OS printer). Developer actions/toggles are absent; zero page errors/external browser requests and no horizontal overflow. The passive Streamlit version footer remains. The judge desktop screenshot was visually inspected.

Actual Record start/countdown/stop/preview/download passed using Chromium's built-in **synthetic screen capture** flags (`--use-fake-device-for-media-stream`, `--use-fake-ui-for-media-stream`, `--auto-select-desktop-capture-source=Entire screen`, `--allow-http-screen-capture`). No personal desktop or microphone was captured. The preview decoded **1280×720**, ready state **4**; downloaded WebM is **12,532 bytes** with a valid EBML signature. Evidence: ignored `browser.json`, screenshots, `recording.json`, `recording-preview.png` and `screen-recording.webm` under `.runtime/cca009-toolbar-verification/`, alongside the temporary trusted browser helpers and HTTP smoke JSON.

Initial browser harness expected the older Settings menu; the installed version instead has direct theme choices. That assertion was corrected without changing application code. Native desktop/tab chooser attempts could not complete unattended in headless Chromium; synthetic capture resolved that environment limitation. One recording harness attempt pressed Escape with the menu open, which dismissed the menu without opening the video preview; the final check uses the visible Stop recording action and Save video to disk button.

TOML parse and preservation of the existing CRLF files passed; final whitespace/diff review passed. **Not run:** full pytest (configuration/docs-only change; actual Docker/browser checks used), live model/contestant execution, user OS screen-share permission/manual microphone recording, physical printing, other browsers/platforms and hosted deployment. No commit/push was performed for this follow-up.

## 2026-10-18 — CCA-008 correction: temporary browser-session drafts, no resume

Authorization: the user explicitly rejected cross-session workflow recovery and requested deleting the temporary task when the session breaks, the page is left or the browser closes. This supersedes the earlier CCA-008 fresh-session resume requirement/evidence; existing human approval checkpoints remain only inside the active session. The preceding CCA-009 toolbar changes remain intact and uncommitted. No new story/release, dependency, provider/worker transport or model execution permission was added.

### Implementation and cleanup boundary

Removed the Resume expander, ID input/button and displayed private recovery ID. A new thread-safe `AuthoringSession`, stored with native Streamlit 1.66 `st.cache_resource(scope="session", on_release=...)`, owns the private creation ID and temporary request/preview/ZIP dictionaries. Native WebSocket disconnect invokes cleanup independently of a browser unload request. Workspace exit also explicitly closes it; reconnect/rebinding clears all authoring widget state, including model/topic/instructions/difficulty/reference opt-in. The config disables retained disconnected sessions (`server.disconnectedSessionTTL = 0`). The UI now offers Refresh draft only for uncertain HTTP responses within a still-connected session, and Discard draft and start over.

DELETE is idempotent and remains available during generation/review. It immediately removes the workflow from the store and retires its ID, even when deletion arrives before the creation POST. A late generation result cannot recreate the workflow: later graph work is blocked and pending checkpoints/previews are cleared on operation exit. The bounded retired-ID ledger prevents replay without retaining task contents. Teacher approval, revision/call limits, private/student package validation and sandbox-only reference execution keep their prior contracts.

Real browser checking exposed native Streamlit media retention: clearing API/checkpoint/private dictionaries alone left old ZIP URLs returning 200. A small version-specific adapter captures the current session ID/media manager and releases its file references with both native mark/delete cleanup passes. Other active session references are preserved. The final test confirms old ZIP URLs return 404. The adapter must be checked when upgrading the pinned Streamlit version. See [Streamlit session resource lifecycle](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_resource) and the installed 1.66.0 runtime/media-manager source.

Cleanup follows server detection of a disconnect; silent network loss first requires normal Streamlit connection detection. An already-started bounded provider/worker operation may finish but its result is discarded, with no automatic retry/new model call. Cleanup attempts only idempotent local DELETE, up to twice per invocation; an unreachable API logs a generic warning without IDs/content. Immediate deletion after a web-process crash or unreachable API is not guaranteed; process-local expiry/restart remains a fallback. Already downloaded files on the teacher's device cannot be recalled. No live provider/reference execution is claimed.

### Commands, tests and browser proof

Same observed WSL2/CPython 3.12.13/Streamlit 1.66.0/FastAPI 0.143.3/LangGraph 1.2.16 and pinned temporary tooling as above. TestClient/AppTest use the existing authorized host path; actual providers/workers remain mocked. Exact commands:

```bash
/tmp/cca006-venv/bin/pytest -q tests/test_authoring_ui.py tests/test_authoring_workflow.py tests/test_workflow_api.py tests/test_package_api.py
/tmp/cca006-venv/bin/pytest -q tests/test_authoring_session.py tests/test_authoring_ui.py tests/test_workflow_api.py tests/test_authoring_workflow.py tests/test_package_api.py
/tmp/cca006-venv/bin/pytest -q tests/test_authoring_ui.py tests/test_authoring_session.py
/tmp/cca006-venv/bin/pytest -q
/tmp/cca006-venv/bin/ruff check .
/tmp/cca006-venv/bin/ruff format --check .
/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node --check scripts/verify_authoring_ui.cjs
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu CCA_BROWSER_NODE=/home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node CCA_PLAYWRIGHT_MODULE=/tmp/cca008-browser/node_modules/playwright CCA_BROWSER_EXECUTABLE=/home/zsolti-wsl/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome /tmp/cca006-venv/bin/python scripts/verify_authoring_ui.py --output .runtime/cca008-session-cleanup-final
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build --wait --wait-timeout 120
/tmp/cca006-venv/bin/python scripts/verify_docker_app.py --output .runtime/cca008-session-docker
/tmp/cca006-venv/bin/python /tmp/cca008-audit-runtime.py
LD_LIBRARY_PATH=/tmp/type-nudge-linux-deps/extracted/usr/lib/x86_64-linux-gnu /home/zsolti-wsl/.nvm/versions/node/v24.18.0/bin/node /tmp/cca008-session-docker.cjs
git -c core.whitespace=cr-at-eol diff HEAD --check
```

Focused checks passed **85 in 10.07s**, then **87 in 10.60s** after the native-media fix. Final UI/session checks, including full form reset, passed **21 in 8.80s**. Final full suite: **550 passed in 32.29s**, no warnings (eight new regressions over prior 542). Earlier full runs before the final form-reset case passed 549 in 31.38s and 32.57s. Ruff passed; **92 files already formatted**; JS syntax/whitespace checks passed. Tests cover deletion during generation, tombstone-before-create, no late preview/checkpoint resurrection, cleanup during a busy authoring slot, private data invalidation, deletion-only retry/error redaction, approved package cleanup, reconnect reset and workspace exit.

Actual local browser fixture harness exited 0 with Chromium **151.0.7922.34**, Playwright **1.61.1**, **1440×1000** desktop / **390×844** mobile. It exercises revision/approval/rejection, separate ZIP/PDF downloads, missing resume/ID controls in a fresh page, tab close after approval, workspace exit, navigation to another page and full browser closure. A second observer browser confirms deletion after closing the first browser. Final API state: **zero workflows, zero retained checkpoints, zero retained previews**. Both old native ZIP URLs and closed workflow API/export paths return **404**. **Seven fixed mocked generation attempts**, zero real provider/worker/source executions, zero page errors/external browser requests. ZIP audience validation/Hungarian PDF extraction passed; hashes match prior unchanged synthetic exports. Codex visually inspected the initial desktop form without Resume. Evidence stays ignored under `.runtime/cca008-session-cleanup-final/`.

The first browser run covered lifecycle cleanup successfully; adding native download URL checking then correctly failed (200 instead of 404), leading to the media-manager fix. The final successful directory contains the corrected proof. Previous failed/intermediate evidence remains separate under `.runtime/cca008-session-cleanup-downloads/` and `.runtime/cca008-session-cleanup/`.

### Docker refresh, review and remaining limits

The socket-free default Compose was rebuilt/recreated from current source; both services healthy. Runtime UI/API checks and installed-source/config audit are recorded under `.runtime/cca008-session-docker/`. Real configured Docker startup/catalog/browser checks make no generation call; full synthetic lifecycle/ZIP proof uses the separate real local fixture services above. CCA-009 integrated worker activation remains pending its existing separate approval; this follow-up does not enable a socket or execute contestant code.

The new source/test files carry the exact short SPDX headers. Existing line endings and the earlier toolbar edits were preserved; no staged paths/commit/push. Local setup, workflow contracts, release README/story, main README and AGENTS status describe the corrected session lifetime. **Not run:** live/paid model generation, real reference/contestant execution, worker activation, hard web-process crash/unreachable-API cleanup guarantee, silent network timeout timing, other browsers/OS/architectures, physical printing, hosted CI/public deployment or external publication.

Final Docker audit: both API and web contain all **27 application Python files** with SHA-256 bytes matching the tested checkout; both report `viewer`, zero disconnected-session retention and no daemon socket. Runtime image: `sha256:55c1a2c08d4a40e8701fab17eec938ace45d79bea65f42b66756e6a4fe79f631` (web), `sha256:55c1a2c08d4a40e8701fab17eec938ace45d79bea65f42b66756e6a4fe79f631` (API). Final HTTP/browser smoke repeated successfully: five model choices without issues, valid/invalid uploads and disabled judge; no Resume/ID controls, retained native themes/Print/Record menu, no page errors/external requests or horizontal overflow. Review covered **20 intended paths**, **73 resolving local Markdown links**, exact new SPDX headers, preserved line endings, no local key values in changed/new files and an empty index. No commit/push.

### Fix commit authorization and review

The user subsequently explicitly authorized committing these follow-ups as a **fix**. The reviewed 20-path scope includes the earlier CCA-009 toolbar cleanup and CCA-008 session-lifetime correction, their regression/browser checks and documentation. The unchanged application source retains the preceding full **550 passed** result; full pytest was not repeated solely for the commit. Ruff, formatting, JavaScript syntax and whitespace checks passed again. Before staging, the empty index, exact intended paths, preserved line endings, local links, short SPDX headers, ignored runtime/.env files and absence of real local key values were checked. Staged blobs are compared to the reviewed normalized bytes before the fix commit. No push is authorized; integrated judge activation remains pending its existing separate approval.
