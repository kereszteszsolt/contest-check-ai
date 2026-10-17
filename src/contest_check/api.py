# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from contest_check.archives import DEFAULT_LIMITS, InvalidUpload, validated_workspace
from contest_check.models import UploadError, ValidationSummary

MAX_REQUEST_BYTES = 2 * DEFAULT_LIMITS.archive_bytes + 65_536


def error_response(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(UploadError(code=code, message=message).model_dump(), status_code=status)


class BoundedUploadBody:
    """Bound the actual body before multipart parsing, even without Content-Length."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != "/api/validate":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            await error_response("request_size", "Invalid upload Content-Length.")(
                scope, receive, send
            )
            return
        body = bytearray()
        if length <= MAX_REQUEST_BYTES:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > MAX_REQUEST_BYTES:
                    length = MAX_REQUEST_BYTES + 1
                    break
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
        if length > MAX_REQUEST_BYTES:
            await error_response("request_size", "Upload exceeds the request size limit.", 413)(
                scope, receive, send
            )
            return

        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)


app = FastAPI(title="ContestCheck AI — archive validation", version="0.1.0")
app.add_middleware(BoundedUploadBody)


@app.exception_handler(InvalidUpload)
async def invalid_upload_handler(request: Request, exc: InvalidUpload):
    return error_response(exc.code, exc.message)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return error_response("request", "Request is invalid or unsupported.", exc.status_code)


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    return error_response("request", "Request does not match the API contract.", 422)


@app.get("/health")
def health():
    return {"status": "ok", "execution_enabled": False}


def validate_pair(task_zip: bytes, submissions_zip: bytes) -> ValidationSummary:
    with validated_workspace(task_zip, submissions_zip) as workspace:
        summary = workspace.summary
    return summary


@app.post(
    "/api/validate",
    response_model=ValidationSummary,
    responses={400: {"model": UploadError}, 413: {"model": UploadError}},
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["task_zip", "submissions_zip"],
                        "additionalProperties": False,
                        "properties": {
                            "task_zip": {"type": "string", "format": "binary"},
                            "submissions_zip": {"type": "string", "format": "binary"},
                        },
                    }
                }
            },
        }
    },
)
async def validate_upload(request: Request) -> ValidationSummary | JSONResponse:
    if (
        request.headers.get("content-type", "").split(";")[0].strip().lower()
        != "multipart/form-data"
    ):
        return error_response(
            "content_type", "Upload two ZIP files using multipart/form-data.", 415
        )
    async with request.form(max_files=2, max_fields=0) as form:
        if len(form.multi_items()) != 2 or set(form) != {"task_zip", "submissions_zip"}:
            return error_response("upload_fields", "Provide exactly task_zip and submissions_zip.")
        payloads = []
        for key in ("task_zip", "submissions_zip"):
            upload = form[key]
            if not isinstance(upload, UploadFile):
                return error_response("upload_fields", "Both upload fields must be ZIP files.")
            payload = await upload.read(DEFAULT_LIMITS.archive_bytes + 1)
            if len(payload) > DEFAULT_LIMITS.archive_bytes:
                return error_response(
                    "archive_size", "ZIP exceeds the compressed upload size limit.", 413
                )
            payloads.append(payload)
    try:
        return await run_in_threadpool(validate_pair, *payloads)
    except OSError:
        return error_response("workspace", "Temporary validation workspace is unavailable.", 503)


@app.post("/api/judge", status_code=503, response_model=UploadError)
def judge_disabled():
    return UploadError(code="execution_disabled", message="Solution execution is not available.")


@app.get("/api/reports/{report_format}", status_code=501, response_model=UploadError)
def reports_unavailable(report_format: Literal["pdf", "xlsx"]):
    return UploadError(code="reports_unavailable", message="Report export is not implemented yet.")
