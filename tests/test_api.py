# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import replace

import pytest
from conftest import INERT_SOURCE, make_zip
from fastapi.testclient import TestClient

from contest_check.api import app
from contest_check.archives import DEFAULT_LIMITS


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


def upload_pair(client, task_zip, submissions_zip):
    return client.post(
        "/api/validate",
        files={
            "task_zip": ("task.zip", task_zip, "application/zip"),
            "submissions_zip": ("submissions.zip", submissions_zip, "application/zip"),
        },
    )


def test_validation_returns_summary_only(client, task_zip, submissions_zip, tmp_path, monkeypatch):
    monkeypatch.setattr("contest_check.archives.tempfile.tempdir", str(tmp_path))
    response = upload_pair(client, task_zip, submissions_zip)
    assert response.status_code == 200
    assert response.json() == {
        "status": "validated",
        "task_id": "addition",
        "test_count": 1,
        "participant_ids": ["1001", "1002"],
        "submission_file_count": 3,
        "extracted_bytes": response.json()["extracted_bytes"],
        "execution_enabled": False,
    }
    assert "root" not in response.text
    assert "source" not in response.text
    assert "01.out" not in response.text
    assert list(tmp_path.iterdir()) == []


def test_upload_error_is_safe_and_not_disqualification(client, task_zip, caplog, capsys):
    marker = b"# PRIVATE_STUDENT_SOURCE_MARKER"
    response = upload_pair(client, task_zip, make_zip([("../main.py", marker)]))
    assert response.status_code == 400
    assert response.json()["code"] == "unsafe_path"
    observed = response.text + caplog.text + str(capsys.readouterr())
    assert marker.decode() not in observed
    assert "cheat" not in observed.lower()
    assert "disqualif" not in observed.lower()


def test_corrupt_zip_is_upload_error(client, task_zip):
    response = upload_pair(client, task_zip, b"not a zip")
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_zip"


def test_manifest_errors_do_not_echo_input(client, manifest, submissions_zip):
    import json

    manifest["private_source"] = "DO_NOT_ECHO_THIS_PRIVATE_CONTENT"
    task = make_zip([("challenge/task-config.json", json.dumps(manifest))])
    response = upload_pair(client, task, submissions_zip)
    assert response.status_code == 400
    assert response.json()["code"] == "manifest"
    assert "DO_NOT_ECHO" not in response.text


@pytest.mark.parametrize(
    "fields",
    [
        [],
        ["task_zip"],
        ["other", "submissions_zip"],
        ["task_zip", "task_zip"],
        ["task_zip", "submissions_zip", "extra"],
    ],
)
def test_missing_extra_duplicate_fields(client, fields):
    response = client.post(
        "/api/validate",
        files=[(field, ("data.zip", b"inert", "application/zip")) for field in fields],
    )
    assert response.status_code in (400, 415)
    assert set(response.json()) == {"code", "message"}


def test_text_fields_rejected(client):
    response = client.post(
        "/api/validate",
        files={"task_zip": ("task.zip", b"inert")},
        data={"submissions_zip": "PRIVATE_TEXT_FIELD"},
    )
    assert response.status_code == 400
    assert "PRIVATE_TEXT_FIELD" not in response.text


def test_malformed_multipart(client):
    response = client.post(
        "/api/validate", content=b"inert", headers={"content-type": "multipart/form-data"}
    )
    assert response.status_code == 400
    assert set(response.json()) == {"code", "message"}


def test_unsupported_content_type(client):
    response = client.post("/api/validate", json={"task_zip": "inert"})
    assert response.status_code == 415


@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}, {"content-length": "999"}])
def test_bounded_body_with_missing_or_dishonest_length(client, monkeypatch, headers):
    monkeypatch.setattr("contest_check.api.MAX_REQUEST_BYTES", 10)
    response = client.post("/api/validate", content=iter([b"x" * 6, b"x" * 6]), headers=headers)
    assert response.status_code == 413
    assert response.json()["code"] == "request_size"


@pytest.mark.parametrize("length", ["invalid", "-1"])
def test_invalid_content_length(client, length):
    response = client.post("/api/validate", content=b"", headers={"content-length": length})
    assert response.status_code == 400


def test_per_archive_api_limit(client, task_zip, submissions_zip, monkeypatch):
    monkeypatch.setattr(
        "contest_check.api.DEFAULT_LIMITS", replace(DEFAULT_LIMITS, archive_bytes=100)
    )
    response = upload_pair(client, task_zip, submissions_zip)
    assert response.status_code == 413
    assert response.json()["code"] == "archive_size"


def test_workspace_failure_returns_safe_error(client, task_zip, submissions_zip, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("PRIVATE_FILESYSTEM_PATH")

    monkeypatch.setattr("contest_check.archives.tempfile.TemporaryDirectory", fail)
    response = upload_pair(client, task_zip, submissions_zip)
    assert response.status_code == 503
    assert response.json()["code"] == "workspace"
    assert "PRIVATE_FILESYSTEM_PATH" not in response.text


def test_execution_cannot_be_enabled_by_environment(client, monkeypatch):
    monkeypatch.setenv("JUDGE_EXECUTION_ENABLED", "true")
    assert client.get("/health").json() == {"status": "ok", "execution_enabled": False}
    response = client.post("/api/judge", content=INERT_SOURCE)
    assert response.status_code == 503
    assert response.json()["code"] == "execution_disabled"


@pytest.mark.parametrize("report_format", ["pdf", "xlsx"])
def test_placeholder_report_contract(client, report_format):
    response = client.get(f"/api/reports/{report_format}")
    assert response.status_code == 501
    assert response.json()["code"] == "reports_unavailable"


def test_openapi_documents_multipart_fields(client):
    api = client.get("/openapi.json").json()
    body = api["paths"]["/api/validate"]["post"]["requestBody"]
    assert body["content"]["multipart/form-data"]["schema"]["required"] == [
        "task_zip",
        "submissions_zip",
    ]
