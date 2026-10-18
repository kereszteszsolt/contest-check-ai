# Bounded authoring and teacher review — CCA-006/008

The teacher-only LangGraph workflow uses the [configured models](model-configuration.md), strict `TaskDraft` schema and qualified offline worker. CCA-008 connects Streamlit generation/revision/approval/rejection to these checkpoints and the separate [student/teacher exports](challenge-packages.md). The legacy one-call CCA-005 API remains available. Local checks use mocked providers and inert source; live model/reference execution and independent challenge correctness review are **Not run**. See [release evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

## Flow and trust boundary

```mermaid
flowchart LR
    G[Generate typed draft] --> V[validate_draft]
    V --> R[run_reference_tests]
    R --> P[Prepare preview]
    G -->|Provider error| P
    V -->|Invalid draft| P
    P --> H[Teacher interrupt / checkpoint]
    H -->|Explicit revision, budget available| G
    H -->|Approve| A[Approved draft, still unverified]
    H -->|Reject| X[Rejected]
```

The workflow accepts teacher instructions, topic, difficulty and an explicitly selected backend model slot. The model cannot select tools, extend budgets, fetch URLs or name a checkpoint/host path. Only the fixed `validate_draft` and `run_reference_tests` nodes are allowed. LangChain model requests still have no tools/plugins, fallback, retries, browsing or tracing. Instructions, prior drafts, revision text and generated source are untrusted data. File-I/O basenames, `main.py`, resource bounds and structured output are validated again before any worker call, including constructed/mutated Pydantic objects.

State records the current draft, safe errors with attempt numbers, warnings, cumulative model/tool/worker counts, per-attempt tool results, approval and minimal review events (`attempt`, `action`). No prompt/source/exception-body logging is added. A revision sends the original instructions plus bounded topic/difficulty, up to 2,000 revision characters and the previous validated draft to the **same** selected provider/model. Teacher-private content stays in this teacher workflow; no contestant submissions enter the model context.

## Streamlit teacher workflow

1. Start one native API process and Streamlit using [local setup](local-development.md). Configure model slots/keys only on the API process. Choose **AI task draft** in the Workspace sidebar; select a model deliberately, then enter topic, difficulty and teacher instructions. OpenRouter shows its transfer/cost notice before generation and revision.
2. Leave **Request isolated reference checks** off unless the operator has configured the qualified worker and you intend to execute the candidate there. **Generate draft** makes one bounded model call and pauses for review. Loading/refreshing the page or choosing a model does not call a provider.
3. Inspect the statement, public examples, fixed exported starter, teacher-only candidate reference/private tests, generated starter suggestion, warnings and per-attempt checks. Content is rendered with plain `st.text`/`st.code`, so generated Markdown/HTML is inert. The generated starter suggestion is never copied into student material.
4. Enter up to 2,000 characters in **Changes requested**, then **Request changes** for another attempt using the same model. At most three attempts and the configured lower call budget apply. Each new checkpoint clears the review acknowledgment/revision input. A malformed model response pauses with a safe error and blocks approval; it can be revised within budget or rejected.
5. Independently review correctness and acknowledge the visible review checkbox, then choose **Approve draft**. Alternatively choose **Reject draft**, which provides no final packages. These actions submit the current review ID; reruns/old clicks cannot repeat its model/worker effects. Approval records a teacher decision and leaves `verification: unverified`.
6. After approval, optionally assert independent review of the reference for inclusion in the teacher ZIP, then **Prepare separate ZIP downloads**. This does not call a model/worker. Download **student ZIP** for students and keep **teacher ZIP** private. The UI validates both audience layouts, attachment names and the public manifest against the reviewed draft before offering either download. Changing reference inclusion clears both cached downloads.

Keep the displayed private workflow ID confidential. A fresh browser session can use **Resume an existing workflow** to retrieve the current checkpoint, including after a browser disconnect. **Refresh workflow** only performs GET. After an uncertain generation/review response, the UI hides decisions/downloads and requires this refresh; it never retries a model call automatically. An absent/expired workflow must be explicitly deleted/cleared with **Delete workflow and start over** before a new generation. Failed/unconfirmed deletion retains the ID. Deletion clears local preview/download state, but cannot recall already downloaded files.

UI requests ignore environment proxies. Reads are bounded to 1 MiB for previews and 10 MiB per ZIP. Generation/revision permits up to 1,050 seconds for the bounded backend operation (120-second model + at most 20 × 45-second worker runs + margin); catalog/refresh/export/delete use 10-second transport timeouts. An export timeout is safe to retry because packaging has no model/worker effects. The single-process checkpoints expire one hour after creation, independent of page activity, and are lost on API restart.

## Local API

Run one native API process as described in [local development](local-development.md). These endpoints have no account/authentication system and are intended for the existing local teacher/operator setup. Workflow IDs are random 128-bit private capabilities; keep them private. There is no workflow-list endpoint or public/student preview. Do not expose this local API as a public service.

| Endpoint | Behavior |
| --- | --- |
| `POST /api/authoring/workflows` | Create one workflow, generate/check once and return at the teacher interrupt |
| `GET /api/authoring/workflows/{workflow_id}` | Read the current preview without another model/tool call |
| `POST /api/authoring/workflows/{workflow_id}/review` | Resume the current interrupt with an explicit decision |
| `DELETE /api/authoring/workflows/{workflow_id}` | Delete its checkpoint and release local capacity; 204 on success |

Create request (only the reference-check opt-in is optional):

```json
{
  "model_slot": "ollama:1",
  "instructions": "Draft a Python file-I/O addition exercise with clear integer bounds.",
  "topic": "Integer arithmetic",
  "difficulty": "beginner",
  "run_reference_tests": false
}
```

`difficulty` is `beginner`, `intermediate` or `advanced`. Instructions require 1–8,000 characters; topic requires 1–120 nonblank characters. The authoring HTTP body remains capped at 64 KiB before parsing. Unknown fields, arbitrary model IDs/endpoints, raw graph commands and checkpoint IDs/paths are refused. No model call happens on an unknown/disabled slot or a full store.

The response is a `WorkflowPreview`: `workflow_id`, `state`, `can_approve`, `can_revise`. At a pause, `state.status` is `awaiting_review` and `state.review_id` identifies that exact preview. `state.draft` includes teacher-private source/tests. Provider timeout/invalid output becomes a safe `state.errors` entry and a reviewable pause with no draft; it does not trigger automatic repair/retry. Approval is blocked without a valid draft. A provider-error pause therefore returns HTTP 200 with explicit error state; the older one-call draft endpoint retains its existing HTTP error behavior.

For creation retry safety, clients may supply `Idempotency-Key: <32 lowercase hexadecimal characters>` generated with a cryptographically secure random source. This becomes the private workflow ID, **not a filesystem/checkpoint path**. The UI stores it before POST, so a lost response can be recovered by GET. Repeating the same creation ID and request returns the current stored preview without generation; a different request returns 409 `workflow_conflict`. Running work returns 503. Deleted/failed IDs remain retired until the one-hour creation window expires, returning 404 rather than regenerating. The ledger is bounded to 64 IDs; capacity returns 503. Without this header, legacy clients receive a fresh random server ID on every POST and must not retry blindly. No idempotency ledger survives process restart or expiry; clients must recover via GET and explicitly start over, never automatically repost a missing workflow.

Review request:

```json
{
  "review_id": "<32 lowercase hexadecimal characters from state.review_id>",
  "action": "revise",
  "revision": "Explain negative integers and their bounds."
}
```

`action` is `approve`, `revise` or `reject`. Only `revise` requires nonblank `revision`; approval/rejection accept only absent/empty revision text. A revision consumes another generation attempt and returns a **new** review ID. Approval/rejection ends the graph and clears the ID. Old, repeated, cross-workflow or terminal review decisions return 409 `stale_review` without repeating effects. Exhausted revision budgets return 409 `revision_budget`; invalid approval returns 409 `approval_blocked`. Unknown/expired workflows return 404. Running/full workflows return safe 503 errors. Successful previews/decisions/deletion and workflow error responses use `Cache-Control: no-store`.

Approval acknowledges the reviewable draft, including any visible mismatch, skipped checks or uncertainty; **it does not establish correctness, independently verify tests, accept official contest tests or publish anything**. `verification` remains `unverified` after approval. CCA-007 allows the approved materials to be downloaded as separate student/teacher packages with this explicit status. The UI requires a review acknowledgment before explicit approval; the application cannot establish whether the teacher has independently proved correctness.

## Reference checking

Reference checking requires both `run_reference_tests: true` and the existing explicit operator settings `JUDGE_EXECUTION_ENABLED=true` / `JUDGE_REVIEWED_PROFILE=true`. These settings select the fixed `DockerWorker` transport; they do not establish qualification. Each worker still qualifies its real sandbox in its own process before running a candidate. Missing configuration returns `blocked / execution_disabled`; failed qualification, malformed worker response or cleanup/infrastructure uncertainty returns `blocked / sandbox_failure` and stops further tests in that check. No host/Python subprocess fallback is added. The [worker protocol and deployment boundary](judge-worker.md) are unchanged.

The candidate reference is sent as the single `main.py` source, together with one declared input and resource limits. Expected outputs stay in the coordinator. Public examples run first, then private tests in draft order. Each case records its group, test ID, existing verdict/reason and measured wall time when available. Successful capture includes up to 2,048 bytes of observed output, UTF-8 decoded with replacement and an explicit truncation flag; comparison uses the complete captured bytes and the existing `exact` / `tokens` rules. Mismatches are reported as observed `WA`; timeout as `TLE`. Memory/output/exit hints retain the existing ambiguous `RE` reasons, without invented memory measurements or DQ.

No opt-in produces `skipped / not_requested`, with all cases counted as not run. The cumulative worker-run cap produces `partial` or `skipped / run_budget`, with exact not-run counts; it never silently claims full coverage. A passing candidate against generated examples/tests remains **unverified** because the same model may have made consistent mistakes in both. Reference results never change official contest verdicts, and failures never initiate autonomous regeneration.

## Budgets, checkpointing and cleanup

| Boundary | Limit |
| --- | --- |
| Generation attempts | At most 3, each subsequent attempt requires explicit teacher revision |
| Model calls | Shared configured `AI_MAX_CALLS_PER_GENERATION` (1–6); the lower available attempt/model budget wins; failures count when an outbound attempt occurs |
| Tool invocations | At most 6 across all revisions: validation + reference-check tool per valid attempt |
| Worker invocations | At most 20 public/private cases **across the whole workflow**, including failures |
| Individual worker deadline | Existing 45-second transport bound, including startup qualification/cleanup; no automatic retry |
| Model deadline/output | Existing 1–120 second absolute call deadline, 256–8,192 tokens, 256 KiB wire response, 128 KiB validated draft |
| Creation IDs | At most 64 retained IDs per one-hour window, including deleted/failed creations; limits repeated creation churn |
| Local workflows | At most 8, each expires 3,600 seconds after creation; expired idle entries are pruned on the next store operation |

The actual LangGraph graph uses Pydantic state, `interrupt(..., response_schema=ReviewRequest)`, `Command(resume=...)` and an `InMemorySaver` with synchronous checkpoint durability during each invocation. Pickle fallback and arbitrary MessagePack class restoration are disabled. Checkpoints contain application JSON and LangGraph's safe built-in types, never backend model settings/API keys. Tracing is disabled around the whole graph, including inherited tracing settings.

Only the review node restarts on ordinary resume; model/worker effects occur in earlier nodes. The service also validates the current review ID before invoking the graph, serializes modifications, and retains the model/worker call ledger across revisions. Unexpected graph/checkpoint failure invalidates the session and prevents automatic replay of uncertain effects. There is no raw `Command`, time-travel/replay API or client state update route.

Checkpoints and call ledgers exist **only in the current API process**; restart loses them. This is not durable crash recovery or a distributed queue. Approval/rejection retains a preview until deletion/expiry; deletion/expiry removes all associated checkpoint storage/writes/blobs. Explicit deletion is blocked while generation/review is running. Shared authoring/judge admission slots prevent concurrent model work and concurrent regular judging/reference checks. The Streamlit UI retains only its current preview and at most two bounded ZIPs in the teacher session; it does not cache provider credentials.

Pinned implementation references: [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), plus installed LangGraph 1.2.16 / checkpoint 4.3.0 source. Mocked API and actual graph/checkpoint tests exercise approval/revision/rejection; synthetic browser decisions also exercise the real local UI/API. A live teacher/model/sandbox session is **Not run**. Streamlit rendering/download behavior follows the installed 1.66.0 API and [plain text](https://docs.streamlit.io/develop/api-reference/text/st.text) / [download-button](https://docs.streamlit.io/develop/api-reference/widgets/st.download_button) documentation.

## Offline browser verification

With an operator-installed Node, Playwright and Chromium, run:

```bash
uv run --frozen python scripts/verify_authoring_ui.py --output .runtime/cca008-verification
```

Optional `CCA_BROWSER_NODE`, `CCA_PLAYWRIGHT_MODULE` and `CCA_BROWSER_EXECUTABLE` select already installed verification tooling. No browser downloads happen at application runtime. The harness starts only child loopback services and cleans them up; a fixed mock replaces generation, the worker is disabled, and provider transport is explicitly refused. It checks revisions/approval/rejection, fresh-session checkpoint resume, safe malformed output, separate downloaded ZIPs/PDF and desktop/mobile layout. Generated external-image markup remains text; the browser fails on any attempted external request. This operator-only script is not run by pytest/CI and does not verify a live provider or independent teacher judgment. Outputs and screenshots stay under the selected local artifact directory.
