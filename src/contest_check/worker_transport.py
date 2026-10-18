# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Local operator transport. Only a fixed, hardened worker command is launched."""

import os
import re
import selectors
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from contest_check.judge.contracts import RuntimeResult, WorkerRequest

REPOSITORY = Path(__file__).resolve().parents[2]
IMAGE = "contest-check-worker:cca003"
MAX_RESPONSE_BYTES = 1_500_000
WORKER_TIMEOUT_SECONDS = 45.0  # Includes trusted startup qualification, not a test metric.
LOCAL_DAEMON = "unix:///var/run/docker.sock"


def configured() -> bool:
    return (
        os.environ.get("JUDGE_EXECUTION_ENABLED") == "true"
        and os.environ.get("JUDGE_REVIEWED_PROFILE") == "true"
    )


def worker_project() -> str:
    # Operator metadata only; never derive labels/names from uploaded task data.
    project = os.environ.get("JUDGE_COMPOSE_PROJECT", "contest-check-ai")
    return project if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", project) else "contest-check-ai"


def worker_command(docker: str, name: str) -> list[str]:
    return [
        docker,
        "--host",
        LOCAL_DAEMON,
        "run",
        "--pull=never",
        "--interactive",
        "--name",
        name,
        # Desktop excludes oneoff=True containers from the project group.
        "--label=com.docker.compose.project=" + worker_project(),
        "--label=com.docker.compose.service=judge-worker",
        "--label=net.kereszteszsolt.contest-check.role=judge-worker",
        "--network=none",
        "--read-only",
        "--user=1000:1000",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--security-opt=seccomp=" + str(REPOSITORY / "deploy/worker/docker-seccomp.json"),
        "--init",
        "--pids-limit=16",
        "--memory=384m",
        "--memory-swap=384m",
        "--cpus=1",
        "--tmpfs=/workspaces:rw,nosuid,nodev,noexec,size=100663296,mode=0700,uid=1000,gid=1000",
        IMAGE,
        "--run",
    ]


def exchange(process: subprocess.Popen, payload: bytes) -> tuple[int, bytes]:
    """Bound both pipes and total wait; never block on an unbounded readline/communicate."""
    deadline = time.monotonic() + WORKER_TIMEOUT_SECONDS
    response = bytearray()
    offset = 0
    os.set_blocking(process.stdin.fileno(), False)
    os.set_blocking(process.stdout.fileno(), False)
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdin, selectors.EVENT_WRITE)
        selector.register(process.stdout, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            for key, _ in selector.select(min(remaining, 0.5)):
                if key.fileobj is process.stdin:
                    try:
                        offset += os.write(
                            process.stdin.fileno(), payload[offset : offset + 65_536]
                        )
                    except BlockingIOError:
                        continue
                    if offset == len(payload):
                        selector.unregister(process.stdin)
                        process.stdin.close()
                else:
                    try:
                        chunk = os.read(process.stdout.fileno(), 65_536)
                    except BlockingIOError:
                        continue
                    if not chunk:
                        selector.unregister(process.stdout)
                        process.stdout.close()
                    elif len(response) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ValueError("Worker response exceeds the protocol limit.")
                    else:
                        response.extend(chunk)
    return process.wait(timeout=max(0.001, deadline - time.monotonic())), bytes(response)


class DockerWorker:
    """One container per test, removed before returning. No host code fallback."""

    def execute(self, request: WorkerRequest) -> RuntimeResult:
        docker = shutil.which("docker")
        if docker is None:
            return RuntimeResult(status="system_error", diagnostic="worker_transport")
        name = worker_project() + "-judge-worker-" + uuid.uuid4().hex
        command = worker_command(docker, name)
        process = None
        result = RuntimeResult(status="system_error", diagnostic="worker_transport")
        cleanup_ok = False
        # Docker is always addressed through the fixed local socket; inherited
        # contexts, remote hosts and credentials cannot redirect a request.
        environment = {"PATH": os.defpath, "LANG": "C.UTF-8"}
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                env=environment,
            )
            code, raw = exchange(process, request.model_dump_json().encode())
            try:
                result = RuntimeResult.model_validate_json(raw)
                if code != (78 if result.status == "system_error" else 0):
                    raise ValueError
            except ValueError:
                result = RuntimeResult(status="system_error", diagnostic="worker_protocol")
        except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
            result = RuntimeResult(status="system_error", diagnostic="worker_transport")
        finally:
            client_stopped = True
            try:
                if process is not None:
                    if process.poll() is None:
                        process.kill()
                        process.wait(timeout=2)
            except (OSError, subprocess.SubprocessError):
                client_stopped = False
            finally:
                if process is not None:
                    for pipe in (process.stdin, process.stdout):
                        if pipe is not None:
                            try:
                                pipe.close()
                            except OSError:
                                client_stopped = False
            # Always attempt daemon-side cleanup, even if the local CLI could
            # not be stopped/reaped. No next test may follow an uncertain stop.
            try:
                removal = subprocess.run(
                    [docker, "--host", LOCAL_DAEMON, "rm", "--force", name],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=10,
                    close_fds=True,
                    env=environment,
                )
                cleanup_ok = client_stopped and removal.returncode == 0
            except (OSError, subprocess.SubprocessError):
                cleanup_ok = False
        if not cleanup_ok:
            return RuntimeResult(status="system_error", diagnostic="cleanup_failed")
        return result
