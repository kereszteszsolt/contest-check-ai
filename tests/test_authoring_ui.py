# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from contest_check.authoring_contracts import DraftResponse, TaskDraft
from contest_check.model_configuration import load_model_settings

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


@pytest.fixture
def authoring_page(monkeypatch):
    config = load_model_settings(
        {
            "OLLAMA_MODEL_1": "fixture:1",
            "OPENROUTER_MODEL_1": "test/fixture",
            "OPENROUTER_API_KEY": "not-a-real-key",
        }
    )
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json=config.catalog().model_dump(),
            request=httpx.Request("GET", "http://127.0.0.1/api/authoring/models"),
        ),
    )
    page = AppTest.from_file(APP_PATH).run()
    page.sidebar.radio[0].set_value("AI task draft").run()
    assert not page.exception
    return page, config


def test_selection_is_explicit_and_cloud_cost_is_visible(authoring_page):
    page, _ = authoring_page
    assert page.selectbox[0].value is None and page.button[0].disabled
    page.selectbox[0].set_value("openrouter:1").run()
    assert page.warning and "charges" in page.warning[0].value
    page.text_area[0].set_value("Draft an addition exercise.").run()
    assert not page.button[0].disabled


def test_draft_preview_resets_after_model_or_instruction_changes(
    authoring_page, draft_data, monkeypatch
):
    page, config = authoring_page
    sent = []

    def post(client, path, **kwargs):
        sent.append((path, kwargs["json"]))
        result = DraftResponse(
            model=config.resolve("ollama:1"),
            draft=TaskDraft.model_validate(draft_data),
            calls_used=1,
        )
        return httpx.Response(200, json=result.model_dump())

    monkeypatch.setattr(httpx.Client, "post", post)
    page.selectbox[0].set_value("ollama:1").run()
    page.text_area[0].set_value("Draft an addition exercise.").run()
    page.button[0].click().run()
    assert not page.exception and len(page.json) == 1
    assert "Unverified draft" in page.warning[0].value
    assert sent == [
        (
            "/api/authoring/draft",
            {"model_slot": "ollama:1", "instructions": "Draft an addition exercise."},
        )
    ]
    page.text_area[0].set_value("Different exercise.").run()
    assert len(page.json) == 0
    page.button[0].click().run()
    page.selectbox[0].set_value("openrouter:1").run()
    assert len(page.json) == 0


def test_missing_key_and_catalog_failure_show_safe_errors(monkeypatch):
    config = load_model_settings({"OPENROUTER_MODEL_1": "test/fixture"})
    monkeypatch.setattr(
        httpx.Client,
        "get",
        lambda *a, **k: httpx.Response(
            200,
            json=config.catalog().model_dump(),
            request=httpx.Request("GET", "http://127.0.0.1/api/authoring/models"),
        ),
    )
    page = AppTest.from_file(APP_PATH).run()
    page.sidebar.radio[0].set_value("AI task draft").run()
    assert page.error and "API key" in page.error[0].value and len(page.selectbox) == 0

    def fail(*args, **kwargs):
        raise httpx.ConnectError("PRIVATE_ERROR")

    monkeypatch.setattr(httpx.Client, "get", fail)
    page.run()
    assert not page.exception and "PRIVATE" not in page.error[0].value
