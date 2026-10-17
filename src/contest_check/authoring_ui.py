# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Teacher-only provider selection and unverified draft preview."""

import httpx
import streamlit as st

from contest_check.authoring_contracts import MAX_INSTRUCTIONS, DraftResponse, ModelCatalog
from contest_check.models import UploadError


def clear_draft():
    st.session_state.pop("provider_draft", None)
    st.session_state.pop("provider_error", None)


def show_authoring(api_url: str):
    st.subheader("AI task draft")
    st.caption("Use teacher instructions only. Do not paste student submissions or personal data.")
    try:
        with httpx.Client(base_url=api_url, trust_env=False, timeout=10) as client:
            response = client.get("/api/authoring/models")
            response.raise_for_status()
            catalog = ModelCatalog.model_validate(response.json())
    except (httpx.HTTPError, ValueError):
        clear_draft()
        st.error("Model configuration is unavailable. Check the local API and try again.")
        return
    for issue in catalog.issues:
        st.error(issue)
    signature = [(model.slot, model.provider, model.model) for model in catalog.models]
    if st.session_state.get("authoring_catalog") != signature:
        clear_draft()
        st.session_state["authoring_catalog"] = signature
    if not catalog.models:
        clear_draft()
        st.info("No models are available. Ask the local operator to configure a model.")
        return
    choices = {model.slot: model for model in catalog.models}
    slot = st.selectbox(
        "Configured model",
        list(choices),
        index=None,
        placeholder="Choose a provider and model explicitly",
        format_func=lambda value: f"{choices[value].provider} · {choices[value].model}",
        key="authoring_model",
        on_change=clear_draft,
    )
    if slot and choices[slot].provider == "openrouter":
        st.warning(
            "OpenRouter sends these instructions to the selected cloud model provider "
            "and may incur charges. Generate only if you accept this."
        )
    instructions = st.text_area(
        "Teacher instructions",
        max_chars=MAX_INSTRUCTIONS,
        key="authoring_instructions",
        on_change=clear_draft,
    )
    if st.button("Generate draft", disabled=slot is None or not instructions.strip()):
        clear_draft()
        with st.status("Preparing an unverified task draft…") as status:
            try:
                with httpx.Client(base_url=api_url, trust_env=False, timeout=125) as client:
                    response = client.post(
                        "/api/authoring/draft",
                        json={"model_slot": slot, "instructions": instructions},
                    )
                if response.is_success:
                    result = DraftResponse.model_validate(response.json())
                    if result.model != choices[slot]:
                        raise ValueError("Selection changed.")
                    st.session_state["provider_draft"] = result.model_dump()
                    status.update(label="Draft ready for inspection", state="complete")
                else:
                    st.session_state["provider_error"] = UploadError.model_validate(
                        response.json()
                    ).message
                    status.update(label="Draft generation failed", state="error")
            except (httpx.HTTPError, ValueError):
                st.session_state["provider_error"] = (
                    "The selected model is unavailable or returned an invalid draft. Try again."
                )
                status.update(label="Draft generation failed", state="error")
    if st.session_state.get("provider_error"):
        st.error(st.session_state["provider_error"])
    if st.session_state.get("provider_draft"):
        st.warning("Unverified draft. Generated code and tests have not been executed or approved.")
        st.json(st.session_state["provider_draft"], expanded=False)
