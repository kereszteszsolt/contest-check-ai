# Dependency license inventory — CCA-001

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
