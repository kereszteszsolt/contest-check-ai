# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
import json
import zipfile

import pytest

INERT_SOURCE = b"# Inert upload fixture; never executed or imported.\n"


def make_zip(entries, compression=zipfile.ZIP_STORED):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return stream.getvalue()


@pytest.fixture
def manifest():
    return {
        "task_id": "addition",
        "language": "python",
        "entry_file": "main.py",
        "input_filename": "input.txt",
        "output_filename": "output.txt",
        "tests": [{"test_id": "01"}],
        "comparison": "exact",
        "limits": {"time_seconds": 1.0, "memory_mb": 128, "output_bytes": 1024},
        "policy": {"max_source_bytes": None, "review_imports": []},
    }


def task_entries(manifest):
    return [
        ("challenge/task-config.json", json.dumps(manifest).encode()),
        ("challenge/tests/01.in", b"1 2\n"),
        ("challenge/tests/01.out", b"3\n"),
    ]


@pytest.fixture
def task_zip(manifest):
    return make_zip(task_entries(manifest))


@pytest.fixture
def submissions_zip():
    return make_zip(
        [
            ("1001/main.py", INERT_SOURCE),
            ("1001/helpers.py", INERT_SOURCE),
            ("1002/main.py", INERT_SOURCE),
        ]
    )
