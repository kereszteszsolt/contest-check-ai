# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import json
import math
import os
import signal
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from contest_check.judge.contracts import PreparedRun, RuntimeResult
from contest_check.judge.environment import BINARY, JAIL_ROOT, POLICY, SCRATCH


def jail_config(job: PreparedRun, work: Path, *, cpu_seconds: int | None = None) -> str:
    """All strings are fixed or validated basenames; protobuf strings use JSON escaping."""

    def quoted(value):
        return json.dumps(str(value))

    # A single process cannot fork/thread. RLIMIT_AS and the outer memory cgroup
    # therefore bound the entire execution; no writable host cgroup mount is needed.
    config = f"""
name: "contest-check-python"
mode: ONCE
hostname: "contest-check"
cwd: "/work"
time_limit: {math.ceil(job.time_seconds) + 1}
max_cpus: 1
nice_level: 0
keep_env: false
envar: "LANG=C.UTF-8"
keep_caps: false
disable_no_new_privs: false
clone_newuser: true
clone_newns: true
clone_newnet: true
clone_newpid: true
clone_newipc: true
clone_newuts: true
clone_newcgroup: true
iface_no_lo: true
mount_proc: false
uidmap {{ inside_id: "65534" outside_id: "1000" count: 1 }}
gidmap {{ inside_id: "65534" outside_id: "1000" count: 1 }}
rlimit_as: {job.memory_mb}
rlimit_cpu: {cpu_seconds if cpu_seconds is not None else math.ceil(job.time_seconds)}
rlimit_core: 0
rlimit_fsize: 1
rlimit_nofile: 32
rlimit_nproc: 1
rlimit_nproc_type: VALUE
rlimit_memlock: 0
rlimit_memlock_type: VALUE
rlimit_stack: 8
rlimit_stack_type: VALUE
rlimit_msgqueue: 0
seccomp_policy_file: {quoted(POLICY)}
mount {{ src: {quoted(JAIL_ROOT / "usr")} dst: "/usr"
         is_bind: true rw: false nosuid: true nodev: true }}
mount {{ src: {quoted(JAIL_ROOT / "lib")} dst: "/lib"
         is_bind: true rw: false nosuid: true nodev: true }}
mount {{ src: {quoted(JAIL_ROOT / "lib64")} dst: "/lib64"
         is_bind: true rw: false nosuid: true nodev: true }}
mount {{ src: {quoted(JAIL_ROOT / "bootstrap.py")} dst: "/bootstrap.py"
         is_bind: true rw: false nosuid: true nodev: true noexec: true }}
mount {{ src: {quoted(work)} dst: "/work" is_bind: true rw: false
         nosuid: true nodev: true noexec: true }}
mount {{ src: {quoted(work / job.output_filename)} dst: {quoted("/work/" + job.output_filename)}
         is_bind: true rw: true is_dir: false nosuid: true nodev: true noexec: true }}
mount {{ dst: "/proc" fstype: "proc" rw: false nosuid: true nodev: true noexec: true }}
exec_bin {{ path: "/usr/local/bin/python3.12" arg: "-I" arg: "-S" arg: "-B"
           arg: "/bootstrap.py" arg: "{job.output_bytes}" }}
"""
    return config


def classify(returncode: int, elapsed: float) -> RuntimeResult:
    if returncode == 0:
        return RuntimeResult(
            status="success", diagnostic="completed", elapsed_seconds=elapsed, exit_code=0
        )
    if returncode == 255 or returncode < 0:
        return RuntimeResult(
            status="system_error", diagnostic="sandbox_setup", elapsed_seconds=elapsed
        )
    if returncode in (70, 71):
        return RuntimeResult(
            status="resource",
            diagnostic="memory_or_exit" if returncode == 70 else "output_or_exit",
            elapsed_seconds=elapsed,
            exit_code=returncode,
        )
    sig = returncode - 128 if 128 < returncode < 193 else None
    if sig in {signal.SIGXCPU, signal.SIGXFSZ, signal.SIGKILL}:
        return RuntimeResult(
            status="resource", diagnostic="signal_limit", elapsed_seconds=elapsed, signal=sig
        )
    return RuntimeResult(
        status="crash",
        diagnostic="program_exit",
        elapsed_seconds=elapsed,
        exit_code=returncode,
        signal=sig,
    )


class NsJailBackend:
    """Only the pinned NsJail executable is ever launched. There is no host fallback."""

    def execute(self, job: PreparedRun, *, cpu_seconds: int | None = None) -> RuntimeResult:
        process = None
        started = time.monotonic()
        try:
            baseline = int(Path("/sys/fs/cgroup/pids.current").read_text())
            with tempfile.TemporaryDirectory(prefix="test-", dir=SCRATCH) as directory:
                root = Path(directory)
                work = root / "work"
                work.mkdir(mode=0o700)
                for name, payload in {**job.sources, job.input_filename: job.input_bytes}.items():
                    target = work / name
                    with target.open("xb") as destination:
                        destination.write(payload)
                    target.chmod(0o400)
                output = work / job.output_filename
                with output.open("xb"):
                    pass
                output.chmod(0o600)
                work.chmod(0o500)
                config = root / "jail.cfg"
                config.write_text(jail_config(job, work, cpu_seconds=cpu_seconds))
                config.chmod(0o600)
                started = time.monotonic()
                process = subprocess.Popen(
                    [str(BINARY), "--config", str(config), "--experimental_mnt", "new", "--quiet"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env={
                        "PATH": "/usr/local/bin:/usr/bin:/bin",
                        "LANG": "C.UTF-8",
                        "TMPDIR": str(root),
                    },
                    close_fds=True,
                    start_new_session=True,
                )
                try:
                    code = process.wait(timeout=job.time_seconds)
                    result = classify(code, time.monotonic() - started)
                except subprocess.TimeoutExpired:
                    if not self._stop(process):
                        return RuntimeResult(status="system_error", diagnostic="cleanup_failed")
                    result = RuntimeResult(
                        status="timeout",
                        diagnostic="wall_limit",
                        elapsed_seconds=time.monotonic() - started,
                    )
                if int(Path("/sys/fs/cgroup/pids.current").read_text()) != baseline:
                    result = RuntimeResult(status="system_error", diagnostic="cleanup_failed")
                descriptor = os.open(output, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(descriptor, "rb") as source:
                    metadata = os.fstat(source.fileno())
                    if result.status == "success":
                        payload = source.read(job.output_bytes + 1)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > job.output_bytes:
                    result = RuntimeResult(status="system_error", diagnostic="sandbox_setup")
                else:
                    result = result.model_copy(update={"output_size_bytes": metadata.st_size})
                    if result.status == "success":
                        result = result.model_copy(
                            update={"output_base64": base64.b64encode(payload).decode("ascii")}
                        )
                # Restore owner traversal permissions for guaranteed normal cleanup.
                work.chmod(0o700)
            return result
        except (OSError, ValueError, subprocess.SubprocessError):
            if process is not None and process.poll() is None:
                self._stop(process)
            return RuntimeResult(status="system_error", diagnostic="sandbox_setup")

    @staticmethod
    def _stop(process: subprocess.Popen) -> bool:
        # NsJail handles TERM by killing/reaping the jail. Its child also has
        # PR_SET_PDEATHSIG=SIGKILL; killing the namespace's PID 1 kills descendants.
        try:
            process.terminate()
            process.wait(timeout=1)
            return True
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
                return True
            except (OSError, subprocess.TimeoutExpired):
                return False
