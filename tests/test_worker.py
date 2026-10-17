# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import io
import json
import signal
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from contest_check.judge import backend, cli, contracts, environment, verification
from contest_check.judge.contracts import (
    PreparedRun,
    RuntimeResult,
    SecurityCheck,
    WorkerRequest,
    parse_request,
)


@pytest.fixture
def worker_job(manifest):
    return {
        "participant_id": "1001",
        "task": manifest,
        "test_id": "01",
        "source_files": {
            "main.py": base64.b64encode(b"# inert fixture; never run by pytest").decode()
        },
        "input_base64": base64.b64encode(b"1 2\n").decode(),
    }


def test_typed_worker_input(worker_job):
    request = parse_request(json.dumps(worker_job).encode())
    prepared = PreparedRun.from_request(request)
    assert prepared.input_bytes == b"1 2\n"
    assert prepared.sources == {"main.py": b"# inert fixture; never run by pytest"}
    assert prepared.output_filename == "output.txt"


@pytest.mark.parametrize(
    "key, value",
    [
        ("command", ["/bin/sh"]),
        ("cwd", "/"),
        ("host_path", "/etc/passwd"),
        ("participant_id", "01001"),
        ("participant_id", "alice"),
        ("test_id", "other"),
        ("source_files", {}),
        ("source_files", {"../main.py": ""}),
        ("source_files", {"main.py": "", "MAIN.py": ""}),
        ("source_files", {"main.py": "invalid base64!"}),
        ("source_files", {"main.py\n": ""}),
        ("input_base64", "!"),
    ],
)
def test_worker_rejects_untrusted_protocol_fields(worker_job, key, value):
    worker_job[key] = value
    with pytest.raises((ValueError, ValidationError)):
        WorkerRequest.model_validate(worker_job)


def test_worker_source_count(worker_job):
    worker_job["source_files"] = {"main.py": "", **{f"m{i}.py": "" for i in range(30)}}
    with pytest.raises(ValidationError):
        WorkerRequest.model_validate(worker_job)


@pytest.mark.parametrize("field", ["input_base64", "source_files"])
def test_decoded_size_is_bounded(worker_job, monkeypatch, field):
    monkeypatch.setattr(contracts, "MAX_FILE_BYTES", 2)
    if field == "input_base64":
        worker_job[field] = base64.b64encode(b"123").decode()
    with pytest.raises(ValidationError):
        WorkerRequest.model_validate(worker_job)


@pytest.mark.parametrize("raw", [b'{"protocol":1,"protocol":1}', b"\xff", b"{", b"[" * 1500])
def test_worker_bad_json(raw):
    with pytest.raises((ValueError, RecursionError)):
        parse_request(raw)


def test_raw_request_limit(worker_job, monkeypatch):
    monkeypatch.setattr(contracts, "MAX_REQUEST_BYTES", 4)
    with pytest.raises(ValueError):
        parse_request(json.dumps(worker_job).encode())


def test_request_cannot_pass_reference_output_or_source(worker_job):
    worker_job["expected_output"] = "teacher-only"
    with pytest.raises(ValidationError):
        WorkerRequest.model_validate(worker_job)


def test_unqualified_worker_never_calls_backend(worker_job, monkeypatch):
    fake = SimpleNamespace(execute=lambda *args, **kwargs: pytest.fail("Unqualified execution"))
    monkeypatch.setenv("JUDGE_EXECUTION_ENABLED", "true")
    result = verification.QualifiedWorker(fake).run(WorkerRequest.model_validate(worker_job))
    assert result.status == "system_error"
    assert result.diagnostic == "sandbox_unavailable"


def test_failed_prerequisite_never_launches_even_trusted_probes(monkeypatch):
    monkeypatch.setattr(
        verification, "outer_checks", lambda: [SecurityCheck(name="offline", passed=False)]
    )
    fake = SimpleNamespace(execute=lambda *args, **kwargs: pytest.fail("No jail may start"))
    report = verification.QualifiedWorker(fake).verify()
    assert report.execution_ready is False


def test_failed_attestation_cannot_qualify(worker_job, monkeypatch, tmp_path):
    monkeypatch.setattr(
        verification, "outer_checks", lambda: [SecurityCheck(name="outer", passed=True)]
    )
    monkeypatch.setattr(verification, "runtime_fingerprint", lambda: "pinned")
    monkeypatch.setattr(verification, "SCRATCH", tmp_path)
    calls = []

    def execute(job, **kwargs):
        calls.append(job)
        return RuntimeResult(status="system_error", diagnostic="sandbox_setup")

    worker = verification.QualifiedWorker(SimpleNamespace(execute=execute))
    assert not worker.verify().execution_ready
    assert len(calls) == 1
    assert worker.run(WorkerRequest.model_validate(worker_job)).status == "system_error"
    assert len(calls) == 1


