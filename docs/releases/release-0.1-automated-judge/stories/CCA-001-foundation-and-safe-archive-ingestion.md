# CCA-001 — Foundation and safe archive ingestion

## Status

**Planned** — no implementation or verification exists.

## User story

As a teacher, I want to provide one programming challenge and an anonymized submissions archive, so the system can validate the input before any code is executed.

## Goal

Create the minimal Python 3.12 Streamlit/FastAPI foundation, pinned package management and a **safe archive validator** with task-manifest schema. Define a Docker layout in documentation but do not enable execution.

## Dependencies

Documentation and [archive contract](../../../archive-contracts.md). No judge worker is required to test upload validation.

## Acceptance criteria

- [ ] Streamlit UI and FastAPI API can start locally with documented, repeatable commands; they perform **no execution of student code**.
- [ ] `task-config.json` has a documented/tested typed schema for one Python task, an allowlisted `main.py`, named file-based input/output and bounded tests/time/memory/output sizes.
- [ ] A submissions ZIP with opaque numeric participant folders and optional sibling `.py` modules passes validation without requiring student names or accounts.
- [ ] The validator rejects path traversal, absolute paths, symlinks, duplicate normalized names, nested archives, unexpected extensions, malformed manifests and compressed/uncompressed/archive-count excess **before extraction**.
- [ ] All allowed files extract into an isolated, private, bounded temporary directory; cleanup is demonstrated on success/failure.
- [ ] Invalid global ZIP data results in a clear upload error, **not an accusation of contestant cheating**; APIs do not log complete student source.
- [ ] Unit/API tests cover valid and adversarial **non-executable** fixture archives; real execution stays disabled.

## Out of scope

Executing solutions, verdicts, AI generation, public deployment, scoring, additional languages, report PDF/XLSX beyond placeholder API contracts.

## Verification guidance

Run focused Python validation and FastAPI tests; demonstrate expected validation failures with benign test archives. Record actual commands and outcomes in `../verification.md`. Do not claim the worker is safe.
