# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated, Literal

from pydantic import Field

from contest_check.models import ContractModel, ResourceLimits

Metric = Annotated[float | None, Field(ge=0, allow_inf_nan=False)]
Verdict = Literal["AC", "WA", "TLE", "MLE", "RE", "SYSTEM_ERROR"]
Reason = Literal[
    "output_matched",
    "output_mismatch",
    "missing_output",
    "time_limit",
    "program_exit",
    "memory_limit_or_exit",
    "output_limit_or_exit",
    "resource_limit_or_exit",
    "sandbox_failure",
    "worker_protocol",
    "workspace_unavailable",
]


class TestResult(ContractModel):
    test_id: str
    verdict: Verdict
    reason: Reason
    wall_seconds: Metric = None
    cpu_seconds: Metric = None
    peak_memory_bytes: Annotated[int | None, Field(ge=0)] = None


class PolicyFinding(ContractModel):
    status: Literal["DQ", "REVIEW"]
    rule: Literal["max_source_bytes", "review_imports"]
    reason: Literal["source_size_exceeded", "import_requires_review", "analysis_unavailable"]
    observed_bytes: int | None = None
    limit_bytes: int | None = None
    module: Literal["socket", "subprocess", "ctypes"] | None = None


class ParticipantResult(ContractModel):
    participant_id: str
    status: Literal["completed", "DQ", "REVIEW", "incomplete", "not_run"]
    passed_tests: int
    failed_tests: int
    system_errors: int
    not_run_tests: int
    tests: list[TestResult]
    findings: list[PolicyFinding]


class BatchResult(ContractModel):
    status: Literal["completed", "incomplete"]
    task_id: str
    comparison: Literal["exact", "tokens"]
    limits: ResourceLimits
    tests_per_participant: int
    participants: list[ParticipantResult]
