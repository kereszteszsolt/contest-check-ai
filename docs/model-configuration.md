# Ollama and OpenRouter model configuration — Release 0.2

CCA-005 implements **at most six explicitly allowlisted models**: three Ollama and three OpenRouter. Settings are read only by FastAPI from its process environment; `.env` is not loaded automatically. Do not give the OpenRouter key to Streamlit, the browser or the offline worker. Blank slots are hidden; repeated IDs within a provider keep only their first slot. A configured choice is not proof that its model is installed, reachable or supports JSON-schema output.

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL_1=
OLLAMA_MODEL_2=
OLLAMA_MODEL_3=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=
OPENROUTER_MODEL_1=
OPENROUTER_MODEL_2=
OPENROUTER_MODEL_3=
AI_MAX_CALLS_PER_GENERATION=6
AI_REQUEST_TIMEOUT_SECONDS=60
AI_MAX_OUTPUT_TOKENS=4096
```

- Ollama runs separately; in Docker, verify `host.docker.internal`/host-gateway connectivity and ensure it is **not opened to the public internet**. The native backend defaults to `http://127.0.0.1:11434`; set `OLLAMA_BASE_URL` explicitly for a different host. Only HTTP(S) root URLs without credentials, query or fragment are accepted. No Ollama model is bundled, listed or pulled by the application. Ambient `OLLAMA_API_KEY` is stripped from outgoing requests; authenticated/cloud Ollama endpoints are not implemented.
- OpenRouter stays disabled without a server-side API key and at least one non-empty configured model ID. Its use may cost money and transmit teacher-provided generation content to the chosen model provider.
- Selection is explicit. **Never silently fail over from free/local to billable cloud** or switch to another model after an error.
- Bound prompt/context length, generation attempts, tool-call count, retries and output size. Avoid logging API keys or uploaded student solutions; do not send student submissions to the LLM by default.
- Configure consistent Pydantic structured outputs for both providers and validate after parsing. Model support for constrained JSON varies; tests must verify compatibility and handle malformed output without fake success.
- All external integrations except configured Ollama/OpenRouter are **out of scope**; the application has no web browsing, arbitrary URL fetching or GitHub access.

## API and teacher flow

Start the native API/Streamlit services as described in [local development](local-development.md), supplying provider settings only to the API process. In Streamlit choose **AI task draft** in the Workspace sidebar. The UI reads `GET /api/authoring/models`, shows safe configuration errors and requires a deliberate model selection (there is no default local/cloud choice). Selecting OpenRouter displays the data-transfer/cost notice. Only **Generate draft** submits the teacher instructions and invokes a model. Merely loading the UI/catalog makes no provider call.

`POST /api/authoring/draft` accepts exactly `model_slot` (e.g. `ollama:1` or `openrouter:2`) and `instructions`. It resolves the slot against backend configuration; there is no client-supplied model name, key, base URL, upload, callback or tool field. An absent/disabled slot returns 400 `unknown_model` before client construction. Invalid request fields return the existing fixed 422 API error without echoing private content. One generation is admitted per API process; concurrent requests receive 503 `authoring_busy`. Use one API process for the documented local setup.

The response contains the exact chosen provider/model, a validated `TaskDraft`, call count, `approved: false` and `executed: false`. This is one bounded adapter call, not the CCA-006 LangGraph workflow. Nothing executes generated source, judges candidate tests, approves a draft or exports a student/teacher package. The preview is teacher-only and explicitly unverified. Changing the model, instructions or returned configuration clears old draft/error state. Data remains in the current Streamlit session; no draft/checkpoint database or shared cache is added. Successful model/catalog responses use `Cache-Control: no-store`.

`TaskDraft` is the shared strict Pydantic contract: title/statement, Python file-I/O names, comparison/resource limits, public examples, starter/candidate reference source, private test pairs and warnings. It reuses the existing manifest checks for test IDs, unique filenames and resource bounds. Extra fields, duplicate JSON keys, Markdown fences, truncated output and invalid types/counts are refused. Passing this schema does not establish algorithm correctness or adequate test coverage.

## Fixed safety bounds

