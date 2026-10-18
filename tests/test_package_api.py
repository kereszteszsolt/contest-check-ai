# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import json

import pytest
from test_challenge_packages import files_of, pdf_text
from test_workflow_api import REQUEST, ROOT, review
from test_workflow_api import client as workflow_client

from contest_check.api import PACKAGE_SLOT

client = workflow_client


def approved(client, reference_checks=False):
    first = client.post(ROOT, json=REQUEST | {"run_reference_tests": reference_checks}).json()
    response = review(client, first, "approve")
    assert response.status_code == 200
    return response.json()


def endpoint(preview, audience="student"):
    return f"{ROOT}/{preview['workflow_id']}/packages/{audience}"


def test_api_downloads_separate_approved_packages_and_judge_accepts_teacher_zip(
    client, submissions_zip
):
    preview = approved(client)
    student = client.post(endpoint(preview), json={})
    teacher = client.post(endpoint(preview, "teacher"), json={})
    for response, audience in [(student, "student"), (teacher, "teacher")]:
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert (
            response.headers["content-disposition"]
            == f'attachment; filename="addition-{audience}.zip"'
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-challenge-verification"] == "unverified"
    assert "problem.pdf" in files_of(student.content)
    assert "problem.pdf" not in files_of(teacher.content)
    assert "teacher/reference/main.py" not in files_of(teacher.content)
    assert len(client.workflow_calls) == 1 and not client.workflow_worker.requests
    validation = client.post(
        "/api/validate",
        files={
            "task_zip": ("addition-teacher.zip", teacher.content, "application/zip"),
            "submissions_zip": ("inert.zip", submissions_zip, "application/zip"),
        },
    )
    assert validation.status_code == 200 and validation.json()["task_id"] == "addition"
    assert not validation.json()["execution_enabled"]


@pytest.mark.parametrize("audience", ["student", "teacher"])
def test_api_unapproved_and_rejected_states_cannot_download(client, audience):
    preview = client.post(ROOT, json=REQUEST).json()
    response = client.post(endpoint(preview, audience), json={})
    assert response.status_code == 409 and response.json()["code"] == "package_unapproved"
    assert response.headers["cache-control"] == "no-store"
    # Existing teacher preview still exposes a clearly unapproved/unverified draft.
    state = client.get(f"{ROOT}/{preview['workflow_id']}").json()["state"]
    assert state["status"] == "awaiting_review" and not state["approved"]
    assert state["verification"] == "unverified"
    assert review(client, preview, "reject").status_code == 200
    assert client.post(endpoint(preview, audience), json={}).status_code == 409


def test_api_reference_is_opt_in_teacher_only_and_export_does_not_rerun_checks(client):
    preview = approved(client, reference_checks=True)
    assert len(client.workflow_worker.requests) == 2
    teacher = client.post(endpoint(preview, "teacher"), json={"include_reviewed_reference": True})
    assert teacher.status_code == 200
    files = files_of(teacher.content)
    assert "teacher/reference/main.py" in files
    checks = json.loads(files["teacher/checks.json"])
    assert checks["reference_runs"] == 2 and checks["verification"] == "unverified"
    assert checks["tool_results"][-1]["reference"]["status"] == "completed"
    assert (
        client.post(endpoint(preview), json={"include_reviewed_reference": True}).status_code == 422
    )
    assert len(client.workflow_worker.requests) == 2 and len(client.workflow_calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"approved": True},
        {"state": {"approved": True}},
        {"output_path": "PRIVATE_PATH"},
        {"include_reviewed_reference": "true"},
        {"reference_source": "PRIVATE_SOURCE"},
    ],
)
def test_api_does_not_accept_caller_state_source_paths_or_coerced_options(client, payload):
    preview = client.post(ROOT, json=REQUEST).json()
    response = client.post(endpoint(preview), json=payload)
    assert response.status_code == 422 and "PRIVATE" not in response.text
    assert len(client.workflow_calls) == 1


def test_api_missing_expired_or_invalid_audience_does_not_export(client):
    response = client.post(f"{ROOT}/{'0' * 32}/packages/student", json={})
    assert response.status_code == 404
    preview = approved(client)
    assert client.post(endpoint(preview, "arbitrary"), json={}).status_code == 422
    run = client.workflow_store.get(preview["workflow_id"])
    run.created -= 3_601
    assert client.post(endpoint(preview), json={}).status_code == 404


def test_api_busy_and_failed_export_release_admission_slot(client, monkeypatch):
    preview = approved(client)
    assert PACKAGE_SLOT.acquire(blocking=False)
    try:
        response = client.post(endpoint(preview), json={})
        assert response.status_code == 503 and response.json()["code"] == "package_busy"
    finally:
        PACKAGE_SLOT.release()

    def fail(*args):
        raise RuntimeError("PRIVATE_EXCEPTION_CONTENT")

    with monkeypatch.context() as scoped:
        scoped.setattr("contest_check.api.build_challenge_package", fail)
        response = client.post(endpoint(preview), json={})
    assert response.status_code == 503 and response.json()["code"] == "package_failed"
    assert "PRIVATE" not in response.text
    assert client.post(endpoint(preview), json={}).status_code == 200


@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}])
def test_api_package_options_body_is_bounded_before_parsing(client, monkeypatch, headers):
    preview = approved(client)
    monkeypatch.setattr("contest_check.api.MAX_AUTHORING_REQUEST_BYTES", 10)
    response = client.post(endpoint(preview), content=iter([b"x" * 6, b"x" * 6]), headers=headers)
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"


def test_pdf_and_public_manifest_do_not_include_backend_credentials(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "PRIVATE_BACKEND_CREDENTIAL")
    preview = approved(client)
    response = client.post(endpoint(preview), json={})
    files = files_of(response.content)
    readable = b"\n".join(data for name, data in files.items() if name != "problem.pdf")
    assert b"PRIVATE_BACKEND_CREDENTIAL" not in readable
    assert "PRIVATE_BACKEND_CREDENTIAL" not in pdf_text(files["problem.pdf"])
    assert b"fixture:1" not in readable and b"ollama" not in readable
