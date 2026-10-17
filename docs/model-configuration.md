# Ollama and OpenRouter model configuration — Release 0.2

The application may expose **at most six explicitly allowlisted models**: three Ollama and three OpenRouter. Each `.env` slot is independent and optional. Blank or duplicate model IDs are hidden. The app must not discover an unbounded model catalogue or accept arbitrary client-selected identifiers.

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
```

- Ollama runs separately; in Docker, verify `host.docker.internal`/host-gateway connectivity and ensure it is **not opened to the public internet**. No Ollama model is bundled with the repository.
- OpenRouter stays disabled without a server-side API key and at least one non-empty configured model ID. Its use may cost money and transmit teacher-provided generation content to the chosen model provider.
- Selection is explicit. **Never silently fail over from free/local to billable cloud** or switch to another model after an error.
- Bound prompt/context length, generation attempts, tool-call count, retries and output size. Avoid logging API keys or uploaded student solutions; do not send student submissions to the LLM by default.
- Configure consistent Pydantic structured outputs for both providers and validate after parsing. Model support for constrained JSON varies; tests must verify compatibility and handle malformed output without fake success.
- All external integrations except configured Ollama/OpenRouter are **out of scope**; the application has no web browsing, arbitrary URL fetching or GitHub access.

The model provider's actual adapter and version will be chosen in approved CCA-005 using current compatible LangChain libraries; no libraries are installed in the baseline.
