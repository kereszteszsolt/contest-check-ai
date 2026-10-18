# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
import json
import stat
import zipfile

import pytest
from pypdf import PdfReader

from contest_check.archives import InvalidUpload, validate_export_archive, validated_workspace
from contest_check.authoring_contracts import ModelChoice, TaskDraft
from contest_check.challenge_packages import build_challenge_package, zip_files
from contest_check.package_contracts import PackageError, PackageOptions, StudentManifest
from contest_check.workflow_contracts import (
    UNVERIFIED,
    ReferenceReport,
    ReviewEvent,
    ToolRecord,
    WorkflowRequest,
    WorkflowState,
)


@pytest.fixture
def approved_challenge(draft_data):
    return WorkflowState(
        request=WorkflowRequest(
            model_slot="ollama:1",
            instructions="PRIVATE_INSTRUCTIONS",
            topic="arithmetic",
            difficulty="beginner",
        ),
        model=ModelChoice(slot="ollama:1", provider="ollama", model="PRIVATE_MODEL"),
        draft=TaskDraft.model_validate(draft_data),
        attempts=1,
        model_calls=1,
        tool_calls=2,
        tool_results=[
            ToolRecord(attempt=1, name="validate_draft", valid=True),
            ToolRecord(
                attempt=1,
                name="run_reference_tests",
                reference=ReferenceReport(status="skipped", reason="not_requested", not_run=2),
            ),
        ],
        warnings=[UNVERIFIED, "PRIVATE_CHECK_WARNING"],
        reviews=[ReviewEvent(attempt=1, action="approve")],
        status="approved",
        approved=True,
    )


def files_of(payload):
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def pdf_text(payload):
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(payload)).pages)


def build(state, audience="student", reference=False):
    return build_challenge_package(
        audience, state, PackageOptions(include_reviewed_reference=reference)
    )


def test_student_projection_never_copies_model_starter_reference_or_private_fields(
    approved_challenge,
):
    state = approved_challenge
    draft = state.draft.model_copy(
        update={
            "starter_source": "# PRIVATE_MODEL_STARTER",
            "reference_source": "# PRIVATE_REFERENCE",
            "warnings": ["PRIVATE_DRAFT_WARNING"],
        }
    )
    state = state.model_copy(update={"draft": draft})
    files = files_of(build(state))
    assert set(files) == {
        "problem.pdf",
        "README.md",
        "student-manifest.json",
        "starter/main.py",
        "examples/sample.in",
        "examples/sample.out",
        "FONT-LICENSE.txt",
    }
    searchable = b"\n".join(data for path, data in files.items() if path != "problem.pdf")
    searchable += pdf_text(files["problem.pdf"]).encode()
    assert b"PRIVATE_" not in searchable
    assert b"3 4" not in searchable  # The private input from the shared inert fixture.
    assert b"reference_source" not in searchable and b"private_tests" not in searchable
    assert b"input.txt" in files["starter/main.py"] and b"output.txt" in files["starter/main.py"]
    assert b'output_text = ""' in files["starter/main.py"]
    assert b"input_text = source.read()" in files["starter/main.py"]
    assert files["examples/sample.in"] == b"1 2\n" and files["examples/sample.out"] == b"3\n"
    manifest = StudentManifest.model_validate_json(files["student-manifest.json"])
    assert manifest.approved and manifest.verification == "unverified"


def test_teacher_package_roundtrips_existing_judge_ingestion(
    approved_challenge, submissions_zip, tmp_path
):
    payload = build(approved_challenge, "teacher", reference=True)
    files = files_of(payload)
    assert set(files) == {
        "challenge/task-config.json",
        "challenge/tests/t1.in",
        "challenge/tests/t1.out",
        "teacher/README.md",
        "teacher/checks.json",
        "teacher/reference/main.py",
    }
    assert files["teacher/reference/main.py"] == b"# INERT_REFERENCE\n"
    assert files["challenge/tests/t1.in"] == b"3 4\n"
    assert files["challenge/tests/t1.out"] == b"7\n"
    checks = json.loads(files["teacher/checks.json"])
    assert checks["verification"] == "unverified" and checks["reference_runs"] == 0
    assert checks["tool_results"][-1]["reference"]["reason"] == "not_requested"
    assert checks["reference_included_on_teacher_review_assertion"]
    assert "PRIVATE_MODEL" not in files["teacher/checks.json"].decode()
    with validated_workspace(payload, submissions_zip, temp_parent=tmp_path) as workspace:
        assert workspace.manifest.task_id == "addition"
        assert workspace.summary.test_count == 1
        assert (
            workspace.root / "task/teacher/reference/main.py"
        ).read_bytes() == b"# INERT_REFERENCE\n"
    assert list(tmp_path.iterdir()) == []


