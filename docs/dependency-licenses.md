# Dependency license inventory

## CCA-009 Docker application images (2026-10-18)

The application image installs the unchanged locked Python distributions, retaining their installed notices and bundled DejaVu license, on the same digest-pinned CPython/Debian base as the worker. Build-only uv 0.11.29 is copied from its exact official image digest; it is absent from the final application images. The optional trusted judge API target adds only the **Docker CLI 29.6.1** binary from the digest-pinned official `docker:29.6.1-cli` image. Its original [Apache-2.0 license and Docker copyright notice](https://github.com/docker/cli/blob/v29.6.1/LICENSE) are retained in `deploy/app/LICENSE-Docker-CLI.txt` and `/usr/share/doc/docker-cli/LICENSE` in that image. Docker CLI source and its Go dependency notices remain upstream; no binary is vendored in Git or image published. The full Alpine CLI image/daemon/plugins are not copied into the Python application image. This local build is not an independent redistribution/legal audit; review all component obligations before external image distribution.

## CCA-007 embedded PDF fonts (2026-10-18)

Python dependency pins/lockfile and worker dependencies are unchanged. The public challenge PDF uses unmodified **DejaVu Sans / DejaVu Sans Mono 2.37** TTF files, copied from the local `fonts-dejavu-core 2.37-8build1` distribution into `src/contest_check/assets/fonts/`. The font files retain the **Bitstream Vera license** copyright/trademark/permission/disclaimer notice, with DejaVu changes in the public domain. The full applicable upstream font notice is in `LICENSE-DejaVu.txt`, retained in the built Python wheel and copied into every student ZIP as `FONT-LICENSE.txt`. The unrelated Debian packaging files/license section was not copied; no Debian packaging code is vendored. See the [upstream font license](https://dejavu-fonts.github.io/License.html).

SHA-256: `DejaVuSans.ttf` = `b4c632e3cdf9acc7f28758fb5a323c8524d7fc6660d46904d9b6cbe2809c419c`; `DejaVuSansMono.ttf` = `a54dca07c76d6289e717e75e0a58c0128f6d7269ef3faf76417c9d7d3bba37ab`. Copied bytes match their installed upstream originals. The application's own source remains Apache-2.0; these font files are third-party assets with their own terms. This targeted notice review is not an independent legal/security audit. No font download, system font discovery or remote fetch occurs during PDF generation.

PDFium **5.14.0** and Pillow **12.3.0** were installed only in `/tmp/cca007-pdf-review` to render a synthetic PDF for Codex visual inspection; they were not added to the application/test lockfile or worker. The existing results-report renderer still uses its original Helvetica path. See [package contracts](challenge-packages.md) and [release evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

## CCA-006 LangGraph additions (2026-10-18)

The API adds the direct pin `langgraph==1.2.16`, with locked `langgraph-checkpoint==4.3.0`, `langgraph-prebuilt==1.1.1`, `langgraph-sdk==0.4.8` and `ormsgpack==1.13.0`. Installed distribution metadata and retained notices were inspected: the four LangGraph distributions are MIT and each retains its LICENSE; ormsgpack declares **Apache-2.0 OR MIT** and retains both LICENSE-APACHE and LICENSE-MIT.

The required SDK declares `websockets>=14,<17`, so the resolver changes the existing web/API transitive dependency from **17.2 to 16.1.1**; its BSD-3-Clause LICENSE is retained. All other pre-existing locked package versions are unchanged. The application uses the local StateGraph/InMemorySaver, not an SDK remote client or hosted LangGraph service. Tracing is explicitly disabled. No dependency is vendored/modified or image published; the offline worker dependency group, requirements and isolation are unchanged. These notices remain component-specific; this is not a new security/legal audit. See [workflow contracts](authoring-workflow.md) and [release evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

## CCA-005 model adapter additions (2026-10-17)

Existing versions remain unchanged. The following new Linux web/API dependencies were resolved with exact direct pins and a hashed lockfile. Installed distribution metadata and retained license files were inspected; this inventory is not a complete security/legal audit of future bundles.

| New component(s), exact installed version | Package license / retained notices |
| --- | --- |
| langchain-core 1.6.12, langchain-ollama 1.1.0, langchain-openrouter 0.2.9, langchain-protocol 0.0.19, langsmith 0.14.11, ollama 0.6.3 | MIT; each installed distribution retains its LICENSE |
| openrouter 0.10.8, distro 1.9.0, requests-toolbelt 1.0.0, tenacity 9.2.1 | Apache-2.0; installed license texts retained |
| httpx2 2.13.1, httpcore2 2.13.1, jsonpatch 1.35, jsonpointer 3.2.1, uuid-utils 0.17.1, zstandard 0.25.0 | BSD-3-Clause; jsonpatch/jsonpointer also retain AUTHORS |
| jsonpath-python 1.1.6, PyYAML 6.0.3, truststore 0.10.5 | MIT |
| sniffio 1.3.1 | MIT OR Apache-2.0; both notices retained |
| xxhash 4.0.1 | BSD-2-Clause |
| orjson 3.13.0 | **MPL-2.0 AND (Apache-2.0 OR MIT)**; LICENSE-MPL-2.0, LICENSE-APACHE and LICENSE-MIT are all retained |

`httpx2-jsfetch==1.0` is an Emscripten-only conditional lock entry; it is not installed or redistributed in this Linux verification environment and its installed notices were not inspected. Browser/WASM deployment is not supported or verified here. The application itself continues to use HTTPX 0.28.1 for guarded provider requests; HTTPX2 is a separate LangSmith transitive dependency. LangSmith tracing is explicitly disabled, not an enabled runtime service.

All new packages are installed from upstream distributions, without vendoring or modification. ContestCheck's own source remains Apache-2.0; third-party notices/terms remain component-specific, including the orjson MPL components. No new image/binary bundle is published; review and preserve corresponding component/source obligations before later redistribution. The separate offline worker image/dependency group is unchanged and receives no model libraries or credentials. See [model configuration](model-configuration.md) and [Release 0.2 evidence](releases/release-0.2-ai-challenge-authoring/verification.md).

## CCA-004 reporting additions (2026-10-17)

All earlier dependency versions are unchanged. Runtime adds [ReportLab 5.0.1](https://pypi.org/project/reportlab/5.0.1/) and [XlsxWriter 3.2.9](https://pypi.org/project/XlsxWriter/3.2.9/); development-only readers add [openpyxl 3.1.5](https://pypi.org/project/openpyxl/3.1.5/), [pypdf 6.21.1](https://pypi.org/project/pypdf/6.21.1/) and et-xmlfile 2.0.0. Installed wheel notices and metadata were inspected, not only the project classifiers:

| Component | Installed notices / scope |
| --- | --- |
| ReportLab toolkit | BSD-3-Clause text in its distribution LICENSE; depends on already installed Pillow/charset-normalizer |
| ReportLab bundled fonts | Bitstream Vera notice and DarkGarden GPL-2.0-or-later font notice with its document-embedding exception are retained in the installed package; these components are not represented as BSD-only |
| XlsxWriter | BSD-2-Clause LICENSE.txt |
| openpyxl / et-xmlfile | MIT; et-xmlfile also retains its Python standard-library-derived-code notice in LICENCE.python |
| pypdf | BSD-3-Clause license text |

The application uses ReportLab's built-in Helvetica and does not copy or embed the bundled Vera/DarkGarden fonts. No dependency source/font is vendored or modified and no new Docker image is published. The separate worker dependency group/image is unchanged: report libraries are installed only in the web/API environment. Upstream notices remain with the wheels; any later bundled/image distribution must preserve the applicable component notices and terms. The application's own source remains Apache-2.0. This is a targeted component inventory, not a complete legal audit of arbitrary future bundles.

PDFium 5.14.0/Pillow 12.3.0 were used only in a temporary external inspection environment to render this story's generated PDF; PDFium is not an application/test dependency or shipped asset. Optional Node/Playwright/Chromium browser verification is also outside the Python runtime and its worker image.

## Earlier foundation and worker inventory

CCA-002 adds a separate worker image, not a change to these installed web-app dependency versions. Its pinned NsJail/Kafel and native runtime component review is in [judge-worker.md](judge-worker.md#licensing-and-distribution); native packages retain LGPL/GPL-with-exception and other component licenses. The image as a whole is not represented as exclusively Apache-2.0. No image was published.

Observed on 2026-10-17 from installed Python 3.12.13 distribution metadata after the locked Linux sync. Versions and hashes are recorded in `uv.lock`. This is a metadata/license-notice review for the foundation, not a security audit or approval of the future judge. No third-party code is vendored or modified.

Direct runtime dependencies: FastAPI (MIT), Pydantic (MIT), Streamlit (Apache-2.0), HTTPX (BSD), python-multipart (Apache-2.0), Uvicorn (BSD-3-Clause). Development tools: pytest and Ruff (MIT). The build backend is Hatchling 1.27.0 (MIT), with its existing upstream notices retained in the uv build cache.

Most transitive dependencies use permissive MIT/BSD/Apache/PSF licenses. `certifi` uses MPL-2.0; its unmodified certificate bundle and notices remain in its package, with no relicensing of that component. NumPy and other binary wheels may carry additional bundled-library notices: preserve the wheel's `dist-info/licenses` and package license files in any later redistributed container/artifact. No production container or bundled redistribution is produced in CCA-001.

| Installed distribution | Version | Declared license expression or metadata |
| --- | --- | --- |
| altair | 6.3.0 | OSI Approved :: BSD License |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.7.22 | OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| fastapi | 0.143.3 | MIT |
| h11 | 0.16.0 | OSI Approved :: MIT License |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpx | 0.28.1 | OSI Approved :: BSD License |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| itsdangerous | 2.2.0 | OSI Approved :: BSD License |
| Jinja2 | 3.1.6 | OSI Approved :: BSD License |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| narwhals | 2.27.1 | MIT |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pandas | 3.0.6 | OSI Approved :: BSD License |
| pillow | 12.3.0 | MIT-CMU |
| pluggy | 1.7.0 | OSI Approved :: MIT License |
| protobuf | 7.36.2 | 3-Clause BSD License |
| pyarrow | 26.0.0 | Apache-2.0 |
| pydantic | 2.14.1 | MIT |
| pydantic_core | 2.50.1 | MIT |
| pydeck | 0.9.3 | Apache License 2.0 |
| Pygments | 2.21.0 | BSD-2-Clause |
| pytest | 9.1.1 | MIT |
| python-dateutil | 2.9.0.post0 | OSI Approved :: BSD License, OSI Approved :: Apache Software License |
| python-multipart | 0.0.32 | Apache-2.0 |
| referencing | 0.37.0 | MIT |
| requests | 2.34.2 | OSI Approved :: Apache Software License |
| rpds-py | 2026.9.1 | MIT |
| ruff | 0.17.1 | MIT |
| six | 1.17.0 | OSI Approved :: MIT License |
| starlette | 1.8.0 | BSD-3-Clause |
| streamlit | 1.66.0 | Apache-2.0 |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| watchdog | 6.0.0 | OSI Approved :: Apache Software License |
| websockets | 17.2 | BSD-3-Clause |
