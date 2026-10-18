# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Teacher review of bounded API workflows; untrusted content is always inert text."""

import io
import json
import zipfile

import httpx
import streamlit as st
from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx

from contest_check.archives import DEFAULT_LIMITS, validate_export_archive
from contest_check.authoring_contracts import MAX_INSTRUCTIONS, ModelCatalog
from contest_check.authoring_session import AuthoringSession
from contest_check.challenge_packages import starter
from contest_check.model_configuration import ERRORS as PROVIDER_ERRORS
from contest_check.package_contracts import PackageError, StudentManifest
from contest_check.workflow_contracts import (
    MAX_ATTEMPTS,
    UNVERIFIED,
    ReviewRequest,
    WorkflowFailure,
    WorkflowPreview,
    WorkflowRequest,
)

ROOT = "/api/authoring/workflows"
# One model timeout (120s), at most 20 worker runs (45s each), plus transport margin.
WORKFLOW_TIMEOUT = httpx.Timeout(1050, connect=5, write=30, pool=5)
KNOWN_ERRORS = PROVIDER_ERRORS | WorkflowFailure.ERRORS | PackageError.ERRORS


def api_request(api_url, method, path, *, payload=None, creation_id=None, slow=False):
    """Fixed local API only; bounded response reads, no proxy or automatic retry."""
    headers = {"Idempotency-Key": creation_id} if creation_id else {}
    limit = DEFAULT_LIMITS.archive_bytes if "/packages/" in path else 1024 * 1024
    with httpx.Client(
        base_url=api_url, trust_env=False, timeout=WORKFLOW_TIMEOUT if slow else 10
    ) as client:
        with client.stream(method, path, json=payload, headers=headers) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > limit:
                    raise ValueError("API response exceeded its limit.")
                body.extend(chunk)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=bytes(body),
                request=response.request,
            )


@st.cache_resource(scope="session", on_release=lambda session: session.close(), show_spinner=False)
def browser_authoring_session(api_url):
    # Pinned Streamlit 1.66 runtime adapter: download storage outlives a disconnected page.
    manager = runtime.get_instance().media_file_mgr
    session_id = get_script_run_ctx().session_id

    def release_files():
        manager.clear_session_refs(session_id)
        # Downloads use mark-then-delete; both passes preserve other active sessions' refs.
        manager.remove_orphaned_files()
        manager.remove_orphaned_files()

    return AuthoringSession(api_url, api_request, release_files)


def clear_authoring_state():
    for key in list(st.session_state):
        if key.startswith(("authoring_", "revision_", "acknowledge_")):
            del st.session_state[key]


def leave_authoring():
    session = st.session_state.get("authoring_resource")
    if session is not None:
        session.close()
        browser_authoring_session.clear(session.api_url)
        clear_authoring_state()


def bind_authoring_session(api_url):
    session = browser_authoring_session(api_url)
    previous = st.session_state.get("authoring_resource")
    if previous is not session:
        if previous is not None:
            previous.close()
        clear_authoring_state()
        st.session_state["authoring_resource"] = session
    return session


def safe_error(response):
    try:
        code = response.json().get("code")
        if code in KNOWN_ERRORS:
            return KNOWN_ERRORS[code][1]
    except (ValueError, AttributeError, TypeError):
        pass
    return "The local API could not complete this action. Check its configuration and refresh."


def clear_packages():
    st.session_state.pop("authoring_packages", None)


def accept_preview(response):
    if not response.is_success:
        raise ValueError(safe_error(response))
    preview = WorkflowPreview.model_validate(response.json())
    if preview.workflow_id != st.session_state["authoring_workflow_id"]:
        raise ValueError("The API returned a different workflow.")
    expected = st.session_state.get("authoring_expected")
    if expected and (
        preview.state.request.model_dump(mode="json") != expected["request"]
        or preview.state.model.model_dump(mode="json") != expected["model"]
    ):
        raise ValueError("The API returned a different request or model.")
    st.session_state["authoring_preview"] = st.session_state["authoring_resource"].remember(
        "preview", preview.model_dump(mode="json")
    )


