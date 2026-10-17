# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Produce known, inert upload examples; never run any submitted Python file."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from contest_check.models import TaskManifest


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    raw = (repository / "examples/task-config.json").read_bytes()
    TaskManifest.model_validate_json(raw)
    output = repository / ".runtime/demo"
    output.mkdir(parents=True, exist_ok=True)
    with ZipFile(output / "task.zip", "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("challenge/task-config.json", raw)
        archive.writestr("challenge/tests/01.in", "1 2\n")
        archive.writestr("challenge/tests/01.out", "3\n")
    with ZipFile(output / "submissions.zip", "w", compression=ZIP_DEFLATED) as archive:
        for participant in ("1001", "1002"):
            archive.writestr(
                f"{participant}/main.py", "# Inert fixture for validation only. Never executed.\n"
            )
        archive.writestr("1001/helpers.py", "# Optional inert sibling module.\n")
    print("Created .runtime/demo/task.zip and .runtime/demo/submissions.zip (inert fixtures).")


if __name__ == "__main__":
    main()
