# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TestSpec(ContractModel):
    test_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")]


class ResourceLimits(ContractModel):
    time_seconds: Annotated[float, Field(gt=0, le=3, allow_inf_nan=False)]
    memory_mb: Annotated[int, Field(ge=1, le=256)]
    output_bytes: Annotated[int, Field(ge=1, le=1_048_576)]


class TaskManifest(ContractModel):
    task_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")]
    language: Literal["python"]
    entry_file: Literal["main.py"]
    input_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(in|txt)$")]
    output_filename: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,47}\.(out|txt)$")]
    tests: Annotated[list[TestSpec], Field(min_length=1, max_length=100)]
    comparison: Literal["exact", "tokens"]
    limits: ResourceLimits
    title: Annotated[str | None, Field(max_length=160)] = None

    @model_validator(mode="after")
    def unique_names(self) -> "TaskManifest":
        if self.input_filename == self.output_filename:
            raise ValueError("Input and output filenames must differ.")
        ids = [test.test_id.casefold() for test in self.tests]
        if len(ids) != len(set(ids)):
            raise ValueError("Test IDs must be unique, including case-insensitive comparison.")
        return self


class ValidationSummary(ContractModel):
    status: Literal["validated"] = "validated"
    task_id: str
    test_count: int
    participant_ids: list[str]
    submission_file_count: int
    extracted_bytes: int
    execution_enabled: Literal[False] = False


class UploadError(ContractModel):
    code: str
    message: str
