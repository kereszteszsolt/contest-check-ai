# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
import json
import stat
import struct
import warnings
import zipfile
import zlib
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import INERT_SOURCE, make_zip, task_entries
from pydantic import ValidationError

from contest_check.archives import DEFAULT_LIMITS, InvalidUpload, validated_workspace
from contest_check.models import TaskManifest


def assert_rejected(task_zip, submissions_zip, tmp_path, *, code=None, **kwargs):
    with pytest.raises(InvalidUpload) as raised:
        with validated_workspace(task_zip, submissions_zip, temp_parent=tmp_path, **kwargs):
            pytest.fail("Invalid archive reached extraction")
    assert list(tmp_path.iterdir()) == []
    if code:
        assert raised.value.code == code


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_valid_private_workspace_and_success_cleanup(manifest, tmp_path, compression):
    task = make_zip(task_entries(manifest), compression)
    submissions = make_zip(
        [
            ("1001/", b""),
            ("1001/main.py", INERT_SOURCE),
            ("1001/helper.py", INERT_SOURCE),
        ],
        compression,
    )
    with validated_workspace(task, submissions, temp_parent=tmp_path) as workspace:
        root = workspace.root
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert workspace.summary.participant_ids == ["1001"]
        assert workspace.summary.test_count == 1
        assert workspace.summary.submission_file_count == 2
        assert workspace.summary.execution_enabled is False
        source = root / "submissions/1001/main.py"
        assert source.read_bytes() == INERT_SOURCE
        assert stat.S_IMODE(source.stat().st_mode) == 0o600
        assert (root / "task/challenge/tests/01.out").read_bytes() == b"3\n"
        assert workspace.summary.extracted_bytes == sum(
            file.stat().st_size for file in root.rglob("*") if file.is_file()
        )
    assert not root.exists()
    assert list(tmp_path.iterdir()) == []


def test_cleanup_on_consumer_failure(task_zip, submissions_zip, tmp_path):
    with pytest.raises(RuntimeError, match="consumer failed"):
        with validated_workspace(task_zip, submissions_zip, temp_parent=tmp_path) as workspace:
            root = workspace.root
            raise RuntimeError("consumer failed")
    assert not root.exists()


def test_cleanup_on_extraction_failure(task_zip, submissions_zip, tmp_path, monkeypatch):
    original = Path.open

    def failing_open(path, *args, **kwargs):
        if path.name == "main.py":
            raise OSError("simulated storage failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    with pytest.raises(OSError):
        with validated_workspace(task_zip, submissions_zip, temp_parent=tmp_path):
            pytest.fail("Extraction must fail")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "path",
    [
        "../main.py",
        "/1001/main.py",
        "1001/../../main.py",
        "1001/./main.py",
        "1001//main.py",
        r"1001\main.py",
        "C:/1001/main.py",
        "1001/main.py:stream",
        "１００１/main.py",
        "1001/mai\u0301n.py",
        "1001/main.py\x00.txt",
        "1001/\nmain.py",
    ],
)
def test_unsafe_paths(task_zip, tmp_path, path):
    # NUL is truncated by the ZIP writer; inject it into both name headers afterwards.
    if "\x00" in path:
        data = make_zip([("1001/main.pyX.txt", INERT_SOURCE)])
        submissions = data.replace(b"main.pyX.txt", b"main.py\x00.txt")
    else:
        submissions = make_zip([(path, INERT_SOURCE)])
    assert_rejected(task_zip, submissions, tmp_path, code="unsafe_path")


@pytest.mark.parametrize(
    "path",
    [
        "alice/main.py",
        "01001/main.py",
        "-1/main.py",
        "1001/Main.py",
        "1001/main.exe",
        "1001/nested/module.py",
        "1001/code.zip",
        "1001/main.py ",
        "10000000000000000/main.py",
        "1001/__pycache__/main.pyc",
    ],
)
def test_bad_submission_layout(task_zip, tmp_path, path):
    assert_rejected(task_zip, make_zip([(path, INERT_SOURCE)]), tmp_path)


@pytest.mark.parametrize(
    "mode", [stat.S_IFLNK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFIFO, stat.S_IFSOCK]
)
def test_special_files(task_zip, tmp_path, mode):
    entry = zipfile.ZipInfo("1001/main.py")
    entry.create_system = 3
    entry.external_attr = (mode | 0o777) << 16
    assert_rejected(task_zip, make_zip([(entry, b"target")]), tmp_path, code="special_file")


@pytest.mark.parametrize("duplicate", ["1001/main.py", "1001/MAIN.py"])
def test_duplicate_and_case_collision(task_zip, tmp_path, duplicate):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        data = make_zip([("1001/main.py", INERT_SOURCE), (duplicate, INERT_SOURCE)])
    assert_rejected(task_zip, data, tmp_path, code="duplicate_path")


