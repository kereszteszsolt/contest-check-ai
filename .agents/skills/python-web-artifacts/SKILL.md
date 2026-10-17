---
name: python-web-artifacts
description: Use for Streamlit, FastAPI, Python packaging, Pydantic request validation, safe ZIP upload/export, Markdown/PDF/XLSX report creation and focused pytest tests.
---

# Python web and artifact engineering

## When to load

Load for an **approved story** changing Streamlit UI, FastAPI routes, archive ingestion, report serialization, dependency management or upload tests. Not for low-level runner isolation or LLM agent prompts.

## Technology practices

1. Keep Streamlit presentation thin and FastAPI domain services testable; do not execute contestant programs in either process.
2. Treat ZIP files as untrusted: cap compressed/uncompressed size and file counts; reject traversal, absolute paths, symlinks, nested ZIPs, duplicate normalized names, unexpected extensions and ambiguous participant IDs. Validate before extraction into a per-job private directory.
3. Use explicit Pydantic/typed schemas for task manifest, accepted filenames, report rows and API boundaries; separate teacher-only and student-facing packages.
4. Export deterministic, sanitized Markdown/PDF/XLSX. Escape cells beginning with spreadsheet formula characters and do not embed executable macros. No student identities beyond supplied opaque IDs.
5. Delete temporary artifacts on completion/failure; avoid secrets, student source or uploaded content in normal logs. Limit in-memory data and upload size.
6. Make Streamlit state transitions explicit: upload, validate, judge, review, download; show progress and safe errors. Keep accessibility and keyboard navigation in mind.
7. Unit tests cover malformed archives, task manifests, data serialization and output generation without starting any untrusted code or contacting an LLM.

## Verification

Run focused pytest (and format/lint/type checks if configured) first. Sandbox integration checks use `isolated-judge-runtime` and must fail closed if prerequisites are absent. Record actual commands and outputs in the current release verification file.
