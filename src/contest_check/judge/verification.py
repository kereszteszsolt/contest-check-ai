# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import json
import os
import signal
from dataclasses import replace

from contest_check.judge.backend import NsJailBackend
from contest_check.judge.contracts import (
    PreparedRun,
    RuntimeResult,
    SecurityCheck,
    VerificationReport,
    WorkerRequest,
)
from contest_check.judge.environment import SCRATCH, outer_checks, runtime_fingerprint


def probe(source: str, **limits) -> PreparedRun:
    return PreparedRun(
        sources={"main.py": source.encode()},
        input_bytes=b"fixture input\n",
        input_filename="input.txt",
        output_filename="output.txt",
        time_seconds=limits.get("time_seconds", 3.0),
        memory_mb=limits.get("memory_mb", 128),
        output_bytes=limits.get("output_bytes", 16_384),
    )


ATTESTATION = """
import json, os, resource
from pathlib import Path
status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines())
cap_names = ("CapEff", "CapPrm", "CapInh", "CapBnd", "CapAmb")
ns_names = ("user", "mnt", "net", "pid", "ipc", "uts", "cgroup")
limit_names = ("AS", "FSIZE", "NOFILE", "NPROC", "CORE", "MEMLOCK", "CPU")
data = {
    "pid": os.getpid(), "uid": os.getuid(), "gid": os.getgid(),
    "caps": [int(status[key].strip(), 16) for key in cap_names],
    "nnp": status["NoNewPrivs"].strip(), "seccomp": status["Seccomp"].strip(),
    "filters": int(status["Seccomp_filters"].strip()),
    "namespaces": {name: os.readlink("/proc/self/ns/" + name) for name in ns_names},
    "limits": {
        name: resource.getrlimit(getattr(resource, "RLIMIT_" + name)) for name in limit_names
    },
    "input": Path("input.txt").read_text(),
    "fds": sorted(int(name) for name in os.listdir("/proc/self/fd")),
    "environment": dict(os.environ),
    "root_read_only": bool(os.statvfs("/").f_flag & os.ST_RDONLY),
    "work_read_only": bool(os.statvfs("/work").f_flag & os.ST_RDONLY),
    "output_mount_writable": not bool(os.statvfs("output.txt").f_flag & os.ST_RDONLY),
}
Path("output.txt").write_text(json.dumps(data))
"""

FILESYSTEM = """
from pathlib import Path
import os
for path in (
    "/opt/cca-worker", "/opt/cca-worker/runtime.json", "/run/secrets", "/var/run/docker.sock",
    "/sys/fs/cgroup", "/etc/passwd", "/workspaces", "/proc/2/root/etc/passwd",
):
    assert not Path(path).exists()
for path in ("/extra", "/work/extra", "/work/input.txt", "/work/main.py", "/bootstrap.py"):
    try:
        open(path, "wb").write(b"forbidden")
    except OSError:
        pass
    else:
        raise SystemExit(3)
Path("output.txt").write_text("isolated")
"""


