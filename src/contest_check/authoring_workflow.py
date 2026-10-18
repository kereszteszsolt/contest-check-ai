# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Bounded local LangGraph sessions with explicit, stale-safe teacher decisions."""

import secrets
import threading
import time

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from langsmith import tracing_context
from pydantic import TypeAdapter
from starlette.concurrency import run_in_threadpool

from contest_check.authoring_contracts import DraftContext
from contest_check.authoring_tools import run_reference_tests, validate_draft
from contest_check.model_configuration import ModelSettings, ProviderError
from contest_check.providers import GenerationSession
from contest_check.workflow_contracts import (
    MAX_ATTEMPTS,
    MAX_REFERENCE_RUNS,
    MAX_TOOL_CALLS,
    UNVERIFIED,
    OpaqueID,
    ReviewEvent,
    ReviewRequest,
    ToolRecord,
    WorkflowError,
    WorkflowFailure,
    WorkflowPreview,
    WorkflowRequest,
    WorkflowState,
)

MAX_WORKFLOWS = 8
MAX_CREATIONS = 64
WORKFLOW_TTL_SECONDS = 3_600


def updated(state: WorkflowState, **changes) -> dict:
    return WorkflowState.model_validate(state.model_dump(mode="json") | changes).model_dump(
        mode="json"
    )


