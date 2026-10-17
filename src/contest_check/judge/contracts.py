# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import base64
import binascii
import json
import math
import re
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import Field, model_validator

from contest_check.models import ContractModel, TaskManifest

MAX_REQUEST_BYTES = 44 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
EncodedFile = Annotated[str, Field(max_length=1_398_104)]
ModuleName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}\.py$")]


class WorkerRequest(ContractModel):
    protocol: Literal[1] = 1
    participant_id: Annotated[str, Field(pattern=r"^(0|[1-9][0-9]{0,15})$")]
    task: TaskManifest
    test_id: str
    source_files: Annotated[dict[ModuleName, EncodedFile], Field(min_length=1, max_length=30)]
    input_base64: EncodedFile

    @model_validator(mode="after")
    def validate_job(self) -> "WorkerRequest":
        names = [name.casefold() for name in self.source_files]
        if "main.py" not in self.source_files or len(names) != len(set(names)):
            raise ValueError("One main.py and unique module names are required.")
        if self.test_id not in {test.test_id for test in self.task.tests}:
            raise ValueError("Test must be declared by the manifest.")
        for content in (*self.source_files.values(), self.input_base64):
            decode_file(content)
        return self


def decode_file(value: str) -> bytes:
    try:
        payload = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid encoded file.") from None
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the worker input limit.")
    return payload


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key.")
        result[key] = value
    return result


def parse_request(raw: bytes) -> WorkerRequest:
    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Request exceeds the worker input limit.")
    return WorkerRequest.model_validate(
        json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    )


class RuntimeResult(ContractModel):
    status: Literal["success", "timeout", "resource", "crash", "system_error"]
    diagnostic: Literal[
        "completed",
        "wall_limit",
        "signal_limit",
        "memory_or_exit",
        "output_or_exit",
        "program_exit",
        "sandbox_unavailable",
        "sandbox_setup",
        "cleanup_failed",
        "invalid_request",
    ]
    elapsed_seconds: Annotated[float, Field(ge=0)] = 0.0
    exit_code: int | None = None
    signal: int | None = None
    output_base64: str | None = None
    output_size_bytes: int | None = None


class SecurityCheck(ContractModel):
    name: str
    passed: bool


class VerificationReport(ContractModel):
    backend: Literal["nsjail-3.5"] = "nsjail-3.5"
    execution_ready: bool = False
    checks: list[SecurityCheck]


@dataclass(frozen=True)
class PreparedRun:
    sources: dict[str, bytes]
    input_bytes: bytes
    input_filename: str
    output_filename: str
    time_seconds: float
    memory_mb: int
    output_bytes: int

    def __post_init__(self) -> None:
        if (
            not 1 <= len(self.sources) <= 30
            or "main.py" not in self.sources
            or len({name.casefold() for name in self.sources}) != len(self.sources)
            or any(
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}\.py", name) is None
                for name in self.sources
            )
            or re.fullmatch(r"[a-z][a-z0-9_-]{0,47}\.(in|txt)", self.input_filename) is None
            or re.fullmatch(r"[a-z][a-z0-9_-]{0,47}\.(out|txt)", self.output_filename) is None
            or self.input_filename == self.output_filename
            or any(
                not isinstance(value, bytes) or len(value) > MAX_FILE_BYTES
                for value in (*self.sources.values(), self.input_bytes)
            )
            or not math.isfinite(self.time_seconds)
            or not 0 < self.time_seconds <= 3
            or type(self.memory_mb) is not int
            or not 1 <= self.memory_mb <= 256
            or type(self.output_bytes) is not int
            or not 1 <= self.output_bytes <= MAX_FILE_BYTES
        ):
            raise ValueError("Invalid isolated run specification.")

    @classmethod
    def from_request(cls, request: WorkerRequest) -> "PreparedRun":
        return cls(
            sources={name: decode_file(value) for name, value in request.source_files.items()},
            input_bytes=decode_file(request.input_base64),
            input_filename=request.task.input_filename,
            output_filename=request.task.output_filename,
            time_seconds=request.task.limits.time_seconds,
            memory_mb=request.task.limits.memory_mb,
            output_bytes=request.task.limits.output_bytes,
        )
