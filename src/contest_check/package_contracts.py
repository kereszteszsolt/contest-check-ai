# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Explicit public fields and teacher export options; no generated source in public data."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from contest_check.authoring_contracts import PublicExample, TaskDraft
from contest_check.models import ContractModel, ResourceLimits, TaskManifest

Audience = Literal["student", "teacher"]


class PackageOptions(ContractModel):
    include_reviewed_reference: bool = False


class ExampleFiles(ContractModel):
    input_file: Annotated[str, Field(pattern=r"^examples/sample(?:-0[2-9]|-10)?\.in$")]
    output_file: Annotated[str, Field(pattern=r"^examples/sample(?:-0[2-9]|-10)?\.out$")]


class StudentManifest(ContractModel):
    format_version: Literal[1] = 1
    audience: Literal["student"] = "student"
    approved: Literal[True] = True
    verification: Literal["unverified"] = "unverified"
    task_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
    title: Annotated[str, Field(min_length=1, max_length=160)]
    language: Literal["python"] = "python"
    entry_file: Literal["main.py"] = "main.py"
    starter_file: Literal["starter/main.py"] = "starter/main.py"
    input_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(in|txt)$")]
    output_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(out|txt)$")]
    comparison: Literal["exact", "tokens"]
    limits: ResourceLimits
    examples: Annotated[list[ExampleFiles], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def coherent_files(self) -> "StudentManifest":
        TaskManifest.model_validate(
            {
                key: getattr(self, key)
                for key in (
                    "task_id",
                    "title",
                    "language",
                    "entry_file",
                    "input_filename",
                    "output_filename",
                    "comparison",
                    "limits",
                )
            }
            | {"tests": [{"test_id": "sample"}]}
        )
        for index, pair in enumerate(self.examples, 1):
            stem = "examples/sample" + (f"-{index:02}" if index > 1 else "")
            if pair.input_file != stem + ".in" or pair.output_file != stem + ".out":
                raise ValueError("Examples must have unique sequential public filenames.")
        return self

    @classmethod
    def from_draft(cls, draft: TaskDraft) -> "StudentManifest":
        return cls.model_validate(
            {
                key: getattr(draft, key)
                for key in (
                    "task_id",
                    "title",
                    "language",
                    "entry_file",
                    "input_filename",
                    "output_filename",
                    "comparison",
                    "limits",
                )
            }
            | {
                "examples": [
                    {
                        "input_file": "examples/sample" + (f"-{i:02}" if i > 1 else "") + ".in",
                        "output_file": "examples/sample" + (f"-{i:02}" if i > 1 else "") + ".out",
                    }
                    for i in range(1, len(draft.examples) + 1)
                ]
            }
        )


class PublicProblem(ContractModel):
    manifest: StudentManifest
    statement: Annotated[str, Field(min_length=1, max_length=12_000)]
    examples: Annotated[list[PublicExample], Field(min_length=1, max_length=10)]


class PackageError(ValueError):
    ERRORS = {
        "package_unapproved": (
            409,
            "Approve the current valid draft before downloading a package.",
        ),
        "package_invalid": (422, "The draft does not satisfy the safe challenge-package contract."),
        "package_options": (422, "Only the teacher package can include a reviewed reference."),
        "package_text": (422, "The PDF contains unsupported characters or control text."),
        "package_size": (413, "The challenge exceeds the package or printable-document limits."),
        "package_busy": (503, "Another challenge package is being prepared. Try later."),
        "package_failed": (503, "Challenge package preparation failed. Try later."),
    }

    def __init__(self, code: str):
        self.code = code
        self.status, self.message = self.ERRORS[code]
        super().__init__(self.message)
