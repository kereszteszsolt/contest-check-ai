# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64

import pytest
from pydantic import ValidationError

from contest_check.authoring_contracts import TaskDraft
from contest_check.authoring_tools import run_reference_tests, validate_draft
from contest_check.judge.contracts import RuntimeResult, decode_file


def success(output):
    return RuntimeResult(
        status="success",
        diagnostic="completed",
        elapsed_seconds=0.1,
        exit_code=0,
        output_base64=base64.b64encode(output).decode(),
        output_size_bytes=len(output),
        output_written=True,
    )


class MockWorker:
    """Returns fixture metadata; never imports or executes submitted source."""

    def __init__(self, results):
        self.results = iter(results)
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        result = next(self.results)
        if isinstance(result, Exception):
            raise result
        return result


def test_public_private_checks_and_teacher_outputs_stay_out_of_worker(draft_data):
    draft_data["private_tests"][0]["expected_output"] = "PRIVATE_EXPECTED"
    worker = MockWorker([success(b"3\n"), success(b"different\n")])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=20
    )
    assert report.status == "completed" and report.not_run == 0
    assert report.verification == "unverified"
    assert [(case.group, case.result.verdict) for case in report.cases] == [
        ("public", "AC"),
        ("private", "WA"),
    ]
    assert report.cases[1].observed_output == "different\n"
    assert len(worker.requests) == 2
    for request in worker.requests:
        assert request.participant_id == "0" and set(request.source_files) == {"main.py"}
        assert decode_file(request.source_files["main.py"]) == b"# INERT_REFERENCE\n"
        assert "PRIVATE_EXPECTED" not in request.model_dump_json()
        assert request.task.limits == TaskDraft.model_validate(draft_data).limits
    assert decode_file(worker.requests[1].input_base64) == b"3 4\n"


@pytest.mark.parametrize(
    "runtime,verdict,reason",
    [
        (success(b"7\n"), "AC", "output_matched"),
        (success(b"wrong\n"), "WA", "output_mismatch"),
        (
            RuntimeResult(status="timeout", diagnostic="wall_limit", elapsed_seconds=0.5),
            "TLE",
            "time_limit",
        ),
        (
            RuntimeResult(status="resource", diagnostic="memory_or_exit"),
            "RE",
            "memory_limit_or_exit",
        ),
        (
            RuntimeResult(status="resource", diagnostic="output_or_exit"),
            "RE",
            "output_limit_or_exit",
        ),
        (RuntimeResult(status="crash", diagnostic="program_exit"), "RE", "program_exit"),
    ],
)
def test_reference_uses_existing_verdict_comparison(draft_data, runtime, verdict, reason):
    worker = MockWorker([success(b"3\n"), runtime])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=20
    )
    assert report.cases[-1].result.verdict == verdict
    assert report.cases[-1].result.reason == reason
    assert report.verification == "unverified"


@pytest.mark.parametrize(
    "runtime",
    [
        RuntimeResult(status="system_error", diagnostic="sandbox_unavailable"),
        RuntimeResult(status="success", diagnostic="completed", output_base64="malformed"),
        OSError("PRIVATE_WORKER_ERROR"),
        object(),
    ],
)
def test_unavailable_or_invalid_worker_halts_without_fallback(draft_data, runtime):
    worker = MockWorker([runtime])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=20
    )
    assert report.status == "blocked" and report.reason == "sandbox_failure"
    assert report.not_run == 1 and len(worker.requests) == 1
    assert report.cases[0].result.verdict == "SYSTEM_ERROR"
    assert report.cases[0].observed_output is None
    assert "PRIVATE" not in report.model_dump_json()


@pytest.mark.parametrize(
    "requested,worker_present,remaining,reason",
    [
        (False, True, 20, "not_requested"),
        (True, False, 20, "execution_disabled"),
        (True, True, 0, "run_budget"),
    ],
)
def test_reference_requires_opt_in_worker_and_budget(
    draft_data, requested, worker_present, remaining, reason
):
    worker = MockWorker([])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data),
        worker if worker_present else None,
        requested=requested,
        remaining=remaining,
    )
    assert report.reason == reason and report.not_run == 2 and not report.cases
    assert not worker.requests


def test_reference_budget_reports_all_unrun_cases(draft_data):
    worker = MockWorker([success(b"3\n")])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=1
    )
    assert report.status == "partial" and report.reason == "run_budget"
    assert report.not_run == 1 and len(report.cases) == 1


@pytest.mark.parametrize("remaining", [-1, 21, True])
def test_invalid_tool_run_budget_cannot_expand_execution(draft_data, remaining):
    worker = MockWorker([])
    with pytest.raises(ValueError, match="run budget"):
        run_reference_tests(
            TaskDraft.model_validate(draft_data), worker, requested=True, remaining=remaining
        )
    assert not worker.requests


def test_invalid_worker_metric_halts_as_protocol_failure(draft_data):
    runtime = success(b"3\n").model_copy(update={"elapsed_seconds": 4_000.0})
    worker = MockWorker([runtime])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=20
    )
    assert report.status == "blocked" and report.cases[0].result.reason == "worker_protocol"
    assert len(worker.requests) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_filename", "../../secret.txt"),
        ("output_filename", "/tmp/out.txt"),
        ("output_filename", "https://example.invalid/out.txt"),
        ("entry_file", "other.py"),
        ("output_filename", "input.txt"),
    ],
)
def test_unsafe_constructed_draft_is_revalidated_before_worker(draft_data, field, value):
    draft = TaskDraft.model_validate(draft_data).model_copy(update={field: value})
    worker = MockWorker([])
    with pytest.raises(ValidationError):
        run_reference_tests(draft, worker, requested=True, remaining=20)
    assert not worker.requests


def test_nested_draft_mutation_is_rejected(draft_data):
    draft = TaskDraft.model_validate(draft_data)
    draft.private_tests.append(draft.private_tests[0])
    with pytest.raises(ValidationError):
        validate_draft(draft)


def test_observed_output_preview_is_bounded_without_affecting_verdict(draft_data):
    draft_data["limits"]["output_bytes"] = 8_192
    worker = MockWorker([success(b"x" * 4_000), success(b"7\n")])
    report = run_reference_tests(
        TaskDraft.model_validate(draft_data), worker, requested=True, remaining=20
    )
    assert report.cases[0].result.verdict == "WA"
    assert len(report.cases[0].observed_output) == 2_048
    assert report.cases[0].output_truncated
