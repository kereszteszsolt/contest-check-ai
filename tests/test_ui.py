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
    assert "disabled" in page.info[0].value


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
    assert page.button[-1].disabled
