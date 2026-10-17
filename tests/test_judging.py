# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import json
import signal

import pytest
from conftest import INERT_SOURCE, make_zip
from pydantic import ValidationError

from contest_check.judge.contracts import RuntimeResult, WorkerRequest
from contest_check.judging import evaluate_policy, evaluate_test, judge_archives, output_matches
from contest_check.models import ContestPolicy, TaskManifest


def completed(output=b"3\n", *, written=True, elapsed=0.125):
    return RuntimeResult(
        status="success",
        diagnostic="completed",
        exit_code=0,
        elapsed_seconds=elapsed,
        output_base64=base64.b64encode(output).decode(),
        output_size_bytes=len(output),
        output_written=written,
    )


@pytest.fixture
def worker_request(manifest):
    return WorkerRequest(
        participant_id="1001",
        task=TaskManifest.model_validate(manifest),
        test_id="01",
        source_files={"main.py": base64.b64encode(INERT_SOURCE).decode()},
        input_base64="",
    )


@pytest.mark.parametrize(
    "actual, expected, mode, matches",
    [
        (b"3\n", b"3\n", "exact", True),
        (b"3\r\n", b"3\n", "exact", False),
        (b"3", b"3\n", "exact", False),
        (b" 3\n", b"3\n", "exact", False),
        (b"", b"", "exact", True),
        (b"\xff", b"\xff", "exact", True),
        (b"\xef\xbb\xbf3", b"3", "exact", False),
        (b"  3\t4\r\n", b"3 4\n", "tokens", True),
        (b"3\v4\f", b"3 4", "tokens", True),
        (b"3 4", b"4 3", "tokens", False),
        (b"3.0", b"3", "tokens", False),
        (b"3\xc2\xa04", b"3 4", "tokens", False),
        (b" \n", b"", "tokens", True),
        (b"3 extra", b"3", "tokens", False),
    ],
)
def test_documented_comparison(actual, expected, mode, matches):
    assert output_matches(actual, expected, mode) is matches


def test_unknown_checker_cannot_silently_fall_back():
    with pytest.raises(ValueError):
        output_matches(b"3", b"3", "custom")


@pytest.mark.parametrize(
    "runtime, expected, verdict, reason",
    [
        (completed(), b"3\n", "AC", "output_matched"),
        (completed(b"4\n"), b"3\n", "WA", "output_mismatch"),
        (completed(b"", written=False), b"", "RE", "missing_output"),
        (completed(b""), b"", "AC", "output_matched"),
        (
            RuntimeResult(status="timeout", diagnostic="wall_limit", elapsed_seconds=0.51),
            b"3",
            "TLE",
            "time_limit",
        ),
        (
            RuntimeResult(status="crash", diagnostic="program_exit", elapsed_seconds=0.1),
            b"3",
            "RE",
            "program_exit",
        ),
        (
            RuntimeResult(status="resource", diagnostic="memory_or_exit", exit_code=70),
            b"3",
            "RE",
            "memory_limit_or_exit",
        ),
        (
            RuntimeResult(status="resource", diagnostic="output_or_exit", exit_code=71),
            b"3",
            "RE",
            "output_limit_or_exit",
        ),
        (
            RuntimeResult(status="resource", diagnostic="signal_limit", signal=signal.SIGKILL),
            b"3",
            "RE",
            "resource_limit_or_exit",
        ),
        (
            RuntimeResult(status="system_error", diagnostic="cleanup_failed"),
            b"3",
            "SYSTEM_ERROR",
            "sandbox_failure",
        ),
    ],
)
def test_honest_verdict_mapping(worker_request, runtime, expected, verdict, reason):
    result = evaluate_test(worker_request, runtime, expected)
    assert result.verdict == verdict and result.reason == reason
    assert result.cpu_seconds is None and result.peak_memory_bytes is None
    if verdict == "SYSTEM_ERROR":
        assert result.wall_seconds is None
    else:
        assert result.wall_seconds == runtime.elapsed_seconds


