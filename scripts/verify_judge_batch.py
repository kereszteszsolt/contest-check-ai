# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Operator-only CCA-003 checks with fixed benign ZIPs. Never run automatically in CI."""

import argparse
import hashlib
import io
import json
import os
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from contest_check.api import app
from contest_check.worker_transport import IMAGE, LOCAL_DAEMON, REPOSITORY

DOCKER = ["docker", "--host", LOCAL_DAEMON]
COMPOSE = [*DOCKER, "compose", "-f", "deploy/worker/compose.yaml"]
REVIEWED = [*COMPOSE, "-f", "deploy/worker/compose.reviewed.yaml"]


def command(args):
    return subprocess.run(args, cwd=REPOSITORY, capture_output=True, timeout=60)


def archive(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as output:
        for name, content in entries:
            output.writestr(name, content)
    return buffer.getvalue()


def fixtures():
    manifest = {
        "task_id": "cca003-fixture",
        "language": "python",
        "entry_file": "main.py",
        "input_filename": "challenge.in",
        "output_filename": "answer.out",
        "tests": [{"test_id": "b"}, {"test_id": "a"}, {"test_id": "empty"}],
        "comparison": "exact",
        "limits": {"time_seconds": 0.5, "memory_mb": 128, "output_bytes": 1024},
        "policy": {"max_source_bytes": 1024, "review_imports": ["socket"]},
    }
    task = archive(
        [
            ("challenge/task-config.json", json.dumps(manifest)),
            ("challenge/tests/b.in", b"1 2\n"),
            ("challenge/tests/b.out", b"3\n"),
            ("challenge/tests/a.in", b"7 4\n"),
            ("challenge/tests/a.out", b"11\n"),
            ("challenge/tests/empty.in", b"EMPTY\n"),
            ("challenge/tests/empty.out", b""),
        ]
    )
    submissions = archive(
        [
            (
                "1001/main.py",
                "if False:\n import socket\nfrom helper import solve\nfrom pathlib import Path\n"
                "assert Path('answer.out').read_bytes() == b''\n"
                "Path('answer.out').write_text(solve(Path('challenge.in').read_text()))",
            ),
            (
                "1001/helper.py",
                "def solve(data):\n if data.strip()=='EMPTY': return ''\n"
                " return str(sum(map(int,data.split())))+'\\n'",
            ),
            ("1002/main.py", "open('answer.out','w').write('wrong\\n')"),
            ("1003/main.py", "import time\ntime.sleep(30)"),
            ("1004/main.py", "pass"),
            ("1005/main.py", "#" * 1025),
        ]
    )
    return task, submissions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-profile", required=True, action="store_true")
    parser.parse_args()
    name = "cca003-qualification-" + uuid.uuid4().hex
    evidence = {}
    try:
        default = command([*COMPOSE, "run", "--rm", "--no-deps", "judge-worker", "--verify"])
        assert default.returncode == 78
        evidence["default_qualification"] = json.loads(default.stdout)
        assert not evidence["default_qualification"]["execution_ready"]
        reviewed = command(
            [*REVIEWED, "run", "--no-deps", "--name", name, "judge-worker", "--verify"]
        )
        assert reviewed.returncode == 0
        evidence["reviewed_qualification"] = json.loads(reviewed.stdout)
        assert evidence["reviewed_qualification"]["execution_ready"]
        inspected = command([*DOCKER, "inspect", name])
        assert inspected.returncode == 0
        inspected = json.loads(inspected.stdout)[0]
        host = inspected["HostConfig"]
        assert host["NetworkMode"] == "none" and host["ReadonlyRootfs"]
        assert not host["Privileged"] and not host.get("CapAdd") and host["CapDrop"] == ["ALL"]
        assert not host.get("Binds") and not host.get("PortBindings")
        evidence["container"] = {
            "image_id": inspected["Image"],
            "image": IMAGE,
            "network_mode": host["NetworkMode"],
            "read_only": host["ReadonlyRootfs"],
            "cap_drop": host["CapDrop"],
            "memory_bytes": host["Memory"],
            "swap_total_bytes": host["MemorySwap"],
            "pids_limit": host["PidsLimit"],
            "nano_cpus": host["NanoCpus"],
            "host_binds": host.get("Binds") or [],
        }
        before = command(
            [*DOCKER, "ps", "--all", "--filter", "name=cca-judge-", "--format", "{{.Names}}"]
        )
        assert before.returncode == 0
        task, submissions = fixtures()
        with tempfile.TemporaryDirectory(prefix="cca003-batch-verification-") as scratch:
            with (
                patch.dict(
                    os.environ,
                    {"JUDGE_EXECUTION_ENABLED": "true", "JUDGE_REVIEWED_PROFILE": "true"},
                ),
                patch("contest_check.archives.tempfile.tempdir", scratch),
            ):
                with TestClient(app) as client:
                    assert client.get("/health").json()["execution_enabled"] is True
                    response = client.post(
                        "/api/judge",
                        files={
                            "task_zip": ("task.zip", task, "application/zip"),
                            "submissions_zip": ("submissions.zip", submissions, "application/zip"),
                        },
                    )
            assert response.status_code == 200
            assert list(Path(scratch).iterdir()) == []
        result = response.json()
        evidence["batch"] = result
        assert result["status"] == "completed"
        assert [p["participant_id"] for p in result["participants"]] == [
            "1001",
            "1002",
            "1003",
            "1004",
            "1005",
        ]
        for participant, verdict in zip(
            result["participants"][:4], ["AC", "WA", "TLE", "RE"], strict=True
        ):
            assert [test["test_id"] for test in participant["tests"]] == ["b", "a", "empty"]
            assert all(test["verdict"] == verdict for test in participant["tests"]), (
                participant["participant_id"],
                participant["tests"],
            )
            assert all(test["wall_seconds"] is not None for test in participant["tests"])
            assert all(
                test["cpu_seconds"] is None and test["peak_memory_bytes"] is None
                for test in participant["tests"]
            )
        assert result["participants"][0]["status"] == "REVIEW"
        assert result["participants"][0]["passed_tests"] == 3
        assert all(
            test["reason"] == "missing_output" for test in result["participants"][3]["tests"]
        )
        dq = result["participants"][4]
        assert dq["status"] == "DQ" and dq["tests"] == [] and dq["not_run_tests"] == 3
        assert dq["findings"][0]["observed_bytes"] == 1025
        assert "source_files" not in response.text and "output_base64" not in response.text
        after = command(
            [*DOCKER, "ps", "--all", "--filter", "name=cca-judge-", "--format", "{{.Names}}"]
        )
        assert after.returncode == 0
        assert set(after.stdout.splitlines()) <= set(before.stdout.splitlines())
        evidence["batch"] = result
        evidence["cleanup"] = {"workspace_empty": True, "no_new_test_containers": True}
        info = command([*DOCKER, "info", "--format", "{{json .}}"])
        assert info.returncode == 0
        info = json.loads(info.stdout)
        evidence["environment"] = {
            key: info[key]
            for key in (
                "ServerVersion",
                "KernelVersion",
                "OperatingSystem",
                "Architecture",
                "CgroupVersion",
            )
        }
        paths = [
            "deploy/worker/compose.yaml",
            "deploy/worker/compose.reviewed.yaml",
            "deploy/worker/docker-seccomp.json",
            "deploy/worker/python.policy",
            "deploy/worker/bootstrap.py",
            "src/contest_check/judge/backend.py",
            "src/contest_check/worker_transport.py",
            "src/contest_check/judging.py",
        ]
        evidence["sha256"] = {
            path: hashlib.sha256((REPOSITORY / path).read_bytes()).hexdigest() for path in paths
        }
        evidence["verified"] = True
        print(json.dumps(evidence, indent=2))
    except Exception:
        evidence["verified"] = False
        print(json.dumps(evidence, indent=2))
        raise
    finally:
        removal = command([*DOCKER, "rm", "--force", name])
        if removal.returncode:
            raise RuntimeError("Qualification container cleanup failed.")


if __name__ == "__main__":
    main()