def transition(api_url, method, path, **kwargs):
    """Invalidate decisions/downloads before a mutation or an uncertain refresh."""
    st.session_state.pop("authoring_preview", None)
    st.session_state.pop("authoring_error", None)
    clear_packages()
    try:
        response = api_request(api_url, method, path, **kwargs)
        if not response.is_success:
            st.session_state["authoring_error"] = safe_error(response)
        else:
            accept_preview(response)
    except (httpx.HTTPError, ValueError):
        st.session_state["authoring_error"] = (
            "The outcome is unknown. Refresh this workflow to recover its current state. "
            "No model call is retried automatically."
        )


def new_workflow(api_url, browser_session):
    try:
        catalog_response = api_request(api_url, "GET", "/api/authoring/models")
        catalog_response.raise_for_status()
        catalog = ModelCatalog.model_validate(catalog_response.json())
    except (httpx.HTTPError, ValueError):
        st.error("Model configuration is unavailable. Check the local API and try again.")
        return
    for issue in catalog.issues:
        st.error("Model configuration issue")
        st.text(issue)
    if not catalog.models:
        st.info("No models are available. Ask the local operator to configure a model.")
        return
    choices = {model.slot: model for model in catalog.models}
    if st.session_state.get("authoring_model") not in choices:
        st.session_state.pop("authoring_model", None)
    slot = st.selectbox(
        "Configured model",
        list(choices),
        index=None,
        placeholder="Choose a provider and model explicitly",
        format_func=lambda value: f"{choices[value].provider} · {choices[value].model}",
        key="authoring_model",
    )
    if slot and choices[slot].provider == "openrouter":
        st.warning(
            "OpenRouter sends instructions and revision context to the selected cloud provider "
            "and may incur charges. Generate only if you accept this."
        )
    topic = st.text_input("Topic", max_chars=120, key="authoring_topic")
    difficulty = st.selectbox(
        "Difficulty", ["beginner", "intermediate", "advanced"], key="authoring_difficulty"
    )
    instructions = st.text_area(
        "Teacher instructions", max_chars=MAX_INSTRUCTIONS, key="authoring_instructions"
    )
    run_reference = st.checkbox(
        "Request isolated reference checks", value=False, key="authoring_reference_checks"
    )
    st.caption(
        "Reference code runs only in the separately enabled, qualified offline worker. "
        "Unavailable checks remain blocked; passing checks do not establish correctness."
    )
    if st.button("Generate draft", disabled=not (slot and topic.strip() and instructions.strip())):
        request = WorkflowRequest(
            model_slot=slot,
            topic=topic,
            difficulty=difficulty,
            instructions=instructions,
            run_reference_tests=run_reference,
        )
        try:
            workflow_id = browser_session.create_id()
        except ValueError:
            st.info("This session ended. Reload the page to start a new draft.")
            return
        st.session_state["authoring_workflow_id"] = workflow_id
        st.session_state["authoring_expected"] = browser_session.remember(
            "request",
            {
                "request": request.model_dump(mode="json"),
                "model": choices[slot].model_dump(mode="json"),
            },
        )
        with st.status("Generating and checking the draft…"):
            transition(
                api_url,
                "POST",
                ROOT,
                payload=request.model_dump(mode="json"),
                creation_id=workflow_id,
                slow=True,
            )
        st.rerun()


