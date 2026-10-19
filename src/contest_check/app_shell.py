# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Streamlit application shell, About dialog and local display configuration."""

import base64
import json
import re
from datetime import date
from functools import lru_cache
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st

PACKAGE_ASSETS = Path(__file__).resolve().parent / "assets"
PACKAGED_APP_INFO = PACKAGE_ASSETS / "app-info"
APP_INFO_PATH = (
    PACKAGED_APP_INFO / "app-info.json"
    if (PACKAGED_APP_INFO / "app-info.json").is_file()
    else Path(__file__).resolve().parents[2] / "brand" / "branding.json"
)
APP_INFO_DIRECTORY = APP_INFO_PATH.parent
LICENSE_URL = "https://www.apache.org/licenses/LICENSE-2.0"


@lru_cache(maxsize=1)
def load_app_info() -> dict:
    return json.loads(APP_INFO_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=3)
def asset_uri(field: str) -> str:
    name = load_app_info().get(field, "")
    if not name:
        return ""
    if not re.fullmatch(r"assets/[A-Za-z0-9_-]+\.(svg|png|ico)", name):
        raise ValueError("Application artwork must be a local file inside brand/assets.")
    image_type = {".svg": "svg+xml", ".png": "png", ".ico": "x-icon"}[Path(name).suffix]
    content = base64.b64encode((APP_INFO_DIRECTORY / name).read_bytes()).decode("ascii")
    return f"data:image/{image_type};base64,{content}"


def attribution_html(*, website: bool = True) -> str:
    app_info = load_app_info()
    author = escape(app_info["authorName"])
    site = app_info["authorWebsite"]
    website_link = ""
    if website and site:
        label = escape(urlsplit(site).netloc + urlsplit(site).path.rstrip("/"))
        website_link = (
            f'<a class="cca-author-site" href="{escape(site, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{label}</a>'
        )
    return (
        '<footer class="cca-attribution">'
        f"<span>© {date.today().year} {author}, "
        f'<a href="{LICENSE_URL}" target="_blank" rel="noopener noreferrer">Apache-2.0</a>'
        f"</span>{website_link}</footer>"
    )


def icon(kind: str) -> str:
    shapes = {
        "globe": (
            '<circle cx="12" cy="12" r="9"/>'
            '<path d="M3 12h18M12 3a17 17 0 0 1 0 18 17 17 0 0 1 0-18Z"/>'
        ),
        "code": '<path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18"/>',
        "user": (
            '<circle cx="12" cy="7" r="4"/><path d="M4 21v-3a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v3Z"/>'
        ),
        "heart": (
            '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1'
            'a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>'
        ),
        "coffee": (
            '<path d="M4 8h13v7a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5'
            'Zm13 1h2a3 3 0 0 1 0 6h-2M7 3v2m4-2v2m4-2v2"/>'
        ),
        "info": '<circle cx="12" cy="12" r="9"/><path d="M12 7v6m0 4h.01"/>',
    }
    return (
        '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" focusable="false">{shapes[kind]}</svg>'
    )


def about_link(field: str, label: str, description: str, kind: str) -> str:
    href = load_app_info().get(field, "")
    if not href:
        return ""
    if urlsplit(href).scheme != "https":
        raise ValueError("About links must use HTTPS.")
    tooltip_id = f"cca-tip-{field}"
    css = "cca-about-link cca-coffee" if kind == "coffee" else "cca-about-link"
    return (
        f'<a class="{css}" href="{escape(href, quote=True)}" target="_blank" '
        f'rel="noopener noreferrer" aria-describedby="{tooltip_id}">{icon(kind)}{escape(label)}'
        f'<span class="cca-tooltip" role="tooltip" id="{tooltip_id}">'
        f"<span>{escape(description)}</span><span>{escape(href)}</span></span></a>"
    )


def about_html() -> str:
    app_info = load_app_info()
    author = app_info["authorName"]
    languages = " | ".join(app_info["authorWebsiteLanguages"])
    website = urlsplit(app_info["authorWebsite"]).netloc
    project_links = "".join(
        [
            about_link(
                "authorWebsite",
                website,
                f"About {author}, projects and contact. Available in {languages}.",
                "globe",
            ),
            about_link("appWebsite", "Project website", "Visit the project website.", "globe"),
            about_link("appGithubUrl", "Source", f"Source code for {app_info['appName']}.", "code"),
            about_link("authorGithub", "GitHub profile", f"Explore {author}'s projects.", "user"),
        ]
    )
    support_links = "".join(
        [
            about_link(
                "authorBuyMeACoffeeUrl",
                "Buy me a Coffee",
                f"Support {author} on Buy Me a Coffee.",
                "coffee",
            ),
            about_link(
                "authorWaysToSupportUrl",
                "Ways to support",
                f"Ways to support {author}'s work.",
                "heart",
            ),
        ]
    )
    poster = asset_uri("appPoster")
    return (
        '<div class="cca-about">'
        f'<img class="cca-poster" src="{poster}" '
        f'alt="{escape(app_info["appName"], quote=True)} project poster" width="780" height="480">'
        f'<p class="cca-about-description">{escape(app_info["appDescription"])}</p>'
        f'<nav class="cca-about-links" aria-label="Project and author links">{project_links}</nav>'
        '<nav class="cca-about-links cca-support-links" aria-label="Support the author">'
        f"{support_links}</nav>"
        f'<div class="cca-support-note" role="note">{icon("info")}'
        f"<p>{escape(app_info['supportRemarkText'])}</p></div>"
        f"{attribution_html(website=False)}</div>"
    )


@st.dialog(f"About {load_app_info()['appName']}", width="medium", position="center")
def show_about() -> None:
    st.markdown(about_html(), unsafe_allow_html=True)


def render_shell() -> None:
    app_info = load_app_info()
    st.set_page_config(
        page_title=app_info["appName"],
        page_icon=asset_uri("appFavicon"),
        layout="wide",
        initial_sidebar_state="expanded",
    )
    # This Streamlit version strips style/SVG tags from st.html. Keep trusted
    # local styles in Markdown; uploaded content never enters this renderer.
    styles = "\n".join(
        (PACKAGE_ASSETS / name).read_text(encoding="utf-8") for name in ("styles.css", "about.css")
    )
    st.markdown(f'<style id="cca-app-styles">{styles}</style>', unsafe_allow_html=True)
    with st.container(
        key="app_navbar",
        horizontal=True,
        horizontal_alignment="distribute",
        vertical_alignment="center",
        wrap=False,
    ):
        with st.container(
            key="app_identity",
            horizontal=True,
            width="content",
            vertical_alignment="center",
            gap="small",
            wrap=False,
        ):
            st.html(
                f'<img class="cca-app-icon" src="{asset_uri("appIcon")}" '
                'alt="" width="40" height="40">',
                width=40,
            )
            st.title(app_info["appName"], anchor=False)
        if st.button("About", key="about_dialog", type="tertiary"):
            show_about()


def render_sidebar_footer() -> None:
    with st.sidebar.container(key="sidebar_footer"):
        st.html(attribution_html())
