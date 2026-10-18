# Separate student and teacher packages — CCA-007

The local authoring backend exports two independent ZIPs from the **stored, approved current draft**. Packaging performs no model calls or reference execution. Correctness stays `unverified`, even after teacher approval or reference/test agreement. The [workflow](authoring-workflow.md) supplies observed reference checks when explicitly requested, through its qualified worker; missing, skipped, partial and failed checks remain visible in the teacher log. Independent final correctness verification and the polished review/download UI remain CCA-008 scope.

## Student archive

```text
<task_id>-student.zip
├── problem.pdf
├── README.md
├── student-manifest.json
├── FONT-LICENSE.txt
├── examples/
│   ├── sample.in
│   ├── sample.out
│   ├── sample-02.in       # only when a second example exists, up to sample-10
│   └── sample-02.out
└── starter/
    └── main.py
```

The public manifest contains the task ID/title, Python entrypoint, fixed starter path, required file-I/O basenames, comparison/resource limits, sequential public example paths and explicit approved/unverified flags. It contains no private test IDs, reference, generated starter, prompts, provider configuration, warnings or check logs. The PDF receives only this public projection plus the statement/public examples; it never receives the entire workflow or draft object.

`starter/main.py` comes from a fixed application template, **not** `TaskDraft.starter_source`. It reads the declared input into `input_text`, leaves a TODO and empty `output_text`, and writes only the declared output filename. It contains no algorithm, model code or hidden answer. Neither starter nor reference source is imported/executed by export. Students copy this file into their solution folder, implement the algorithm and follow the teacher's submission instructions; the student archive itself is not a judge task/submissions ZIP.

Example files retain exact UTF-8 input/output bytes, including empty files and CRLF. The printable PDF shows the statement, file-I/O/resource constraints, examples and explanations. Sample display expands tabs and wraps long lines; the `.in`/`.out` files are authoritative for exact bytes. User text is escaped as plain text: HTML-like strings cannot become images, links, scripts or filesystem/URL reads. PDF actions, attachments and active forms are not generated.

Bundled DejaVu Sans/Mono 2.37 provide embedded glyphs including Hungarian long accents; the PDF does not depend on fonts installed on the operator's machine. Unsupported glyphs/control or bidirectional formatting text fail explicitly instead of silently replacing characters. Complex-script shaping/universal Unicode support is not claimed. The font notice is included in both the installed package and student ZIP; see [license inventory](dependency-licenses.md).

This boundary prevents accidental inclusion of private **fields/files**. A teacher must still inspect the public statement and examples for semantic mistakes or sensitive text that a model/teacher has placed in a public field. Packaging does not independently prove challenge correctness or classify arbitrary secrets in public prose.

## Teacher archive and judge compatibility

```text
<task_id>-teacher.zip
├── challenge/
│   ├── task-config.json
│   └── tests/
│       ├── <test_id>.in
│       └── <test_id>.out
└── teacher/
    ├── README.md
    ├── checks.json
    └── reference/
        └── main.py        # optional; explicit teacher review assertion required
```

Upload this archive **directly** as the existing judge's task ZIP, together with a separate anonymous submissions ZIP. Its `challenge/task-config.json` uses the unchanged strict `TaskManifest`, original test IDs/order, comparison and resource limits. Only private tests are official manifest tests; public examples are student materials. Expected outputs must satisfy the manifest's byte limit.

The [archive safety policy](archive-contracts.md) now accepts exactly `teacher/README.md` and `teacher/checks.json` together, optionally with `teacher/reference/main.py`. All other undeclared paths/extensions remain rejected. Legacy task archives without these metadata files remain supported. Metadata passes the same path/type/count/size/CRC/nested-archive checks but is **ignored by judging**, never rendered, executed, sent to a worker or used to enable execution/qualification. The worker still receives only the current anonymous submission, one input and its limits; the exported reference cannot replace a submission accidentally.

`checks.json` records approved/unverified status, cumulative counts, per-attempt tool results, observed output previews, not-run gaps, warnings/errors and minimal teacher decisions. It excludes workflow capability IDs, provider names/configuration, keys and original prompts. Its statements are review data, not trusted sandbox qualification. An optional reference is included only when the teacher explicitly asserts having reviewed that current source; this does not establish independent correctness.

## API and approval gate

```text
POST /api/authoring/workflows/{workflow_id}/packages/student
Content-Type: application/json
{}

POST /api/authoring/workflows/{workflow_id}/packages/teacher
Content-Type: application/json
{"include_reviewed_reference": false}
```

Only the teacher endpoint accepts `include_reviewed_reference: true`. This option is the teacher's explicit review assertion for inclusion, not a sandbox request or a new verification result. No caller-supplied draft/state, approval flag, output path or source is accepted. The server reads the existing workflow, revalidates the typed state/draft and requires a final current-attempt approval, successful schema validation and no current generation error. Unapproved/rejected workflows cannot export either package; their existing teacher-only JSON preview remains clearly marked with status and `verification: unverified`.

Successful downloads use `application/zip`, a safe task-ID/audience attachment filename, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` and `X-Challenge-Verification: unverified`. All authoring errors are also no-store. Workflows remain local private capabilities, without an account/public sharing system; use the existing single-process local operator setup.

| Failure | HTTP / fixed code |
| --- | --- |
| Unapproved/rejected/missing valid approval | 409 `package_unapproved` |
| Unsafe/malformed draft, expected output over task limit or failed archive validation | 422 `package_invalid` |
| Student requests reference inclusion | 422 `package_options` |
| Unsupported printable characters/control text | 422 `package_text` |
| Printable lines/pages/bytes or archive bounds exceeded | 413 `package_size` |
| Concurrent package generation | 503 `package_busy` |
| Unexpected render/export failure | 503 `package_failed` |
| Absent/expired workflow or running workflow | Existing 404/503 workflow errors |

Packaging is in memory, with one admitted export per API process. It creates no upload/export directory or persistent artifact cache. The source workflow follows its existing capacity/expiry/deletion rules. Export uses a copied approved snapshot; deleting a workflow does not recall a download already admitted from that snapshot.

PDF output is capped at **1 MiB**, **60 pages** and **2,400 rendered line units**. ZIPs obey the existing **10 MiB** archive / **50 MiB** expanded / **1 MiB** per-file / **4,096** entry limits and the strict manifest caps. All generated ZIPs are read back through the same safety validator without extraction. ZIP_STORED avoids expansion-ratio surprises for repetitive tests; sorted members, fixed timestamps/ordinary file modes, stable JSON and ReportLab invariant output make the same approved draft/options deterministic in the pinned environment. Cross-version/platform PDF byte identity is not promised.

## Verification boundary

Tests inspect ZIP members, independently parse PDF/JSON, check Hungarian glyphs and inactive content, verify deterministic public/private separation and fixed starter behavior, exercise actual workflow approval/API export with mocked model/worker responses, and upload the generated teacher archive through the existing judge validation route. The synthetic Hungarian sample PDF was rendered with temporary external PDFium tooling and visually inspected by Codex. No live provider, generated-source execution, manual teacher correctness review, new UI/browser flow or hosted deployment was verified. Exact commands and results are in [release evidence](releases/release-0.2-ai-challenge-authoring/verification.md).
