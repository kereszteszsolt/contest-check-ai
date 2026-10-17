# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import os

import httpx
import streamlit as st
from pydantic import ValidationError

from contest_check.models import UploadError, ValidationSummary


def local_api_url() -> str:
    port = int(os.environ.get("API_PORT", "8000"))
    if not 1 <= port <= 65_535:
        raise ValueError("API_PORT must be between 1 and 65535.")
    return f"http://127.0.0.1:{port}"


def clear_validation() -> None:
    st.session_state["validation_status"] = "idle"
    st.session_state.pop("validation_summary", None)
    st.session_state.pop("validation_error", None)


def main() -> None:
    st.set_page_config(page_title="ContestCheck AI", page_icon="📦", layout="centered")
    st.title("ContestCheck AI")
    st.caption("Validate one task package and anonymous Python submissions.")
    st.info(
        "Running solutions is disabled in this screen. This step checks uploaded archives only."
    )
    st.session_state.setdefault("validation_status", "idle")
    task = st.file_uploader(
        "Teacher task package (.zip)",
        type=["zip"],
        key="task_zip",
        help=("Contains challenge/task-config.json and private test pairs. Maximum 10 MiB."),
        on_change=clear_validation,
    )
    submissions = st.file_uploader(
        "Anonymous submissions (.zip)",
        type=["zip"],
        key="submissions_zip",
        help="Numeric folders with main.py and optional sibling Python modules. Maximum 10 MiB.",
        on_change=clear_validation,
    )
    if st.button("Validate archives", type="primary", disabled=task is None or submissions is None):
        clear_validation()
        st.session_state["validation_status"] = "validating"
        with st.spinner("Checking archives and task manifest…"):
            try:
                with httpx.Client(base_url=local_api_url(), timeout=60, trust_env=False) as client:
                    response = client.post(
                        "/api/validate",
                        files={
                            "task_zip": ("task.zip", task.getvalue(), "application/zip"),
                            "submissions_zip": (
                                "submissions.zip",
                                submissions.getvalue(),
                                "application/zip",
                            ),
                        },
                    )
                if response.is_success:
                    summary = ValidationSummary.model_validate(response.json())
                    st.session_state["validation_summary"] = summary.model_dump()
                    st.session_state["validation_status"] = "validated"
                else:
                    error = UploadError.model_validate(response.json())
                    st.session_state["validation_error"] = error.message
                    st.session_state["validation_status"] = "error"
            except (httpx.HTTPError, ValueError, ValidationError):
                st.session_state["validation_error"] = (
                    "The validation service is unavailable. Start the local API and try again."
                )
                st.session_state["validation_status"] = "error"
    if st.session_state["validation_status"] == "validated":
        summary = st.session_state["validation_summary"]
        st.success("Archives validated. Temporary validation files have been removed.")
        st.text(f"Task: {summary['task_id']}")
        st.text(f"Tests: {summary['test_count']} · Participants: {len(summary['participant_ids'])}")
        st.text("Participant IDs: " + ", ".join(summary["participant_ids"]))
    elif st.session_state["validation_status"] == "error":
        st.error(st.session_state["validation_error"])
    st.button(
        "Run solutions",
        disabled=True,
        help="Running solutions and viewing test results in this screen is not available yet.",
    )