class AuthoringWorkflow:
    """One process-lifetime checkpoint and call ledger; never accepts raw graph commands."""

    def __init__(
        self, request: WorkflowRequest, settings: ModelSettings, worker=None, *, workflow_id=None
    ):
        self.request = WorkflowRequest.model_validate(request.model_dump(mode="json"))
        self.session = GenerationSession(settings, request.model_slot)
        self.worker = worker
        self.workflow_id = TypeAdapter(OpaqueID).validate_python(
            workflow_id or secrets.token_hex(16)
        )
        self.created = time.monotonic()
        self.lock = threading.Lock()
        self.tool_calls = 0
        self.reference_runs = 0
        self.failed = False
        self.discarded = threading.Event()
        self.view = None
        # Checkpoints contain application JSON values and LangGraph's safe built-in types.
        self.checkpointer = InMemorySaver(
            serde=JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=[])
        )
        graph = StateGraph(WorkflowState)
        graph.add_node("generate", self._generate)
        graph.add_node("validate_draft", self._validate)
        graph.add_node("run_reference_tests", self._reference)
        graph.add_node("prepare_review", self._prepare_review)
        graph.add_node("teacher_review", self._review)
        graph.add_edge(START, "generate")
        graph.add_conditional_edges(
            "generate",
            lambda state: "validate_draft" if state.draft is not None else "prepare_review",
        )
        graph.add_conditional_edges(
            "validate_draft",
            lambda state: "prepare_review" if self._has_error(state) else "run_reference_tests",
        )
        graph.add_edge("run_reference_tests", "prepare_review")
        graph.add_edge("prepare_review", "teacher_review")
        graph.add_conditional_edges(
            "teacher_review", lambda state: "generate" if state.status == "generating" else END
        )
        self.graph = graph.compile(checkpointer=self.checkpointer)
        self.config = {
            "configurable": {"thread_id": self.workflow_id},
            "callbacks": [],
            "recursion_limit": 24,
        }

    def _ensure_active(self):
        if self.discarded.is_set():
            raise WorkflowFailure("workflow_missing")

    def discard(self):
        self.discarded.set()
        if self.lock.acquire(blocking=False):
            try:
                self._clear_discarded()
            finally:
                self.lock.release()

    def _clear_discarded(self):
        if self.discarded.is_set():
            self.checkpointer.delete_thread(self.workflow_id)
            self.view = None

    @staticmethod
    def _has_error(state):
        return any(error.attempt == state.attempts for error in state.errors)

    def _can_revise(self, state):
        return (
            state.attempts < MAX_ATTEMPTS
            and self.session.budget.used < self.session.budget.maximum
            and self.tool_calls + 2 <= MAX_TOOL_CALLS
        )

    def _can_approve(self, state):
        return (
            state.draft is not None
            and not self._has_error(state)
            and any(
                tool.attempt == state.attempts and tool.name == "validate_draft" and tool.valid
                for tool in state.tool_results
            )
        )

    def _preview(self, state):
        pending = state.status == "awaiting_review"
        return WorkflowPreview(
            workflow_id=self.workflow_id,
            state=state,
            can_approve=pending and self._can_approve(state),
            can_revise=pending and self._can_revise(state),
        )

    async def _generate(self, state):
        self._ensure_active()
        attempt = state.attempts + 1
        if attempt > MAX_ATTEMPTS:
            raise WorkflowFailure("revision_budget")
        context = state.revision or DraftContext(
            topic=self.request.topic, difficulty=self.request.difficulty
        )
        try:
            response = await self.session.generate(self.request.instructions, context=context)
            if (
                response.model != self.session.choice
                or response.calls_used != self.session.budget.used
            ):
                raise ProviderError("invalid_output")
            draft = validate_draft(response.draft)
        except ProviderError as error:
            return updated(
                state,
                attempts=attempt,
                model_calls=self.session.budget.used,
                draft=None,
                revision=None,
                errors=[*state.errors, WorkflowError(attempt=attempt, code=error.code)],
                warnings=[UNVERIFIED],
            )
        except ValueError:
            return updated(
                state,
                attempts=attempt,
                model_calls=self.session.budget.used,
                draft=None,
                revision=None,
                errors=[*state.errors, WorkflowError(attempt=attempt, code="invalid_output")],
                warnings=[UNVERIFIED],
            )
        return updated(
            state,
            draft=draft,
            revision=None,
            attempts=attempt,
            model_calls=self.session.budget.used,
            warnings=[UNVERIFIED, *draft.warnings],
        )

    def _reserve_tool(self):
        self._ensure_active()
        if self.tool_calls >= MAX_TOOL_CALLS:
            raise WorkflowFailure("revision_budget")
        self.tool_calls += 1

    def _validate(self, state):
        self._reserve_tool()
        try:
            validate_draft(state.draft)
            valid = True
        except ValueError:
            valid = False
        record = ToolRecord(attempt=state.attempts, name="validate_draft", valid=valid)
        return updated(
            state,
            tool_calls=self.tool_calls,
            tool_results=[*state.tool_results, record],
            errors=state.errors
            if valid
            else [*state.errors, WorkflowError(attempt=state.attempts, code="invalid_draft")],
        )

    async def _reference(self, state):
        self._reserve_tool()
        report = await run_in_threadpool(
            run_reference_tests,
            state.draft,
            self.worker,
            requested=self.request.run_reference_tests,
            remaining=MAX_REFERENCE_RUNS - self.reference_runs,
        )
        self.reference_runs += len(report.cases)
        warnings = list(state.warnings)
        if report.status != "completed":
            warnings.append(
                f"Reference checks {report.status}: {report.reason}; {report.not_run} not run."
            )
        if any(case.result.verdict != "AC" for case in report.cases):
            warnings.append(
                "Observed reference failures require teacher review; no automatic repair."
            )
        return updated(
            state,
            tool_calls=self.tool_calls,
            reference_runs=self.reference_runs,
            warnings=warnings,
            tool_results=[
                *state.tool_results,
                ToolRecord(attempt=state.attempts, name="run_reference_tests", reference=report),
            ],
        )

    def _prepare_review(self, state):
        self._ensure_active()
        return updated(state, status="awaiting_review", review_id=secrets.token_hex(16))

    def _review(self, state):
        # This node restarts on resume. All model/worker effects belong to earlier nodes.
        decision = interrupt(
            self._preview(state).model_dump(mode="json"), response_schema=ReviewRequest
        )
        decision = ReviewRequest.model_validate(decision.model_dump(mode="json"))
        if decision.review_id != state.review_id:
            raise WorkflowFailure("stale_review")
        if decision.action == "revise" and not self._can_revise(state):
            raise WorkflowFailure("revision_budget")
        if decision.action == "approve" and not self._can_approve(state):
            raise WorkflowFailure("approval_blocked")
        return updated(
            state,
            review_id=None,
            status={"approve": "approved", "reject": "rejected", "revise": "generating"}[
                decision.action
            ],
            approved=decision.action == "approve",
            revision=DraftContext(
                topic=self.request.topic,
                difficulty=self.request.difficulty,
                revision=decision.revision,
                previous_draft=state.draft,
            )
            if decision.action == "revise"
            else None,
            reviews=[*state.reviews, ReviewEvent(attempt=state.attempts, action=decision.action)],
        )

    async def _invoke(self, value):
        try:
            self._ensure_active()
            with tracing_context(enabled=False):
                result = await self.graph.ainvoke(value, config=self.config, durability="sync")
            self._ensure_active()
            data = {key: value for key, value in result.items() if key != "__interrupt__"}
            state = WorkflowState.model_validate(data)
            self.view = self._preview(state)
            return self.view.model_copy(deep=True)
        except Exception:
            self.failed = True
            raise WorkflowFailure(
                "workflow_missing" if self.discarded.is_set() else "workflow_failed"
            ) from None
        except BaseException:
            # An uncertain effect is never retried from a partially completed checkpoint.
            self.failed = True
            raise

    async def start(self):
        if not self.lock.acquire(blocking=False):
            raise WorkflowFailure("workflow_busy")
        try:
            self._ensure_active()
            if self.view is not None or self.failed:
                raise WorkflowFailure("stale_review")
            state = WorkflowState(request=self.request, model=self.session.choice)
            return await self._invoke(state.model_dump(mode="json"))
        finally:
            self.lock.release()
            if self.discarded.is_set():
                self.discard()

    def preview(self):
        self._ensure_active()
        if self.failed:
            raise WorkflowFailure("workflow_failed")
        if self.lock.locked() or self.view is None:
            raise WorkflowFailure("workflow_busy")
        # A caller cannot mutate the authoritative cached preview's nested containers.
        return self.view.model_copy(deep=True)

    async def resume(self, decision: ReviewRequest):
        decision = ReviewRequest.model_validate(decision.model_dump(mode="json"))
        if not self.lock.acquire(blocking=False):
            raise WorkflowFailure("workflow_busy")
        try:
            self._ensure_active()
            if self.failed:
                raise WorkflowFailure("workflow_failed")
            state = self.view.state if self.view is not None else None
            if (
                state is None
                or state.status != "awaiting_review"
                or decision.review_id != state.review_id
            ):
                raise WorkflowFailure("stale_review")
            if decision.action == "revise" and not self._can_revise(state):
                raise WorkflowFailure("revision_budget")
            if decision.action == "approve" and not self._can_approve(state):
                raise WorkflowFailure("approval_blocked")
            return await self._invoke(Command(resume=decision.model_dump(mode="json")))
        finally:
            self.lock.release()
            if self.discarded.is_set():
                self.discard()


