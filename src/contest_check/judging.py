# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import ast
import base64
import binascii
from pathlib import Path
from typing import Protocol

from contest_check.archives import validated_workspace
from contest_check.judge.contracts import RuntimeResult, WorkerRequest
from contest_check.models import ContestPolicy
from contest_check.results import BatchResult, ParticipantResult, PolicyFinding, TestResult


class WorkerExecutor(Protocol):
    def execute(self, request: WorkerRequest) -> RuntimeResult: ...


def output_matches(actual: bytes, expected: bytes, comparison: str) -> bool:
    if comparison == "exact":
        return actual == expected
    if comparison == "tokens":
        return actual.split() == expected.split()
    raise ValueError("Unsupported comparison.")


def evaluate_policy(sources: dict[str, bytes], policy: ContestPolicy) -> list[PolicyFinding]:
    size = sum(len(content) for content in sources.values())
    if policy.max_source_bytes is not None and size > policy.max_source_bytes:
        return [
            PolicyFinding(
                status="DQ",
                rule="max_source_bytes",
                reason="source_size_exceeded",
                observed_bytes=size,
                limit_bytes=policy.max_source_bytes,
            )
        ]
    findings = []
    if not policy.review_imports:
        return findings
    modules = set()
    unavailable = False
    for source in sources.values():
        try:
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    modules.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules.add(node.module.split(".")[0])
        except (SyntaxError, ValueError, RecursionError, MemoryError):
            unavailable = True
    for module in sorted(modules.intersection(policy.review_imports)):
        findings.append(
            PolicyFinding(
                status="REVIEW",
                rule="review_imports",
                reason="import_requires_review",
                module=module,
            )
        )
    if unavailable:
        findings.append(
            PolicyFinding(
                status="REVIEW",
                rule="review_imports",
                reason="analysis_unavailable",
            )
        )
    return findings


def evaluate_test(request: WorkerRequest, runtime: RuntimeResult, expected: bytes) -> TestResult:
    def result(verdict, reason, *, measured=True):
        return TestResult(
            test_id=request.test_id,
            verdict=verdict,
            reason=reason,
            wall_seconds=runtime.elapsed_seconds if measured else None,
        )

    if runtime.status == "system_error":
        return result("SYSTEM_ERROR", "sandbox_failure", measured=False)
    if runtime.output_base64 is not None and runtime.status != "success":
        return result("SYSTEM_ERROR", "worker_protocol", measured=False)
    if runtime.status == "timeout":
        return result("TLE", "time_limit")
    if runtime.status == "crash":
        return result("RE", "program_exit")
    if runtime.status == "resource":
        # Exit/signal encodings can be chosen by a program. There is no reliable
        # per-test OOM event in this backend, so never invent an MLE verdict.
        reason = {
            "memory_or_exit": "memory_limit_or_exit",
            "output_or_exit": "output_limit_or_exit",
        }.get(runtime.diagnostic, "resource_limit_or_exit")
        return result("RE", reason)
    try:
        if runtime.output_base64 is None or runtime.output_written is None:
            raise ValueError
        actual = base64.b64decode(runtime.output_base64, validate=True)
        if (
            runtime.diagnostic != "completed"
            or runtime.exit_code != 0
            or runtime.signal is not None
            or runtime.output_size_bytes != len(actual)
            or len(actual) > request.task.limits.output_bytes
            or (not runtime.output_written and actual)
        ):
            raise ValueError
    except (ValueError, binascii.Error):
        return result("SYSTEM_ERROR", "worker_protocol", measured=False)
    if not runtime.output_written:
        return result("RE", "missing_output")
    if output_matches(actual, expected, request.task.comparison):
        return result("AC", "output_matched")
    return result("WA", "output_mismatch")


def summarize(participant_id, status, tests, findings, count) -> ParticipantResult:
    return ParticipantResult(
        participant_id=participant_id,
        status=status,
        tests=tests,
        findings=findings,
        passed_tests=sum(test.verdict == "AC" for test in tests),
        failed_tests=sum(test.verdict in {"WA", "TLE", "MLE", "RE"} for test in tests),
        system_errors=sum(test.verdict == "SYSTEM_ERROR" for test in tests),
        not_run_tests=count - len(tests),
    )


def judge_archives(
    task_zip: bytes,
    submissions_zip: bytes,
    worker: WorkerExecutor,
    *,
    temp_parent: Path | None = None,
) -> BatchResult:
    participants = []
    halted = False
    with validated_workspace(task_zip, submissions_zip, temp_parent=temp_parent) as workspace:
        manifest = workspace.manifest
        count = len(manifest.tests)
        for participant_id in workspace.summary.participant_ids:
            if halted:
                participants.append(summarize(participant_id, "not_run", [], [], count))
                continue
            tests = []
            findings = []
            try:
                folder = workspace.root / "submissions" / participant_id
                sources = {path.name: path.read_bytes() for path in sorted(folder.iterdir())}
                findings = evaluate_policy(sources, manifest.policy)
                if any(finding.status == "DQ" for finding in findings):
                    participants.append(summarize(participant_id, "DQ", [], findings, count))
                    continue
                encoded = {name: base64.b64encode(data).decode() for name, data in sources.items()}
                for test in manifest.tests:
                    prefix = workspace.root / "task/challenge/tests" / test.test_id
                    expected = prefix.with_suffix(".out").read_bytes()
                    request = WorkerRequest(
                        participant_id=participant_id,
                        task=manifest,
                        test_id=test.test_id,
                        source_files=encoded,
                        input_base64=base64.b64encode(
                            prefix.with_suffix(".in").read_bytes()
                        ).decode(),
                    )
                    try:
                        runtime = worker.execute(request)
                        if not isinstance(runtime, RuntimeResult):
                            raise ValueError
                        outcome = evaluate_test(request, runtime, expected)
                    except Exception:
                        # A broken adapter is infrastructure failure, never a
                        # contestant failure. Do not expose exception text.
                        outcome = TestResult(
                            test_id=test.test_id, verdict="SYSTEM_ERROR", reason="sandbox_failure"
                        )
                    tests.append(outcome)
                    if outcome.verdict == "SYSTEM_ERROR":
                        halted = True
                        break
            except (OSError, ValueError):
                halted = True
                tests.append(
                    TestResult(
                        test_id=manifest.tests[len(tests)].test_id,
                        verdict="SYSTEM_ERROR",
                        reason="workspace_unavailable",
                    )
                )
            status = "incomplete" if halted else "REVIEW" if findings else "completed"
            participants.append(summarize(participant_id, status, tests, findings, count))
        return BatchResult(
            status="incomplete" if halted else "completed",
            task_id=manifest.task_id,
            comparison=manifest.comparison,
            limits=manifest.limits,
            tests_per_participant=count,
            test_ids=[test.test_id for test in manifest.tests],
            participants=participants,
        )