class QualifiedWorker:
    """Qualification is in-memory, for this process/runtime only; never loaded from a file."""

    def __init__(self, backend: NsJailBackend | None = None):
        self.backend = backend if backend is not None else NsJailBackend()
        self._fingerprint: str | None = None

    def verify(self) -> VerificationReport:
        self._fingerprint = None
        checks = outer_checks()
        if not all(check.passed for check in checks):
            return VerificationReport(checks=checks)
        fingerprint = runtime_fingerprint()
        before = set(SCRATCH.iterdir())

        def execute(name, job, accept, **kwargs):
            try:
                result = self.backend.execute(job, **kwargs)
                passed = bool(accept(result))
            except (OSError, ValueError, KeyError, TypeError):
                passed = False
            checks.append(SecurityCheck(name=name, passed=passed))
            return passed

        def attest(result):
            if result.status != "success" or result.output_base64 is None:
                return False
            data = json.loads(base64.b64decode(result.output_base64))
            namespaces = data["namespaces"]
            expected_limits = {
                "AS": 128 * 1024 * 1024,
                "FSIZE": 16_384,
                "NOFILE": 32,
                "NPROC": 1,
                "CORE": 0,
                "MEMLOCK": 0,
                "CPU": 3,
            }
            return (
                data["pid"] == 1
                and data["uid"] == data["gid"] == 65534
                and data["caps"] == [0] * 5
                and data["nnp"] == "1"
                and data["seccomp"] == "2"
                and data["filters"] >= 2
                and set(namespaces) == {"user", "mnt", "net", "pid", "ipc", "uts", "cgroup"}
                and all(
                    value != os.readlink("/proc/self/ns/" + name)
                    for name, value in namespaces.items()
                )
                and all(
                    data["limits"][name] == [value, value]
                    for name, value in expected_limits.items()
                )
                and data["input"] == "fixture input\n"
                and max(data["fds"]) <= 3
                and set(data["environment"]) <= {"LANG", "LC_CTYPE"}
                and data["root_read_only"]
                and data["work_read_only"]
                and data["output_mount_writable"]
            )

        # No submitted program is used in qualification. Stop immediately if even
        # the trusted namespace/limit attestation cannot establish the boundary.
        if not execute("jail_namespaces_privileges_limits", probe(ATTESTATION), attest):
            return VerificationReport(checks=checks)

        cases = [
            (
                "filesystem_allowlist",
                probe(FILESYSTEM),
                lambda r: (
                    r.status == "success" and base64.b64decode(r.output_base64 or "") == b"isolated"
                ),
            ),
            (
                "network_syscall_denied",
                probe("import socket; socket.socket(socket.AF_INET, socket.SOCK_STREAM)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "unix_socket_denied",
                probe("import socket; socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "netlink_socket_denied",
                probe("import socket; socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, 0)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "dns_denied",
                probe("import socket; socket.getaddrinfo('example.invalid', 80)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            ("fork_denied", probe("import os; os.fork()"), lambda r: r.signal == signal.SIGSYS),
            (
                "namespace_change_denied",
                probe("import os; os.unshare(os.CLONE_NEWUSER)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "symlink_denied",
                probe("import os; os.symlink('/proc/2/root/etc/passwd', '/work/link')"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "ptrace_denied",
                probe("import ctypes; ctypes.CDLL(None).ptrace(0, 0, 0, 0)"),
                lambda r: r.signal == signal.SIGSYS,
            ),
            (
                "memory_limit",
                probe("blocks=[]\nwhile True: blocks.append(bytearray(8*1024*1024))", memory_mb=64),
                lambda r: r.status == "resource" and r.diagnostic == "memory_or_exit",
            ),
            (
                "output_limit",
                probe(
                    "with open('output.txt','wb',buffering=0) as f:\n"
                    " while True: f.write(b'x'*4096)",
                    output_bytes=4096,
                ),
                lambda r: (
                    r.status == "resource"
                    and r.diagnostic == "output_or_exit"
                    and r.output_size_bytes == 4096
                ),
            ),
            (
                "wall_timeout",
                probe("import time\ntime.sleep(30)", time_seconds=0.5),
                lambda r: r.status == "timeout" and r.elapsed_seconds < 2,
            ),
            (
                "runtime_crash",
                probe("raise RuntimeError('PRIVATE_SOURCE_MUST_NOT_BE_LOGGED')"),
                lambda r: r.status == "crash",
            ),
            (
                "sibling_import",
                replace(
                    probe("from helper import answer\nopen('output.txt','w').write(answer)"),
                    sources={
                        "main.py": (
                            b"from helper import answer\nopen('output.txt','w').write(answer)"
                        ),
                        "helper.py": b"answer='module-ok'",
                    },
                ),
                lambda r: (
                    r.status == "success"
                    and base64.b64decode(r.output_base64 or "") == b"module-ok"
                ),
            ),
            (
                "fd_limit",
                probe(
                    "import errno\nf=[]\ntry:\n while True: f.append(open('input.txt','rb'))\n"
                    "except OSError as e:\n assert e.errno == errno.EMFILE\n"
                    "for item in f: item.close()\nopen('output.txt','w').write('fd-capped')"
                ),
                lambda r: r.status == "success",
            ),
        ]
        for name, job, accept in cases:
            if not execute(name, job, accept):
                return VerificationReport(checks=checks)
        if not execute(
            "cpu_limit",
            probe("while True: pass"),
            lambda r: r.status == "resource" and r.signal in {signal.SIGKILL, signal.SIGXCPU},
            cpu_seconds=1,
        ):
            return VerificationReport(checks=checks)
        clean = set(SCRATCH.iterdir()) == before
        checks.append(SecurityCheck(name="workspace_cleanup", passed=clean))
        unchanged = runtime_fingerprint() == fingerprint
        checks.append(SecurityCheck(name="runtime_unchanged", passed=unchanged))
        ready = clean and unchanged
        if ready:
            self._fingerprint = fingerprint
        return VerificationReport(execution_ready=ready, checks=checks)

    def run(self, request: WorkerRequest) -> RuntimeResult:
        try:
            if self._fingerprint is None or runtime_fingerprint() != self._fingerprint:
                self._fingerprint = None
                return RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")
            if not all(check.passed for check in outer_checks()):
                self._fingerprint = None
                return RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")
            result = self.backend.execute(PreparedRun.from_request(request))
            if result.status == "system_error":
                self._fingerprint = None
            return result
        except (OSError, ValueError):
            self._fingerprint = None
            return RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")
