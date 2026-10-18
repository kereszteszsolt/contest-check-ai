# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import asyncio
from dataclasses import replace

import pytest
from pydantic import ValidationError
from test_authoring_tools import MockWorker, success

from contest_check.authoring_contracts import DraftResponse, TaskDraft
from contest_check.authoring_workflow import AuthoringWorkflow, WorkflowStore
from contest_check.model_configuration import ProviderError, load_model_settings
from contest_check.workflow_contracts import (
    ReviewRequest,
    WorkflowFailure,
    WorkflowRequest,
    WorkflowState,
)


@pytest.fixture
def generation(draft_data, monkeypatch):
    calls = []

    async def generate(session, instructions, *, context):
        session.budget.reserve()
        calls.append((instructions, context))
        return DraftResponse(
            model=session.choice,
            draft=TaskDraft.model_validate(draft_data),
            calls_used=session.budget.used,
        )

    monkeypatch.setattr("contest_check.authoring_workflow.GenerationSession.generate", generate)
    return calls


def workflow(*, worker=None, requested=False, max_calls=6):
    return AuthoringWorkflow(
        WorkflowRequest(
            model_slot="ollama:1",
            instructions="Create an addition exercise.",
            topic="integer arithmetic",
            difficulty="beginner",
            run_reference_tests=requested,
        ),
        replace(load_model_settings({"OLLAMA_MODEL_1": "fixture:1"}), max_calls=max_calls),
        worker,
    )


def decision(preview, action, revision=""):
    return ReviewRequest(review_id=preview.state.review_id, action=action, revision=revision)


def test_actual_graph_checkpoint_preview_and_approval_do_not_repeat_effects(generation):
    worker = MockWorker([success(b"3\n"), success(b"7\n")])
    run = workflow(worker=worker, requested=True)

    async def scenario():
        preview = await run.start()
        assert preview.state.status == "awaiting_review" and not preview.state.approved
        assert preview.state.model_calls == 1 and preview.state.tool_calls == 2
        assert preview.state.reference_runs == 2
        snapshot = await run.graph.aget_state(run.config)
        assert snapshot.next == ("teacher_review",)
        pending = snapshot.tasks[0].interrupts[0]
        assert pending.value == preview.model_dump(mode="json")
        assert pending.response_schema == ReviewRequest.model_json_schema()
        assert list(run.checkpointer.list(run.config))
        assert preview == run.preview()
        approved = await run.resume(decision(preview, "approve"))
        assert approved.state.status == "approved" and approved.state.approved
        assert approved.state.verification == "unverified"
        assert approved.state.review_id is None and not approved.can_revise
        assert (await run.graph.aget_state(run.config)).next == ()
        with pytest.raises(WorkflowFailure) as caught:
            await run.resume(decision(preview, "approve"))
        assert caught.value.code == "stale_review"
        assert len(generation) == 1 and len(worker.requests) == 2

    asyncio.run(scenario())


def test_revision_carries_prior_draft_and_gets_new_review_identity(generation):
    run = workflow()

    async def scenario():
        first = await run.start()
        second = await run.resume(decision(first, "revise", "Explain negative integers."))
        assert second.state.attempts == second.state.model_calls == 2
        assert second.state.tool_calls == 4 and second.state.review_id != first.state.review_id
        assert generation[1][1].previous_draft == first.state.draft
        assert generation[1][1].revision == "Explain negative integers."
        assert generation[1][1].topic == "integer arithmetic"
        with pytest.raises(WorkflowFailure, match="no longer pending"):
            await run.resume(decision(first, "reject"))
        rejected = await run.resume(decision(second, "reject"))
        assert rejected.state.status == "rejected" and not rejected.state.approved
        assert [review.action for review in rejected.state.reviews] == ["revise", "reject"]
        assert len(generation) == 2

    asyncio.run(scenario())


