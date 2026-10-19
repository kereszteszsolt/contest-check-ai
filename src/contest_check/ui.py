# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import os

import httpx
import streamlit as st

from contest_check.app_shell import render_shell, render_sidebar_footer
from contest_check.authoring_ui import leave_authoring, show_authoring
from contest_check.models import UploadError, ValidationSummary
from contest_check.presentation import (
    DQ_COLUMNS,
    MEASUREMENT_NOTE,
    REVIEW_COLUMNS,
    SUMMARY_COLUMNS,
    TEST_COLUMNS,
    policy_rows,
    summary_rows,
    test_rows,
)
from contest_check.reports import MAX_REPORT_BYTES, MIME_TYPES, REJECTION_NOTE, REVIEW_NOTE
from contest_check.results import BatchResult


def local_api_url() -> str:
    host = os.environ.get("API_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "api"}:
        raise ValueError("API_HOST must be loopback or the local Compose API service.")
    port = int(os.environ.get("API_PORT", "8000"))
    if not 1 <= port <= 65_535:
        raise ValueError("API_PORT must be between 1 and 65535.")
    return f"http://{host}:{port}"


def judge_execution_setting() -> bool | None:
    """Read operator intent only; each worker still qualifies before execution."""
    try:
        with httpx.Client(base_url=local_api_url(), timeout=3, trust_env=False) as client:
            response = client.get("/health")
        response.raise_for_status()
        value = response.json()
        if (
            isinstance(value, dict)
            and value.get("status") == "ok"
            and type(value.get("execution_enabled")) is bool
        ):
            return value["execution_enabled"]
    except (httpx.HTTPError, ValueError):
        pass
    return None


def clear_results() -> None:
    st.session_state["judge_status"] = "idle"
    st.session_state["reports"] = {}
    for key in ("batch_result", "judge_error", "export_error"):
        st.session_state.pop(key, None)


def clear_validation() -> None:
    st.session_state["validation_status"] = "idle"
    st.session_state.pop("validation_summary", None)
    st.session_state.pop("validation_error", None)
    clear_results()


def upload_files(task, submissions):
    return {
        "task_zip": ("task.zip", task.getvalue(), "application/zip"),
        "submissions_zip": ("submissions.zip", submissions.getvalue(), "application/zip"),
    }


def service_message(response: httpx.Response) -> str:
    try:
        error = UploadError.model_validate(response.json())
        if error.code == "execution_disabled":
            return (
                "Solution execution is disabled. Archive validation is available; "
                "ask the local operator to enable isolated judging."
            )
        return error.message
    except ValueError:
        return "The service returned an invalid response. Try again."


def validate(task, submissions) -> None:
    clear_validation()
    st.session_state["validation_status"] = "validating"
    with st.status("Validating both archives…", expanded=True) as status:
        st.write("Checking file paths, size limits, task configuration and anonymous IDs.")
        try:
            with httpx.Client(base_url=local_api_url(), timeout=60, trust_env=False) as client:
                response = client.post("/api/validate", files=upload_files(task, submissions))
            if response.is_success:
                summary = ValidationSummary.model_validate(response.json())
                st.session_state["validation_summary"] = summary.model_dump()
                st.session_state["validation_status"] = "validated"
                status.update(label="Archives validated", state="complete", expanded=False)
            else:
                st.session_state["validation_error"] = service_message(response)
                st.session_state["validation_status"] = "error"
                status.update(label="Validation failed", state="error")
        except (httpx.HTTPError, ValueError):
            st.session_state["validation_error"] = (
                "The validation service is unavailable. Try again."
            )
            st.session_state["validation_status"] = "error"
            status.update(label="Validation service unavailable", state="error")


def run_solutions(task, submissions) -> None:
    clear_results()
    summary = ValidationSummary.model_validate(st.session_state["validation_summary"])
    st.session_state["judge_status"] = "running"
    with st.status("Running solutions…", expanded=True) as status:
        st.write(f"{len(summary.participant_ids)} participants · {summary.test_count} tests each.")
        st.write("Each test gets a fresh time limit. Results appear when the batch finishes.")
        try:
            # The separate per-test deadline remains in the worker. This bounds
            # the complete synchronous batch, including qualification and cleanup.
            timeout = httpx.Timeout(
                connect=5,
                read=60 * summary.test_count * len(summary.participant_ids) + 30,
                write=30,
                pool=5,
            )
            with httpx.Client(base_url=local_api_url(), timeout=timeout, trust_env=False) as client:
                response = client.post("/api/judge", files=upload_files(task, submissions))
            if not response.is_success:
                st.session_state["judge_error"] = service_message(response)
                st.session_state["judge_status"] = "error"
                status.update(label="Judging could not finish", state="error")
                return
            batch = BatchResult.model_validate(response.json())
            if (
                batch.task_id != summary.task_id
                or batch.tests_per_participant != summary.test_count
                or [p.participant_id for p in batch.participants] != summary.participant_ids
            ):
                raise ValueError("Result does not belong to the validated uploads.")
            st.session_state["batch_result"] = batch.model_dump()
            st.session_state["judge_status"] = batch.status
            status.update(
                label="Judging complete" if batch.status == "completed" else "Batch incomplete",
                state="complete" if batch.status == "completed" else "error",
                expanded=False,
            )
        except (httpx.HTTPError, ValueError):
            st.session_state["judge_error"] = (
                "Judging is unavailable or returned an invalid result. "
                "Revalidate the archives before retrying."
            )
            st.session_state["judge_status"] = "error"
            status.update(label="Judging unavailable", state="error")


def prepare_reports(batch: BatchResult) -> None:
    st.session_state.pop("export_error", None)
    with st.status("Preparing downloads…", expanded=True) as status:
        try:
            with httpx.Client(base_url=local_api_url(), timeout=60, trust_env=False) as client:
                for report_format in ("pdf", "xlsx"):
                    st.write(f"Preparing {report_format.upper()}…")
                    response = client.post(f"/api/reports/{report_format}", json=batch.model_dump())
                    if not response.is_success:
                        st.session_state["export_error"] = service_message(response)
                        status.update(label="Report preparation failed", state="error")
                        return
                    payload = response.content
                    signature = b"%PDF-" if report_format == "pdf" else b"PK\x03\x04"
                    if (
                        len(payload) > MAX_REPORT_BYTES
                        or not payload.startswith(signature)
                        or response.headers.get("content-type", "").split(";")[0]
                        != MIME_TYPES[report_format]
                    ):
                        raise ValueError("Invalid report response.")
                    st.session_state["reports"][report_format] = payload
            status.update(label="Downloads ready", state="complete", expanded=False)
        except (httpx.HTTPError, ValueError):
            st.session_state["export_error"] = (
                "Reports are unavailable. Your results remain visible; "
                "try preparing the downloads again."
            )
            status.update(label="Report service unavailable", state="error")


def show_table(columns, rows, *, key):
    # Text metrics preserve N/A; participant IDs always remain exact text.
    records = [
        dict(zip(columns, [f"{v:.6g}" if isinstance(v, float) else v for v in row], strict=True))
        for row in rows
    ]
    st.dataframe(
        records,
        hide_index=True,
        width="stretch",
        key=key,
        column_config={
            "Participant ID": st.column_config.TextColumn("Participant ID"),
        },
    )


def show_results(batch: BatchResult) -> None:
    st.subheader("Results")
    st.text(f"Task: {batch.task_id} · Comparison: {batch.comparison}")
    if batch.status == "incomplete":
        st.warning(
            "The batch stopped after a judge system error. "
            "Not-run tests are not participant failures."
        )
    else:
        st.success("Batch complete. Results contain anonymous participant IDs only.")
    st.caption(
        f"Limits per test: {batch.limits.time_seconds:g} s · {batch.limits.memory_mb} MiB · "
        f"{batch.limits.output_bytes} output bytes."
    )
    show_table(SUMMARY_COLUMNS, summary_rows(batch), key="summary_table")
    st.subheader("Per-test outcomes")
    show_table(TEST_COLUMNS, test_rows(batch), key="tests_table")
    st.caption(MEASUREMENT_NOTE)
    st.subheader("Disqualified / Rejected")
    st.caption(REJECTION_NOTE)
    dq = policy_rows(batch, "DQ")
    if dq:
        show_table(DQ_COLUMNS, dq, key="dq_table")
    else:
        st.text("No disqualified participants.")
    st.subheader("Requires Review")
    st.caption(REVIEW_NOTE)
    review = policy_rows(batch, "REVIEW")
    if review:
        show_table(REVIEW_COLUMNS, review, key="review_table")
    else:
        st.text("No review flags.")
    if st.button("Prepare PDF and XLSX", key="prepare_reports"):
        prepare_reports(batch)
    if st.session_state.get("export_error"):
        st.error(st.session_state["export_error"])
    columns = st.columns(2)
    for column, report_format in zip(columns, ("pdf", "xlsx"), strict=True):
        if report_format in st.session_state["reports"]:
            with column:
                st.download_button(
                    f"Download {report_format.upper()}",
                    st.session_state["reports"][report_format],
                    file_name=f"contestcheck-{batch.task_id}.{report_format}",
                    mime=MIME_TYPES[report_format],
                    on_click="ignore",
                    key=f"download_{report_format}",
                )


def main() -> None:
    render_shell()
    workspace = st.sidebar.radio("Workspace", ["Judge submissions", "AI task draft"])
    render_sidebar_footer()
    if workspace == "AI task draft":
        st.caption("Draft a Python challenge, review it and export student and teacher packages.")
        show_authoring(local_api_url())
        return
    leave_authoring()
    st.caption("Validate anonymous Python submissions and test them against private test cases.")
    execution_enabled = judge_execution_setting()
    st.session_state.setdefault("validation_status", "idle")
    st.session_state.setdefault("judge_status", "idle")
    st.session_state.setdefault("reports", {})
    upload_columns = st.columns(2)
    with upload_columns[0]:
        task = st.file_uploader(
            "Teacher task package (.zip)",
            type=["zip"],
            key="task_zip",
            help="Contains challenge/task-config.json and private test pairs. Maximum 10 MiB.",
            on_change=clear_validation,
        )
    with upload_columns[1]:
        submissions = st.file_uploader(
            "Anonymous submissions (.zip)",
            type=["zip"],
            key="submissions_zip",
            help=(
                "Numeric folders with main.py and optional sibling Python modules. Maximum 10 MiB."
            ),
            on_change=clear_validation,
        )
    if st.button("Validate archives", disabled=task is None or submissions is None):
        validate(task, submissions)
    if st.session_state["validation_status"] == "validated":
        summary = st.session_state["validation_summary"]
        st.success("Both archives passed validation.")
        st.text(f"Task: {summary['task_id']}")
        st.text(f"Tests: {summary['test_count']} · Participants: {len(summary['participant_ids'])}")
        st.text("Participant IDs: " + ", ".join(summary["participant_ids"]))
    elif st.session_state["validation_status"] == "error":
        st.error(st.session_state["validation_error"])
    else:
        st.info("Upload both archives and validate them before running solutions.")
    if execution_enabled is False:
        st.info("Solution execution is disabled. You can still upload and validate archives.")
    elif execution_enabled is None:
        st.warning("Cannot confirm the judge status. Check the local API and refresh the page.")
    else:
        st.caption("Isolated judging is enabled. Each worker checks its sandbox before running.")
    if st.button(
        "Run solutions",
        type="primary",
        disabled=execution_enabled is not True
        or st.session_state["validation_status"] != "validated"
        or task is None
        or submissions is None,
    ):
        run_solutions(task, submissions)
    if st.session_state.get("judge_error"):
        st.error(st.session_state["judge_error"])
    if st.session_state.get("batch_result"):
        show_results(BatchResult.model_validate(st.session_state["batch_result"]))