| Boundary | Implemented limit |
| --- | --- |
| Teacher instructions | 1–8,000 characters, non-whitespace; no uploaded submission is read |
| Authoring HTTP body | 64 KiB before JSON parsing, including missing/dishonest Content-Length |
| Output tokens | `AI_MAX_OUTPUT_TOKENS`, default 4,096, accepted 256–8,192; Ollama `num_predict` / OpenRouter `max_tokens` |
| Request deadline | `AI_REQUEST_TIMEOUT_SECONDS`, default 60, accepted 1–120 seconds; absolute async deadline plus HTTP timeouts |
| Provider calls | `AI_MAX_CALLS_PER_GENERATION`, default 6, accepted 1–6; shared `GenerationSession` budget counts every actual attempt, including failed calls |
| Current draft request | One call; **zero retries**, repairs, streaming, tools, discovery or fallback |
| Provider response | 256 KiB before SDK parsing; actual chunks counted; compressed responses rejected |
| Structured draft | 128 KiB UTF-8 JSON, at most 10 examples / 100 private tests / 10 warnings; bounded individual text/source fields |

Input characters are bounded without downloading a tokenizer; they are not an exact provider input-token estimate. Output tokens include provider-specific accounting; compatibility errors fail explicitly. Invalid budget settings disable all choices with a safe configuration error. Invalid endpoint/credential settings disable the affected provider; invalid model slots are hidden with a safe issue. Model IDs use a bounded ASCII allowlist. Dynamic `openrouter/*` routers and `:online` search variants are refused, as are Ollama `:cloud` variants.

Every adapter uses a guarded async HTTP transport permitting only POST to the configured Ollama `/api/chat` or fixed `https://openrouter.ai/api/v1/chat/completions`. Redirects, environment proxies, unrelated endpoints and synchronous transport are refused. OpenRouter requests set `allow_fallbacks: false`, `require_parameters: true`, JSON-schema strict output, no tools and no plugins. Native constrained JSON is requested for Ollama. Unsupported models return a safe error; there is no relaxed-output fallback.

The pinned OpenRouter SDK has a default retry policy even when the LangChain wrapper receives `max_retries=0`; the application also passes SDK `retry_config=None` and request `retries=None`. Both SDK clients/transports close on success/error. The absolute deadline cancels a slow call; it cannot guarantee a remote provider stops billing/processing a request already accepted. No automatic retry follows a timeout.

Errors are fixed codes/messages: `timeout` (504), `rate_limit`/`credentials`/`provider_error`/`transport_policy` (503), `invalid_output`/`output_size` (502), exhausted `call_budget` (429). Normal diagnostics contain provider plus safe code only, never instructions, response bodies, generated source, headers or exception dumps. LangSmith/LangChain tracing is explicitly disabled around calls, including when inherited tracing variables are true; OpenRouter's optional debug logger is replaced with a no-op logger. LangSmith is a required LangChain dependency here, not an enabled external integration.

## Verification and pinned dependencies

Runtime adapters: `langchain-core==1.6.12`, `langchain-ollama==1.1.0`, `langchain-openrouter==0.2.9`, `langsmith==0.14.11`; their resolved SDKs are `ollama==0.6.3` and `openrouter==0.10.8`. Versions/hashes are locked; earlier package versions and the offline worker dependency group are unchanged. See [license inventory](dependency-licenses.md).

```bash
uv run --frozen pytest -q tests/test_providers.py tests/test_authoring_api.py tests/test_authoring_ui.py
```

These tests exercise real LangChain/provider serialization and parsing over a mocked HTTP transport, plus mocked API/AppTest flows. No model is contacted or generated program executed. Exact environment, failures and limitations are in [Release 0.2 verification](releases/release-0.2-ai-challenge-authoring/verification.md). Agent-driven live model smoke tests require separate approval; no live model/version/cost is claimed verified.

Primary implementation references: [LangChain Ollama](https://docs.langchain.com/oss/python/integrations/chat/ollama), [LangChain OpenRouter](https://docs.langchain.com/oss/python/integrations/chat/openrouter), [OpenRouter structured output](https://openrouter.ai/docs/guides/features/structured-outputs), [provider routing](https://openrouter.ai/docs/guides/routing/provider-selection), [Ollama chat](https://docs.ollama.com/api/chat). Installed pinned SDK source was also inspected for retries, environment keys and client cleanup.