def test_undeclared_directory(task_zip, tmp_path):
    data = make_zip([("1001/main.py", INERT_SOURCE), ("unexpected/", b"")])
    assert_rejected(task_zip, data, tmp_path, code="archive_layout")


@pytest.mark.parametrize(
    "payload",
    [
        make_zip([("inert.txt", b"data")]),
        b"\x1f\x8brenamed gzip",
        b"BZhrenamed bzip",
        b"\xfd7zXZ\x00renamed xz",
        b"7z\xbc\xaf\x27\x1crenamed 7z",
        b"Rar!renamed rar",
        b"\x00" * 257 + b"ustar",
        b"prefix" + make_zip([("inert.txt", b"data")]),
    ],
)
def test_renamed_nested_archives(task_zip, tmp_path, payload):
    assert_rejected(
        task_zip, make_zip([("1001/main.py", payload)]), tmp_path, code="nested_archive"
    )


@pytest.mark.parametrize(
    "limit, value, code",
    [
        ("archive_bytes", 100, "archive_size"),
        ("entries", 2, "entry_count"),
        ("extracted_bytes", 80, "expanded_size"),
        ("file_bytes", 3, "file_size"),
        ("manifest_bytes", 10, "file_size"),
        ("participants", 1, "submission_count"),
        ("submission_files", 1, "submission_count"),
    ],
)
def test_limits(task_zip, submissions_zip, tmp_path, limit, value, code):
    assert_rejected(
        task_zip,
        submissions_zip,
        tmp_path,
        limits=replace(DEFAULT_LIMITS, **{limit: value}),
        code=code,
    )


def test_compression_bomb(task_zip, tmp_path):
    data = make_zip([("1001/main.py", b"#" * 100_000)], zipfile.ZIP_DEFLATED)
    assert_rejected(task_zip, data, tmp_path, code="compression_ratio")


def test_dishonest_central_count_is_bounded(task_zip, tmp_path):
    data = bytearray(make_zip([(f"1001/m{i}.py", INERT_SOURCE) for i in range(10)]))
    end = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, end + 8, 1, 1)
    assert_rejected(
        task_zip,
        bytes(data),
        tmp_path,
        limits=replace(DEFAULT_LIMITS, entries=4),
        code="entry_count",
    )


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_forged_expanded_size_cannot_hide_data(task_zip, tmp_path, compression):
    payload = b"#" * 100_000
    data = bytearray(make_zip([("1001/main.py", payload)], compression))
    central = data.index(b"PK\x01\x02")
    # Forge the declared size and checksum to match only the first byte. Ordinary
    # ZipExtFile reads can stop there; the validator must check the entire stream.
    struct.pack_into("<I", data, 22, 1)
    struct.pack_into("<I", data, central + 24, 1)
    struct.pack_into("<I", data, 14, zlib.crc32(payload[:1]))
    struct.pack_into("<I", data, central + 16, zlib.crc32(payload[:1]))
    assert_rejected(task_zip, bytes(data), tmp_path, code="invalid_zip")


@pytest.mark.parametrize(
    "mutation", ["truncated", "crc", "local_name", "encrypted", "split", "trailing", "prefix"]
)
def test_corrupt_zip(task_zip, tmp_path, mutation):
    data = bytearray(make_zip([("1001/main.py", INERT_SOURCE)]))
    central = data.index(b"PK\x01\x02")
    if mutation == "truncated":
        data = data[:-5]
    elif mutation == "crc":
        data[data.index(INERT_SOURCE)] ^= 1
    elif mutation == "local_name":
        data[30] = ord("9")
    elif mutation == "encrypted":
        struct.pack_into("<H", data, central + 8, 1)
    elif mutation == "split":
        struct.pack_into("<H", data, data.rfind(b"PK\x05\x06") + 4, 1)
    elif mutation == "trailing":
        data.extend(b"garbage")
    elif mutation == "prefix":
        data = b"stub" + data
    assert_rejected(task_zip, bytes(data), tmp_path)


@pytest.mark.parametrize("compression", [zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA])
def test_unsupported_compression(task_zip, tmp_path, compression):
    assert_rejected(
        task_zip,
        make_zip([("1001/main.py", INERT_SOURCE)], compression),
        tmp_path,
        code="zip_encoding",
    )


