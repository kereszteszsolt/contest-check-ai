# Release 0.2 verification

**Status: In progress — CCA-005/006/007 implemented and locally verified with mocked providers/workers and synthetic artifacts.** Actual graph approval/resume and approved student/teacher ZIP/PDF exports are exercised; the teacher ZIP passes judge validation and a Hungarian sample PDF was rendered/visually inspected by Codex. No live model, generated-reference execution, independent correctness review or polished approval/download UI is claimed verified.

| Story | State | Mock/Pydantic tests | Approved model / sandbox / HITL | Notes |
| --- | --- | --- | --- | --- |
| CCA-005 | Implemented | 78 focused checks; 408 full-suite tests; lint/format passed | Live model / generated-code sandbox / HITL Not run | Actual LangChain/SDK serialization and parsing over mocked HTTP; API/AppTest mocks |
| CCA-006 | Implemented | 72 new checks; 150 focused authoring checks; 480 full-suite tests; lint/format passed | Actual graph/checkpoint/approve-revise-reject with synthetic decisions; live model/reference/manual teacher smoke Not run | Strict state, fixed tools, bounded call ledgers, private local API |
| CCA-007 | Implemented | 42 new checks; 173 focused checks; 522 full-suite tests; lint/format passed | Mocked graph/API decisions; real ZIP/PDF parsing and Codex visual PDF inspection; live reference Not run | Separate public/private projections, fixed starter, direct teacher-ZIP judge ingestion |
| CCA-008 | Planned | Not run | Not run | No polished approval UI, independent final verification or final smoke tests |

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
