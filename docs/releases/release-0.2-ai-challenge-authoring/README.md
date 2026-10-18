# Release 0.2 — AI Challenge Authoring

**Status: In progress — CCA-005/006/007 implemented and locally verified with mocked providers/workers and synthetic artifacts.** Configured adapters and the one-call preview are joined by a bounded LangGraph backend with opt-in worker reference checks and teacher approve/revise/reject checkpoints. Actual graph/checkpoint behavior is tested; no live model or generated-reference execution is verified. CCA-007 adds separate approved student/teacher ZIPs and a public PDF; teacher exports pass judge archive validation. CCA-008 polished review/download UI and final independent teacher verification remain planned. See [package contracts](../../challenge-packages.md). Depends on the verified, fail-closed Python judge from Release 0.1. See [workflow contracts](../../authoring-workflow.md).

## Goal

Given teacher instructions, produce a **reviewable** algorithm challenge draft with statement, public input/output examples, starter Python source, a candidate reference solution and private tests. Use bounded LangChain/LangGraph workflows through explicitly chosen Ollama/OpenRouter models. No student package is finalized until the teacher explicitly approves; then download distinct student and teacher ZIPs.

## Story order

| Story | Goal | Status |
| --- | --- | --- |
| [CCA-005](stories/CCA-005-configured-llm-providers.md) | Up to 3+3 configured models and validated outputs | Implemented; mocked SDK/API/UI checks passed, live models Not run |
| [CCA-006](stories/CCA-006-langgraph-generation-and-tools.md) | Bounded LangGraph / sandbox-backed test tools | Implemented; actual graph/API with mocked models/workers, live checks Not run |
| [CCA-007](stories/CCA-007-student-teacher-artifact-packages.md) | PDF + examples/starter ZIP, private test ZIP | Implemented; synthetic ZIP/PDF/API checks and visual PDF inspection, live reference Not run |
| [CCA-008](stories/CCA-008-teacher-approval-and-verification.md) | HITL approval, UI, security tests, CI and docs | Planned |

No RAG, GitHub access, arbitrary web fetching, auto-publication, advanced scoring, custom checker execution or multi-agent swarm. Observed evidence belongs in [verification.md](verification.md).
