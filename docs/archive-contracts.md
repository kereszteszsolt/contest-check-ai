# Archive contracts — planned Release 0.1 / 0.2

## Initial judge inputs

**Teacher task ZIP** contains one challenge with `challenge/task-config.json` and `challenge/tests/NN.in` / `NN.out` pairs. The manifest describes `task_id`, `language: python`, `entry_file: main.py`, `input_filename`, `output_filename`, a bounded list of `test_id`s, comparison mode, time/memory/output limits and optional display metadata. Schemas and exact fields are finalized in CCA-001 with tests.

**Submissions ZIP:** a bounded number of strictly numeric opaque folder IDs, each containing an expected `main.py` entrypoint and optional same-folder `.py` modules. Allow only relative paths and approved source extensions. A multi-task archive is **not** MVP scope.

```text
submissions.zip
├── 1001/
│   ├── main.py
│   └── helpers.py
├── 1002/
│   └── main.py
└── 1003/
    └── main.py
```

The worker places the manifest-named input file(s) in an isolated working directory before each run and retrieves only the expected output filename(s) afterwards. MVP supports one defined input and one defined output file per test. Additional files or stdin/stdout modes require explicit scope changes.

## Secure ingestion rules

- Validate ZIP central directory, entry count, maximum compressed and uncompressed sizes, normalized paths, duplicate names and extensions **before extraction**.
- Reject absolute paths, `..` traversals, symlinks, device entries, executables, nested archives, zip bombs, and unexpected or duplicate entrypoints; never trust Unicode or path normalization blindly.
- Process each participant in a fresh restricted workspace. A malformed global archive is rejected as an upload, not misrepresented as a participant's cheating attempt.
- Validate task-manifest filenames using a strict allowlist; never form shell commands by concatenating paths.
- Keep teacher private tests and source isolated from student starter/output packages.

## Release 0.2 exports

The **student ZIP** has `problem.pdf`, `README.md`, `examples/sample.in`, `examples/sample.out`, `starter/main.py` and a public manifest. The **teacher ZIP**, downloaded separately, contains the judge-ready private tests/expected outputs, metadata and teacher-reviewed reference solution. Teacher approval is required before either export.

Starter code intentionally does only safe file I/O according to the task filenames. It is not an answer/solution to the algorithmic task.

## Files and scoring

No user-submitted numeric scoring-rules upload in the MVP: it records pass/fail for **each test** without points. Future scoring rules may live in a separate file after the judge is reliable; see `docs/future.md`.