def preview_draft(preview):
    state = preview.state
    st.text(f"Model: {state.model.provider} · {state.model.model}")
    st.text(
        f"Status: {state.status} | Attempt: {state.attempts}/{MAX_ATTEMPTS} | "
        f"Model calls: {state.model_calls} | Tools: {state.tool_calls}/6 | "
        f"Reference runs: {state.reference_runs}/20"
    )
    st.warning(UNVERIFIED)
    with st.expander("Original teacher request"):
        st.text(f"Topic: {state.request.topic} | Difficulty: {state.request.difficulty}")
        st.text(state.request.instructions)
    if state.model.provider == "openrouter" and preview.can_revise:
        st.warning(
            "Requesting changes makes another call to this cloud model and may incur charges."
        )
    for error in state.errors:
        st.text(f"Attempt {error.attempt}: {error.code}")
    draft = state.draft
    if draft is not None:
        st.subheader("Problem statement")
        st.text(draft.title)
        st.text(draft.statement)
        st.text(
            f"Files: {draft.input_filename} → {draft.output_filename} | "
            f"Comparison: {draft.comparison} | Time: {draft.limits.time_seconds}s | "
            f"Memory: {draft.limits.memory_mb} MiB | Output: {draft.limits.output_bytes} bytes"
        )
        with st.expander("Public examples and exported starter", expanded=True):
            for index, example in enumerate(draft.examples, 1):
                st.text(f"Example {index} input")
                st.code(example.input, language="text", wrap_lines=True)
                st.text("Expected output")
                st.code(example.output, language="text", wrap_lines=True)
                st.text(example.explanation)
            st.text("Student starter: fixed file I/O scaffold; generated starter text is excluded.")
            st.code(starter(StudentManifest.from_draft(draft)).decode(), language="python")
        with st.expander("Teacher only: reference, private tests and generated starter suggestion"):
            st.text("Reference solution candidate")
            st.code(draft.reference_source, language="python", wrap_lines=True)
            st.text("Private tests")
            st.code(
                json.dumps([test.model_dump() for test in draft.private_tests], indent=2),
                language="json",
                wrap_lines=True,
            )
            st.text("Generated starter suggestion (teacher only; never included in student ZIP)")
            st.code(draft.starter_source, language="python", wrap_lines=True)
    with st.expander("Warnings, checks and decision history", expanded=True):
        for warning in state.warnings + (draft.warnings if draft else []):
            st.text(warning)
        st.code(
            json.dumps(
                {
                    "checks": [tool.model_dump(mode="json") for tool in state.tool_results],
                    "decisions": [event.model_dump(mode="json") for event in state.reviews],
                },
                indent=2,
            ),
            language="json",
            wrap_lines=True,
        )


def review_controls(api_url, preview):
    review_id = preview.state.review_id
    revision = st.text_area("Changes requested", max_chars=2000, key=f"revision_{review_id}")
    acknowledged = st.checkbox(
        "I reviewed the statement, examples, reference and private tests, and accept the warnings.",
        key=f"acknowledge_{review_id}",
    )
    action = None
    if (
        st.button(
            "Request changes",
            key=f"revise_{review_id}",
            disabled=not (preview.can_revise and revision.strip()),
        )
        and preview.can_revise
        and revision.strip()
    ):
        action = "revise"
    if not preview.can_revise:
        st.info("The revision budget is exhausted. Reject this draft or review it for approval.")
    if (
        st.button(
            "Approve draft",
            key=f"approve_{review_id}",
            disabled=not (preview.can_approve and acknowledged),
        )
        and preview.can_approve
        and acknowledged
    ):
        action = "approve"
    if st.button("Reject draft", key=f"reject_{review_id}"):
        action = "reject"
    if action:
        decision = ReviewRequest(
            review_id=review_id, action=action, revision=revision if action == "revise" else ""
        )
        with st.status("Applying the teacher decision…"):
            transition(
                api_url,
                "POST",
                f"{ROOT}/{preview.workflow_id}/review",
                payload=decision.model_dump(mode="json"),
                slow=action == "revise",
            )
        st.rerun()


