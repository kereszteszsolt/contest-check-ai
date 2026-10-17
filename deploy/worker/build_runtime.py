# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Build-time only: assemble a minimal jail from trusted, pinned-image Python files."""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/opt/cca-jail")


def copy_library(path: Path) -> None:
    destination = ROOT / path.relative_to("/")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copy2(path, destination, follow_symlinks=True)


def main() -> None:
    python = Path("/usr/local/bin/python3.12")
    copy_library(python)
    stdlib = Path("/usr/local/lib/python3.12")
    shutil.copytree(
        stdlib,
        ROOT / stdlib.relative_to("/"),
        ignore=shutil.ignore_patterns(
            "site-packages", "ensurepip", "idlelib", "tkinter", "test", "__pycache__"
        ),
    )
    targets = [python, *stdlib.rglob("*.so")]
    for target in targets:
        if "site-packages" in target.parts:
            continue
        # ldd is applied only to known image binaries, never to uploaded programs.
        result = subprocess.run(["ldd", str(target)], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            match = re.search(r"(?:=>\s+)?(/[^\s]+)", line)
            if match:
                copy_library(Path(match.group(1)).absolute())
    for name in ("work", "proc"):
        (ROOT / name).mkdir(mode=0o555)
    shutil.copy2("/build/bootstrap.py", ROOT / "bootstrap.py")
    (ROOT / "bootstrap.py").chmod(0o444)
    files = (
        Path("/usr/local/bin/nsjail"),
        Path("/opt/cca-worker/python.policy"),
        ROOT / "bootstrap.py",
    )
    manifest = {
        "nsjail_revision": "402e2b4c13c79731c632c2add4c3884dd1afc25f",
        "kafel_revision": "b4241da9f3d17e786387280fc6e4965634fdf45b",
        "python_image": (
            "python:3.12.13-slim-bookworm@sha256:"
            "4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2"
        ),
        "sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in files},
    }
    Path("/opt/cca-worker/runtime.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
