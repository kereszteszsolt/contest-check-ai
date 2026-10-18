# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Two fixed authoring tools. No shell, paths, fetching or model-directed dispatch."""

import base64

from contest_check.authoring_contracts import TaskDraft
from contest_check.judge.contracts import RuntimeResult, WorkerRequest, decode_file
from contest_check.judging import WorkerExecutor, evaluate_test
from contest_check.models import TaskManifest
from contest_check.results import TestResult
from contest_check.workflow_contracts import MAX_REFERENCE_RUNS, ReferenceCase, ReferenceReport

TOOL_ALLOWLIST = frozenset({"validate_draft", "run_reference_tests"})


def validate_draft(draft: TaskDraft) -> TaskDraft:
    # Revalidate even a constructed model or a mutated nested list before any worker call.
    return TaskDraft.model_validate(draft.model_dump(mode="json"))


def run_reference_tests(
    draft: TaskDraft, worker: WorkerExecutor | None, *, requested: bool, remaining: int
) -> ReferenceReport:
    """Only the injected operator worker may run code; expected outputs stay here."""
    if type(remaining) is not int or not 0 <= remaining <= MAX_REFERENCE_RUNS:
        raise ValueError("Invalid reference run budget.")
    draft = validate_draft(draft)
    cases = [
        ("public", f"example_{index}", case.input, case.output)
        for index, case in enumerate(draft.examples, 1)
    ] + [
        ("private", case.test_id, case.input, case.expected_output) for case in draft.private_tests
    ]
    if not requested or worker is None or remaining <= 0:
        return ReferenceReport(
            status="skipped" if not requested or remaining <= 0 else "blocked",
            reason=(
                "not_requested"
                if not requested
                else "execution_disabled"
                if worker is None
                else "run_budget"
            ),
            not_run=len(cases),
        )
    outcomes = []
    for group, test_id, input_text, expected in cases[:remaining]:
        manifest = TaskManifest.model_validate(
            {
                key: value
                for key, value in draft.model_dump(mode="json").items()
                if key
                in {
                    "task_id",
                    "title",
                    "language",
                    "entry_file",
                    "input_filename",
                    "output_filename",
                    "comparison",
                    "limits",
                }
            }
            | {"tests": [{"test_id": test_id}]}
        )
        request = WorkerRequest(
            participant_id="0",
            task=manifest,
            test_id=test_id,
            source_files={"main.py": base64.b64encode(draft.reference_source.encode()).decode()},
            input_base64=base64.b64encode(input_text.encode()).decode(),
        )
        try:
            runtime = worker.execute(request)
            # Never trust a worker adapter to have returned a valid Pydantic instance.
            runtime = RuntimeResult.model_validate(runtime.model_dump(mode="json"))
        except Exception:
            runtime = RuntimeResult(status="system_error", diagnostic="worker_protocol")
        try:
            result = evaluate_test(request, runtime, expected.encode())
        except ValueError:
            result = TestResult(test_id=test_id, verdict="SYSTEM_ERROR", reason="worker_protocol")
        observed = None
        truncated = False
        if result.verdict in {"AC", "WA"}:
            raw = decode_file(runtime.output_base64)
            observed = raw[:2_048].decode("utf-8", errors="replace")
            truncated = len(raw) > 2_048
        outcomes.append(
            ReferenceCase(
                group=group, result=result, observed_output=observed, output_truncated=truncated
            )
        )
        if result.verdict == "SYSTEM_ERROR":
            return ReferenceReport(
                status="blocked",
                reason="sandbox_failure",
                cases=outcomes,
                not_run=len(cases) - len(outcomes),
            )
    return ReferenceReport(
        status="completed" if len(outcomes) == len(cases) else "partial",
        reason="checked" if len(outcomes) == len(cases) else "run_budget",
        cases=outcomes,
        not_run=len(cases) - len(outcomes),
    )
