---
name: langgraph-ai-authoring
description: Use for LangChain/LangGraph stateful challenge generation, bounded tool calling, Ollama/OpenRouter model allowlists, Pydantic structured outputs, checkpointing and teacher human approval.
---

# LangChain / LangGraph authoring workflows

## When to load

Only for an **approved Release 0.2 authoring story** concerning model adapters, prompt/workflow logic, generated task drafts, reference test calls or human-in-the-loop validation. Do not load for ordinary ZIP judging.

## Technology practices

1. Choose the provider/model strictly from up to three non-empty Ollama slots and three non-empty OpenRouter slots. Never silently fall back to billable cloud use; enforce a per-request call budget, timeouts and output limits.
2. Use a typed Pydantic state/output contract and a small explicit LangGraph workflow. An agent tool is approved and narrowly scoped, not general OS access. No web search, GitHub fetch, arbitrary URL requests or unrestricted filesystem tools.
3. Treat user instructions, task drafts, hidden tests and generated code as untrusted data. LLM text may suggest content but cannot authorize filesystem access or relax sandbox restrictions.
4. Reference-solution tests MUST use the same verified offline judge sandbox; no execution in agent or web process. Never claim test coverage proves a generated challenge correct.
5. Use LangGraph interrupt + checkpoint for teacher review. Approval or revision is explicit, reproducible and logged with minimal metadata. No student package export or official test acceptance before approval.
6. Separate teacher/private tests and reference solutions from student ZIP. Bound generation loops and handle malformed structured output explicitly.
7. Mock model clients and tool outputs in CI; real Ollama/OpenRouter calls require human approval and may incur costs. Test missing key, invalid model, provider error, excessive tool calls and approval rejection.

## Verification

Run focused LangGraph/Pydantic unit and integration tests with mocked models. If available, run an approved local smoke test with bounded input. Record whether human approval and checkpoint/resume were actually exercised.
