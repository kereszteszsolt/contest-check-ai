# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from contest_check.ui import local_api_url

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def test_api_address_can_change_port_but_stays_on_loopback(monkeypatch):
    monkeypatch.setenv("API_PORT", "18000")
    assert local_api_url() == "http://127.0.0.1:18000"


@pytest.mark.parametrize("port", ["0", "65536", "https://example.com"])
def test_api_address_rejects_invalid_port(monkeypatch, port):
    monkeypatch.setenv("API_PORT", port)
    with pytest.raises(ValueError):
        local_api_url()


def test_ui_starts_with_disabled_execution():
    page = AppTest.from_file(APP_PATH).run()
    assert not page.exception
    assert page.title[0].value == "ContestCheck AI"
    assert len(page.get("file_uploader")) == 2
    assert page.button[0].disabled
    assert page.button[1].disabled
    assert "validate" in page.info[0].value


@pytest.mark.parametrize("outcome", ["success", "rejected", "offline"])
def test_ui_upload_states(task_zip, submissions_zip, monkeypatch, outcome):
    files = {"task_zip": io.BytesIO(task_zip), "submissions_zip": io.BytesIO(submissions_zip)}
    monkeypatch.setattr(
        "contest_check.ui.st.file_uploader", lambda *args, key, **kwargs: files[key]
    )

    def post(client, path, **kwargs):
        assert path == "/api/validate"
        assert set(kwargs["files"]) == {"task_zip", "submissions_zip"}
        if outcome == "offline":
            raise httpx.ConnectError("offline")
        if outcome == "rejected":
            return httpx.Response(400, json={"code": "invalid_zip", "message": "ZIP is invalid."})
        return httpx.Response(
            200,
            json={
                "status": "validated",
                "task_id": "addition",
                "test_count": 1,
                "participant_ids": ["1001", "1002"],
                "submission_file_count": 3,
                "extracted_bytes": 512,
                "execution_enabled": False,
            },
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    page = AppTest.from_file(APP_PATH).run()
    page.button[0].click().run()
    assert not page.exception
    if outcome == "success":
        assert page.success
        assert page.session_state["validation_status"] == "validated"
        assert "1001, 1002" in page.text[-1].value
    else:
        assert page.error
        assert page.session_state["validation_status"] == "error"
    assert page.button[-1].disabled is (outcome != "success")


@pytest.fixture
def judging_page(task_zip, submissions_zip, report_batch, monkeypatch):
    files = {"task_zip": io.BytesIO(task_zip), "submissions_zip": io.BytesIO(submissions_zip)}
    monkeypatch.setattr(
        "contest_check.ui.st.file_uploader", lambda *args, key, **kwargs: files[key]
    )

    def post(client, path, **kwargs):
        if path == "/api/validate":
            return httpx.Response(
                200,
                json={
                    "status": "validated",
                    "task_id": report_batch.task_id,
                    "test_count": report_batch.tests_per_participant,
                    "participant_ids": [p.participant_id for p in report_batch.participants],
                    "submission_file_count": 3,
                    "extracted_bytes": 512,
                    "execution_enabled": False,
                },
            )
        if path == "/api/judge":
            return httpx.Response(200, json=report_batch.model_dump())
        from contest_check.reports import MIME_TYPES, build_report

        report_format = path.rsplit("/", 1)[1]
        return httpx.Response(
            200,
            content=build_report(report_format, report_batch),
            headers={"content-type": MIME_TYPES[report_format]},
        )

    monkeypatch.setattr(httpx.Client, "post", post)
    page = AppTest.from_file(APP_PATH).run()
    page.button[0].click().run()
    return page


def test_ui_runs_displays_all_results_and_prepares_downloads(judging_page):
    page = judging_page
    assert not page.button[1].disabled
    page.button[1].click().run()
    assert not page.exception
    assert page.session_state["judge_status"] == "completed"
    assert len(page.dataframe) == 4
    detail = page.dataframe[1].value
    assert len(detail) == 6 and set(detail["Outcome"]) == {"Pass", "Fail", "Not run"}
    assert set(detail["CPU (s)"]) == {"N/A"}
    assert set(detail["Participant ID"]) == {"1001", "1002", "1003"}
    page.button(key="prepare_reports").click().run()
    assert not page.exception
    assert set(page.session_state["reports"]) == {"pdf", "xlsx"}
    assert len(page.get("download_button")) == 2


def test_upload_changes_clear_results_and_downloads(judging_page, monkeypatch):
    page = judging_page
    page.button[1].click().run()
    page.button(key="prepare_reports").click().run()
    callbacks = []

    def upload(*args, key, on_change, **kwargs):
        if key == "task_zip":
            on_change()
            callbacks.append(key)
        return None

    monkeypatch.setattr("contest_check.ui.st.file_uploader", upload)
    page.run()
    assert callbacks == ["task_zip"]
    assert page.session_state["validation_status"] == "idle"
    assert page.session_state["reports"] == {}
    assert len(page.dataframe) == 0 and len(page.get("download_button")) == 0
    assert page.button[1].disabled


def test_ui_preserves_results_when_report_service_fails(judging_page, monkeypatch):
    page = judging_page
    page.button[1].click().run()
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *args, **kwargs: httpx.Response(
            503, json={"code": "report_failed", "message": "Report preparation failed."}
        ),
    )
    page.button(key="prepare_reports").click().run()
    assert not page.exception
    assert page.error and len(page.dataframe) == 4
    assert page.session_state["reports"] == {}


