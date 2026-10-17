# Codex setup — minimal and technical

The main Codex session is the default worker. An **optional** `implementation_worker` may handle **one approved story as the sole writer**, never parallel competing edits. The `.codex/config.toml` cap is one worker thread per session.

| Technology skill | Load only when |
| --- | --- |
| [`python-web-artifacts`](../.agents/skills/python-web-artifacts/SKILL.md) | Streamlit / FastAPI UI and APIs, safe ZIP handling, PDF/XLSX, pytest |
| [`isolated-judge-runtime`](../.agents/skills/isolated-judge-runtime/SKILL.md) | Sandboxed Python execution, timeouts, file isolation, verdicts |
| [`langgraph-ai-authoring`](../.agents/skills/langgraph-ai-authoring/SKILL.md) | LangChain/LangGraph, model allowlists, Pydantic outputs, human approval |

Skills explain **how to work with technologies**. Product requirements belong in approved story files and application behavior; do not duplicate business rules across skills.

Begin with `AGENTS.md`, one story, and the smallest needed documents. No automatic parallel reviewers, no speculative features, no unapproved paid model calls, no automatic commits or pushes.