def test_reference_requires_explicit_teacher_review_assertion(approved_challenge):
    assert "teacher/reference/main.py" not in files_of(build(approved_challenge, "teacher"))
    with pytest.raises(PackageError) as caught:
        build(approved_challenge, reference=True)
    assert caught.value.code == "package_options"


def test_maximum_task_id_fits_footer_and_stays_complete_in_public_manifest(approved_challenge):
    draft = approved_challenge.draft.model_copy(update={"task_id": "W" * 64})
    files = files_of(build(approved_challenge.model_copy(update={"draft": draft})))
    assert json.loads(files["student-manifest.json"])["task_id"] == "W" * 64
    assert "ContestCheck AI | " + "W" * 32 + "..." in pdf_text(files["problem.pdf"])


@pytest.mark.parametrize("audience", ["student", "teacher"])
def test_package_bytes_metadata_and_modes_are_deterministic(
    approved_challenge, audience, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("Export must not execute code, contact a model, or create temporary files")

    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("tempfile.mkstemp", forbidden)
    monkeypatch.setattr("tempfile.NamedTemporaryFile", forbidden)
    first = build(approved_challenge, audience)
    assert first == build(approved_challenge, audience)
    validate_export_archive(first, audience)
    with zipfile.ZipFile(io.BytesIO(first)) as archive:
        assert archive.comment == b"" and archive.testzip() is None
        for info in archive.infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)
            assert stat.S_IFMT(info.external_attr >> 16) == stat.S_IFREG
            assert info.compress_type == zipfile.ZIP_STORED and info.extra == b""
            assert info.flag_bits & 1 == 0


def test_private_changes_cannot_change_student_artifacts(approved_challenge):
    first = build(approved_challenge)
    changed = approved_challenge.model_copy(
        update={
            "draft": approved_challenge.draft.model_copy(
                update={
                    "reference_source": "# DIFFERENT_PRIVATE_REFERENCE",
                    "starter_source": "# DIFFERENT_PRIVATE_STARTER",
                    "warnings": ["PRIVATE_WARNING"],
                }
            ),
            "warnings": ["DIFFERENT_PRIVATE_CHECK_WARNING"],
        }
    )
    assert first == build(changed)


def test_pdf_readable_unicode_constraints_and_no_active_content(approved_challenge):
    draft = approved_challenge.draft.model_copy(
        update={
            "title": "Árvíztűrő tükörfúrógép",
            "statement": (
                "N egész szám, 1 <= N <= 10.\n"
                '<img src="https://invalid.example/x"/> & <b>szöveg</b>'
            ),
        }
    )
    files = files_of(build(approved_challenge.model_copy(update={"draft": draft})))
    text = pdf_text(files["problem.pdf"])
    for expected in [
        "Árvíztűrő tükörfúrógép",
        "1 <= N <= 10",
        "<img",
        "<b>szöveg</b>",
        "input.txt",
        "output.txt",
        "0.5",
        "128",
        "1024",
        "1 2",
        "3",
        "unverified",
    ]:
        assert expected in text
    reader = PdfReader(io.BytesIO(files["problem.pdf"]))
    root = reader.trailer["/Root"]
    assert not reader.attachments
    assert not any(key in root for key in ["/OpenAction", "/AA", "/JavaScript", "/AcroForm"])
    assert all(not page.get("/Annots") for page in reader.pages)
    assert any(
        "/FontFile2" in font.get_object().get("/FontDescriptor", {})
        for font in reader.pages[0]["/Resources"]["/Font"].values()
    )


@pytest.mark.parametrize("status", ["awaiting_review", "rejected", "generating"])
@pytest.mark.parametrize("audience", ["student", "teacher"])
def test_unapproved_and_rejected_states_cannot_export(approved_challenge, status, audience):
    state = approved_challenge.model_copy(
        update={
            "status": status,
            "approved": False,
            "review_id": "a" * 32 if status == "awaiting_review" else None,
        }
    )
    with pytest.raises(PackageError) as caught:
        build(state, audience)
    assert caught.value.code == "package_unapproved"


