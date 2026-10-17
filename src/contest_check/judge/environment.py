# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
import os
import platform
import stat
from pathlib import Path

from contest_check.judge.contracts import SecurityCheck

NSJAIL_REVISION = "402e2b4c13c79731c632c2add4c3884dd1afc25f"
KAFEL_REVISION = "b4241da9f3d17e786387280fc6e4965634fdf45b"
BINARY = Path("/usr/local/bin/nsjail")
JAIL_ROOT = Path("/opt/cca-jail")
POLICY = Path("/opt/cca-worker/python.policy")
RUNTIME_MANIFEST = Path("/opt/cca-worker/runtime.json")
SCRATCH = Path("/workspaces")
EXPECTED_MOUNTS = {
    "/",
    "/workspaces",
    "/etc/hosts",
    "/etc/hostname",
    "/etc/resolv.conf",
    "/usr/sbin/docker-init",
    "/dev",
    "/dev/mqueue",
    "/dev/pts",
    "/dev/shm",
    "/proc",
    "/proc/acpi",
    "/proc/bus",
    "/proc/fs",
    "/proc/interrupts",
    "/proc/irq",
    "/proc/kcore",
    "/proc/keys",
    "/proc/latency_stats",
    "/proc/scsi",
    "/proc/sys",
    "/proc/sysrq-trigger",
    "/proc/timer_list",
    "/sys",
    "/sys/firmware",
    "/sys/fs/cgroup",
}
ALLOWED_ENVIRONMENT = {
    "PATH",
    "HOSTNAME",
    "HOME",
    "LANG",
    "LC_ALL",
    "PYTHON_VERSION",
    "PYTHON_SHA256",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
    "GPG_KEY",
    "PYTHON_PIP_VERSION",
    "PYTHON_SETUPTOOLS_VERSION",
    "PYTHON_GET_PIP_URL",
    "PYTHON_GET_PIP_SHA256",
}


def process_status() -> dict[str, str]:
    return dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())


def mounts() -> dict[str, tuple[set[str], str]]:
    result = {}
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        separator = fields.index("-")
        result[fields[4]] = (set(fields[5].split(",")), fields[separator + 1])
    return result


def runtime_fingerprint() -> str:
    raw = RUNTIME_MANIFEST.read_bytes()
    manifest = json.loads(raw)
    if (
        manifest["nsjail_revision"] != NSJAIL_REVISION
        or manifest["kafel_revision"] != KAFEL_REVISION
    ):
        raise ValueError("Unrecognized backend revision.")
    paths = {str(BINARY), str(POLICY), str(JAIL_ROOT / "bootstrap.py")}
    if set(manifest["sha256"]) != paths:
        raise ValueError("Unrecognized runtime files.")
    for name, digest in manifest["sha256"].items():
        path = Path(name)
        mode = path.stat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_uid != 0 or mode.st_mode & 0o022:
            raise ValueError("Runtime file is not immutable to the worker.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Runtime digest mismatch.")
    return hashlib.sha256(raw).hexdigest()


def outer_checks() -> list[SecurityCheck]:
    checks = []

    def check(name, evaluate):
        try:
            passed = bool(evaluate())
        except (OSError, ValueError, KeyError, TypeError):
            passed = False
        checks.append(SecurityCheck(name=name, passed=passed))

    check("linux_x86_64", lambda: platform.system() == "Linux" and platform.machine() == "x86_64")
    check("non_root_worker", lambda: os.getuid() == os.geteuid() == 1000)
    check(
        "no_capabilities",
        lambda: all(
            int(process_status()[key].strip(), 16) == 0
            for key in ("CapEff", "CapPrm", "CapInh", "CapBnd", "CapAmb")
        ),
    )
    check("no_new_privileges", lambda: process_status()["NoNewPrivs"].strip() == "1")
    check("outer_seccomp", lambda: process_status()["Seccomp"].strip() == "2")
    check("no_unexpected_environment", lambda: set(os.environ) <= ALLOWED_ENVIRONMENT)
    check(
        "offline_worker", lambda: {path.name for path in Path("/sys/class/net").iterdir()} == {"lo"}
    )
    check(
        "no_docker_socket_or_secrets",
        lambda: (
            not any(
                path.exists()
                for path in (
                    Path("/var/run/docker.sock"),
                    Path("/run/docker.sock"),
                    Path("/run/secrets"),
                )
            )
        ),
    )
    check("read_only_root", lambda: "ro" in mounts()["/"][0])
    check(
        "no_extra_mounts",
        lambda: set(mounts()) <= EXPECTED_MOUNTS,
    )
    check(
        "private_bounded_tmpfs",
        lambda: (
            mounts()[str(SCRATCH)][1] == "tmpfs"
            and {"rw", "nosuid", "nodev", "noexec"} <= mounts()[str(SCRATCH)][0]
            and SCRATCH.stat().st_uid == 1000
            and stat.S_IMODE(SCRATCH.stat().st_mode) == 0o700
            and os.statvfs(SCRATCH).f_blocks * os.statvfs(SCRATCH).f_frsize <= 96 * 1024 * 1024
        ),
    )
    check(
        "memory_and_swap_cap",
        lambda: (
            0 < int(Path("/sys/fs/cgroup/memory.max").read_text()) <= 384 * 1024 * 1024
            and int(Path("/sys/fs/cgroup/memory.swap.max").read_text()) == 0
        ),
    )
    check("process_cap", lambda: 0 < int(Path("/sys/fs/cgroup/pids.max").read_text()) <= 16)

    def cpu_capped():
        quota, period = map(int, Path("/sys/fs/cgroup/cpu.max").read_text().split())
        return 0 < quota <= period

    check("cpu_cap", cpu_capped)
    check("single_worker", lambda: int(Path("/sys/fs/cgroup/pids.current").read_text()) <= 2)
    check("pinned_runtime_integrity", runtime_fingerprint)
    return checks
