# CCA-005 — Configured Ollama/OpenRouter LLM providers

## Status

**Planned**.

## User story

As a teacher, I want to select a preconfigured local or cloud model for drafting a challenge, so I know which provider is used and can control potential costs.

## Goal

Create narrowly scoped LangChain model adapters and Pydantic draft outputs using backend-only configuration.

## Dependencies

Release 0.1 validated app. See [model contract](../../../model-configuration.md).

## Acceptance criteria

- [ ] Up to `OLLAMA_MODEL_1..3` and `OPENROUTER_MODEL_1..3` appear as choices only when non-empty, distinct and correctly configured; arbitrary model names from UI are rejected.
- [ ] OpenRouter requires backend-only key and explicit teacher selection; missing key disables cloud models with a clear UI error.
- [ ] No implicit provider/model fallback, web search, GitHub API, dynamic model discovery or other external service access.
- [ ] A shared Pydantic contract represents a task draft, public examples, candidate reference solution, private tests and warnings; model responses are strictly validated before use.
- [ ] Enforce bounded input, output tokens, timeout/retries and total provider calls; log only safe diagnostics and avoid transmitting student submissions to any model.
- [ ] Tests with mock LLM clients cover valid/malformed structured outputs, missing credentials, unknown model, timeout/rate-limit and no-fallback behavior.

## Out of scope

LangGraph graph/orchestration, starter ZIPs, approval UI and direct execution of generated code.

## Verification guidance

Run focused mocked provider/Pydantic tests. Only approved smoke tests contact Ollama/OpenRouter, with named model/version, spend warning and observed response; no required billable CI calls.
