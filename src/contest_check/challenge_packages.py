# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Deterministic, separately projected student/teacher ZIPs from stored approval state."""

import io
import json
import stat
import zipfile

from contest_check.archives import DEFAULT_LIMITS, InvalidUpload, validate_export_archive
from contest_check.authoring_tools import validate_draft
from contest_check.models import TaskManifest
from contest_check.package_contracts import (
    Audience,
    PackageError,
    PackageOptions,
    PublicProblem,
    StudentManifest,
)
from contest_check.problem_pdf import FONT_DIRECTORY, problem_pdf
from contest_check.workflow_contracts import WorkflowState

STUDENT_README = """# Student challenge package

Read problem.pdf and student-manifest.json for the statement, filenames and limits.
The teacher approved these materials; correctness remains independently unverified.

Copy starter/main.py into your own solution folder. It reads the required input
file and writes an empty output file. Implement the algorithm yourself.
Rename/copy an examples/*.in file to the input filename from the manifest when
trying examples; compare your output with the corresponding examples/*.out file.
Exact sample bytes are in those files; PDF line wrapping is only for printing.

Ask your teacher how to submit your completed main.py. Do not submit this entire
package as a submissions ZIP. Fonts embedded in problem.pdf retain the notices
in FONT-LICENSE.txt. This archive contains only public student materials.
"""
TEACHER_README = """# Teacher-only challenge package

Keep this archive private. It contains expected outputs and may include a
teacher-reviewed reference source. Never distribute it as the student package.

Upload this ZIP directly as the task package to the ContestCheck judge, together
with a separate anonymous submissions ZIP. challenge/task-config.json and the
exact challenge/tests/*.in/*.out pairs are the judge inputs. teacher/* files
are private review metadata and never execute or affect official verdicts.

teacher/checks.json records warnings, observed checks, gaps and review decisions.
Approval and reference/test agreement do not establish independent correctness.
No model calls or reference runs occur during export. If present,
teacher/reference/main.py was explicitly requested as already reviewed by the
teacher; this assertion is not proof of correctness or sandbox qualification.
The separate student ZIP is the only package intended for students.
"""


def json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def starter(manifest: StudentManifest) -> bytes:
    # Basenames have already passed the shared strict task contract. Never copy model code.
    return (
        f'with open("{manifest.input_filename}", encoding="utf-8") as source:\n'
        "    input_text = source.read()\n\n"
        "# TODO: implement the algorithm and set output_text.\n"
        'output_text = ""\n\n'
        f'with open("{manifest.output_filename}", "w", encoding="utf-8", newline="") as target:\n'
        "    target.write(output_text)\n"
    ).encode()


def approved_state(state: WorkflowState) -> WorkflowState:
    try:
        state = WorkflowState.model_validate(state.model_dump(mode="json"))
    except (ValueError, AttributeError):
        raise PackageError("package_invalid") from None
    if (
        not state.approved
        or state.status != "approved"
        or state.draft is None
        or not state.reviews
        or state.reviews[-1].action != "approve"
        or state.reviews[-1].attempt != state.attempts
        or any(error.attempt == state.attempts for error in state.errors)
        or not any(
            tool.attempt == state.attempts and tool.name == "validate_draft" and tool.valid
            for tool in state.tool_results
        )
    ):
        raise PackageError("package_unapproved")
    validate_draft(state.draft)
    if any(
        len(value.encode()) > state.draft.limits.output_bytes
        for value in (
            *[case.output for case in state.draft.examples],
            *[case.expected_output for case in state.draft.private_tests],
        )
    ):
        raise PackageError("package_invalid")
    return state


def student_files(state: WorkflowState) -> dict[str, bytes]:
    draft = state.draft
    manifest = StudentManifest.from_draft(draft)
    public = PublicProblem(manifest=manifest, statement=draft.statement, examples=draft.examples)
    files = {
        "problem.pdf": problem_pdf(public),
        "README.md": STUDENT_README.encode(),
        "student-manifest.json": json_bytes(manifest.model_dump(mode="json")),
        "starter/main.py": starter(manifest),
        "FONT-LICENSE.txt": (FONT_DIRECTORY / "LICENSE-DejaVu.txt").read_bytes(),
    }
    for example, pair in zip(draft.examples, manifest.examples, strict=True):
        files[pair.input_file] = example.input.encode()
        files[pair.output_file] = example.output.encode()
    return files


def teacher_files(state: WorkflowState, include_reference: bool) -> dict[str, bytes]:
    draft = state.draft
    manifest = TaskManifest.model_validate(
        {
            key: getattr(draft, key)
            for key in (
                "task_id",
                "title",
                "language",
                "entry_file",
                "input_filename",
                "output_filename",
                "comparison",
                "limits",
            )
        }
        | {"tests": [{"test_id": test.test_id} for test in draft.private_tests]}
    )
    checks = {
        "format_version": 1,
        "audience": "teacher",
        "task_id": draft.task_id,
        "approved": True,
        "verification": "unverified",
        "reference_included_on_teacher_review_assertion": include_reference,
        "warnings": state.warnings,
        "draft_warnings": draft.warnings,
        "attempts": state.attempts,
        "model_calls": state.model_calls,
        "tool_calls": state.tool_calls,
        "reference_runs": state.reference_runs,
        "tool_results": [tool.model_dump(mode="json") for tool in state.tool_results],
        "errors": [error.model_dump(mode="json") for error in state.errors],
        "reviews": [review.model_dump(mode="json") for review in state.reviews],
        "reference_check_note": (
            "Checks are observations from the workflow, not independent correctness proof. "
            "Missing, skipped, blocked, partial or failed checks remain gaps; export runs no code."
        ),
    }
    files = {
        "challenge/task-config.json": json_bytes(manifest.model_dump(mode="json")),
        "teacher/README.md": TEACHER_README.encode(),
        "teacher/checks.json": json_bytes(checks),
    }
    for case in draft.private_tests:
        files[f"challenge/tests/{case.test_id}.in"] = case.input.encode()
        files[f"challenge/tests/{case.test_id}.out"] = case.expected_output.encode()
    if include_reference:
        files["teacher/reference/main.py"] = draft.reference_source.encode()
    return files


def zip_files(files: dict[str, bytes], audience: Audience) -> bytes:
    if (
        len(files) > DEFAULT_LIMITS.entries
        or sum(map(len, files.values())) > DEFAULT_LIMITS.extracted_bytes
        or any(len(content) > DEFAULT_LIMITS.file_bytes for content in files.values())
    ):
        raise PackageError("package_size")
    if (
        sum(len(data) + 120 + 2 * len(name) for name, data in files.items()) + 22
        > DEFAULT_LIMITS.archive_bytes
    ):
        raise PackageError("package_size")
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(
            buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False
        ) as archive:
            for name, payload in sorted(files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o600) << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, payload)
        data = buffer.getvalue()
    try:
        validate_export_archive(data, audience)
    except InvalidUpload:
        raise PackageError("package_invalid") from None
    return data


def build_challenge_package(
    audience: Audience, state: WorkflowState, options: PackageOptions
) -> bytes:
    if audience not in {"student", "teacher"}:
        raise PackageError("package_invalid")
    options = PackageOptions.model_validate(options.model_dump(mode="json"))
    if audience == "student" and options.include_reviewed_reference:
        raise PackageError("package_options")
    state = approved_state(state)
    files = (
        student_files(state)
        if audience == "student"
        else teacher_files(state, options.include_reviewed_reference)
    )
    return zip_files(files, audience)
