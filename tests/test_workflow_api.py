# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import pytest
from fastapi.testclient import TestClient
from test_authoring_tools import MockWorker, success

from contest_check.api import (
    AUTHORING_SLOT,
    JUDGE_SLOT,
    app,
    get_model_settings,
    get_worker,
    get_workflow_store,
)
from contest_check.authoring_contracts import DraftResponse, TaskDraft
from contest_check.authoring_workflow import WorkflowStore
from contest_check.model_configuration import ProviderError, load_model_settings

REQUEST = {
    "model_slot": "ollama:1",
    "instructions": "Create an addition exercise.",
    "topic": "arithmetic",
    "difficulty": "beginner",
}
ROOT = "/api/authoring/workflows"


@pytest.fixture
def client(draft_data, monkeypatch):
    store = WorkflowStore()
    worker = MockWorker([success(b"3\n"), success(b"7\n")] * 3)
    settings = load_model_settings({"OLLAMA_MODEL_1": "fixture:1"})
    overrides = {
        get_model_settings: lambda: settings,
        get_worker: lambda: worker,
        get_workflow_store: lambda: store,
    }
    calls = []

    async def generate(session, instructions, *, context):
        session.budget.reserve()
        calls.append(context)
        return DraftResponse(
            model=session.choice,
            draft=TaskDraft.model_validate(draft_data),
            calls_used=session.budget.used,
        )

    monkeypatch.setattr("contest_check.authoring_workflow.GenerationSession.generate", generate)
    app.dependency_overrides.update(overrides)
    try:
        with TestClient(app) as value:
            value.workflow_calls = calls
            value.workflow_store = store
            value.workflow_worker = worker
            yield value
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency, None)


def review(client, preview, action, revision=""):
    return client.post(
        f"{ROOT}/{preview['workflow_id']}/review",
        json={"review_id": preview["state"]["review_id"], "action": action, "revision": revision},
    )


def test_api_create_preview_revision_approval_and_deletion(client):
    created = client.post(ROOT, json=REQUEST)
    assert created.status_code == 200 and created.headers["cache-control"] == "no-store"
    first = created.json()
    assert first["state"]["status"] == "awaiting_review"
    assert first["state"]["tool_results"][-1]["reference"]["reason"] == "not_requested"
    assert not client.workflow_worker.requests
    path = f"{ROOT}/{first['workflow_id']}"
    assert client.get(path).json() == first and len(client.workflow_calls) == 1
    revised = review(client, first, "revise", "Explain negative integers.")
    assert revised.status_code == 200
    assert revised.json()["state"]["attempts"] == 2
    assert review(client, first, "approve").status_code == 409
    approved = review(client, revised.json(), "approve")
    assert approved.status_code == 200 and approved.json()["state"]["approved"]
    assert approved.json()["state"]["verification"] == "unverified"
    assert len(client.workflow_calls) == 2
    assert review(client, revised.json(), "approve").status_code == 409
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404


def test_api_only_explicit_reference_opt_in_can_contact_worker(client):
    response = client.post(ROOT, json=REQUEST | {"run_reference_tests": True})
    assert response.status_code == 200
    preview = response.json()
    assert preview["state"]["reference_runs"] == 2
    assert len(client.workflow_worker.requests) == 2
    assert review(client, preview, "reject").json()["state"]["status"] == "rejected"
    assert len(client.workflow_worker.requests) == 2


def test_api_disabled_worker_cannot_be_enabled_by_request(client):
    app.dependency_overrides[get_worker] = lambda: None
    response = client.post(ROOT, json=REQUEST | {"run_reference_tests": True})
    report = response.json()["state"]["tool_results"][-1]["reference"]
    assert report["status"] == "blocked" and report["reason"] == "execution_disabled"
    assert not client.workflow_worker.requests


@pytest.mark.parametrize(
    "field",
    [
        "model",
        "base_url",
        "api_key",
        "tools",
        "shell",
        "checkpoint",
        "approved",
        "output_path",
    ],
)
def test_api_refuses_untrusted_authority_fields_without_echo(client, field):
    response = client.post(ROOT, json=REQUEST | {field: "PRIVATE_VALUE"})
    assert response.status_code == 422 and "PRIVATE" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert not client.workflow_calls and not client.workflow_store.workflows


@pytest.mark.parametrize(
    "change",
    [
        {"instructions": " "},
        {"instructions": "x" * 8_001},
        {"topic": " "},
        {"topic": "x" * 121},
        {"difficulty": "arbitrary"},
        {"run_reference_tests": "true"},
    ],
)
def test_api_validates_workflow_requirements_before_generation(client, change):
    response = client.post(ROOT, json=REQUEST | change)
    assert response.status_code == 422 and not client.workflow_calls


def test_api_invalid_review_keeps_checkpoint_available(client):
    preview = client.post(ROOT, json=REQUEST).json()
    path = f"{ROOT}/{preview['workflow_id']}/review"
    for payload in [
        {"action": "approve"},
        {"review_id": preview["state"]["review_id"], "action": "revise", "revision": " "},
        {"review_id": preview["state"]["review_id"], "action": "approve", "approved": True},
        {"review_id": preview["state"]["review_id"], "action": "approve", "revision": "PRIVATE"},
    ]:
        response = client.post(path, json=payload)
        assert response.status_code == 422 and "PRIVATE" not in response.text
    assert review(client, preview, "approve").status_code == 200
    assert len(client.workflow_calls) == 1


@pytest.mark.parametrize("path,status", [("0" * 32, 404), ("unsafe", 422)])
def test_api_unknown_or_malformed_id_is_safe(client, path, status):
    response = client.get(f"{ROOT}/{path}")
    assert response.status_code == status and not client.workflow_calls
    assert response.headers["cache-control"] == "no-store"


