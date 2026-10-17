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


@pytest.fixture
def report_batch():
    from contest_check.results import BatchResult

    def test(test_id, verdict="AC"):
        return {
            "test_id": test_id,
            "verdict": verdict,
            "reason": "output_matched" if verdict == "AC" else "output_mismatch",
            "wall_seconds": 0.125,
        }

    return BatchResult.model_validate(
        {
            "status": "completed",
            "task_id": "addition",
            "comparison": "exact",
            "limits": {"time_seconds": 0.5, "memory_mb": 128, "output_bytes": 1024},
            "tests_per_participant": 2,
            "test_ids": ["z", "a"],
            "participants": [
                {
                    "participant_id": "1001",
                    "status": "completed",
                    "passed_tests": 1,
                    "failed_tests": 1,
                    "system_errors": 0,
                    "not_run_tests": 0,
                    "tests": [test("z"), test("a", "WA")],
                    "findings": [],
                },
                {
                    "participant_id": "1002",
                    "status": "REVIEW",
                    "passed_tests": 2,
                    "failed_tests": 0,
                    "system_errors": 0,
                    "not_run_tests": 0,
                    "tests": [test("z"), test("a")],
                    "findings": [
                        {
                            "status": "REVIEW",
                            "rule": "review_imports",
                            "reason": "import_requires_review",
                            "module": "socket",
                        }
                    ],
                },
                {
                    "participant_id": "1003",
                    "status": "DQ",
                    "passed_tests": 0,
                    "failed_tests": 0,
                    "system_errors": 0,
                    "not_run_tests": 2,
                    "tests": [],
                    "findings": [
                        {
                            "status": "DQ",
                            "rule": "max_source_bytes",
                            "reason": "source_size_exceeded",
                            "observed_bytes": 2048,
                            "limit_bytes": 1024,
                        }
                    ],
                },
            ],
        }
    )