@pytest.mark.parametrize("outcome", ["disabled", "offline", "invalid_result"])
def test_ui_judging_errors_keep_downloads_unavailable(judging_page, monkeypatch, outcome):
    page = judging_page

    def post(*args, **kwargs):
        if outcome == "offline":
            raise httpx.ConnectError("PRIVATE_ERROR")
        if outcome == "invalid_result":
            return httpx.Response(200, json={"source": "PRIVATE_SOURCE"})
        return httpx.Response(503, json={"code": "execution_disabled", "message": "Disabled"})

    monkeypatch.setattr(httpx.Client, "post", post)
    page.button[1].click().run()
    assert not page.exception
    assert page.error and page.session_state["judge_status"] == "error"
    assert len(page.dataframe) == 0 and page.session_state["reports"] == {}
    assert "PRIVATE" not in page.error[0].value


def test_ui_incomplete_batch_does_not_show_unrun_tests_as_failed(
    judging_page, report_batch, monkeypatch
):
    page = judging_page
    value = report_batch.model_dump()
    value["status"] = "incomplete"
    first, *remaining = value["participants"]
    first.update(
        status="incomplete", passed_tests=0, failed_tests=0, system_errors=1, not_run_tests=1
    )
    first["tests"] = [
        dict(first["tests"][0], verdict="SYSTEM_ERROR", reason="sandbox_failure", wall_seconds=None)
    ]
    for participant in remaining:
        participant.update(
            status="not_run",
            passed_tests=0,
            failed_tests=0,
            system_errors=0,
            not_run_tests=2,
            tests=[],
            findings=[],
        )
    monkeypatch.setattr(httpx.Client, "post", lambda *a, **k: httpx.Response(200, json=value))
    page.button[1].click().run()
    assert not page.exception and page.warning
    assert page.session_state["judge_status"] == "incomplete"
    assert set(page.dataframe[1].value["Outcome"]) == {"System error", "Not run"}


def test_invalid_download_bytes_never_become_a_download(judging_page, monkeypatch):
    page = judging_page
    page.button[1].click().run()
    monkeypatch.setattr(
        httpx.Client,
        "post",
        lambda *a, **k: httpx.Response(
            200, content=b"PRIVATE_BAD_BINARY", headers={"content-type": "application/pdf"}
        ),
    )
    page.button(key="prepare_reports").click().run()
    assert not page.exception and page.error
    assert page.session_state["reports"] == {} and len(page.get("download_button")) == 0
    assert "PRIVATE" not in page.error[0].value
