# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Bounded in-memory exports. No uploaded source, templates, URLs or office files."""

import io
import re
from datetime import datetime
from xml.sax.saxutils import escape

import xlsxwriter
from pydantic import ValidationError
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from contest_check.presentation import (
    DQ_COLUMNS,
    MEASUREMENT_NOTE,
    REVIEW_COLUMNS,
    SUMMARY_COLUMNS,
    TEST_COLUMNS,
    policy_rows,
    summary_rows,
    test_rows,
)
from contest_check.results import BatchResult

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_REPORT_REQUEST_BYTES = 8 * 1024 * 1024
MIME_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
REJECTION_NOTE = "Invalid ZIP uploads are rejected before judging and have no participant verdict."
REVIEW_NOTE = "Review flags require a teacher's judgment and do not change official test verdicts."


class ReportError(ValueError):
    pass


class ReportLimit(ReportError):
    pass


class BoundedBuffer(io.BytesIO):
    exceeded = False

    def write(self, payload):
        if self.exceeded or self.tell() + len(payload) > MAX_REPORT_BYTES:
            # Drain library writers without retaining bytes beyond the cap.
            # Raising mid-ZIP-write can leave its archive finalizer unclosed.
            self.exceeded = True
            self.seek(len(payload), io.SEEK_CUR)
            return len(payload)
        return super().write(payload)

    def getvalue(self):
        if self.exceeded:
            raise ReportLimit("Report exceeds the export size limit.")
        return super().getvalue()


def excel_text(value: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        text = "'" + text
    return text[:32_767]


def metadata_rows(batch: BatchResult) -> list[list]:
    return [
        ["Task", batch.task_id],
        ["Batch status", batch.status],
        ["Comparison", batch.comparison],
        ["Wall limit (s/test)", batch.limits.time_seconds],
        ["Memory limit (MiB/test)", batch.limits.memory_mb],
        ["Output limit (bytes/test)", batch.limits.output_bytes],
        ["Tests per participant", batch.tests_per_participant],
    ]


def xlsx_report(batch: BatchResult, buffer: BoundedBuffer) -> None:
    with xlsxwriter.Workbook(
        buffer,
        {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    ) as workbook:
        workbook.set_properties(
            {
                "title": "ContestCheck AI results",
                "author": "ContestCheck AI",
                "created": datetime(2000, 1, 1),
            }
        )
        header = workbook.add_format({"bold": True, "bg_color": "#E2E8F0", "text_wrap": True})
        regular = workbook.add_format({"text_wrap": True, "valign": "top"})
        seconds = workbook.add_format({"num_format": "0.000000", "valign": "top"})

        def write_row(sheet, index, values, style=regular):
            for column, value in enumerate(values):
                if isinstance(value, str) or (isinstance(value, int) and abs(value) > 2**53 - 1):
                    sheet.write_string(index, column, excel_text(str(value)), style)
                elif value is None:
                    sheet.write_string(index, column, "N/A", style)
                else:
                    sheet.write_number(
                        index, column, value, seconds if isinstance(value, float) else style
                    )

        sheets = [
            ("Summary", SUMMARY_COLUMNS, summary_rows(batch)),
            ("Tests", TEST_COLUMNS, test_rows(batch)),
            ("Disqualified - Rejected", DQ_COLUMNS, policy_rows(batch, "DQ")),
            ("Requires Review", REVIEW_COLUMNS, policy_rows(batch, "REVIEW")),
        ]
        for name, columns, rows in sheets:
            sheet = workbook.add_worksheet(name)
            sheet.set_column(0, 0, 21)
            sheet.set_column(1, len(columns) - 1, 22)
            start = 0
            if name == "Summary":
                for index, row in enumerate(metadata_rows(batch)):
                    write_row(sheet, index, row)
                start = len(metadata_rows(batch)) + 2
            elif name == "Disqualified - Rejected":
                write_row(sheet, 0, ["Disqualified / Rejected"])
                write_row(sheet, 1, [REJECTION_NOTE])
                start = 3
            elif name == "Requires Review":
                write_row(sheet, 0, [REVIEW_NOTE])
                start = 2
            write_row(sheet, start, columns, header)
            sheet.set_row(start, 30)
            for index, row in enumerate(rows, start + 1):
                write_row(sheet, index, row)
            if rows:
                sheet.autofilter(start, 0, start + len(rows), len(columns) - 1)
            sheet.freeze_panes(start + 1, 1)
            sheet.repeat_rows(start)
            sheet.set_landscape()
            sheet.fit_to_pages(1, 0)
            sheet.set_footer("&CContestCheck AI | Page &P of &N")
            if name == "Tests":
                sheet.set_column(4, 4, 52)
            if name == "Summary":
                write_row(sheet, start + len(rows) + 3, [MEASUREMENT_NOTE])


def pdf_report(batch: BatchResult, buffer: BoundedBuffer) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Report body", parent=styles["BodyText"], fontSize=8, leading=11)
    cell = ParagraphStyle("Report cell", parent=body, fontSize=7, leading=9)
    story = [Paragraph("ContestCheck AI results", styles["Title"])]
    for key, value in metadata_rows(batch):
        story.append(Paragraph(f"<b>{escape(key)}:</b> {escape(str(value))}", body))
    story.extend([Spacer(1, 10), Paragraph(escape(MEASUREMENT_NOTE), body)])
    if batch.status == "incomplete":
        story.append(
            Paragraph("<b>Incomplete batch: unrun tests are not participant failures.</b>", body)
        )

    def table(title, columns, rows, widths, note=None):
        story.extend([Spacer(1, 14), Paragraph(title, styles["Heading2"])])
        if note:
            story.append(Paragraph(escape(note), body))
            story.append(Spacer(1, 6))
        if not rows:
            story.append(Paragraph("None.", body))
            return

        def paragraph(value):
            text = f"{value:.6g}" if isinstance(value, float) else str(value)
            return Paragraph(escape(text), cell)

        data = [[paragraph(value) for value in row] for row in [columns, *rows]]
        report_table = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        report_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#94A3B8")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(report_table)

    table(
        "Anonymous participant summary",
        SUMMARY_COLUMNS,
        summary_rows(batch),
        [100, 130, 70, 70, 90, 90],
    )
    table("Per-test outcomes", TEST_COLUMNS, test_rows(batch), [85, 90, 65, 70, 230, 70, 70, 100])
    table(
        "Disqualified / Rejected",
        DQ_COLUMNS,
        policy_rows(batch, "DQ"),
        [90, 115, 230, 110, 110],
        REJECTION_NOTE,
    )
    table(
        "Requires Review",
        REVIEW_COLUMNS,
        policy_rows(batch, "REVIEW"),
        [90, 120, 310, 100],
        REVIEW_NOTE,
    )

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.drawString(28, 18, f"ContestCheck AI | Page {document.page}")

    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=28,
        rightMargin=28,
        topMargin=30,
        bottomMargin=32,
        title="ContestCheck AI results",
        author="ContestCheck AI",
        invariant=1,
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)


def build_report(report_format: str, batch: BatchResult) -> bytes:
    try:
        # Revalidate dictionaries too, rather than trusting model_construct/copy.
        batch = BatchResult.model_validate(batch.model_dump())
    except (ValidationError, AttributeError):
        raise ReportError("Invalid result contract.") from None
    if report_format not in MIME_TYPES:
        raise ReportError("Unsupported report format.")
    with BoundedBuffer() as buffer:
        if report_format == "pdf":
            pdf_report(batch, buffer)
        else:
            xlsx_report(batch, buffer)
        return buffer.getvalue()
