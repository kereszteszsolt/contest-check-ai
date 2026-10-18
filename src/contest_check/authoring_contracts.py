# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Untrusted, unapproved challenge drafts; never executable application state."""

from typing import Annotated, Literal

from pydantic import Field, model_validator

from contest_check.models import ContractModel, ResourceLimits, TaskManifest

MAX_INSTRUCTIONS = 8_000
MAX_DRAFT_BYTES = 128 * 1024
MAX_AUTHORING_REQUEST_BYTES = 64 * 1024
Provider = Literal["ollama", "openrouter"]
ModelSlot = Annotated[str, Field(pattern=r"^(ollama|openrouter):[1-3]$")]
ModelName = Annotated[str, Field(min_length=1, max_length=128)]
TestID = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")]
TestText = Annotated[str, Field(max_length=8_192)]


class PublicExample(ContractModel):
    input: TestText
    output: TestText
    explanation: Annotated[str, Field(max_length=2_000)]


class PrivateTest(ContractModel):
    test_id: TestID
    input: TestText
    expected_output: TestText


class TaskDraft(ContractModel):
    task_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
    title: Annotated[str, Field(min_length=1, max_length=160)]
    statement: Annotated[str, Field(min_length=1, max_length=12_000)]
    language: Literal["python"]
    entry_file: Literal["main.py"]
    input_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(in|txt)$")]
    output_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(out|txt)$")]
    comparison: Literal["exact", "tokens"]
    limits: ResourceLimits
    examples: Annotated[list[PublicExample], Field(min_length=1, max_length=10)]
    starter_source: Annotated[str, Field(min_length=1, max_length=16_384)]
    reference_source: Annotated[str, Field(min_length=1, max_length=32_768)]
    private_tests: Annotated[list[PrivateTest], Field(min_length=1, max_length=100)]
    warnings: Annotated[list[Annotated[str, Field(max_length=500)]], Field(max_length=10)]

    @model_validator(mode="after")
    def coherent_task(self) -> "TaskDraft":
        TaskManifest.model_validate(
            {
                "task_id": self.task_id,
                "language": self.language,
                "entry_file": self.entry_file,
                "input_filename": self.input_filename,
                "output_filename": self.output_filename,
                "tests": [{"test_id": t.test_id} for t in self.private_tests],
                "comparison": self.comparison,
                "limits": self.limits.model_dump(),
                "title": self.title,
            }
        )
        if not self.title.strip() or not self.statement.strip():
            raise ValueError("Draft title and statement must contain text.")
        if len(self.model_dump_json().encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError("Draft exceeds the size limit.")
        return self


class DraftRequest(ContractModel):
    model_slot: ModelSlot
    instructions: Annotated[str, Field(min_length=1, max_length=MAX_INSTRUCTIONS)]

    @model_validator(mode="after")
    def meaningful_instructions(self) -> "DraftRequest":
        if not self.instructions.strip():
            raise ValueError("Teacher instructions are required.")
        return self


class DraftContext(ContractModel):
    """Bounded workflow context, carried as data in a separate model message."""

    topic: Annotated[str, Field(min_length=1, max_length=120)]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    revision: Annotated[str, Field(max_length=2_000)] = ""
    previous_draft: TaskDraft | None = None


class ModelChoice(ContractModel):
    slot: ModelSlot
    provider: Provider
    model: ModelName


class ModelCatalog(ContractModel):
    models: Annotated[list[ModelChoice], Field(max_length=6)]
    issues: list[str]


class DraftResponse(ContractModel):
    model: ModelChoice
    draft: TaskDraft
    calls_used: Annotated[int, Field(ge=1, le=6)]
    approved: Literal[False] = False
    executed: Literal[False] = False
