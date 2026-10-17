# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

import threading
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

from contest_check.archives import DEFAULT_LIMITS, InvalidUpload, validated_workspace
from contest_check.judging import judge_archives
from contest_check.models import UploadError, ValidationSummary
from contest_check.reports import MAX_REPORT_REQUEST_BYTES, MIME_TYPES, ReportLimit, build_report
from contest_check.results import BatchResult
from contest_check.worker_transport import DockerWorker, configured

MAX_REQUEST_BYTES = 2 * DEFAULT_LIMITS.archive_bytes + 65_536
JUDGE_SLOT = threading.BoundedSemaphore(1)
REPORT_SLOT = threading.BoundedSemaphore(1)
UPLOAD_BODY = {
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
}


def error_response(code: str, message: str, status: int = 400) -> JSONResponse:
    return JSONResponse(UploadError(code=code, message=message).model_dump(), status_code=status)


class BoundedUploadBody:
    """Bound bodies before multipart/JSON parsing, even without Content-Length."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        report = scope.get("path", "").startswith("/api/reports/")
        if scope["type"] != "http" or (
            not report and scope["path"] not in {"/api/validate", "/api/judge"}
        ):
            await self.app(scope, receive, send)
            return
        maximum = MAX_REPORT_REQUEST_BYTES if report else MAX_REQUEST_BYTES
        headers = dict(scope["headers"])
        try:
            length = int(headers.get(b"content-length", b"0"))
            if length < 0:
                raise ValueError
        except ValueError:
            await error_response("request_size", "Invalid request Content-Length.")(
                scope, receive, send
            )
            return
        body = bytearray()
        if length <= maximum:
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > maximum:
                    length = maximum + 1
                    break
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
        if length > maximum:
            await error_response("request_size", "Request exceeds the body size limit.", 413)(
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


app = FastAPI(title="ContestCheck AI — Python judge", version="0.1.0")
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
    # This is operator configuration, never a saved sandbox qualification.
    return {"status": "ok", "execution_enabled": configured()}


def validate_pair(task_zip: bytes, submissions_zip: bytes) -> ValidationSummary:
    with validated_workspace(task_zip, submissions_zip) as workspace:
        summary = workspace.summary
    return summary


@app.post(
    "/api/validate",
    response_model=ValidationSummary,
    responses={400: {"model": UploadError}, 413: {"model": UploadError}},
    openapi_extra=UPLOAD_BODY,
)
async def validate_upload(request: Request) -> ValidationSummary | JSONResponse:
    payloads = await read_uploads(request)
    if isinstance(payloads, JSONResponse):
        return payloads
    try:
        return await run_in_threadpool(validate_pair, *payloads)
    except OSError:
        return error_response("workspace", "Temporary validation workspace is unavailable.", 503)


async def read_uploads(request: Request) -> list[bytes] | JSONResponse:
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
    return payloads


def get_worker():
    return DockerWorker() if configured() else None


@app.post(
    "/api/judge",
    response_model=BatchResult,
    openapi_extra=UPLOAD_BODY,
    responses={
        400: {"model": UploadError},
        413: {"model": UploadError},
        503: {"model": UploadError},
    },
)
async def judge_upload(
    request: Request, worker: Annotated[object, Depends(get_worker)]
) -> BatchResult | JSONResponse:
    if worker is None:
        return error_response("execution_disabled", "Solution execution is not configured.", 503)
    if not JUDGE_SLOT.acquire(blocking=False):
        return error_response(
            "judge_busy", "Another judging batch is running. Try again later.", 503
        )
    try:
        payloads = await read_uploads(request)
        if isinstance(payloads, JSONResponse):
            return payloads
        try:
            return await run_in_threadpool(judge_archives, *payloads, worker)
        except OSError:
            return error_response("workspace", "Temporary judging workspace is unavailable.", 503)
    finally:
        JUDGE_SLOT.release()


@app.post("/api/reports/{report_format}", response_class=Response)
async def export_report(report_format: Literal["pdf", "xlsx"], batch: BatchResult):
    if not REPORT_SLOT.acquire(blocking=False):
        return error_response(
            "report_busy", "Another report is being prepared. Try again later.", 503
        )
    try:
        try:
            content = await run_in_threadpool(build_report, report_format, batch)
        except ReportLimit:
            return error_response("report_size", "Report exceeds the export size limit.", 413)
        except Exception:
            return error_response(
                "report_failed", "Report preparation failed. Try again later.", 503
            )
        return Response(
            content,
            media_type=MIME_TYPES[report_format],
            headers={
                "Content-Disposition": (
                    f'attachment; filename="contestcheck-results.{report_format}"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    finally:
        REPORT_SLOT.release()
