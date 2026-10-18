# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io
import zipfile
from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest
from test_workflow_api import client as workflow_client

from contest_check.model_configuration import load_model_settings

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"
client = workflow_client


def button(page, label):
    return next(item for item in page.button if item.label == label)


def text_input(page, label):
    return next(item for item in page.text_input if item.label == label)


def checkbox(page, startswith):
    return next(item for item in page.checkbox if item.label.startswith(startswith))


@pytest.fixture
def authoring_page(client, monkeypatch):
    config = load_model_settings(
        {
            "OLLAMA_MODEL_1": "fixture:1",
            "OPENROUTER_MODEL_1": "test/fixture",
            "OPENROUTER_API_KEY": "not-a-real-key",
        }
    )
    calls = []

    def request(api_url, method, path, *, payload=None, creation_id=None, slow=False):
        calls.append((method, path, payload))
        if path == "/api/authoring/models":
            return httpx.Response(
                200,
                json=config.catalog().model_dump(),
                request=httpx.Request(method, "http://testserver" + path),
            )
        return client.request(
            method,
            path,
            json=payload,
            headers={"Idempotency-Key": creation_id} if creation_id else {},
        )

    monkeypatch.setattr("contest_check.authoring_ui.api_request", request)
    page = AppTest.from_file(APP_PATH, default_timeout=20).run()
    page.sidebar.radio[0].set_value("AI task draft").run()
    assert not page.exception
    return page, calls, request


def generate(page):
    page.selectbox[0].set_value("ollama:1").run()
    text_input(page, "Topic").set_value("arithmetic").run()
    page.text_area[0].set_value("Create an addition exercise.").run()
    button(page, "Generate draft").click().run()
    assert not page.exception
    return page


def approve(page):
    checkbox(page, "I reviewed").check().run()
    button(page, "Approve draft").click().run()
    assert not page.exception


def test_selection_is_explicit_and_cloud_cost_is_visible(authoring_page):
    page, calls, _ = authoring_page
    assert page.selectbox[0].value is None and button(page, "Generate draft").disabled
    page.selectbox[0].set_value("openrouter:1").run()
    assert any("charges" in item.value for item in page.warning)
    text_input(page, "Topic").set_value("arithmetic").run()
    page.text_area[0].set_value("Draft an addition exercise.").run()
    assert not button(page, "Generate draft").disabled
    assert not any(method == "POST" for method, _, _ in calls)
    assert not checkbox(page, "Request isolated").value


def test_real_checkpoint_revision_approval_and_separate_private_downloads(authoring_page, client):
    page, calls, _ = authoring_page
    generate(page)
    first = page.session_state["authoring_preview"]
    assert first["state"]["status"] == "awaiting_review"
    assert button(page, "Approve draft").disabled
    assert not page.get("download_button")
    assert any("independent human review" in warning.value for warning in page.warning)
    page.text_area[0].set_value("Explain negative integers.").run()
    button(page, "Request changes").click().run()
    assert not page.exception and len(client.workflow_calls) == 2
    revised = page.session_state["authoring_preview"]
    assert revised["state"]["review_id"] != first["state"]["review_id"]
    assert not checkbox(page, "I reviewed").value
    assert page.text_area[0].value == ""
    approve(page)
    button(page, "Prepare separate ZIP downloads").click().run()
    assert not page.exception and len(page.get("download_button")) == 2
    _, packages = page.session_state["authoring_packages"]
    with zipfile.ZipFile(io.BytesIO(packages["student"][1])) as archive:
        assert "student-manifest.json" in archive.namelist()
        assert not any("reference" in name or "tests/" in name for name in archive.namelist())
        assert b"INERT" not in archive.read("starter/main.py")
    with zipfile.ZipFile(io.BytesIO(packages["teacher"][1])) as archive:
        assert (
            "challenge/tests/t1.out" in archive.namelist()
            and "teacher/reference/main.py" not in archive.namelist()
        )
    checkbox(page, "Include the reference").check().run()
    assert not page.get("download_button")
    button(page, "Prepare separate ZIP downloads").click().run()
    with zipfile.ZipFile(
        io.BytesIO(page.session_state["authoring_packages"][1]["teacher"][1])
    ) as archive:
        assert archive.read("teacher/reference/main.py") == b"# INERT_REFERENCE\n"
    assert len(client.workflow_calls) == 2
    assert sum(path.endswith("/review") for _, path, _ in calls) == 2
    button(page, "Delete workflow and start over").click().run()
    assert not page.get("download_button") and page.selectbox[0].value is None