def test_runtime_change_revokes_qualification(worker_job, monkeypatch):
    worker = verification.QualifiedWorker(
        SimpleNamespace(execute=lambda job: pytest.fail("Runtime changed"))
    )
    worker._fingerprint = "previous"
    monkeypatch.setattr(verification, "runtime_fingerprint", lambda: "changed")
    assert worker.run(WorkerRequest.model_validate(worker_job)).status == "system_error"
    assert worker._fingerprint is None


def test_preflight_failures_do_not_log_environment_or_paths(monkeypatch, capsys):
    monkeypatch.setenv("OPENROUTER_API_KEY", "DO_NOT_LOG_THIS_SECRET")
    results = environment.outer_checks()
    assert not next(item for item in results if item.name == "no_unexpected_environment").passed
    assert "DO_NOT_LOG_THIS_SECRET" not in str(results) + str(capsys.readouterr())


@pytest.mark.parametrize("path", ["/secrets", "/dev/private", "/sys/private", "/proc/private"])
def test_even_system_prefixes_cannot_hide_an_extra_mount(monkeypatch, path):
    monkeypatch.setattr(
        environment, "mounts", lambda: {"/": ({"ro"}, "overlay"), path: ({"ro"}, "ext4")}
    )
    result = next(item for item in environment.outer_checks() if item.name == "no_extra_mounts")
    assert not result.passed


@pytest.mark.parametrize(
    "code, status, diagnostic, sig",
    [
        (0, "success", "completed", None),
        (1, "crash", "program_exit", None),
        (70, "resource", "memory_or_exit", None),
        (71, "resource", "output_or_exit", None),
        (128 + signal.SIGXCPU, "resource", "signal_limit", signal.SIGXCPU),
        (128 + signal.SIGXFSZ, "resource", "signal_limit", signal.SIGXFSZ),
        (128 + signal.SIGSYS, "crash", "program_exit", signal.SIGSYS),
        (255, "system_error", "sandbox_setup", None),
        (-9, "system_error", "sandbox_setup", None),
    ],
)
def test_safe_runtime_classification(code, status, diagnostic, sig):
    value = backend.classify(code, 0.25)
    assert (value.status, value.diagnostic, value.signal) == (status, diagnostic, sig)
    assert value.elapsed_seconds == 0.25
    assert value.output_base64 is None


def test_jail_config_has_explicit_boundaries(worker_job, tmp_path):
    job = PreparedRun.from_request(WorkerRequest.model_validate(worker_job))
    cfg = backend.jail_config(job, tmp_path / "work")
    for namespace in ("user", "ns", "net", "pid", "ipc", "uts", "cgroup"):
        assert f"clone_new{namespace}: true" in cfg
    assert 'path: "/usr/local/bin/python3.12"' in cfg
    assert 'arg: "/bootstrap.py"' in cfg
    assert 'inside_id: "65534" outside_id: "1000"' in cfg
    assert "rlimit_nproc_type: VALUE" in cfg
    assert "keep_env: false" in cfg and "keep_caps: false" in cfg
    assert "iface_no_lo: true" in cfg and "seccomp_policy_file:" in cfg
    assert '"/work/output.txt"' in cfg
    assert 'dst: "/usr"' in cfg and 'dst: "/lib64"' in cfg
    assert 'src: "/opt/cca-jail/usr"' in cfg
    assert 'src: "/"' not in cfg
    assert "teacher-only" not in cfg


