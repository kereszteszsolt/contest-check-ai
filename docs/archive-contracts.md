# Archive contracts — CCA-001 inputs / planned Release 0.2 exports

## Initial judge inputs

**Teacher task ZIP** contains one challenge with `challenge/task-config.json` and exactly the declared `challenge/tests/<test_id>.in` / `<test_id>.out` pairs. CCA-001 validates/extracts the pair; CCA-003 connects it to a separately qualified worker through an explicitly configured local API. See [judging.md](judging.md).

### Task manifest v0.1

The strict Pydantic contract is `src/contest_check/models.py`; its generated [JSON Schema](task-config.schema.json) and the [complete example](../examples/task-config.json) are tested together. UTF-8 JSON only; reject duplicate keys, unknown fields and automatic string-to-number coercion. All fields below are required except `title`.

| Field | Allowed value |
| --- | --- |
| `task_id` | ASCII letter/digit followed by up to 63 letters/digits/underscores/hyphens |
| `language` | Exactly `python` |
| `entry_file` | Exactly `main.py` |
| `input_filename` | Lowercase ASCII basename matching `[a-z][a-z0-9_-]{0,47}\.(in\|txt)` |
| `output_filename` | Lowercase ASCII basename matching `[a-z][a-z0-9_-]{0,47}\.(out\|txt)`; must differ from input |
| `tests` | 1–100 objects, each containing only `test_id` |
| `tests[].test_id` | ASCII letter/digit followed by up to 31 letters/digits/underscores/hyphens; unique ignoring case |
| `comparison` | `exact` (identical bytes) or `tokens` (ordered ASCII-whitespace-separated byte tokens); implemented in CCA-003 |
| `limits.time_seconds` | Finite number greater than 0 and at most 3 |
| `limits.memory_mb` | Integer 1–256; booleans rejected |
| `limits.output_bytes` | Integer 1–1,048,576; also caps each expected `.out` file |
| `title` | Optional string of at most 160 characters or `null` |

`exact` compares identical bytes without newline, whitespace or encoding normalization. `tokens` compares ordered lists from `bytes.split()`, using ASCII whitespace only, with no numeric conversion. The complete tested rules are in [judging.md](judging.md#comparison-rules). Runtime filenames are data, never shell command fragments. The worker enforces manifest resource limits afresh for every test.

The optional `policy` object defaults to `{"max_source_bytes": null, "review_imports": []}`. `max_source_bytes` is an explicitly configured total-source-byte limit (1–30 MiB); exceeding it records objective DQ evidence and skips that participant. `review_imports` accepts at most the three distinct names `socket`, `subprocess`, `ctypes`; static matches generate REVIEW notices without changing test verdicts. See the [policy contract](judging.md#optional-contest-policy). Archive rejection is never a DQ.

**Submissions ZIP:** 1–100 strictly numeric opaque folder IDs, each containing exactly one `main.py` entrypoint and optional same-folder `.py` modules. IDs match `0|[1-9][0-9]{0,15}`; leading-zero aliases, signs, names and Unicode numerals are rejected. Filenames match `[A-Za-z_][A-Za-z0-9_]{0,63}\.py`. Maximum 30 files per participant. Only relative paths are accepted. A multi-task archive is **not** MVP scope.

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

Fixed CCA-001 limits apply independently to each ZIP: 10 MiB uploaded/compressed archive, 50 MiB expanded data, 4,096 central-directory entries (including directory entries), 1 MiB per file, 64 KiB for the manifest, and a maximum 100:1 expansion ratio per file. Two uploads together can therefore extract at most 100 MiB. The API bounds the entire multipart request to 20 MiB + 64 KiB, including requests without an honest `Content-Length`. Limits are code constants in `ArchiveLimits`; `.env` does not override them in CCA-001.

Only standard stored/deflated ZIPs are supported. ZIP64, split/encrypted archives, prepended stubs, trailing data and unsupported compression are rejected. Paths must be ASCII, contain no control characters, backslashes, drive prefixes, empty/dot/traversal segments, and remain unique ignoring case. Explicit empty directories are optional and must be ancestors of allowed files. Symlinks, devices and other special file entries are rejected.

The central directory is counted before constructing ZIP member objects. All metadata, payload sizes, full deflate stream endings, CRCs, manifest fields and test-pair/submission layouts are checked **before creating the extraction directory**. Known nested archive signatures and ZIP end records are rejected even when renamed to an allowed extension. This is archive ingestion, not static source analysis or a general content-security scanner.

Both complete validated packages extract to separate `task/` and `submissions/` subdirectories inside a random `cca-validate-*` system temporary directory (0700; files 0600). No uploaded names choose the root directory. The context manager removes the directory on success, consumer failure and partial extraction failure; the API returns only a summary after cleanup. Multipart upload spools are bounded by the request limit and closed before extraction. Process crashes/forced termination are outside normal context-manager cleanup; use the dedicated temporary filesystem proposed in the [local setup](local-development.md) for future containers.

Errors describe invalid uploads, never cheating or disqualification. The API returns no private test payload, source text, manifest validation internals or local filesystem paths, and does not log request bodies.

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
