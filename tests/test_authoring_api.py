# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import pytest
from fastapi.testclient import TestClient

from contest_check.api import AUTHORING_SLOT, app, get_model_settings
from contest_check.authoring_contracts import DraftResponse, TaskDraft
from contest_check.model_configuration import ProviderError, load_model_settings


@pytest.fixture
def client(draft_data, monkeypatch):
    settings = load_model_settings({"OLLAMA_MODEL_1": "fixture:1"})
    app.dependency_overrides[get_model_settings] = lambda: settings

    async def generate(session, instructions):
        return DraftResponse(
            model=session.choice, draft=TaskDraft.model_validate(draft_data), calls_used=1
        )

    monkeypatch.setattr("contest_check.api.GenerationSession.generate", generate)
    try:
        with TestClient(app) as value:
            yield value
    finally:
        app.dependency_overrides.pop(get_model_settings, None)


def test_model_catalog_exposes_no_backend_settings(client):
    response = client.get("/api/authoring/models")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "models": [{"slot": "ollama:1", "provider": "ollama", "model": "fixture:1"}],
        "issues": [],
    }


def test_api_can_return_only_an_unapproved_unexecuted_draft(client):
    response = client.post(
        "/api/authoring/draft", json={"model_slot": "ollama:1", "instructions": "Addition exercise"}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["approved"] is False and response.json()["executed"] is False
    assert response.json()["draft"]["private_tests"][0]["test_id"] == "t1"


def test_unconfigured_slot_is_rejected_before_provider_call(client, monkeypatch):
    async def forbidden(*args):
        pytest.fail("Unknown slot must never invoke a model")

    monkeypatch.setattr("contest_check.api.GenerationSession.generate", forbidden)
    response = client.post(
        "/api/authoring/draft", json={"model_slot": "openrouter:1", "instructions": "Exercise"}
    )
    assert response.status_code == 400 and response.json()["code"] == "unknown_model"


@pytest.mark.parametrize("field", ["model", "base_url", "api_key", "submissions_zip", "callbacks"])
def test_extra_request_fields_never_reach_provider_or_echo(client, field):
    response = client.post(
        "/api/authoring/draft",
        json={"model_slot": "ollama:1", "instructions": "Exercise", field: "PRIVATE_VALUE"},
    )
    assert response.status_code == 422 and "PRIVATE" not in response.text


@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}])
def test_authoring_body_cap_precedes_json_parsing(client, monkeypatch, headers):
    monkeypatch.setattr("contest_check.api.MAX_AUTHORING_REQUEST_BYTES", 10)
    response = client.post(
        "/api/authoring/draft", content=iter([b"x" * 6, b"x" * 6]), headers=headers
    )
    assert response.status_code == 413


def test_busy_and_failed_generation_release_slot(client, monkeypatch):
    payload = {"model_slot": "ollama:1", "instructions": "Exercise"}
    assert AUTHORING_SLOT.acquire(blocking=False)
    try:
        response = client.post("/api/authoring/draft", json=payload)
        assert response.status_code == 503 and response.json()["code"] == "authoring_busy"
    finally:
        AUTHORING_SLOT.release()

    async def fail(*args):
        raise ProviderError("timeout")

    with monkeypatch.context() as scoped:
        scoped.setattr("contest_check.api.GenerationSession.generate", fail)
        response = client.post("/api/authoring/draft", json=payload)
        assert response.status_code == 504 and response.json()["code"] == "timeout"
    assert client.post("/api/authoring/draft", json=payload).status_code == 200


def test_missing_key_has_a_clear_catalog_error(client):
    app.dependency_overrides[get_model_settings] = lambda: load_model_settings(
        {"OPENROUTER_MODEL_1": "test/fixture"}
    )
    payload = client.get("/api/authoring/models").json()
    assert payload["models"] == [] and "API key" in payload["issues"][0]
