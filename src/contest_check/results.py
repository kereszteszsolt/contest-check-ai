# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated, Literal

from pydantic import Field, model_validator

from contest_check.models import ContractModel, ResourceLimits

Metric = Annotated[float | None, Field(ge=0, le=3600, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=0, le=100)]
TestID = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")]
ParticipantID = Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,15})$")]
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
    test_id: TestID
    verdict: Verdict
    reason: Reason
    wall_seconds: Metric = None
    cpu_seconds: Metric = None
    peak_memory_bytes: Annotated[int | None, Field(ge=0, le=2**63 - 1)] = None


class PolicyFinding(ContractModel):
    status: Literal["DQ", "REVIEW"]
    rule: Literal["max_source_bytes", "review_imports"]
    reason: Literal["source_size_exceeded", "import_requires_review", "analysis_unavailable"]
    observed_bytes: Annotated[int | None, Field(ge=0, le=30 * 1_048_576)] = None
    limit_bytes: Annotated[int | None, Field(ge=1, le=30 * 1_048_576)] = None
    module: Literal["socket", "subprocess", "ctypes"] | None = None

    @model_validator(mode="after")
    def coherent_evidence(self) -> "PolicyFinding":
        if self.status == "DQ":
            valid = (
                self.rule == "max_source_bytes"
                and self.reason == "source_size_exceeded"
                and self.observed_bytes is not None
                and self.limit_bytes is not None
                and self.observed_bytes > self.limit_bytes
                and self.module is None
            )
        else:
            valid = (
                self.rule == "review_imports"
                and self.observed_bytes is None
                and self.limit_bytes is None
                and (
                    (self.reason == "import_requires_review" and self.module is not None)
                    or (self.reason == "analysis_unavailable" and self.module is None)
                )
            )
        if not valid:
            raise ValueError("Policy evidence is inconsistent.")
        return self


class ParticipantResult(ContractModel):
    participant_id: ParticipantID
    status: Literal["completed", "DQ", "REVIEW", "incomplete", "not_run"]
    passed_tests: Count
    failed_tests: Count
    system_errors: Annotated[int, Field(ge=0, le=1)]
    not_run_tests: Count
    tests: Annotated[list[TestResult], Field(max_length=100)]
    findings: Annotated[list[PolicyFinding], Field(max_length=4)]

    @model_validator(mode="after")
    def coherent_counts(self) -> "ParticipantResult":
        if (
            self.passed_tests != sum(t.verdict == "AC" for t in self.tests)
            or self.failed_tests != sum(t.verdict in {"WA", "TLE", "MLE", "RE"} for t in self.tests)
            or self.system_errors != sum(t.verdict == "SYSTEM_ERROR" for t in self.tests)
            or len({t.test_id for t in self.tests}) != len(self.tests)
        ):
            raise ValueError("Test counts are inconsistent.")
        dq = any(f.status == "DQ" for f in self.findings)
        review = any(f.status == "REVIEW" for f in self.findings)
        valid = {
            "DQ": dq and not review and not self.tests,
            "REVIEW": review and not dq and not self.system_errors and not self.not_run_tests,
            "completed": not self.findings and not self.system_errors and not self.not_run_tests,
            "incomplete": not dq
            and self.system_errors == 1
            and bool(self.tests)
            and self.tests[-1].verdict == "SYSTEM_ERROR",
            "not_run": not self.tests and not self.findings,
        }[self.status]
        if not valid:
            raise ValueError("Participant state is inconsistent.")
        return self


class BatchResult(ContractModel):
    status: Literal["completed", "incomplete"]
    task_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
    comparison: Literal["exact", "tokens"]
    limits: ResourceLimits
    tests_per_participant: Annotated[int, Field(ge=1, le=100)]
    test_ids: Annotated[list[TestID], Field(min_length=1, max_length=100)]
    participants: Annotated[list[ParticipantResult], Field(min_length=1, max_length=100)]

    @model_validator(mode="after")
    def coherent_batch(self) -> "BatchResult":
        if (
            len(self.test_ids) != self.tests_per_participant
            or len({test.casefold() for test in self.test_ids}) != len(self.test_ids)
            or len({p.participant_id for p in self.participants}) != len(self.participants)
        ):
            raise ValueError("Batch identifiers/counts are inconsistent.")
        stopped = False
        for participant in self.participants:
            if (
                len(participant.tests) + participant.not_run_tests != self.tests_per_participant
                or [t.test_id for t in participant.tests] != self.test_ids[: len(participant.tests)]
                or (stopped and participant.status != "not_run")
                or (not stopped and participant.status == "not_run")
            ):
                raise ValueError("Batch progress is inconsistent.")
            if participant.status == "incomplete":
                stopped = True
        if (self.status == "incomplete") != stopped:
            raise ValueError("Batch completion is inconsistent.")
        return self
