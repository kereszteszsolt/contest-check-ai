FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2 AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf bison flex gcc g++ git ca-certificates libprotobuf-dev \
    libnl-route-3-dev libtool make pkg-config protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
RUN git init /build/nsjail \
    && git -C /build/nsjail remote add origin https://github.com/google/nsjail.git \
    && git -C /build/nsjail fetch --depth 1 origin 402e2b4c13c79731c632c2add4c3884dd1afc25f \
    && git -C /build/nsjail checkout --detach FETCH_HEAD \
    && git -C /build/nsjail submodule update --init --depth 1 \
    && test "$(git -C /build/nsjail rev-parse HEAD)" = 402e2b4c13c79731c632c2add4c3884dd1afc25f \
    && test "$(git -C /build/nsjail/kafel rev-parse HEAD)" = b4241da9f3d17e786387280fc6e4965634fdf45b \
    && make -C /build/nsjail -j2 \
    && install -m 0755 /build/nsjail/nsjail /usr/local/bin/nsjail
COPY deploy/worker/python.policy /opt/cca-worker/python.policy
COPY deploy/worker/bootstrap.py deploy/worker/build_runtime.py /build/
RUN chmod 0444 /opt/cca-worker/python.policy && python -I -S /build/build_runtime.py

FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libprotobuf32 libnl-route-3-200 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY deploy/worker/requirements.txt /build/requirements.txt
RUN pip install --no-cache-dir --require-hashes -r /build/requirements.txt \
    && rm -rf /build \
    && mkdir -p /workspaces \
    && chown 1000:1000 /workspaces && chmod 0700 /workspaces
COPY --from=build /usr/local/bin/nsjail /usr/local/bin/nsjail
COPY --from=build /opt/cca-jail /opt/cca-jail
COPY --from=build /opt/cca-worker /opt/cca-worker
COPY --from=build /build/nsjail/LICENSE /usr/share/doc/cca-nsjail/LICENSE
COPY --from=build /build/nsjail/kafel/LICENSE /usr/share/doc/cca-kafel/LICENSE
COPY LICENSE /usr/share/doc/contest-check-ai/LICENSE
COPY src/contest_check/__init__.py src/contest_check/models.py /opt/cca-worker/contest_check/
COPY src/contest_check/judge/ /opt/cca-worker/contest_check/judge/
COPY deploy/worker/entrypoint.py /opt/cca-worker/entrypoint.py
USER 1000:1000
WORKDIR /opt/cca-worker
ENTRYPOINT ["python", "-I", "-B", "/opt/cca-worker/entrypoint.py"]
CMD ["--check"]
