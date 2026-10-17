# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pypdf import PdfReader

from contest_check.api import REPORT_SLOT, app
from contest_check.reports import MIME_TYPES, ReportLimit


@pytest.fixture
def client():
    with TestClient(app) as value:
        yield value


@pytest.mark.parametrize("report_format", ["pdf", "xlsx"])
def test_api_returns_only_safe_download_bytes(client, report_batch, report_format):
    response = client.post(f"/api/reports/{report_format}", json=report_batch.model_dump())
    assert response.status_code == 200
    assert response.headers["content-type"] == MIME_TYPES[report_format]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].endswith(
        f'contestcheck-results.{report_format}"'
    )
    if report_format == "pdf":
        assert "1001" in PdfReader(io.BytesIO(response.content)).pages[0].extract_text()
    else:
        workbook = load_workbook(io.BytesIO(response.content))
        assert workbook["Tests"]["A2"].value == "1001"
        workbook.close()


@pytest.mark.parametrize("field", ["source_files", "expected_output", "reference_source"])
def test_private_payloads_are_rejected_without_echoing(client, report_batch, field):
    payload = report_batch.model_dump()
    payload[field] = "PRIVATE_CONTENT_DO_NOT_ECHO"
    response = client.post("/api/reports/pdf", json=payload)
    assert response.status_code == 422
    assert set(response.json()) == {"code", "message"}
    assert "PRIVATE_CONTENT" not in response.text


@pytest.mark.parametrize("path", ["pdf", "xlsx", "unknown"])
@pytest.mark.parametrize("headers", [{}, {"content-length": "1"}])
def test_report_body_is_bounded_before_json_parsing(client, monkeypatch, path, headers):
    monkeypatch.setattr("contest_check.api.MAX_REPORT_REQUEST_BYTES", 10)
    response = client.post(
        f"/api/reports/{path}", content=iter([b"x" * 6, b"x" * 6]), headers=headers
    )
    assert response.status_code == 413 and response.json()["code"] == "request_size"


def test_report_failure_is_safe_and_releases_the_slot(client, report_batch, monkeypatch):
    def fail(*args):
        raise RuntimeError("PRIVATE_SOURCE_OR_PATH")

    with monkeypatch.context() as scoped:
        scoped.setattr("contest_check.api.build_report", fail)
        response = client.post("/api/reports/pdf", json=report_batch.model_dump())
        assert response.status_code == 503
        assert response.json()["code"] == "report_failed" and "PRIVATE" not in response.text
    assert client.post("/api/reports/pdf", json=report_batch.model_dump()).status_code == 200


def test_report_byte_limit_is_explicit(client, report_batch, monkeypatch):
    def fail(*args):
        raise ReportLimit("PRIVATE_PATH")

    monkeypatch.setattr("contest_check.api.build_report", fail)
    response = client.post("/api/reports/xlsx", json=report_batch.model_dump())
    assert response.status_code == 413 and response.json()["code"] == "report_size"
    assert "PRIVATE" not in response.text


def test_concurrent_exports_are_bounded(client, report_batch):
    assert REPORT_SLOT.acquire(blocking=False)
    try:
        response = client.post("/api/reports/pdf", json=report_batch.model_dump())
        assert response.status_code == 503 and response.json()["code"] == "report_busy"
    finally:
        REPORT_SLOT.release()


def test_report_counts_and_ids_are_validated(client, report_batch):
    value = report_batch.model_dump()
    value["participants"][0]["participant_id"] = '=HYPERLINK("PRIVATE")'
    value["participants"][0]["passed_tests"] = 100
    response = client.post("/api/reports/xlsx", json=value)
    assert response.status_code == 422 and "PRIVATE" not in response.text


def test_report_contract_is_documented_as_json(client):
    operation = client.get("/openapi.json").json()["paths"]["/api/reports/{report_format}"]["post"]
    assert "application/json" in operation["requestBody"]["content"]