def test_rejection_produces_no_downloads_or_additional_model_calls(authoring_page, client):
    page, _, _ = authoring_page
    generate(page)
    button(page, "Reject draft").click().run()
    assert not page.exception
    assert page.session_state["authoring_preview"]["state"]["status"] == "rejected"
    assert not page.get("download_button") and len(client.workflow_calls) == 1
    button(page, "Refresh workflow").click().run()
    assert not page.get("download_button") and len(client.workflow_calls) == 1


@pytest.mark.parametrize("uncertain_action", ["create", "revise", "approve"])
def test_lost_response_requires_read_only_recovery(
    authoring_page, client, monkeypatch, uncertain_action
):
    page, _, request = authoring_page
    if uncertain_action != "create":
        generate(page)
    if uncertain_action == "revise":
        page.text_area[0].set_value("Explain negative integers.").run()
    if uncertain_action == "approve":
        checkbox(page, "I reviewed").check().run()

    def lost(*args, **kwargs):
        response = request(*args, **kwargs)
        if args[1] == "POST":
            raise httpx.ReadTimeout("PRIVATE_PROVIDER_DATA")
        return response

    monkeypatch.setattr("contest_check.authoring_ui.api_request", lost)
    if uncertain_action == "create":
        generate(page)
    else:
        button(
            page, "Request changes" if uncertain_action == "revise" else "Approve draft"
        ).click().run()
    assert not page.exception and "unknown" in page.error[0].value
    assert "PRIVATE" not in page.error[0].value
    assert not any(
        item.label in ("Approve draft", "Generate draft", "Request changes") for item in page.button
    )
    assert not page.get("download_button")
    calls = len(client.workflow_calls)
    page.run()  # rerun never repeats the uncertain POST
    button(page, "Refresh workflow").click().run()
    assert not page.exception and len(client.workflow_calls) == calls
    expected = "approved" if uncertain_action == "approve" else "awaiting_review"
    assert page.session_state["authoring_preview"]["state"]["status"] == expected


def test_malformed_model_output_can_be_revised_or_rejected(authoring_page, client, monkeypatch):
    from contest_check.model_configuration import ProviderError

    async def broken(session, instructions, *, context):
        session.budget.reserve()
        raise ProviderError("invalid_output")

    monkeypatch.setattr("contest_check.authoring_workflow.GenerationSession.generate", broken)
    page, _, _ = authoring_page
    generate(page)
    assert button(page, "Approve draft").disabled and not page.get("download_button")
    assert any("invalid_output" in item.value for item in page.text)
    page.text_area[0].set_value("Return a valid structured problem.").run()
    assert not button(page, "Request changes").disabled
    button(page, "Reject draft").click().run()
    assert page.session_state["authoring_preview"]["state"]["status"] == "rejected"


def test_wrong_audience_archive_never_becomes_a_student_download(
    authoring_page, client, monkeypatch
):
    page, _, request = authoring_page
    generate(page)
    approve(page)

    def switched(api_url, method, path, **kwargs):
        response = request(
            api_url, method, path.replace("/packages/student", "/packages/teacher"), **kwargs
        )
        if path.endswith("/packages/student"):
            response.headers["content-disposition"] = 'attachment; filename="addition-student.zip"'
        return response

    monkeypatch.setattr("contest_check.authoring_ui.api_request", switched)
    button(page, "Prepare separate ZIP downloads").click().run()
    assert not page.exception and page.error and not page.get("download_button")
    assert len(client.workflow_calls) == 1


def test_untrusted_content_is_rendered_as_inert_text(authoring_page, draft_data):
    payload = "<script>alert(1)</script> ![tracking](https://outside.invalid/pixel)"
    draft_data["statement"] = payload
    draft_data["reference_source"] = 'import os; os.system("curl https://outside.invalid")'
    page, _, _ = authoring_page
    generate(page)
    assert any(payload == item.value for item in page.text)
    assert not any("outside.invalid" in item.value for item in page.markdown)
    assert any("os.system" in item.value for item in page.code)


