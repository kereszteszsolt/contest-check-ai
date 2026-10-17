# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Shared, source-free table rows for the teacher UI and reports."""

from contest_check.results import BatchResult

SUMMARY_COLUMNS = ["Participant ID", "Status", "Passed", "Failed", "System errors", "Not run"]
TEST_COLUMNS = [
    "Participant ID",
    "Test",
    "Outcome",
    "Verdict",
    "Reason",
    "Wall (s)",
    "CPU (s)",
    "Peak memory (bytes)",
]
DQ_COLUMNS = ["Participant ID", "Rule", "Reason", "Observed source bytes", "Allowed source bytes"]
REVIEW_COLUMNS = ["Participant ID", "Rule", "Reason", "Module"]
REASONS = {
    "output_matched": "Output matched",
    "output_mismatch": "Output differed",
    "missing_output": "Expected output file was not written",
    "time_limit": "Time limit exceeded",
    "program_exit": "Program exited with an error",
    "memory_limit_or_exit": "Memory limit or program-selected exit code",
    "output_limit_or_exit": "Output limit or program-selected exit code",
    "resource_limit_or_exit": "Resource limit or program-selected exit code",
    "sandbox_failure": "Judge infrastructure failed",
    "worker_protocol": "Invalid worker response",
    "workspace_unavailable": "Temporary workspace unavailable",
    "source_size_exceeded": "Configured source-byte limit exceeded",
    "import_requires_review": "Configured import indicator; teacher review required",
    "analysis_unavailable": "Static inspection unavailable; teacher review required",
}
MEASUREMENT_NOTE = (
    "Wall time includes jail setup and bounded termination; worker startup and qualification "
    "are excluded. CPU time and peak memory are N/A when unavailable. "
    "No numeric score or ranking is calculated."
)


def summary_rows(batch: BatchResult) -> list[list]:
    return [
        [
            p.participant_id,
            p.status,
            p.passed_tests,
            p.failed_tests,
            p.system_errors,
            p.not_run_tests,
        ]
        for p in batch.participants
    ]


def test_rows(batch: BatchResult) -> list[list]:
    rows = []
    for participant in batch.participants:
        known = {test.test_id: test for test in participant.tests}
        for test_id in batch.test_ids:
            test = known.get(test_id)
            if test is None:
                reason = (
                    "Disqualified by configured policy"
                    if participant.status == "DQ"
                    else "Batch stopped before this test"
                )
                rows.append(
                    [
                        participant.participant_id,
                        test_id,
                        "Not run",
                        "NOT_RUN",
                        reason,
                        "N/A",
                        "N/A",
                        "N/A",
                    ]
                )
                continue
            outcome = (
                "Pass"
                if test.verdict == "AC"
                else "System error"
                if test.verdict == "SYSTEM_ERROR"
                else "Fail"
            )
            rows.append(
                [
                    participant.participant_id,
                    test_id,
                    outcome,
                    test.verdict,
                    REASONS[test.reason],
                    test.wall_seconds if test.wall_seconds is not None else "N/A",
                    test.cpu_seconds if test.cpu_seconds is not None else "N/A",
                    test.peak_memory_bytes if test.peak_memory_bytes is not None else "N/A",
                ]
            )
    return rows


def policy_rows(batch: BatchResult, status: str) -> list[list]:
    rows = []
    for participant in batch.participants:
        for finding in participant.findings:
            if finding.status != status:
                continue
            tail = (
                [finding.observed_bytes, finding.limit_bytes]
                if status == "DQ"
                else [finding.module or "N/A"]
            )
            rows.append([participant.participant_id, finding.rule, REASONS[finding.reason], *tail])
    return rows
