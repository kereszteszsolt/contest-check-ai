FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build
COPY --from=ghcr.io/astral-sh/uv@sha256:78923b1c11ab847cc275c5706c70debc9eac743f935d7ad11966c1c983236aa3 /usr/local/bin/uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS app
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 contest \
    && useradd --uid 1000 --gid 1000 --create-home contest
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANGSMITH_TRACING=false \
    LANGCHAIN_TRACING_V2=false
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY streamlit_app.py LICENSE ./
COPY .streamlit/config.toml ./.streamlit/config.toml
USER 1000:1000
CMD ["uvicorn", "contest_check.api:app", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "4"]

# Only the explicitly enabled trusted coordinator gets a Docker CLI.
FROM docker:29.6.1-cli@sha256:862099ada15c669000bef53aa4cb9d821262829f45b0dda2159ccb276443043b AS docker-cli
FROM app AS judge-api
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
# worker_transport resolves this location from the installed package, not the host checkout.
COPY deploy/worker/docker-seccomp.json /app/.venv/lib/python3.12/deploy/worker/docker-seccomp.json
COPY deploy/app/LICENSE-Docker-CLI.txt /usr/share/doc/docker-cli/LICENSE
RUN python -c "from contest_check.worker_transport import REPOSITORY; assert (REPOSITORY / 'deploy/worker/docker-seccomp.json').is_file()"