@pytest.mark.parametrize(
    "updates",
    [
        {"output_base64": "!"},
        {"output_base64": None},
        {"output_size_bytes": 99},
        {"output_written": None},
        {"output_written": False},
        {"exit_code": 71},
        {"diagnostic": "sandbox_setup"},
        {"signal": 9},
        {"status": "crash", "diagnostic": "program_exit"},
    ],
)
def test_bad_worker_output_is_system_failure(worker_request, updates):
    result = evaluate_test(worker_request, completed().model_copy(update=updates), b"3\n")
    assert result.verdict == "SYSTEM_ERROR" and result.wall_seconds is None


def test_oversized_capture_is_a_broken_sandbox_contract(worker_request):
    result = evaluate_test(worker_request, completed(b"x" * 1025), b"3")
    assert result.verdict == "SYSTEM_ERROR" and result.reason == "worker_protocol"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0])
def test_unusable_metrics_are_not_accepted(value):
    with pytest.raises(ValidationError):
        RuntimeResult(status="success", diagnostic="completed", elapsed_seconds=value)


def test_policy_is_opt_in_objective_and_records_evidence():
    sources = {"main.py": b"# one", "helper.py": b"# two"}
    assert evaluate_policy(sources, ContestPolicy()) == []
    assert evaluate_policy(sources, ContestPolicy(max_source_bytes=10)) == []
    (finding,) = evaluate_policy(sources, ContestPolicy(max_source_bytes=9))
    assert finding.model_dump(exclude_none=True) == {
        "status": "DQ",
        "rule": "max_source_bytes",
        "reason": "source_size_exceeded",
        "observed_bytes": 10,
        "limit_bytes": 9,
    }


def test_import_suspicion_only_requests_review():
    sources = {"main.py": b"import socket\nfrom ctypes import CDLL\n# import subprocess"}
    assert evaluate_policy(sources, ContestPolicy()) == []
    findings = evaluate_policy(
        sources, ContestPolicy(review_imports=["socket", "ctypes", "subprocess"])
    )
    assert [finding.module for finding in findings] == ["ctypes", "socket"]
    assert all(finding.status == "REVIEW" for finding in findings)


def test_failed_static_analysis_is_never_guilt():
    findings = evaluate_policy(
        {"main.py": b"syntax error!"}, ContestPolicy(review_imports=["socket"])
    )
    assert findings[0].status == "REVIEW" and findings[0].reason == "analysis_unavailable"


@pytest.mark.parametrize(
    "policy",
    [
        {"max_source_bytes": 0},
        {"max_source_bytes": True},
        {"max_source_bytes": 31_457_281},
        {"review_imports": ["os"]},
        {"review_imports": ["socket", "socket"]},
        {"score": 100},
    ],
)
def test_policy_configuration_is_bounded(policy):
    with pytest.raises(ValidationError):
        ContestPolicy.model_validate(policy)


def ordered_task(manifest):
    manifest = {
        **manifest,
        "tests": [{"test_id": "z"}, {"test_id": "a"}],
        "input_filename": "challenge.in",
        "output_filename": "answer.out",
    }
    return make_zip(
        [
            ("challenge/task-config.json", json.dumps(manifest)),
            ("challenge/tests/z.in", b"first-private-input"),
            ("challenge/tests/z.out", b"first-private-expected"),
            ("challenge/tests/a.in", b"second-private-input"),
            ("challenge/tests/a.out", b"second-private-expected"),
        ]
    )


def test_batch_preserves_order_ids_privacy_and_removes_workspace(manifest, tmp_path):
    requests = []

    class Worker:
        def execute(self, worker_request):
            requests.append(worker_request)
            assert worker_request.task.input_filename == "challenge.in"
            assert worker_request.task.output_filename == "answer.out"
            assert "private-expected" not in worker_request.model_dump_json()
            assert base64.b64decode(worker_request.source_files["main.py"]) == INERT_SOURCE
            if worker_request.participant_id == "1001":
                return completed(
                    b"first-private-expected"
                    if worker_request.test_id == "z"
                    else b"second-private-expected"
                )
            return completed(b"wrong")

    submissions = make_zip([("1002/main.py", INERT_SOURCE), ("1001/main.py", INERT_SOURCE)])
    result = judge_archives(ordered_task(manifest), submissions, Worker(), temp_parent=tmp_path)
    assert result.status == "completed"
    assert [(r.participant_id, r.test_id) for r in requests] == [
        ("1001", "z"),
        ("1001", "a"),
        ("1002", "z"),
        ("1002", "a"),
    ]
    assert [base64.b64decode(r.input_base64) for r in requests[:2]] == [
        b"first-private-input",
        b"second-private-input",
    ]
    assert result.participants[0].passed_tests == 2
    assert result.participants[1].failed_tests == 2
    data = result.model_dump_json()
    assert "private" not in data and "source_files" not in data
    assert not {"score", "ranking", "winner"}.intersection(type(result).model_fields)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", ["system_error", "exception", "invalid_response"])
