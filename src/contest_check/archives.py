# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
import json
import re
import stat
import struct
import tempfile
import zipfile
import zlib
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from contest_check.models import TaskManifest, ValidationSummary
from contest_check.package_contracts import StudentManifest

TEACHER_METADATA = frozenset({"teacher/README.md", "teacher/checks.json"})
TEACHER_REFERENCE = "teacher/reference/main.py"


@dataclass(frozen=True)
class ArchiveLimits:
    archive_bytes: int = 10_485_760
    extracted_bytes: int = 52_428_800
    file_bytes: int = 1_048_576
    manifest_bytes: int = 65_536
    entries: int = 4096
    participants: int = 100
    submission_files: int = 30
    compression_ratio: int = 100


DEFAULT_LIMITS = ArchiveLimits()


class InvalidUpload(ValueError):
    """Only fixed, source-free error messages may cross the API boundary."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def reject(code: str, message: str) -> None:
    raise InvalidUpload(code, message)


def _check_directory(data: bytes, limits: ArchiveLimits) -> None:
    """Bound central-directory allocation before ZipFile constructs ZipInfo objects.

    This deliberately narrow format excludes ZIP64, split archives, prepended stubs
    and trailing data. Both normal stored and deflated ZIP files are supported.
    """
    if len(data) > limits.archive_bytes:
        reject("archive_size", "ZIP exceeds the compressed upload size limit.")
    end = data.rfind(b"PK\x05\x06", max(0, len(data) - 65_557))
    if end < 0 or end + 22 > len(data):
        reject("invalid_zip", "Upload must be a complete, supported ZIP archive.")
    _, disk, start_disk, disk_count, count, size, offset, comment = struct.unpack_from(
        "<4s4H2IH", data, end
    )
    if (
        disk
        or start_disk
        or disk_count != count
        or count == 65_535
        or offset + size != end
        or end + 22 + comment != len(data)
        or not data.startswith(b"PK\x03\x04")
    ):
        reject("invalid_zip", "Split, ZIP64, empty or noncanonical ZIP archives are unsupported.")
    cursor = offset
    observed = 0
    while cursor < end:
        observed += 1
        if observed > limits.entries:
            reject("entry_count", "ZIP contains too many entries.")
        if cursor + 46 > end or data[cursor : cursor + 4] != b"PK\x01\x02":
            reject("invalid_zip", "ZIP central directory is malformed.")
        name_size, extra_size, comment_size = struct.unpack_from("<3H", data, cursor + 28)
        cursor += 46 + name_size + extra_size + comment_size
    if cursor != end or observed != count or not observed:
        reject("invalid_zip", "ZIP central directory is inconsistent.")


def _path(info: zipfile.ZipInfo) -> str:
    name = info.orig_filename
    if (
        name != info.filename
        or not name.isascii()
        or len(name) > 160
        or "\\" in name
        or ":" in name
        or name.startswith("/")
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        reject("unsafe_path", "ZIP contains an unsafe or ambiguous path.")
    path = name.removesuffix("/")
    if not path or any(part in ("", ".", "..") for part in path.split("/")):
        reject("unsafe_path", "ZIP contains an unsafe or ambiguous path.")
    return path


def _is_archive(payload: bytes) -> bool:
    return (
        payload.startswith(
            (
                b"PK\x03\x04",
                b"PK\x05\x06",
                b"PK\x07\x08",
                b"\x1f\x8b",
                b"BZh",
                b"\xfd7zXZ\x00",
                b"7z\xbc\xaf\x27\x1c",
                b"Rar!",
            )
        )
        or payload[257:262] == b"ustar"
        or zipfile.is_zipfile(io.BytesIO(payload))
    )


def _read_payload(archive: zipfile.ZipFile, data: bytes, info: zipfile.ZipInfo) -> bytes:
    # Let zipfile check local names, unsupported flags and overlapping member ranges.
    with archive.open(info):
        pass
    if struct.unpack_from("<H", data, info.header_offset + 4)[0] >= 45:
        reject("zip_encoding", "ZIP64 or newer ZIP entry formats are unsupported.")
    name_size, extra_size = struct.unpack_from("<HH", data, info.header_offset + 26)
    start = info.header_offset + 30 + name_size + extra_size
    compressed = memoryview(data)[start : start + info.compress_size]
    if info.compress_type == zipfile.ZIP_STORED:
        if info.compress_size != info.file_size:
            reject("invalid_zip", "ZIP stored entry has inconsistent sizes.")
        payload = bytes(compressed)
    else:
        # ZipExtFile can truncate at the declared size. Check the real deflate end,
        # bounded to one byte over that size, so a forged size cannot hide expansion.
        decoder = zlib.decompressobj(-15)
        payload = decoder.decompress(compressed, info.file_size + 1)
        if not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            reject("invalid_zip", "ZIP compressed entry has inconsistent sizes or data.")
    if len(payload) != info.file_size or zlib.crc32(payload) != info.CRC:
        reject("invalid_zip", "ZIP entry size or checksum is invalid.")
    return payload


def _read_archive(data: bytes, kind: str, limits: ArchiveLimits) -> dict[str, bytes]:
    if kind not in {"task", "submissions", "student"}:
        reject("archive_layout", "Unsupported archive format.")
    _check_directory(data, limits)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            seen: set[str] = set()
            files: list[tuple[zipfile.ZipInfo, str]] = []
            total = 0
            directories: set[str] = set()
            directory_entries: list[zipfile.ZipInfo] = []
            for info in archive.infolist():
                path = _path(info)
                key = path.casefold()
                if key in seen:
                    reject("duplicate_path", "ZIP contains duplicate or case-ambiguous paths.")
                seen.add(key)
                mode = info.external_attr >> 16
                file_type = stat.S_IFMT(mode)
                allowed_type = stat.S_IFDIR if info.is_dir() else stat.S_IFREG
                if file_type not in (0, allowed_type) or info.external_attr & 0x400:
                    reject("special_file", "ZIP may contain only regular files and directories.")
                if (
                    info.flag_bits & 1
                    or info.extract_version >= 45
                    or info.volume != 0
                    or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                ):
                    reject("zip_encoding", "Encrypted or unsupported ZIP entries are not allowed.")
                if info.is_dir():
                    if info.file_size or info.compress_size > 2:
                        reject("invalid_zip", "ZIP directories must not contain data.")
                    directories.add(path)
                    directory_entries.append(info)
                    continue
                cap = (
                    limits.manifest_bytes
                    if path in {"challenge/task-config.json", "student-manifest.json"}
                    else limits.file_bytes
                )
                if info.file_size > cap or info.compress_size > limits.archive_bytes:
                    reject("file_size", "ZIP entry exceeds the file size limit.")
                total += info.file_size
                if total > limits.extracted_bytes:
                    reject("expanded_size", "ZIP exceeds the total expanded size limit.")
                if info.file_size > max(1, info.compress_size) * limits.compression_ratio:
                    reject("compression_ratio", "ZIP entry exceeds the compression ratio limit.")
                if kind == "task":
                    allowed = (
                        path == "challenge/task-config.json"
                        or re.fullmatch(
                            r"challenge/tests/[A-Za-z0-9][A-Za-z0-9_-]{0,31}\.(in|out)", path
                        )
                        or path in TEACHER_METADATA
                        or path == TEACHER_REFERENCE
                    )
                elif kind == "student":
                    allowed = path in {
                        "problem.pdf",
                        "README.md",
                        "student-manifest.json",
                        "starter/main.py",
                        "FONT-LICENSE.txt",
                    } or re.fullmatch(r"examples/sample(?:-0[2-9]|-10)?\.(in|out)", path)
                else:
                    allowed = re.fullmatch(
                        r"(0|[1-9][0-9]{0,15})/[A-Za-z_][A-Za-z0-9_]{0,63}\.py", path
                    )
                if not allowed:
                    reject(
                        "archive_layout", "ZIP contains an unsupported filename or folder layout."
                    )
                files.append((info, path))
            ancestors = {
                "/".join(path.split("/")[:index])
                for _, path in files
                for index in range(1, len(path.split("/")))
            }
            if not directories <= ancestors or any(path in ancestors for _, path in files):
                reject("archive_layout", "ZIP contains unexpected or conflicting directories.")
            # Verify every payload/CRC in bounded memory before creating an extraction directory.
            payloads: dict[str, bytes] = {}
            actual_total = 0
            for info in directory_entries:
                _read_payload(archive, data, info)
            for info, path in files:
                payload = _read_payload(archive, data, info)
                actual_total += len(payload)
                if len(payload) != info.file_size or actual_total > limits.extracted_bytes:
                    reject("expanded_size", "ZIP content exceeds its declared or permitted size.")
                if _is_archive(payload):
                    reject(
                        "nested_archive",
                        "Nested archives, including renamed archives, are not allowed.",
                    )
                payloads[path] = payload
            if not payloads:
                reject("archive_layout", "ZIP must contain the required files.")
            return payloads
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        NotImplementedError,
        RuntimeError,
        EOFError,
        OSError,
        ValueError,
        zlib.error,
    ) as exc:
        if isinstance(exc, InvalidUpload):
            raise
        raise InvalidUpload("invalid_zip", "ZIP data is corrupt or unsupported.") from None


def _unique_json(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _manifest(files: dict[str, bytes], limits: ArchiveLimits) -> TaskManifest:
    raw = files.get("challenge/task-config.json")
    if raw is None or len(raw) > limits.manifest_bytes:
        reject("manifest", "Task ZIP requires a bounded challenge/task-config.json.")
    try:
        manifest = TaskManifest.model_validate(
            json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json)
        )
    except (ValidationError, ValueError, UnicodeError, RecursionError):
        raise InvalidUpload(
            "manifest", "Task manifest does not match the documented schema."
        ) from None
    required = {"challenge/task-config.json"}
    for test in manifest.tests:
        for suffix in ("in", "out"):
            name = f"challenge/tests/{test.test_id}.{suffix}"
            required.add(name)
            if suffix == "out" and len(files.get(name, b"")) > manifest.limits.output_bytes:
                reject(
                    "test_output_size", "Expected test output exceeds the manifest output limit."
                )
    extra = set(files) - required
    if extra and not (
        TEACHER_METADATA <= extra and extra <= TEACHER_METADATA | {TEACHER_REFERENCE}
    ):
        reject("task_tests", "Task ZIP contains unsupported or incomplete teacher metadata.")
    if not required <= files.keys():
        reject("task_tests", "Task ZIP must contain exactly the declared input/output test pairs.")
    return manifest


def validate_export_archive(data: bytes, audience: str) -> None:
    """Apply the ingestion safety checks to generated ZIP bytes, without extraction."""
    if audience == "teacher":
        _manifest(_read_archive(data, "task", DEFAULT_LIMITS), DEFAULT_LIMITS)
        return
    if audience != "student":
        reject("archive_layout", "Unsupported archive format.")
    files = _read_archive(data, "student", DEFAULT_LIMITS)
    try:
        manifest = StudentManifest.model_validate(
            json.loads(files["student-manifest.json"].decode(), object_pairs_hook=_unique_json)
        )
    except (KeyError, ValueError, UnicodeError, RecursionError):
        reject("manifest", "Student manifest does not match the documented schema.")
    required = {
        "problem.pdf",
        "README.md",
        "student-manifest.json",
        "starter/main.py",
        "FONT-LICENSE.txt",
    }
    for pair in manifest.examples:
        required.update((pair.input_file, pair.output_file))
        if len(files.get(pair.output_file, b"")) > manifest.limits.output_bytes:
            reject("test_output_size", "Example output exceeds the task output limit.")
    if set(files) != required:
        reject("archive_layout", "Student ZIP must contain exactly its declared public files.")


@dataclass(frozen=True)
class ValidatedWorkspace:
    root: Path
    manifest: TaskManifest
    summary: ValidationSummary


@contextmanager
def validated_workspace(
    task_zip: bytes,
    submissions_zip: bytes,
    *,
    limits: ArchiveLimits = DEFAULT_LIMITS,
    temp_parent: Path | None = None,
) -> Iterator[ValidatedWorkspace]:
    """Validate both archives completely, then extract privately; always remove on exit."""
    task = _read_archive(task_zip, "task", limits)
    manifest = _manifest(task, limits)
    submissions = _read_archive(submissions_zip, "submissions", limits)
    counts = Counter(path.split("/")[0] for path in submissions)
    if len(counts) > limits.participants or any(
        n > limits.submission_files for n in counts.values()
    ):
        reject("submission_count", "ZIP exceeds the participant or per-participant file limit.")
    if any(f"{participant}/main.py" not in submissions for participant in counts):
        reject("entrypoint", "Each participant folder requires exactly one main.py.")
    summary = ValidationSummary(
        task_id=manifest.task_id,
        test_count=len(manifest.tests),
        participant_ids=sorted(counts),
        submission_file_count=len(submissions),
        extracted_bytes=sum(len(content) for content in (*task.values(), *submissions.values())),
    )
    # mkdtemp is private (0700) independently of the operator's umask.
    with tempfile.TemporaryDirectory(prefix="cca-validate-", dir=temp_parent) as directory:
        root = Path(directory)
        for group, files in (("task", task), ("submissions", submissions)):
            for name, payload in files.items():
                target = root / group / name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with target.open("xb") as destination:
                    target.chmod(0o600)
                    destination.write(payload)
        yield ValidatedWorkspace(root, manifest, summary)
