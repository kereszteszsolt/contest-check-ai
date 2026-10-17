# Release 0.2 — AI Challenge Authoring

**Status: Planned.** Depends on a verified, fail-closed Python judge from Release 0.1.

## Goal

Given teacher instructions, produce a **reviewable** algorithm challenge draft with statement, public input/output examples, starter Python source, a candidate reference solution and private tests. Use bounded LangChain/LangGraph workflows through explicitly chosen Ollama/OpenRouter models. No student package is finalized until the teacher explicitly approves; then download distinct student and teacher ZIPs.

## Story order

| Story | Goal | Status |
| --- | --- | --- |
| [CCA-005](stories/CCA-005-configured-llm-providers.md) | Up to 3+3 configured models and validated outputs | Planned |
| [CCA-006](stories/CCA-006-langgraph-generation-and-tools.md) | Bounded LangGraph / sandbox-backed test tools | Planned |
| [CCA-007](stories/CCA-007-student-teacher-artifact-packages.md) | PDF + examples/starter ZIP, private test ZIP | Planned |
| [CCA-008](stories/CCA-008-teacher-approval-and-verification.md) | HITL approval, UI, security tests, CI and docs | Planned |

No RAG, GitHub access, arbitrary web fetching, auto-publication, advanced scoring, custom checker execution or multi-agent swarm. Observed evidence belongs in [verification.md](verification.md).
