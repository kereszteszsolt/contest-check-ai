# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Operator-only authoring browser smoke with a fixed model mock and no worker.

Starts loopback services, never executes generated source or calls a provider.
Not invoked by pytest/CI. Requires an operator-installed Node/Playwright browser.
"""

import argparse
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import httpx
from pypdf import PdfReader
from verify_ui_reports import free_port

from contest_check.archives import validate_export_archive

ROOT = Path(__file__).resolve().parents[1]


def serve(port):
    import uvicorn

    from contest_check.api import app, get_model_settings, get_worker, get_workflow_store
    from contest_check.authoring_contracts import DraftResponse, TaskDraft
    from contest_check.authoring_workflow import WorkflowStore
    from contest_check.model_configuration import ProviderError, load_model_settings
    from contest_check.providers import GenerationSession, ProviderTransport

    settings = load_model_settings(
        {
            "OLLAMA_MODEL_1": "offline-fixture:1",
            "OPENROUTER_MODEL_1": "offline/fixture",
            "OPENROUTER_API_KEY": "not-a-real-key",
        }
    )
    store = WorkflowStore()
    calls = []

    async def deny_network(*args, **kwargs):
        raise AssertionError("Offline verification forbids provider traffic.")

    async def generate(session, instructions, *, context):
        session.budget.reserve()
        calls.append(
            {"revision": bool(context.revision), "malformed": instructions.startswith("Malformed")}
        )
        if instructions.startswith("Malformed"):
            raise ProviderError("invalid_output")
        draft = TaskDraft(
            task_id="offline-authoring",
            title="Összeadás – árvíztűrő tükörfúrógép",
            statement="Olvass be két egész számot az input.txt fájlból. "
            "Írd összegüket az output.txt fájlba.\n"
            "Untrusted text: ![tracking](https://outside.invalid/pixel)",
            language="python",
            entry_file="main.py",
            input_filename="input.txt",
            output_filename="output.txt",
            comparison="tokens",
            limits={"time_seconds": 0.5, "memory_mb": 128, "output_bytes": 1024},
            examples=[{"input": "1 2\n", "output": "3\n", "explanation": "1 + 2 = 3"}],
            starter_source="# INERT_GENERATED_STARTER\n",
            reference_source="# INERT_PRIVATE_REFERENCE\n",
            private_tests=[{"test_id": "hidden", "input": "3 4\n", "expected_output": "7\n"}],
            warnings=["Synthetic fixture. No reference code is executed."],
        )
        return DraftResponse(model=session.choice, draft=draft, calls_used=session.budget.used)

    GenerationSession.generate = generate
    ProviderTransport.handle_async_request = deny_network
    app.dependency_overrides.update(
        {
            get_model_settings: lambda: settings,
            get_worker: lambda: None,
            get_workflow_store: lambda: store,
        }
    )

    @app.get("/_offline/evidence")
    def evidence():
        return {
            "calls": calls,
            "statuses": [run.preview().state.status for run in store.workflows.values()],
        }

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def verify(output):
    output.mkdir(parents=True, exist_ok=True)
    api_port, ui_port = free_port(), free_port()
    while api_port == ui_port:
        ui_port = free_port()
    environment = {
        **os.environ,
        "API_PORT": str(api_port),
        "JUDGE_EXECUTION_ENABLED": "false",
        "JUDGE_REVIEWED_PROFILE": "false",
        "OPENROUTER_API_KEY": "",
        "OLLAMA_API_KEY": "",
        "LANGSMITH_TRACING": "false",
        "LANGCHAIN_TRACING_V2": "false",
        **{
            f"{provider}_MODEL_{i}": ""
            for provider in ("OLLAMA", "OPENROUTER")
            for i in range(1, 4)
        },
    }
    processes, handles = [], []
    try:
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
            for url in (
                f"http://127.0.0.1:{api_port}/health",
                f"http://127.0.0.1:{ui_port}/_stcore/health",
            ):
                deadline = time.monotonic() + 30
                while True:
                    try:
                        if client.get(url).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if time.monotonic() >= deadline or any(p.poll() is not None for p in processes):
                        raise RuntimeError("Offline authoring services did not start.")
                    time.sleep(0.1)
            browser = subprocess.run(
                [
                    environment.get("CCA_BROWSER_NODE", "node"),
                    str(ROOT / "scripts/verify_authoring_ui.cjs"),
                    f"http://127.0.0.1:{ui_port}",
                    f"http://127.0.0.1:{api_port}",
                    str(output.resolve()),
                ],
                env=environment,
                cwd=ROOT,
                capture_output=True,
                timeout=180,
            )
            if browser.returncode:
                (output / "browser-error.log").write_bytes(browser.stdout + browser.stderr)
                raise RuntimeError(
                    "Offline authoring browser checks failed; inspect browser-error.log."
                )
            evidence = json.loads(browser.stdout)
            evidence["backend"] = client.get(
                f"http://127.0.0.1:{api_port}/_offline/evidence"
            ).json()
        hashes = {}
        for audience in ("student", "teacher"):
            artifact = output / f"{audience}.zip"
            validate_export_archive(artifact.read_bytes(), audience)
            hashes[artifact.name] = hashlib.sha256(artifact.read_bytes()).hexdigest()
        with zipfile.ZipFile(output / "student.zip") as archive:
            pdf = archive.read("problem.pdf")
            text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
            assert "árvíztűrő tükörfúrógép" in text and "INERT_" not in text
            (output / "problem.pdf").write_bytes(pdf)
        with zipfile.ZipFile(output / "teacher.zip") as archive:
            assert "challenge/tests/hidden.out" in archive.namelist()
            assert "teacher/reference/main.py" not in archive.namelist()
            checks = json.loads(archive.read("teacher/checks.json"))
            assert checks["verification"] == "unverified"
        assert len(evidence["backend"]["calls"]) == 4
        assert evidence["backend"]["statuses"] == ["rejected"]
        evidence.update(
            {
                "execution": "Fixed mocked generation; no provider/worker/source execution",
                "zip_validation": True,
                "hungarian_pdf_text": True,
                "sha256": hashes,
            }
        )
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
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/cca008-verification")
    arguments = parser.parse_args()
    if arguments.serve_fixtures:
        serve(arguments.serve_fixtures)
    else:
        verify(arguments.output)


if __name__ == "__main__":
    main()