def test_generation_and_tool_budgets_survive_revision(generation):
    run = workflow()

    async def scenario():
        preview = await run.start()
        for _ in range(2):
            preview = await run.resume(decision(preview, "revise", "Improve the wording."))
        assert not preview.can_revise
        assert preview.state.attempts == 3 and preview.state.tool_calls == 6
        with pytest.raises(WorkflowFailure) as caught:
            await run.resume(decision(preview, "revise", "One more."))
        assert caught.value.code == "revision_budget"
        assert run.preview() == preview
        assert len(generation) == 3
        assert (await run.resume(decision(preview, "reject"))).state.status == "rejected"

    asyncio.run(scenario())


def test_operator_model_budget_takes_precedence(generation):
    run = workflow(max_calls=1)

    async def scenario():
        preview = await run.start()
        assert not preview.can_revise
        with pytest.raises(WorkflowFailure) as caught:
            await run.resume(decision(preview, "revise", "Again."))
        assert caught.value.code == "revision_budget" and len(generation) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("code", ["timeout", "invalid_output", "output_size", "credentials"])
def test_provider_failure_is_reviewable_without_retry_or_invalid_approval(code, monkeypatch):
    async def fail(session, instructions, **kwargs):
        session.budget.reserve()
        raise ProviderError(code)

    monkeypatch.setattr("contest_check.authoring_workflow.GenerationSession.generate", fail)
    run = workflow()

    async def scenario():
        preview = await run.start()
        assert preview.state.errors[0].code == code and preview.state.model_calls == 1
        assert preview.state.draft is None and not preview.can_approve
        assert not preview.state.tool_results and preview.can_revise
        with pytest.raises(WorkflowFailure) as caught:
            await run.resume(decision(preview, "approve"))
        assert caught.value.code == "approval_blocked"
        assert (await run.resume(decision(preview, "reject"))).state.status == "rejected"
        assert run.session.budget.used == 1

    asyncio.run(scenario())


def test_failed_attempt_remains_in_history_after_explicit_revision(generation, monkeypatch):
    run = workflow()
    normal = run.session.generate

    async def fail_once(instructions, **kwargs):
        run.session.budget.reserve()
        raise ProviderError("timeout")

    async def scenario():
        with monkeypatch.context() as scoped:
            scoped.setattr(run.session, "generate", fail_once)
            first = await run.start()
        assert run.session.generate == normal
        second = await run.resume(decision(first, "revise", "Try a smaller exercise."))
        assert second.can_approve and second.state.model_calls == 2
        assert second.state.errors[0].code == "timeout"
        assert len(generation) == 1

    asyncio.run(scenario())


def test_mismatch_and_disabled_reference_always_remain_unverified(generation):
    async def scenario():
        worker = MockWorker([success(b"wrong"), success(b"7\n")])
        run = workflow(worker=worker, requested=True)
        preview = await run.start()
        assert preview.state.tool_results[-1].reference.cases[0].result.verdict == "WA"
        assert any("Observed reference failures" in warning for warning in preview.state.warnings)
        assert len(generation) == 1
        disabled = await workflow(requested=True).start()
        assert disabled.state.tool_results[-1].reference.reason == "execution_disabled"
        assert disabled.state.reference_runs == 0 and disabled.state.verification == "unverified"

    asyncio.run(scenario())


def test_reference_run_budget_is_shared_across_revisions(generation, draft_data):
    draft_data["private_tests"] = [
        {"test_id": f"t{i}", "input": "1 2\n", "expected_output": "3\n"} for i in range(11)
    ]
    worker = MockWorker([success(b"3\n")] * 20)
    run = workflow(worker=worker, requested=True)

    async def scenario():
        first = await run.start()
        assert first.state.reference_runs == 12
        second = await run.resume(decision(first, "revise", "Improve."))
        report = second.state.tool_results[-1].reference
        assert second.state.reference_runs == 20 and report.not_run == 4
        third = await run.resume(decision(second, "revise", "Improve again."))
        assert third.state.tool_results[-1].reference.reason == "run_budget"
        assert third.state.tool_results[-1].reference.not_run == 12
        assert len(worker.requests) == 20 and len(generation) == 3

    asyncio.run(scenario())