def package_downloads(api_url, preview):
    st.success("Teacher approval recorded. The challenge remains unverified.")
    st.warning("Keep the teacher ZIP private: it contains hidden tests and review metadata.")
    include_reference = st.checkbox(
        "Include the reference source I independently reviewed in the teacher ZIP",
        key="authoring_include_reference",
        on_change=clear_packages,
    )
    cache_key = (preview.workflow_id, include_reference)
    if st.button("Prepare separate ZIP downloads"):
        clear_packages()
        try:
            packages = {}
            for audience in ("student", "teacher"):
                response = api_request(
                    api_url,
                    "POST",
                    f"{ROOT}/{preview.workflow_id}/packages/{audience}",
                    payload={
                        "include_reviewed_reference": include_reference and audience == "teacher"
                    },
                )
                if not response.is_success:
                    st.error(safe_error(response))
                    return
                filename = f"{preview.state.draft.task_id}-{audience}.zip"
                if (
                    response.headers.get("content-type") != "application/zip"
                    or response.headers.get("content-disposition")
                    != f'attachment; filename="{filename}"'
                    or len(response.content) > DEFAULT_LIMITS.archive_bytes
                ):
                    raise ValueError("Invalid archive response.")
                validate_export_archive(response.content, audience)
                if audience == "student":
                    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
                        manifest = StudentManifest.model_validate_json(
                            archive.read("student-manifest.json")
                        )
                    if manifest != StudentManifest.from_draft(preview.state.draft):
                        raise ValueError("Archive does not match the reviewed draft.")
                packages[audience] = (filename, response.content)
            st.session_state["authoring_resource"].remember("packages", packages)
            st.session_state["authoring_packages"] = (cache_key, packages)
        except (httpx.HTTPError, ValueError, zipfile.BadZipFile, KeyError):
            st.error(
                "The ZIP response could not be verified. Refresh and prepare the packages again."
            )
    cached = st.session_state.get("authoring_packages")
    if cached and cached[0] == cache_key:
        for audience, (filename, content) in cached[1].items():
            st.download_button(
                f"Download {audience} ZIP",
                data=content,
                file_name=filename,
                mime="application/zip",
                on_click="ignore",
                key=f"download_{audience}",
            )


def show_authoring(api_url: str):
    st.subheader("AI task draft")
    st.caption("Teacher workspace. Do not paste student submissions or personal data.")
    browser_session = bind_authoring_session(api_url)
    st.caption("Drafts are temporary. Leaving this workspace or disconnecting deletes the draft.")
    workflow_id = st.session_state.get("authoring_workflow_id")
    if not workflow_id:
        new_workflow(api_url, browser_session)
        return
    st.caption("Refresh reads the current draft without calling a model.")
    if st.button("Refresh draft", key=f"refresh_{workflow_id}"):
        transition(api_url, "GET", f"{ROOT}/{workflow_id}")
        st.rerun()
    if st.button("Discard draft and start over", key=f"delete_{workflow_id}"):
        try:
            response = api_request(api_url, "DELETE", f"{ROOT}/{workflow_id}")
            if response.status_code not in (204, 404):
                st.error(safe_error(response))
                return
        except (httpx.HTTPError, ValueError):
            st.error("Deletion is unconfirmed. Refresh before trying again.")
            return
        browser_session.forget()
        clear_authoring_state()
        st.session_state["authoring_resource"] = browser_session
        st.rerun()
    if st.session_state.get("authoring_error"):
        st.error(st.session_state["authoring_error"])
    raw_preview = st.session_state.get("authoring_preview")
    if raw_preview is None:
        st.info(
            "Refresh to confirm the result before making another decision or downloading packages."
        )
        return
    preview = WorkflowPreview.model_validate(raw_preview)
    preview_draft(preview)
    if preview.state.status == "awaiting_review":
        review_controls(api_url, preview)
    elif preview.state.status == "approved":
        package_downloads(api_url, preview)
    elif preview.state.status == "rejected":
        st.info("Draft rejected. No final packages are available.")