def test_zip64_local_entries_rejected(task_zip, tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        with archive.open("1001/main.py", "w", force_zip64=True) as target:
            target.write(INERT_SOURCE)
    assert_rejected(task_zip, stream.getvalue(), tmp_path, code="zip_encoding")


def test_missing_entrypoint(task_zip, tmp_path):
    assert_rejected(
        task_zip, make_zip([("1001/helper.py", INERT_SOURCE)]), tmp_path, code="entrypoint"
    )


@pytest.mark.parametrize(
    "field, value",
    [
        ("language", "cpp"),
        ("entry_file", "other.py"),
        ("input_filename", "../data.in"),
        ("output_filename", "main.py"),
        ("output_filename", "input.txt"),
        ("input_filename", "INPUT.txt"),
        ("comparison", "custom"),
        ("score", 100),
        ("tests", []),
        ("tests", [{"test_id": "01"}] * 101),
        ("tests", [{"test_id": "A"}, {"test_id": "a"}]),
        ("tests", [{"test_id": "../01"}]),
        ("tests", [{"test_id": "01", "points": 1}]),
        ("title", "x" * 161),
    ],
)
def test_manifest_schema(manifest, field, value):
    manifest[field] = value
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(manifest)


@pytest.mark.parametrize(
    "field, value",
    [
        ("time_seconds", 0),
        ("time_seconds", 3.01),
        ("time_seconds", float("nan")),
        ("time_seconds", float("inf")),
        ("time_seconds", "1"),
        ("memory_mb", 257),
        ("memory_mb", True),
        ("memory_mb", 0),
        ("output_bytes", 0),
        ("output_bytes", 1_048_577),
        ("output_bytes", "1024"),
    ],
)
def test_manifest_resource_bounds(manifest, field, value):
    manifest["limits"][field] = value
    with pytest.raises(ValidationError):
        TaskManifest.model_validate(manifest)


@pytest.mark.parametrize(
    "payload", [b"{", b"[]", b"\xff", b'{"task_id":"a","task_id":"b"}', b"[" * 1500]
)
def test_malformed_manifest(submissions_zip, tmp_path, payload):
    assert_rejected(
        make_zip([("challenge/task-config.json", payload)]),
        submissions_zip,
        tmp_path,
        code="manifest",
    )


@pytest.mark.parametrize(
    "mutation", ["missing_manifest", "missing_test", "extra_test", "oversized_output"]
)
def test_task_pair_contract(manifest, submissions_zip, tmp_path, mutation):
    entries = task_entries(manifest)
    if mutation == "missing_manifest":
        entries = entries[1:]
    elif mutation == "missing_test":
        entries = entries[:-1]
    elif mutation == "extra_test":
        entries.append(("challenge/tests/02.in", b"data"))
    else:
        entries[-1] = ("challenge/tests/01.out", b"x" * 1025)
    assert_rejected(make_zip(entries), submissions_zip, tmp_path)


def test_task_path_safety(submissions_zip, tmp_path):
    assert_rejected(
        make_zip([("challenge/../secret.txt", b"inert")]),
        submissions_zip,
        tmp_path,
        code="unsafe_path",
    )


def test_invalid_manifest_prevents_any_extraction(manifest, submissions_zip, tmp_path, monkeypatch):
    manifest["language"] = "javascript"

    def no_workspace(*args, **kwargs):
        pytest.fail("Workspace created before full validation")

    monkeypatch.setattr("contest_check.archives.tempfile.TemporaryDirectory", no_workspace)
    assert_rejected(make_zip(task_entries(manifest)), submissions_zip, tmp_path, code="manifest")


def test_invalid_submissions_prevent_any_extraction(task_zip, tmp_path, monkeypatch):
    def no_workspace(*args, **kwargs):
        pytest.fail("Workspace created before full validation")

    monkeypatch.setattr("contest_check.archives.tempfile.TemporaryDirectory", no_workspace)
    assert_rejected(
        task_zip, make_zip([("../main.py", INERT_SOURCE)]), tmp_path, code="unsafe_path"
    )


def test_real_schema_json_round_trip(manifest):
    value = TaskManifest.model_validate_json(json.dumps(manifest))
    assert value.model_dump() == {**manifest, "title": None}


def test_documented_example_and_schema_match_contract():
    example = Path("examples/task-config.json").read_bytes()
    assert TaskManifest.model_validate_json(example).entry_file == "main.py"
    schema = json.loads(Path("docs/task-config.schema.json").read_text())
    assert schema == TaskManifest.model_json_schema()


def test_empty_archives(task_zip, tmp_path):
    assert_rejected(task_zip, make_zip([]), tmp_path)


def test_no_student_execution(task_zip, tmp_path, monkeypatch):
    def no_execution(*args, **kwargs):
        pytest.fail("No subprocess execution is allowed")

    monkeypatch.setattr("subprocess.Popen", no_execution)
    monkeypatch.setattr("os.system", no_execution)
    # This is deliberately not valid Python syntax; ingestion must never import it.
    with validated_workspace(
        task_zip, make_zip([("0/main.py", b"inert data, not code!")]), temp_parent=tmp_path
    ) as workspace:
        assert workspace.summary.participant_ids == ["0"]
