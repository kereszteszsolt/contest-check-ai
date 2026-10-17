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


def upload_pair(client, task_zip, submissions_zip, path="/api/validate"):
    return client.post(
        path,
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
def test_reports_have_no_public_stored_download_endpoint(client, report_format):
    response = client.get(f"/api/reports/{report_format}")
    assert response.status_code == 405


def test_openapi_documents_multipart_fields(client):
    api = client.get("/openapi.json").json()
    body = api["paths"]["/api/validate"]["post"]["requestBody"]
    assert body["content"]["multipart/form-data"]["schema"]["required"] == [
        "task_zip",
        "submissions_zip",
    ]


@pytest.fixture
def judge_worker():
    from contest_check.api import get_worker
    from contest_check.judge.contracts import RuntimeResult

    calls = []

    class Worker:
        def execute(self, request):
            calls.append(request)
            return RuntimeResult(
                status="success",
                diagnostic="completed",
                exit_code=0,
                elapsed_seconds=0.1,
                output_base64="Mwo=",
                output_size_bytes=2,
                output_written=True,
            )

    app.dependency_overrides[get_worker] = Worker
    try:
        yield calls
    finally:
        app.dependency_overrides.pop(get_worker, None)


def test_judging_validates_uploads_and_returns_private_typed_results(
    client, judge_worker, task_zip, submissions_zip, tmp_path, monkeypatch
):
    monkeypatch.setattr("contest_check.archives.tempfile.tempdir", str(tmp_path))
    response = upload_pair(client, task_zip, submissions_zip, "/api/judge")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "completed"
    assert [p["participant_id"] for p in result["participants"]] == ["1001", "1002"]
    assert all(p["passed_tests"] == 1 for p in result["participants"])
    assert len(judge_worker) == 2 and judge_worker[0].test_id == "01"
    assert "source_files" not in response.text and "output_base64" not in response.text
    assert result["participants"][0]["tests"][0]["cpu_seconds"] is None
    assert list(tmp_path.iterdir()) == []


def test_judging_rejects_bad_archives_before_worker(client, judge_worker, task_zip):
    response = upload_pair(client, task_zip, b"invalid", "/api/judge")
    assert response.status_code == 400 and response.json()["code"] == "invalid_zip"
    assert judge_worker == []


def test_judging_body_is_bounded_before_parsing(client, judge_worker, monkeypatch):
    monkeypatch.setattr("contest_check.api.MAX_REQUEST_BYTES", 10)
    response = client.post("/api/judge", content=iter([b"x" * 6, b"x" * 6]))
    assert response.status_code == 413 and judge_worker == []


def test_only_one_batch_is_admitted(client, judge_worker, task_zip, submissions_zip):
    from contest_check.api import JUDGE_SLOT

    assert JUDGE_SLOT.acquire(blocking=False)
    try:
        response = upload_pair(client, task_zip, submissions_zip, "/api/judge")
        assert response.status_code == 503 and response.json()["code"] == "judge_busy"
        assert judge_worker == []
    finally:
        JUDGE_SLOT.release()
    assert upload_pair(client, task_zip, submissions_zip, "/api/judge").status_code == 200


def test_judge_slot_is_released_after_upload_error(client, judge_worker, task_zip, submissions_zip):
    assert upload_pair(client, task_zip, b"bad", "/api/judge").status_code == 400
    assert upload_pair(client, task_zip, submissions_zip, "/api/judge").status_code == 200


def test_judging_system_failure_is_explicitly_incomplete(
    client, judge_worker, task_zip, submissions_zip
):
    from contest_check.api import get_worker
    from contest_check.judge.contracts import RuntimeResult

    class FailedWorker:
        def execute(self, request):
            judge_worker.append(request)
            return RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")

    app.dependency_overrides[get_worker] = FailedWorker
    response = upload_pair(client, task_zip, submissions_zip, "/api/judge")
    assert response.status_code == 200 and response.json()["status"] == "incomplete"
    first, second = response.json()["participants"]
    assert first["system_errors"] == 1 and first["failed_tests"] == 0
    assert second["status"] == "not_run" and second["tests"] == []
    assert len(judge_worker) == 1