def test_system_failure_stops_the_whole_batch_without_blame(
    manifest, submissions_zip, tmp_path, failure
):
    calls = []

    class Worker:
        def execute(self, worker_request):
            calls.append(worker_request.test_id)
            if failure == "exception":
                raise RuntimeError("PRIVATE_DIAGNOSTIC")
            if failure == "invalid_response":
                return None
            return RuntimeResult(status="system_error", diagnostic="cleanup_failed")

    result = judge_archives(ordered_task(manifest), submissions_zip, Worker(), temp_parent=tmp_path)
    first, second = result.participants
    assert calls == ["z"] and result.status == "incomplete"
    assert first.status == "incomplete" and first.failed_tests == first.passed_tests == 0
    assert first.system_errors == first.not_run_tests == 1
    assert first.tests[0].wall_seconds is None
    assert second.status == "not_run" and second.not_run_tests == 2 and second.tests == []
    assert "PRIVATE" not in result.model_dump_json()
    assert list(tmp_path.iterdir()) == []


def test_invalid_archive_never_reaches_worker(task_zip, tmp_path):
    class Worker:
        def execute(self, worker_request):
            pytest.fail("Invalid uploads must not execute")

    from contest_check.archives import InvalidUpload

    with pytest.raises(InvalidUpload):
        judge_archives(task_zip, b"not ZIP", Worker(), temp_parent=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_incomplete_batch_retains_preceding_results(manifest, submissions_zip, tmp_path):
    calls = []

    class Worker:
        def execute(self, worker_request):
            calls.append((worker_request.participant_id, worker_request.test_id))
            if worker_request.test_id == "z":
                return completed(b"first-private-expected", elapsed=None)
            return RuntimeResult(status="system_error", diagnostic="worker_transport")

    result = judge_archives(ordered_task(manifest), submissions_zip, Worker(), temp_parent=tmp_path)
    assert calls == [("1001", "z"), ("1001", "a")]
    first, second = result.participants
    assert first.passed_tests == first.system_errors == 1
    assert first.failed_tests == first.not_run_tests == 0
    assert [test.verdict for test in first.tests] == ["AC", "SYSTEM_ERROR"]
    assert first.tests[0].wall_seconds is None
    assert second.not_run_tests == 2 and second.tests == []
    assert list(tmp_path.iterdir()) == []


def test_dq_skips_execution_but_review_preserves_official_results(manifest, tmp_path):
    manifest = {**manifest, "policy": {"max_source_bytes": 100, "review_imports": ["socket"]}}
    task = ordered_task(manifest)
    submissions = make_zip(
        [
            ("1001/main.py", b"#" * 101),
            ("1002/main.py", b"import socket\n# inert, never executed"),
        ]
    )
    calls = []

    class Worker:
        def execute(self, worker_request):
            calls.append(worker_request.participant_id)
            return completed(
                b"first-private-expected"
                if worker_request.test_id == "z"
                else b"second-private-expected"
            )

    result = judge_archives(task, submissions, Worker(), temp_parent=tmp_path)
    dq, review = result.participants
    assert result.status == "completed"
    assert dq.status == "DQ" and dq.not_run_tests == 2 and dq.tests == []
    assert dq.findings[0].observed_bytes == 101 and dq.findings[0].limit_bytes == 100
    assert calls == ["1002", "1002"]
    assert review.status == "REVIEW" and review.passed_tests == 2
    assert all(test.verdict == "AC" for test in review.tests)
    assert list(tmp_path.iterdir()) == []