@pytest.fixture
def mock_execution(monkeypatch, tmp_path):
    monkeypatch.setattr(backend, "SCRATCH", tmp_path)
    original_read = Path.read_text

    def read_text(path, *args, **kwargs):
        if str(path) == "/sys/fs/cgroup/pids.current":
            return "2"
        return original_read(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    return tmp_path


def test_launch_is_fixed_and_output_cleanup_is_bounded(worker_job, mock_execution, monkeypatch):
    calls = []

    class FakeProcess:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.root = Path(command[2]).parent
            assert (self.root / "work/main.py").read_bytes().startswith(b"# inert")
            assert (self.root / "work/input.txt").read_bytes() == b"1 2\n"

        def wait(self, timeout):
            (self.root / "work/output.txt").write_bytes(b"3\n")
            return 0

    monkeypatch.setattr(backend.subprocess, "Popen", FakeProcess)
    job = PreparedRun.from_request(WorkerRequest.model_validate(worker_job))
    result = backend.NsJailBackend().execute(job)
    assert result.status == "success"
    assert base64.b64decode(result.output_base64) == b"3\n"
    command, options = calls[0]
    assert command[0] == "/usr/local/bin/nsjail"
    assert command[command.index("--experimental_mnt") + 1] == "new"
    assert options["stdin"] == options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert options["close_fds"] and options["start_new_session"]
    assert set(options["env"]) == {"PATH", "LANG", "TMPDIR"}
    assert not options.get("shell", False)
    assert list(mock_execution.iterdir()) == []


@pytest.mark.parametrize("case", ["oversized", "symlink", "launch_error"])
def test_backend_errors_never_return_partial_or_external_output(
    worker_job, mock_execution, monkeypatch, case
):
    sentinel = mock_execution / "private-canary"
    sentinel.write_bytes(b"PRIVATE_CONTENT")

    class FakeProcess:
        def __init__(self, command, **kwargs):
            if case == "launch_error":
                raise OSError("PRIVATE_PATH")
            self.root = Path(command[2]).parent

        def wait(self, timeout):
            output = self.root / "work/output.txt"
            if case == "symlink":
                output.unlink()
                output.symlink_to(sentinel)
            else:
                output.write_bytes(b"x" * 1025)
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(backend.subprocess, "Popen", FakeProcess)
    result = backend.NsJailBackend().execute(
        PreparedRun.from_request(WorkerRequest.model_validate(worker_job))
    )
    assert result.status == "system_error" and result.output_base64 is None
    assert "PRIVATE" not in result.model_dump_json()
    assert list(mock_execution.iterdir()) == [sentinel]


def test_timeout_terminates_and_reaps_nsjail(worker_job, mock_execution, monkeypatch):
    events = []

    class FakeProcess:
        stopped = False

        def __init__(self, *args, **kwargs):
            pass

        def wait(self, timeout):
            events.append(("wait", timeout))
            if not self.stopped:
                raise subprocess.TimeoutExpired("fixed-nsjail", timeout)
            return 137

        def terminate(self):
            self.stopped = True
            events.append(("terminate", None))

    monkeypatch.setattr(backend.subprocess, "Popen", FakeProcess)
    result = backend.NsJailBackend().execute(
        PreparedRun.from_request(WorkerRequest.model_validate(worker_job))
    )
    assert result.status == "timeout"
    assert ("terminate", None) in events and events[-1] == ("wait", 1)
    assert list(mock_execution.iterdir()) == []


@pytest.mark.parametrize(
    "first_status, exit_code", [("success", 0), ("crash", 1), ("resource", 71), ("timeout", None)]
)
def test_each_test_gets_a_fresh_deadline_and_workspace(
    worker_job, mock_execution, monkeypatch, first_status, exit_code
):
    roots = []
    waits = []
    elapsed = 0.5 if first_status == "timeout" else 0.125
    clock = [10.0]
    monkeypatch.setattr(backend.time, "monotonic", lambda: clock[0])
    job = replace(
        PreparedRun.from_request(WorkerRequest.model_validate(worker_job)), time_seconds=0.5
    )
    next_job = replace(job, sources={"main.py": b"# next inert fixture"}, input_bytes=b"next\n")

    class FakeProcess:
        def __init__(self, command, **kwargs):
            assert all(not root.exists() for root in roots)
            self.root = Path(command[2]).parent
            self.index = len(roots)
            self.stopped = False
            roots.append(self.root)
            current = next_job if self.index else job
            work = self.root / "work"
            assert (work / "main.py").read_bytes() == current.sources["main.py"]
            assert (work / "input.txt").read_bytes() == current.input_bytes
            assert (work / "output.txt").read_bytes() == b""
            assert sorted(path.name for path in work.iterdir()) == [
                "input.txt",
                "main.py",
                "output.txt",
            ]
            generated = self.root / "generated"
            generated.mkdir()
            (generated / "temporary-data").write_bytes(b"discard before the next test")

        def wait(self, timeout):
            if self.stopped:
                return 137
            waits.append(timeout)
            clock[0] += elapsed if not self.index else 0.125
            (self.root / "work/output.txt").write_bytes(b"previous" if not self.index else b"next")
            if not self.index and first_status == "timeout":
                raise subprocess.TimeoutExpired("fixed-nsjail", timeout)
            return exit_code if not self.index else 0

        def terminate(self):
            self.stopped = True

    monkeypatch.setattr(backend.subprocess, "Popen", FakeProcess)
    runner = backend.NsJailBackend()
    first = runner.execute(job)
    assert first.status == first_status
    assert list(mock_execution.iterdir()) == []
    clock[0] += 90.0
    second = runner.execute(next_job)
    assert second.status == "success"
    assert base64.b64decode(second.output_base64) == b"next"
    assert waits == [0.5, 0.5]
    assert first.elapsed_seconds == elapsed
    assert second.elapsed_seconds == 0.125
    assert len(roots) == 2 and roots[0] != roots[1]
    assert list(mock_execution.iterdir()) == []


def test_failed_workspace_cleanup_blocks_the_next_test(worker_job, mock_execution, monkeypatch):
    cleanups = []
    launches = []
    original_directory = backend.tempfile.TemporaryDirectory

    def failing_directory(*args, **kwargs):
        directory = original_directory(*args, **kwargs)
        cleanups.append(directory.cleanup)

        def fail():
            raise OSError("PRIVATE_CLEANUP_PATH")

        monkeypatch.setattr(directory, "cleanup", fail)
        return directory

    class FakeProcess:
        def __init__(self, command, **kwargs):
            launches.append(command)

        def wait(self, timeout):
            return 0

        def poll(self):
            return 0

    monkeypatch.setattr(backend.tempfile, "TemporaryDirectory", failing_directory)
    monkeypatch.setattr(backend.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(verification, "runtime_fingerprint", lambda: "pinned")
    monkeypatch.setattr(
        verification, "outer_checks", lambda: [SecurityCheck(name="outer", passed=True)]
    )
    worker = verification.QualifiedWorker()
    worker._fingerprint = "pinned"
    request = WorkerRequest.model_validate(worker_job)
    try:
        result = worker.run(request)
        assert result.status == "system_error" and result.output_base64 is None
        assert "PRIVATE" not in result.model_dump_json()
        assert worker._fingerprint is None
        assert len(list(mock_execution.iterdir())) == 1
        assert worker.run(request).diagnostic == "sandbox_unavailable"
        assert len(launches) == 1
    finally:
        for cleanup in cleanups:
            cleanup()
    assert list(mock_execution.iterdir()) == []


def test_cli_invalid_request_has_safe_error(worker_job, monkeypatch, capsys):
    worker_job["host_path"] = "/PRIVATE_PATH"
    raw = json.dumps(worker_job).encode()
    monkeypatch.setattr(cli.sys, "stdin", SimpleNamespace(buffer=io.BytesIO(raw)))
    monkeypatch.setattr(cli.sys, "argv", ["worker", "--run"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 65
    captured = capsys.readouterr()
    assert json.loads(captured.out)["diagnostic"] == "invalid_request"
    assert "PRIVATE" not in captured.out + captured.err


def test_cli_failed_check_cannot_be_enabled_by_flag(monkeypatch, capsys):
    monkeypatch.setenv("JUDGE_EXECUTION_ENABLED", "true")
    monkeypatch.setattr(
        cli, "outer_checks", lambda: [SecurityCheck(name="namespace", passed=False)]
    )
    monkeypatch.setattr(cli.sys, "argv", ["worker", "--check"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 78
    assert not json.loads(capsys.readouterr().out)["execution_ready"]


def test_default_compose_does_not_apply_review_override():
    compose = Path("deploy/worker/compose.yaml").read_text()
    assert "seccomp=" not in compose
    assert "network_mode: none" in compose
    assert "cap_drop: [ALL]" in compose
    assert "read_only: true" in compose
    assert "privileged" not in compose
    assert "ports:" not in compose and "volumes:" not in compose


@pytest.mark.parametrize(
    "update",
    [
        {"sources": {"../main.py": b"inert"}},
        {"input_filename": "../input.txt"},
        {"output_filename": 'result.out" shell'},
        {"output_bytes": 0},
        {"time_seconds": float("nan")},
        {"time_seconds": 4.0},
        {"memory_mb": True},
    ],
)
def test_internal_run_boundary_rejects_unsafe_specifications(worker_job, update):
    prepared = PreparedRun.from_request(WorkerRequest.model_validate(worker_job))
    with pytest.raises(ValueError):
        replace(prepared, **update)


def test_watchdog_uses_kill_if_nsjail_does_not_stop():
    events = []

    class Process:
        killed = False

        def terminate(self):
            events.append("term")

        def kill(self):
            events.append("kill")
            self.killed = True

        def wait(self, timeout):
            if not self.killed:
                raise subprocess.TimeoutExpired("nsjail", timeout)

    assert backend.NsJailBackend._stop(Process())
    assert events == ["term", "kill"]


def test_watchdog_reports_an_unreaped_process():
    class Process:
        def terminate(self):
            pass

        def kill(self):
            pass

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("nsjail", timeout)

    assert not backend.NsJailBackend._stop(Process())


def test_unexpected_cli_exception_returns_safe_metadata(monkeypatch, capsys):
    def fail():
        raise RuntimeError("PRIVATE_TRACEBACK_CONTENT")

    monkeypatch.setattr(cli, "outer_checks", fail)
    monkeypatch.setattr(cli.sys, "argv", ["worker", "--check"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 78
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "system_error"
    assert "PRIVATE" not in captured.out + captured.err
