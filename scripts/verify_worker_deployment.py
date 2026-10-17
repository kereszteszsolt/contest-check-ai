# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Operator-only Docker integration checks using fixed, benign fixture programs.

This script never executes a fixture on the host, accepts no external source,
and never mounts the Docker socket into a container. Not part of default pytest.
"""

import argparse
import base64
import json
import subprocess
import uuid
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
COMPOSE = ["docker", "compose", "-f", "deploy/worker/compose.yaml"]
REVIEWED = [*COMPOSE, "-f", "deploy/worker/compose.reviewed.yaml"]


def command(args, *, payload=None, timeout=60):
    return subprocess.run(
        args,
        cwd=REPOSITORY,
        input=payload,
        capture_output=True,
        timeout=timeout,
    )


def fixture_request(source, *, modules=None, **limits):
    task = json.loads((REPOSITORY / "examples/task-config.json").read_text())
    task["input_filename"] = "challenge.in"
    task["output_filename"] = "answer.out"
    task["limits"].update(limits)
    files = {"main.py": source, **(modules or {})}
    return json.dumps(
        {
            "participant_id": "1001",
            "task": task,
            "test_id": "01",
            "source_files": {
                name: base64.b64encode(value.encode()).decode() for name, value in files.items()
            },
            "input_base64": base64.b64encode(b"1 2\n").decode(),
        }
    ).encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reviewed-profile",
        action="store_true",
        required=True,
        help="Confirm the documented worker-only syscall profile was reviewed",
    )
    parser.parse_args()
    created = []
    evidence = {"qualification": {}, "runtime_cases": {}, "container": {}}

    def run_worker(arguments, *, payload=None, reviewed=True):
        name = "cca002-verification-" + uuid.uuid4().hex[:12]
        created.append(name)
        process = command(
            [
                *(REVIEWED if reviewed else COMPOSE),
                "run",
                "--no-deps",
                "--name",
                name,
                "judge-worker",
                *arguments,
            ],
            payload=payload,
        )
        if not process.stdout:
            raise RuntimeError("Worker did not return structured metadata.")
        result = json.loads(process.stdout)
        if b"CCA002_PRIVATE_DIAGNOSTIC" in process.stdout + process.stderr:
            raise RuntimeError("Source fixture was exposed in a diagnostic.")
        return name, process.returncode, result

    try:
        _, code, default = run_worker(["--verify"], reviewed=False)
        assert code == 78 and default["execution_ready"] is False
        evidence["qualification"]["default_profile"] = default
        name, code, reviewed = run_worker(["--verify"])
        assert code == 0 and reviewed["execution_ready"] is True
        evidence["qualification"]["reviewed_profile"] = reviewed

        inspected = command(["docker", "inspect", name])
        assert inspected.returncode == 0
        container = json.loads(inspected.stdout)[0]
        host = container["HostConfig"]
        assert host["NetworkMode"] == "none" and not host["Privileged"]
        assert host["ReadonlyRootfs"] and host["Init"]
        assert host["CapDrop"] == ["ALL"] and not host.get("CapAdd")
        assert not host.get("Binds") and not host.get("PortBindings")
        assert host["Memory"] == host["MemorySwap"] == 384 * 1024 * 1024
        assert host["NanoCpus"] == 1_000_000_000 and host["PidsLimit"] == 16
        assert "no-new-privileges:true" in host["SecurityOpt"]
        assert any(
            value.startswith("seccomp=") or value.startswith("seccomp:")
            for value in host["SecurityOpt"]
        )
        evidence["container"] = {
            "image_id": container["Image"],
            "network_mode": host["NetworkMode"],
            "read_only": host["ReadonlyRootfs"],
            "cap_drop": host["CapDrop"],
            "memory_bytes": host["Memory"],
            "swap_total_bytes": host["MemorySwap"],
            "nano_cpus": host["NanoCpus"],
            "pids_limit": host["PidsLimit"],
            "host_binds": host.get("Binds") or [],
            "published_ports": host.get("PortBindings") or {},
        }

        cases = {
            "file_io_and_sibling_module": (
                fixture_request(
                    "from helper import solve\n"
                    "a,b=map(int,open('challenge.in').read().split())\n"
                    "open('answer.out','w').write(str(solve(a,b))+'\\n')",
                    modules={"helper.py": "def solve(a,b): return a+b"},
                ),
                "success",
                "completed",
            ),
            "crash_private_diagnostic": (
                fixture_request("raise RuntimeError('CCA002_PRIVATE_DIAGNOSTIC')"),
                "crash",
                "program_exit",
            ),
            "wall_limit": (
                fixture_request("import time;time.sleep(30)", time_seconds=0.5),
                "timeout",
                "wall_limit",
            ),
            "output_limit": (
                fixture_request(
                    "with open('answer.out','wb',buffering=0) as f:\n"
                    " while True: f.write(b'x'*4096)",
                    output_bytes=4096,
                ),
                "resource",
                "output_or_exit",
            ),
            "memory_limit": (
                fixture_request(
                    "blocks=[]\nwhile True: blocks.append(bytearray(8*1024*1024))", memory_mb=64
                ),
                "resource",
                "memory_or_exit",
            ),
            "network_denied": (
                fixture_request("import socket;socket.socket(socket.AF_INET,socket.SOCK_STREAM)"),
                "crash",
                "program_exit",
            ),
        }
        for label, (payload, status, diagnostic) in cases.items():
            _, code, result = run_worker(["--run"], payload=payload)
            assert code == 0 and result["status"] == status and result["diagnostic"] == diagnostic
            if status == "success":
                assert base64.b64decode(result["output_base64"]) == b"3\n"
            else:
                assert result["output_base64"] is None
            if label == "output_limit":
                assert result["output_size_bytes"] == 4096
            evidence["runtime_cases"][label] = result
        print(json.dumps(evidence, indent=2))
    finally:
        for name in created:
            command(["docker", "rm", "--force", name], timeout=15)


if __name__ == "__main__":
    main()