@pytest.mark.parametrize(
    "field,value",
    [
        ("output_filename", "../../out.txt"),
        ("entry_file", "other.py"),
        ("task_id", "../secret"),
        ("input_filename", "/tmp/input.txt"),
    ],
)
def test_constructed_unsafe_draft_cannot_reach_export(approved_challenge, field, value):
    state = approved_challenge.model_copy(
        update={"draft": approved_challenge.draft.model_copy(update={field: value})}
    )
    with pytest.raises(PackageError) as caught:
        build(state)
    assert caught.value.code == "package_invalid"


@pytest.mark.parametrize("text", ["PRIVATE\x00TEXT", "PRIVATE\u202eTEXT", "PRIVATE\U0010ffff"])
def test_unsupported_pdf_text_fails_without_silent_replacement(approved_challenge, text):
    state = approved_challenge.model_copy(
        update={"draft": approved_challenge.draft.model_copy(update={"statement": text})}
    )
    with pytest.raises(PackageError) as caught:
        build(state)
    assert caught.value.code == "package_text" and "PRIVATE" not in str(caught.value)


def test_excessive_print_lines_fail_closed(approved_challenge):
    example = approved_challenge.draft.examples[0].model_copy(update={"input": "\n" * 3_000})
    state = approved_challenge.model_copy(
        update={"draft": approved_challenge.draft.model_copy(update={"examples": [example]})}
    )
    with pytest.raises(PackageError) as caught:
        build(state)
    assert caught.value.code == "package_size"


@pytest.mark.parametrize("boundary", ["MAX_PDF_PAGES", "MAX_PDF_BYTES"])
def test_pdf_page_and_byte_caps_fail_closed(approved_challenge, monkeypatch, boundary):
    monkeypatch.setattr("contest_check.problem_pdf." + boundary, 1)
    draft = approved_challenge.draft.model_copy(update={"statement": "Long statement.\n" * 150})
    with pytest.raises(PackageError) as caught:
        build(approved_challenge.model_copy(update={"draft": draft}))
    assert caught.value.code == "package_size"


def test_judge_output_byte_limit_applies_to_expected_outputs(approved_challenge):
    state = approved_challenge.model_copy(
        update={
            "draft": approved_challenge.draft.model_copy(
                update={
                    "limits": approved_challenge.draft.limits.model_copy(update={"output_bytes": 1})
                }
            )
        }
    )
    with pytest.raises(PackageError) as caught:
        build(state, "teacher")
    assert caught.value.code == "package_invalid"


def test_zip_validator_rejects_unapproved_paths_and_nested_payloads(approved_challenge):
    files = files_of(build(approved_challenge))
    for changed in [
        files | {"../escape.py": b"# inert"},
        files | {"teacher/reference/main.py": b"# inert"},
        files | {"examples/sample.in": b"PK\x03\x04renamed archive"},
    ]:
        with pytest.raises(PackageError) as caught:
            zip_files(changed, "student")
        assert caught.value.code == "package_invalid"


def test_teacher_metadata_allowlist_is_narrow(approved_challenge):
    base = files_of(build(approved_challenge, "teacher"))
    for changed in [
        base | {"teacher/other.py": b"# inert"},
        {name: data for name, data in base.items() if name != "teacher/checks.json"},
    ]:
        with pytest.raises(PackageError):
            zip_files(changed, "teacher")
    with pytest.raises(InvalidUpload):
        validate_export_archive(build(approved_challenge), "teacher")


def test_multiple_examples_keep_exact_bytes_and_empty_files(approved_challenge):
    first = approved_challenge.draft.examples[0].model_copy(update={"input": "ő\r\n", "output": ""})
    second = first.model_copy(update={"input": "", "output": "ű\n"})
    state = approved_challenge.model_copy(
        update={"draft": approved_challenge.draft.model_copy(update={"examples": [first, second]})}
    )
    files = files_of(build(state))
    assert files["examples/sample.in"] == "ő\r\n".encode()
    assert files["examples/sample.out"] == b""
    assert files["examples/sample-02.in"] == b""
    assert files["examples/sample-02.out"] == "ű\n".encode()
