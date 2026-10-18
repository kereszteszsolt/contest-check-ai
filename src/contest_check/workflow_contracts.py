# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Teacher-only workflow contracts; approval never asserts independent correctness."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from contest_check.authoring_contracts import DraftContext, DraftRequest, ModelChoice, TaskDraft
from contest_check.models import ContractModel
from contest_check.results import TestResult

MAX_ATTEMPTS = 3
MAX_TOOL_CALLS = 6
MAX_REFERENCE_RUNS = 20
UNVERIFIED = "Unverified: generated reference and tests require independent human review."
OpaqueID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Attempt = Annotated[int, Field(ge=1, le=MAX_ATTEMPTS)]
Action = Literal["approve", "revise", "reject"]
ErrorCode = Literal[
    "unknown_model",
    "call_budget",
    "timeout",
    "rate_limit",
    "credentials",
    "provider_error",
    "invalid_output",
    "output_size",
    "transport_policy",
    "tool_budget",
    "invalid_draft",
]


class WorkflowRequest(DraftRequest):
    topic: Annotated[str, Field(min_length=1, max_length=120)]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    run_reference_tests: bool = False

    @model_validator(mode="after")
    def meaningful_topic(self) -> "WorkflowRequest":
        if not self.topic.strip():
            raise ValueError("A topic is required.")
        return self


class ReviewRequest(ContractModel):
    review_id: OpaqueID
    action: Action
    revision: Annotated[str, Field(max_length=2_000)] = ""

    @model_validator(mode="after")
    def explicit_revision(self) -> "ReviewRequest":
        if (self.action == "revise") != bool(self.revision.strip()):
            raise ValueError("Only a revision decision requires revision instructions.")
        if self.action != "revise" and self.revision:
            raise ValueError("Approval/rejection cannot carry revision instructions.")
        return self


class ReferenceCase(ContractModel):
    group: Literal["public", "private"]
    result: TestResult
    observed_output: Annotated[str | None, Field(max_length=2_048)] = None
    output_truncated: bool = False


class ReferenceReport(ContractModel):
    status: Literal["completed", "partial", "blocked", "skipped"]
    reason: Literal[
        "checked", "not_requested", "execution_disabled", "sandbox_failure", "run_budget"
    ]
    cases: Annotated[list[ReferenceCase], Field(max_length=MAX_REFERENCE_RUNS)] = Field(
        default_factory=list
    )
    not_run: Annotated[int, Field(ge=0, le=110)]
    verification: Literal["unverified"] = "unverified"


class ToolRecord(ContractModel):
    attempt: Attempt
    name: Literal["validate_draft", "run_reference_tests"]
    valid: bool | None = None
    reference: ReferenceReport | None = None


class WorkflowError(ContractModel):
    attempt: Attempt
    code: ErrorCode


class ReviewEvent(ContractModel):
    attempt: Attempt
    action: Action


class WorkflowState(ContractModel):
    request: WorkflowRequest
    model: ModelChoice
    draft: TaskDraft | None = None
    revision: DraftContext | None = None
    attempts: Annotated[int, Field(ge=0, le=MAX_ATTEMPTS)] = 0
    model_calls: Annotated[int, Field(ge=0, le=6)] = 0
    tool_calls: Annotated[int, Field(ge=0, le=MAX_TOOL_CALLS)] = 0
    reference_runs: Annotated[int, Field(ge=0, le=MAX_REFERENCE_RUNS)] = 0
    tool_results: Annotated[list[ToolRecord], Field(max_length=MAX_TOOL_CALLS)] = Field(
        default_factory=list
    )
    warnings: Annotated[list[str], Field(max_length=16)] = Field(
        default_factory=lambda: [UNVERIFIED]
    )
    errors: Annotated[list[WorkflowError], Field(max_length=MAX_TOOL_CALLS)] = Field(
        default_factory=list
    )
    reviews: Annotated[list[ReviewEvent], Field(max_length=MAX_ATTEMPTS)] = Field(
        default_factory=list
    )
    status: Literal["generating", "awaiting_review", "approved", "rejected"] = "generating"
    approved: bool = False
    verification: Literal["unverified"] = "unverified"
    review_id: OpaqueID | None = None

    @model_validator(mode="after")
    def coherent_approval(self) -> "WorkflowState":
        if self.approved != (self.status == "approved") or (self.approved and self.draft is None):
            raise ValueError("Inconsistent approval state.")
        if (
            (self.status == "awaiting_review") != (self.review_id is not None)
            or self.tool_calls != len(self.tool_results)
            or self.reference_runs
            != sum(
                len(tool.reference.cases)
                for tool in self.tool_results
                if tool.reference is not None
            )
            or any(
                item.attempt > self.attempts
                for item in [*self.tool_results, *self.errors, *self.reviews]
            )
        ):
            raise ValueError("Inconsistent workflow progress.")
        return self


class WorkflowPreview(ContractModel):
    workflow_id: OpaqueID
    state: WorkflowState
    can_approve: bool
    can_revise: bool


class WorkflowFailure(ValueError):
    ERRORS = {
        "workflow_missing": (404, "The workflow is absent or expired. Start a new workflow."),
        "workflow_capacity": (503, "The local workflow capacity is full. Delete an old workflow."),
        "workflow_busy": (503, "The workflow is already running. Try later."),
        "stale_review": (409, "This review is no longer pending. Read the current preview."),
        "revision_budget": (409, "The workflow generation or tool budget is exhausted."),
        "approval_blocked": (409, "A valid generated draft is required before approval."),
        "workflow_failed": (503, "The workflow stopped unexpectedly. Start a new workflow."),
    }

    def __init__(self, code: str):
        self.code = code
        self.status, self.message = self.ERRORS[code]
        super().__init__(self.message)
