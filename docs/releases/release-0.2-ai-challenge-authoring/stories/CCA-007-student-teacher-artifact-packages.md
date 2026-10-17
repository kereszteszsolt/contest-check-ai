# CCA-007 — Separate student and teacher challenge ZIP packages

## Status

**Planned**.

## User story

As a teacher, I want a printable challenge statement, example input/output and minimal source starter for students, without revealing the private answer keys.

## Goal

Generate **two clearly separated downloadable ZIP formats** from an approved, typed challenge draft, using the same file-based task contract as the judge.

## Dependencies

CCA-005/006 typed draft and teacher review state; Release 0.1 archive manifest requirements.

## Acceptance criteria

- [ ] Student package includes `problem.pdf`, user-facing README/manifest, at least one illustrative `.in`/`.out` example and a minimal **Python** starter source that only reads/writes required task file names (does not solve the algorithm).
- [ ] Teacher package includes judge-ready `task-config.json`, teacher-private test inputs/expected outputs, optional reviewed reference source, and warnings/check logs kept separate from student materials.
- [ ] Generated filenames, task IDs and paths are validated through the same strict archive safety policy; no symlinks/traversal, active content or hidden-test accidental leakage.
- [ ] The generated reference solution is validated using the actual sandbox when enabled and reports gaps; do not misrepresent agreement between model-generated tests and model-generated solution as independent correctness proof.
- [ ] PDF render includes readable task statement, constraints and sample I/O; the report omits private grading data and model credentials.
- [ ] For an unapproved or rejected draft, no final student package can be downloaded as a validated challenge; teacher review can still inspect a clearly marked draft preview.
- [ ] Archive-content tests assert that student ZIP never contains hidden test/reference directories; artifacts are deterministic from the same approved draft where feasible.

## Out of scope

C/C++/Pascal starter generation, multi-task competition books, points scoring, automatic publication and arbitrary executable checkers.

## Verification guidance

Inspect generated PDF/ZIP content with unit tests and a human read-through; verify in a non-sensitive fixture that public and private archives differ exactly as specified.
