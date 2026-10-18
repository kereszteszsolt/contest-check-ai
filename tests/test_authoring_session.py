# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import httpx
import pytest

from contest_check.authoring_session import AuthoringSession


def test_closed_session_releases_private_data_and_refuses_late_results_or_creation():
    calls = []

    def delete(api_url, method, path):
        calls.append((api_url, method, path))
        return httpx.Response(204)

    session = AuthoringSession("http://127.0.0.1:8000", delete)
    workflow_id = session.create_id()
    preview = session.remember("preview", {"private": "hidden tests"})
    packages = session.remember("packages", {"teacher": b"private ZIP"})
    assert session.close() and session.close()
    assert preview == {} and packages == {}
    assert calls == [("http://127.0.0.1:8000", "DELETE", f"/api/authoring/workflows/{workflow_id}")]
    with pytest.raises(ValueError):
        session.create_id()
    late_result = {"private": "late generation response"}
    with pytest.raises(ValueError):
        session.remember("preview", late_result)
    assert late_result == {}


def test_cleanup_retries_only_deletion_and_keeps_failed_id_for_another_attempt(caplog):
    calls = []

    def unavailable(*args):
        calls.append(args)
        raise httpx.ConnectError("PRIVATE_INTERNAL_ERROR")

    released = []
    session = AuthoringSession(
        "http://127.0.0.1:8000", unavailable, release_files=lambda: released.append(True)
    )
    workflow_id = session.create_id()
    assert not session.close()
    assert released == [True]
    assert len(calls) == 2 and all(call[1] == "DELETE" for call in calls)
    assert session.workflow_id == workflow_id and session.closed
    assert "PRIVATE" not in caplog.text and workflow_id not in caplog.text
    session.request = lambda *args: httpx.Response(204)
    assert session.close() and session.workflow_id is None