class WorkflowStore:
    """Bounded, expiring local memory. IDs are private capabilities, never public URLs."""

    def __init__(self):
        self.workflows = {}
        self.used_ids = {}
        self.lock = threading.RLock()

    def _expire(self):
        for workflow_id, workflow in list(self.workflows.items()):
            if (
                time.monotonic() - workflow.created >= WORKFLOW_TTL_SECONDS
                and not workflow.lock.locked()
            ):
                self.delete(workflow_id)

        self.used_ids = {
            key: created
            for key, created in self.used_ids.items()
            if key in self.workflows or time.monotonic() - created < WORKFLOW_TTL_SECONDS
        }

    def existing_creation(self, workflow_id, request):
        """Replays read state only; retired IDs cannot silently regenerate a task."""
        with self.lock:
            self._expire()
            workflow = self.workflows.get(workflow_id)
            if workflow is not None:
                if workflow.request != request:
                    raise WorkflowFailure("workflow_conflict")
                return workflow
            if workflow_id in self.used_ids:
                raise WorkflowFailure("workflow_missing")
            return None

    def create(self, request, settings, worker=None, *, workflow_id=None):
        with self.lock:
            self._expire()
            if workflow_id is not None and self.existing_creation(workflow_id, request) is not None:
                raise WorkflowFailure("workflow_conflict")
            if len(self.workflows) >= MAX_WORKFLOWS or len(self.used_ids) >= MAX_CREATIONS:
                raise WorkflowFailure("workflow_capacity")
            workflow = AuthoringWorkflow(request, settings, worker, workflow_id=workflow_id)
            self.workflows[workflow.workflow_id] = workflow
            self.used_ids[workflow.workflow_id] = workflow.created
            return workflow

    def get(self, workflow_id):
        with self.lock:
            self._expire()
            if workflow_id not in self.workflows:
                raise WorkflowFailure("workflow_missing")
            return self.workflows[workflow_id]

    def delete(self, workflow_id):
        with self.lock:
            workflow = self.workflows.get(workflow_id)
            if workflow is None:
                raise WorkflowFailure("workflow_missing")
            if workflow.lock.locked():
                raise WorkflowFailure("workflow_busy")
            workflow.checkpointer.delete_thread(workflow_id)
            del self.workflows[workflow_id]

    def discard(self, workflow_id):
        """Retire the ID immediately; a running operation clears its state on exit."""
        with self.lock:
            self._expire()
            if workflow_id not in self.used_ids:
                if len(self.used_ids) >= MAX_CREATIONS:
                    raise WorkflowFailure("workflow_capacity")
                self.used_ids[workflow_id] = time.monotonic()
            workflow = self.workflows.pop(workflow_id, None)
            if workflow is not None:
                workflow.discard()