def test_api_unknown_model_and_store_capacity_make_no_model_call(client, monkeypatch):
    response = client.post(ROOT, json=REQUEST | {"model_slot": "openrouter:1"})
    assert response.status_code == 400 and response.json()["code"] == "unknown_model"
    assert not client.workflow_calls
    monkeypatch.setattr("contest_check.authoring_workflow.MAX_WORKFLOWS", 1)
    assert client.post(ROOT, json=REQUEST).status_code == 200
    response = client.post(ROOT, json=REQUEST)
    assert response.status_code == 503 and response.json()["code"] == "workflow_capacity"
    assert len(client.workflow_calls) == 1


def test_api_shared_slots_prevent_parallel_model_or_judge_work(client):
    assert AUTHORING_SLOT.acquire(blocking=False)
    try:
        assert client.post(ROOT, json=REQUEST).json()["code"] == "workflow_busy"
    finally:
        AUTHORING_SLOT.release()
    assert JUDGE_SLOT.acquire(blocking=False)
    try:
        response = client.post(ROOT, json=REQUEST | {"run_reference_tests": True})
        assert response.status_code == 503 and response.json()["code"] == "workflow_busy"
        assert not client.workflow_calls
        preview = client.post(ROOT, json=REQUEST).json()
        assert review(client, preview, "reject").status_code == 200
    finally:
        JUDGE_SLOT.release()


def test_api_timeout_is_reviewable_and_releases_slots(client, monkeypatch):
    async def fail(session, instructions, **kwargs):
        session.budget.reserve()
        raise ProviderError("timeout")

    with monkeypatch.context() as scoped:
        scoped.setattr("contest_check.authoring_workflow.GenerationSession.generate", fail)
        response = client.post(ROOT, json=REQUEST)
    assert response.status_code == 200
    preview = response.json()
    assert preview["state"]["errors"] == [{"attempt": 1, "code": "timeout"}]
    assert review(client, preview, "approve").json()["code"] == "approval_blocked"
    assert review(client, preview, "revise", "Use a smaller exercise.").status_code == 200
    assert len(client.workflow_calls) == 1


def test_api_unexpected_graph_error_is_sanitized_and_discards_workflow(client, monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError("PRIVATE_CONTENT")

    with monkeypatch.context() as scoped:
        scoped.setattr("contest_check.authoring_workflow.GenerationSession.generate", fail)
        response = client.post(ROOT, json=REQUEST)
    assert response.status_code == 503 and response.json()["code"] == "workflow_failed"
    assert "PRIVATE" not in response.text and not client.workflow_store.workflows
    assert client.post(ROOT, json=REQUEST).status_code == 200


@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}])
def test_api_caps_workflow_body_before_parsing(client, monkeypatch, headers):
    monkeypatch.setattr("contest_check.api.MAX_AUTHORING_REQUEST_BYTES", 10)
    response = client.post(ROOT, content=iter([b"x" * 6, b"x" * 6]), headers=headers)
    assert response.status_code == 413 and not client.workflow_calls
    assert response.headers["cache-control"] == "no-store"


def test_creation_id_replay_reads_checkpoint_without_another_model_call(client):
    headers = {"Idempotency-Key": "ab" * 16}
    first = client.post(ROOT, json=REQUEST, headers=headers)
    assert first.status_code == 200 and first.json()["workflow_id"] == headers["Idempotency-Key"]
    assert client.post(ROOT, json=REQUEST, headers=headers).json() == first.json()
    approved = review(client, first.json(), "approve").json()
    assert client.post(ROOT, json=REQUEST, headers=headers).json() == approved
    assert len(client.workflow_calls) == 1
    conflict = client.post(ROOT, json=REQUEST | {"topic": "different"}, headers=headers)
    assert conflict.status_code == 409 and conflict.json()["code"] == "workflow_conflict"
    client.delete(f"{ROOT}/{approved['workflow_id']}")
    assert client.post(ROOT, json=REQUEST, headers=headers).status_code == 404
    assert len(client.workflow_calls) == 1


@pytest.mark.parametrize("creation_id", ["../escape", "A" * 32, "a" * 33, ""])
def test_invalid_creation_ids_never_contact_a_model(client, creation_id):
    assert (
        client.post(ROOT, json=REQUEST, headers={"Idempotency-Key": creation_id}).status_code == 422
    )
    assert not client.workflow_calls


def test_failed_creation_id_is_retired_instead_of_silently_retried(client, monkeypatch):
    from contest_check.authoring_workflow import AuthoringWorkflow
    from contest_check.workflow_contracts import WorkflowFailure

    async def fail(workflow):
        workflow.session.budget.reserve()
        client.workflow_calls.append("failed")
        raise WorkflowFailure("workflow_failed")

    monkeypatch.setattr(AuthoringWorkflow, "start", fail)
    headers = {"Idempotency-Key": "cd" * 16}
    assert client.post(ROOT, json=REQUEST, headers=headers).status_code == 503
    assert client.post(ROOT, json=REQUEST, headers=headers).status_code == 404
    assert len(client.workflow_calls) == 1


def test_retired_creation_ids_are_bounded_and_expire(client, monkeypatch):
    import contest_check.authoring_workflow as module

    monkeypatch.setattr(module, "MAX_CREATIONS", 1)
    headers = {"Idempotency-Key": "ef" * 16}
    first = client.post(ROOT, json=REQUEST, headers=headers).json()
    client.delete(f"{ROOT}/{first['workflow_id']}")
    assert client.post(ROOT, json=REQUEST).status_code == 503
    client.workflow_store.used_ids[first["workflow_id"]] -= module.WORKFLOW_TTL_SECONDS + 1
    assert client.post(ROOT, json=REQUEST).status_code == 200
