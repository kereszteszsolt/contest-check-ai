# Release 0.2 — AI Challenge Authoring

**Status: CCA-005–009 implemented and locally verified.** CCA-009 has real benign Docker API-to-worker verdict/export/cleanup evidence after explicit local API socket approval; CCA-005–008 authoring evidence uses mocked providers and synthetic artifacts; CCA-009 also verifies two real isolated reference runs from a fixed benign draft. Docker Desktop shows web, API and the retained stopped worker together, with one port per web/API container. The configured adapters feed a bounded LangGraph workflow, explicit Streamlit approve/revise/reject checkpoints and separate approved student/teacher ZIP/PDF downloads. Actual graph/checkpoint/API/AppTest behavior and a real local browser flow are exercised, including same-session lost-response recovery and automatic draft deletion on workspace exit/browser disconnect; cross-session resume was removed at the user's request. The teacher ZIP passes judge archive validation. No live model, generated-reference execution, independent teacher correctness review, hosted CI or public deployment is verified. See [workflow contracts](../../authoring-workflow.md), [package contracts](../../challenge-packages.md) and [verification evidence](verification.md). Reference checks depend on the existing qualified, fail-closed Release 0.1 judge.

## Goal

Given teacher instructions, produce a **reviewable** algorithm challenge draft with statement, public input/output examples, starter Python source, a candidate reference solution and private tests. Use bounded LangChain/LangGraph workflows through explicitly chosen Ollama/OpenRouter models. No student package is finalized until the teacher explicitly approves; then download distinct student and teacher ZIPs.

## Story order

| Story | Goal | Status |
| --- | --- | --- |
| [CCA-005](stories/CCA-005-configured-llm-providers.md) | Up to 3+3 configured models and validated outputs | Implemented; mocked SDK/API/UI checks passed, live models Not run |
| [CCA-006](stories/CCA-006-langgraph-generation-and-tools.md) | Bounded LangGraph / sandbox-backed test tools | Implemented; actual graph/API with mocked models/workers, live checks Not run |
| [CCA-007](stories/CCA-007-student-teacher-artifact-packages.md) | PDF + examples/starter ZIP, private test ZIP | Implemented; synthetic ZIP/PDF/API checks and visual PDF inspection, live reference Not run |
| [CCA-008](stories/CCA-008-teacher-approval-and-verification.md) | HITL approval, UI, security tests, CI and docs | Implemented; actual UI/API/graph with mocks, synthetic browser decisions and ZIP/PDF checks; live provider/reference Not run |
| [CCA-009](stories/CCA-009-local-docker-deployment.md) | Local Docker UI/API deployment and isolated Linux judge execution | Implemented; approved local judge mode, real benign verdict/export/cleanup checks, 43871/43872 host ports |

No RAG, GitHub access, arbitrary web fetching, auto-publication, advanced scoring, custom checker execution or multi-agent swarm. Observed evidence belongs in [verification.md](verification.md).