def test_malformed_input_state_never_calls_model_or_worker(generation):
    request = workflow().request.model_copy(update={"topic": "", "run_reference_tests": "true"})
    with pytest.warns(UserWarning, match="serializer warnings"), pytest.raises(ValidationError):
        AuthoringWorkflow(request, load_model_settings({"OLLAMA_MODEL_1": "fixture:1"}))
    assert not generation
    with pytest.raises(ValidationError):
        WorkflowState.model_validate({"request": {"shell": "PRIVATE_SHELL"}})


def test_concurrent_resume_is_refused_while_revision_is_in_flight(generation, monkeypatch):
    run = workflow()
    normal = run.session.generate

    async def scenario():
        first = await run.start()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def delayed(*args, **kwargs):
            entered.set()
            await release.wait()
            return await normal(*args, **kwargs)

        monkeypatch.setattr(run.session, "generate", delayed)
        task = asyncio.create_task(run.resume(decision(first, "revise", "Improve.")))
        await entered.wait()
        try:
            with pytest.raises(WorkflowFailure) as caught:
                await run.resume(decision(first, "revise", "Duplicate."))
            assert caught.value.code == "workflow_busy"
        finally:
            release.set()
        second = await task
        assert second.state.attempts == 2 and len(generation) == 2

    asyncio.run(scenario())


def test_inherited_tracing_is_disabled_for_the_whole_graph(generation, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "PRIVATE_TEST_KEY")

    def forbidden(*args, **kwargs):
        pytest.fail("Graph checkpoints or prompts must not be sent to tracing services")

    monkeypatch.setattr("langsmith.client.Client.create_run", forbidden)
    monkeypatch.setattr("langsmith.client.Client.update_run", forbidden)

    async def scenario():
        run = workflow()
        preview = await run.start()
        assert "PRIVATE_TEST_KEY" not in repr(list(run.checkpointer.list(run.config)))
        assert (await run.resume(decision(preview, "reject"))).state.status == "rejected"

    asyncio.run(scenario())


def test_preview_mutation_cannot_change_approval_or_tests(generation):
    async def scenario():
        run = workflow()
        preview = await run.start()
        preview.state.draft.private_tests.clear()
        run.preview().state.draft.private_tests.clear()
        assert len(run.preview().state.draft.private_tests) == 1
        assert (await run.resume(decision(preview, "approve"))).state.approved

    asyncio.run(scenario())


def test_failed_checkpoint_side_effect_is_never_retried(generation, monkeypatch):
    run = workflow()

    # Fail the checkpoint write after a model call, without repeating that call.
    original = run.checkpointer.aput

    async def fail_after_call(*args, **kwargs):
        if run.session.budget.used:
            raise RuntimeError("PRIVATE_CONTENT")
        return await original(*args, **kwargs)

    monkeypatch.setattr(run.checkpointer, "aput", fail_after_call)

    async def scenario():
        with pytest.raises(WorkflowFailure) as caught:
            await run.start()
        assert caught.value.code == "workflow_failed" and "PRIVATE" not in str(caught.value)
        with pytest.raises(WorkflowFailure):
            await run.start()
        with pytest.raises(WorkflowFailure):
            run.preview()
        assert len(generation) == 1

    asyncio.run(scenario())


def test_store_capacity_expiry_and_deletion_clear_checkpoint(generation, monkeypatch):
    store = WorkflowStore()
    monkeypatch.setattr("contest_check.authoring_workflow.MAX_WORKFLOWS", 1)
    settings = load_model_settings({"OLLAMA_MODEL_1": "fixture:1"})
    run = store.create(workflow().request, settings)
    asyncio.run(run.start())
    assert list(run.checkpointer.list(run.config))
    with pytest.raises(WorkflowFailure) as caught:
        store.create(run.request, settings)
    assert caught.value.code == "workflow_capacity"
    assert run.lock.acquire(blocking=False)
    try:
        with pytest.raises(WorkflowFailure) as caught:
            store.delete(run.workflow_id)
        assert caught.value.code == "workflow_busy"
    finally:
        run.lock.release()
    run.created -= 3_601
    with pytest.raises(WorkflowFailure) as caught:
        store.get(run.workflow_id)
    assert caught.value.code == "workflow_missing"
    assert not list(run.checkpointer.list(run.config))
    assert store.create(run.request, settings).workflow_id != run.workflow_id
