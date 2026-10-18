# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Explicit local browser verification with inert ZIPs and a fixed mocked worker.

No uploaded program is executed, no Docker/model call is made, and no service
binds outside loopback. Not run by pytest or CI. Artifacts default to .runtime/.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import httpx
from openpyxl import load_workbook
from pypdf import PdfReader

from contest_check.judge.contracts import RuntimeResult

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "1001": b"# INERT_CORRECT_FIXTURE\n",
    "1002": b"if False:\n import socket\n# INERT_WRONG_FIXTURE\n",
    "1003": b"# INERT_TIMEOUT_FIXTURE\n",
    "1004": b"#" * 1025,
}
SYSTEM_SOURCE = b"# INERT_SYSTEM_ERROR_FIXTURE\n"
INPUTS = {"z": b"1 2\n", "a": b"4 5\n"}
EXPECTED = {"z": b"3\n", "a": b"9\n"}


class OfflineWorker:
    def execute(self, request):
        source = base64.b64decode(request.source_files.get("main.py", ""))
        if (
            request.task.task_id != "offline-ui-fixture"
            or request.test_id not in INPUTS
            or base64.b64decode(request.input_base64) != INPUTS[request.test_id]
            or set(request.source_files) != {"main.py"}
            or source not in {SOURCES.get(request.participant_id), SYSTEM_SOURCE}
        ):
            return RuntimeResult(status="system_error", diagnostic="invalid_request")
        time.sleep(0.2)  # Make the UI's indeterminate running state observable.
        if source == SYSTEM_SOURCE:
            return RuntimeResult(status="system_error", diagnostic="sandbox_unavailable")
        if request.participant_id == "1003":
            return RuntimeResult(status="timeout", diagnostic="wall_limit", elapsed_seconds=0.51)
        output = EXPECTED[request.test_id] if request.participant_id == "1001" else b"wrong\n"
        return RuntimeResult(
            status="success",
            diagnostic="completed",
            exit_code=0,
            elapsed_seconds=0.125,
            output_base64=base64.b64encode(output).decode(),
            output_size_bytes=len(output),
            output_written=True,
        )


def make_archive(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, payload in entries:
            archive.writestr(name, payload)
    return buffer.getvalue()


def write_fixtures(folder):
    manifest = {
        "task_id": "offline-ui-fixture",
        "language": "python",
        "entry_file": "main.py",
        "input_filename": "input.txt",
        "output_filename": "output.txt",
        "tests": [{"test_id": "z"}, {"test_id": "a"}],
        "comparison": "exact",
        "limits": {"time_seconds": 0.5, "memory_mb": 128, "output_bytes": 1024},
        "policy": {"max_source_bytes": 1024, "review_imports": ["socket"]},
    }
    task = [("challenge/task-config.json", json.dumps(manifest))]
    for test_id in INPUTS:
        task.extend(
            [
                (f"challenge/tests/{test_id}.in", INPUTS[test_id]),
                (f"challenge/tests/{test_id}.out", EXPECTED[test_id]),
            ]
        )
    (folder / "task.zip").write_bytes(make_archive(task))
    for filename, system in (("submissions.zip", False), ("incomplete.zip", True)):
        (folder / filename).write_bytes(
            make_archive(
                [
                    (
                        f"{participant}/main.py",
                        SYSTEM_SOURCE if system and participant == "1001" else source,
                    )
                    for participant, source in SOURCES.items()
                ]
            )
        )
    (folder / "invalid.zip").write_bytes(b"not a ZIP archive")


def free_port():
    with socket.socket() as connection:
        connection.bind(("127.0.0.1", 0))
        return connection.getsockname()[1]


def serve(port):
    import uvicorn

    from contest_check import api
    from contest_check.api import app, get_worker

    # Advertise the fixed fixture worker to the real UI, without enabling Docker.
    api.configured = lambda: True
    app.dependency_overrides[get_worker] = OfflineWorker
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def verify(output):
    output.mkdir(parents=True, exist_ok=True)
    api_port, ui_port = free_port(), free_port()
    while ui_port == api_port:
        ui_port = free_port()
    environment = {
        **os.environ,
        "API_PORT": str(api_port),
        "JUDGE_EXECUTION_ENABLED": "false",
        "JUDGE_REVIEWED_PROFILE": "false",
    }
    processes = []
    handles = []
    with tempfile.TemporaryDirectory(prefix="cca004-ui-fixtures-") as directory:
        fixtures = Path(directory)
        write_fixtures(fixtures)
        commands = [
            [sys.executable, str(Path(__file__).resolve()), "--serve-fixtures", str(api_port)],
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.port",
                str(ui_port),
            ],
        ]
        try:
            for index, command in enumerate(commands):
                handle = (output / f"service-{index}.log").open("wb")
                handles.append(handle)
                processes.append(
                    subprocess.Popen(
                        command,
                        cwd=ROOT,
                        env=environment,
                        stdout=handle,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                )
            with httpx.Client(trust_env=False, timeout=2) as client:
                deadline = time.monotonic() + 30
                for url in (
                    f"http://127.0.0.1:{api_port}/health",
                    f"http://127.0.0.1:{ui_port}/_stcore/health",
                ):
                    while True:
                        try:
                            if client.get(url).status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        if time.monotonic() >= deadline or any(
                            p.poll() is not None for p in processes
                        ):
                            raise RuntimeError("Offline verification service did not start.")
                        time.sleep(0.1)
            node = environment.get("CCA_BROWSER_NODE", "node")
            browser = subprocess.run(
                [
                    node,
                    str(ROOT / "scripts/verify_ui_reports.cjs"),
                    f"http://127.0.0.1:{ui_port}",
                    str(fixtures),
                    str(output.resolve()),
                ],
                env=environment,
                cwd=ROOT,
                capture_output=True,
                timeout=120,
            )
            if browser.returncode:
                (output / "browser-error.log").write_bytes(browser.stdout + browser.stderr)
                raise RuntimeError("Browser verification failed; inspect browser-error.log.")
            evidence = json.loads(browser.stdout)
            pdf = (output / "download.pdf").read_bytes()
            workbook = load_workbook(output / "download.xlsx", data_only=False)
            text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
            assert (
                "offline-ui-fixture" in text
                and "Requires Review" in text
                and "Disqualified / Rejected" in text
            )
            assert all(participant in text for participant in SOURCES)
            assert "INERT_" not in text
            assert workbook["Tests"].max_row == 9
            assert workbook["Tests"]["A2"].value == "1001"
            assert all(cell.data_type != "f" for sheet in workbook for row in sheet for cell in row)
            workbook.close()
            evidence["execution"] = (
                "Mocked fixed inert fixtures; no student execution or Docker/model calls"
            )
            evidence["report_checks"] = {"pdf_text": True, "xlsx_rows": 8, "no_formulas": True}
            evidence["sha256"] = {
                name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                for name in ("download.pdf", "download.xlsx")
            }
            (output / "verification.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(json.dumps(evidence, indent=2))
        finally:
            for process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
            for handle in handles:
                handle.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve-fixtures", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/cca004-verification")
    arguments = parser.parse_args()
    if arguments.serve_fixtures:
        serve(arguments.serve_fixtures)
    else:
        verify(arguments.output)


if __name__ == "__main__":
    main()
