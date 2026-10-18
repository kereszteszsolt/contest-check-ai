# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import io
import os
import threading
from types import SimpleNamespace

import pytest

from contest_check import worker_transport as transport
from contest_check.judge.contracts import RuntimeResult, WorkerRequest
from contest_check.models import TaskManifest


@pytest.fixture
def worker_request(manifest):
    return WorkerRequest(
        participant_id="1001",
        task=TaskManifest.model_validate(manifest),
        test_id="01",
        source_files={"main.py": base64.b64encode(b"# PRIVATE_INERT_SOURCE").decode()},
        input_base64="",
    )


def test_command_is_fixed_offline_and_has_no_code_or_socket_mount(worker_request, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://untrusted.invalid:2375")
    command = transport.worker_command("/usr/bin/docker", "controlled-name")
    assert command[:4] == ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock", "run"]
    for flag in (
        "--pull=never",
        "--network=none",
        "--read-only",
        "--user=1000:1000",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--pids-limit=16",
        "--memory=384m",
        "--memory-swap=384m",
        "--cpus=1",
        "--init",
    ):
        assert flag in command
    assert command[-2:] == [transport.IMAGE, "--run"]
    assert not any(
        value.startswith(("--volume", "--mount", "--publish", "--env")) for value in command
    )
    assert "PRIVATE" not in str(command) and "untrusted.invalid" not in str(command)
    assert worker_request.source_files["main.py"] not in command


@pytest.mark.parametrize(
    "failure", [None, "timeout", "invalid_json", "bad_exit", "cleanup", "kill"]
)
def test_transport_always_removes_only_its_container(worker_request, monkeypatch, failure):
    launches = []
    removals = []

    class Process:
        def __init__(self, command, **kwargs):
            launches.append((command, kwargs))
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO()
            self.killed = False

        def poll(self):
            return None if failure in {"timeout", "kill"} and not self.killed else 0

        def kill(self):
            if failure == "kill":
                raise OSError("PRIVATE_CLI_ERROR")
            self.killed = True

        def wait(self, timeout):
            return 0

    def exchange(process, payload):
        assert payload == worker_request.model_dump_json().encode()
        if failure in {"timeout", "kill"}:
            raise TimeoutError("PRIVATE_PATH")
        if failure == "invalid_json":
            return 0, b"PRIVATE_TRACEBACK"
        raw = (
            RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")
            .model_dump_json()
            .encode()
        )
        return (0 if failure == "bad_exit" else 78), raw

    def remove(command, **kwargs):
        removals.append((command, kwargs))
        return SimpleNamespace(returncode=1 if failure == "cleanup" else 0)

    monkeypatch.setattr(transport.shutil, "which", lambda value: "/usr/bin/docker")
    monkeypatch.setattr(transport.subprocess, "Popen", Process)
    monkeypatch.setattr(transport, "exchange", exchange)
    monkeypatch.setattr(transport.subprocess, "run", remove)
    result = transport.DockerWorker().execute(worker_request)
    assert result.status == "system_error"
    assert "PRIVATE" not in result.model_dump_json()
    assert len(launches) == len(removals) == 1
    command, options = launches[0]
    name = command[command.index("--name") + 1]
    assert name.startswith(transport.worker_project() + "-judge-worker-")
    assert removals[0][0] == [
        "/usr/bin/docker",
        "--host",
        transport.LOCAL_DAEMON,
        "rm",
        "--force",
        name,
    ]
    assert options["env"] == {"PATH": os.defpath, "LANG": "C.UTF-8"}
    if failure in {"cleanup", "kill"}:
        assert result.diagnostic == "cleanup_failed"
    if failure in {"invalid_json", "bad_exit"}:
        assert result.diagnostic == "worker_protocol"


def test_no_docker_means_no_fallback(worker_request, monkeypatch):
    monkeypatch.setattr(transport.shutil, "which", lambda value: None)
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *a, **kw: pytest.fail("No fallback"))
    result = transport.DockerWorker().execute(worker_request)
    assert result.status == "system_error" and result.diagnostic == "worker_transport"


def test_unresponsive_worker_has_a_bounded_infrastructure_deadline(monkeypatch):
    input_read, input_write = os.pipe()
    output_read, output_write = os.pipe()
    process = SimpleNamespace(
        stdin=os.fdopen(input_write, "wb", buffering=0),
        stdout=os.fdopen(output_read, "rb", buffering=0),
    )
    monkeypatch.setattr(transport, "WORKER_TIMEOUT_SECONDS", 0)
    try:
        with pytest.raises(TimeoutError):
            transport.exchange(process, b"inert request")
    finally:
        process.stdin.close()
        process.stdout.close()
        os.close(input_read)
        os.close(output_write)


@pytest.mark.parametrize(
    "enabled, reviewed, expected",
    [
        ("false", "true", False),
        ("true", "false", False),
        ("true", "true", True),
        ("TRUE", "true", False),
        ("true", "TRUE", False),
    ],
)
def test_configuration_requires_both_explicit_operator_settings(
    monkeypatch, enabled, reviewed, expected
):
    monkeypatch.setenv("JUDGE_EXECUTION_ENABLED", enabled)
    monkeypatch.setenv("JUDGE_REVIEWED_PROFILE", reviewed)
    assert transport.configured() is expected


@pytest.mark.parametrize("response_size, cap", [(10, 100), (101, 100)])
def test_exchange_bounds_pipe_output_and_drains_input(monkeypatch, response_size, cap):
    # Trusted pipe helper only: no child interpreter or student program is launched.
    input_read, input_write = os.pipe()
    output_read, output_write = os.pipe()
    payload = b"inert request" * 10_000
    received = bytearray()
    process = SimpleNamespace(
        stdin=os.fdopen(input_write, "wb", buffering=0),
        stdout=os.fdopen(output_read, "rb", buffering=0),
        wait=lambda timeout: 0,
    )

    def peer():
        with os.fdopen(input_read, "rb") as incoming, os.fdopen(output_write, "wb") as outgoing:
            received.extend(incoming.read())
            outgoing.write(b"x" * response_size)

    monkeypatch.setattr(transport, "MAX_RESPONSE_BYTES", cap)
    thread = threading.Thread(target=peer)
    thread.start()
    try:
        if response_size > cap:
            with pytest.raises(ValueError):
                transport.exchange(process, payload)
        else:
            code, raw = transport.exchange(process, payload)
            assert code == 0 and raw == b"x" * response_size
    finally:
        process.stdin.close()
        process.stdout.close()
        thread.join(timeout=2)
    assert not thread.is_alive() and bytes(received) == payload


@pytest.mark.parametrize("project", ["contest-check-ai", "cca-second_local"])
def test_workers_are_grouped_in_the_operator_compose_project(monkeypatch, project):
    monkeypatch.setenv("JUDGE_COMPOSE_PROJECT", project)
    command = transport.worker_command("/usr/bin/docker", "trusted-worker-name")
    assert f"--label=com.docker.compose.project={project}" in command
    assert "--label=com.docker.compose.service=judge-worker" in command
    assert not any("com.docker.compose.oneoff" in value for value in command)
    assert "--label=net.kereszteszsolt.contest-check.role=judge-worker" in command
    assert not any(value.startswith(("--env", "--mount", "--publish")) for value in command)


@pytest.mark.parametrize("project", ["", "Bad Project", "../escape", "--privileged", "a" * 64])
def test_invalid_operator_project_names_use_the_safe_default(monkeypatch, project):
    monkeypatch.setenv("JUDGE_COMPOSE_PROJECT", project)
    assert transport.worker_project() == "contest-check-ai"