def test_missing_key_and_catalog_failure_show_safe_errors(monkeypatch):
    config = load_model_settings({"OPENROUTER_MODEL_1": "test/fixture"})
    monkeypatch.setattr(
        "contest_check.authoring_ui.api_request",
        lambda *a, **k: httpx.Response(
            200,
            json=config.catalog().model_dump(),
            request=httpx.Request("GET", "http://testserver"),
        ),
    )
    page = AppTest.from_file(APP_PATH).run()
    page.sidebar.radio[0].set_value("AI task draft").run()
    assert any("API key" in item.value for item in page.text) and len(page.selectbox) == 0

    def fail(*args, **kwargs):
        raise httpx.ConnectError("PRIVATE_ERROR")

    monkeypatch.setattr("contest_check.authoring_ui.api_request", fail)
    page.run()
    assert not page.exception and "PRIVATE" not in page.error[0].value


@pytest.mark.parametrize("corruption", ["invalid_json", "wrong_id", "wrong_model"])
def test_invalid_preview_disables_decisions_until_refresh(
    authoring_page, client, monkeypatch, corruption
):
    page, _, request = authoring_page

    def corrupt(*args, **kwargs):
        response = request(*args, **kwargs)
        if args[1] == "POST":
            if corruption == "invalid_json":
                return httpx.Response(200, content=b"PRIVATE_INVALID_JSON")
            body = response.json()
            if corruption == "wrong_id":
                body["workflow_id"] = "00" * 16
            else:
                body["state"]["model"]["model"] = "unexpected-model"
            return httpx.Response(200, json=body)
        return response

    monkeypatch.setattr("contest_check.authoring_ui.api_request", corrupt)
    generate(page)
    assert page.error and "PRIVATE" not in page.error[0].value
    assert not any(item.label == "Approve draft" for item in page.button)
    button(page, "Refresh workflow").click().run()
    assert not page.exception and button(page, "Approve draft").disabled
    assert len(client.workflow_calls) == 1


def test_exhausted_call_budget_disables_revision(authoring_page, client):
    from contest_check.api import app, get_model_settings

    settings = load_model_settings(
        {"OLLAMA_MODEL_1": "fixture:1", "AI_MAX_CALLS_PER_GENERATION": "1"}
    )
    app.dependency_overrides[get_model_settings] = lambda: settings
    page, _, _ = authoring_page
    generate(page)
    page.text_area[0].set_value("More examples.").run()
    assert button(page, "Request changes").disabled and len(client.workflow_calls) == 1
    assert any("revision budget" in item.value for item in page.info)


def test_http_preview_stream_is_bounded_and_disables_environment_proxies(monkeypatch):
    from contest_check.authoring_ui import api_request

    original = httpx.Client
    options = []

    class Oversized(httpx.SyncByteStream):
        def __iter__(self):
            yield b"a" * 700_000
            yield b"b" * 700_000

    def client_factory(**kwargs):
        options.append(kwargs)
        return original(
            **kwargs,
            transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=Oversized())),
        )

    monkeypatch.setattr("contest_check.authoring_ui.httpx.Client", client_factory)
    with pytest.raises(ValueError, match="exceeded"):
        api_request("http://127.0.0.1:8000", "GET", "/api/authoring/workflows/" + "00" * 16)
    assert options[0]["trust_env"] is False


def test_delayed_approval_click_from_previous_checkpoint_cannot_approve_revision(
    authoring_page, client
):
    page, _, _ = authoring_page
    generate(page)
    checkbox(page, "I reviewed").check().run()
    old_approval = button(page, "Approve draft")
    page.text_area[0].set_value("Explain negative integers.").run()
    button(page, "Request changes").click().run()
    assert not checkbox(page, "I reviewed").value
    states = page._tree.get_widget_states()
    states.widgets.add(id=old_approval.id, trigger_value=True)
    page._run(states)
    assert not page.exception
    assert page.session_state["authoring_preview"]["state"]["status"] == "awaiting_review"
    assert len(client.workflow_calls) == 2 and not page.get("download_button")
