# SPDX-FileCopyrightText: 2026 Keresztes Zsolt <https://kereszteszsolt.hu>
# SPDX-License-Identifier: Apache-2.0

"""Printable public text only; escaped markup, embedded local fonts, bounded pages."""

import io
import textwrap
import unicodedata
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer

from contest_check.package_contracts import PackageError, PublicProblem

FONT_DIRECTORY = Path(__file__).parent / "assets/fonts"
MAX_PDF_BYTES = 1_048_576
MAX_PDF_PAGES = 60
MAX_RENDER_LINES = 2_400
BODY_FONT = "CCA-DejaVuSans"
CODE_FONT = "CCA-DejaVuSansMono"


@lru_cache(maxsize=1)
def register_fonts():
    for name, filename in [(BODY_FONT, "DejaVuSans.ttf"), (CODE_FONT, "DejaVuSansMono.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIRECTORY / filename)))


def printable(text: str, font: str) -> str:
    widths = pdfmetrics.getFont(font).face.charWidths
    if any(
        (unicodedata.category(char).startswith("C") or ord(char) not in widths)
        and char not in "\n\r\t"
        for char in text
    ):
        raise PackageError("package_text")
    return text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)


class PDFBuffer(io.BytesIO):
    def write(self, payload):
        if self.tell() + len(payload) > MAX_PDF_BYTES:
            raise PackageError("package_size")
        return super().write(payload)


class PageLimit(Exception):
    """Internal exception compatible with ReportLab's exception annotation."""


def problem_pdf(problem: PublicProblem) -> bytes:
    problem = PublicProblem.model_validate(problem.model_dump(mode="json"))
    register_fonts()
    manifest = problem.manifest
    body = ParagraphStyle(
        "Challenge body",
        fontName=BODY_FONT,
        fontSize=10,
        leading=15,
        spaceAfter=8,
        splitLongWords=True,
    )
    title = ParagraphStyle(
        "Challenge title",
        parent=body,
        fontSize=20,
        leading=26,
        spaceAfter=14,
        textColor=colors.HexColor("#172554"),
    )
    heading = ParagraphStyle(
        "Challenge heading",
        parent=body,
        fontSize=13,
        leading=18,
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True,
    )
    code = ParagraphStyle(
        "Challenge sample",
        parent=body,
        fontName=CODE_FONT,
        fontSize=9,
        leading=12,
        leftIndent=8,
        rightIndent=8,
        spaceAfter=10,
    )
    story = []
    rendered_lines = 0

    def paragraph(text, style=body):
        nonlocal rendered_lines
        text = printable(text, BODY_FONT)
        rendered_lines += len(text.split("\n")) + len(text) // 80
        if rendered_lines > MAX_RENDER_LINES:
            raise PackageError("package_size")
        story.append(Paragraph(escape(text).replace("\n", "<br/>"), style))

    def sample(text):
        nonlocal rendered_lines
        text = printable(text, CODE_FONT)
        lines = []
        for line in text.split("\n"):
            lines.extend(
                textwrap.wrap(
                    line,
                    width=84,
                    replace_whitespace=False,
                    drop_whitespace=False,
                    break_on_hyphens=False,
                )
                or [""]
            )
        rendered_lines += len(lines)
        if rendered_lines > MAX_RENDER_LINES:
            raise PackageError("package_size")
        story.append(Preformatted("\n".join(lines) if text else "(empty file)", code))

    paragraph(manifest.title, title)
    paragraph(f"Task: {manifest.task_id} | Python | File-based input/output")
    paragraph(
        "Teacher-approved materials. Status: unverified; correctness requires independent review."
    )
    paragraph("Problem statement", heading)
    # Separate source paragraphs so large statements can split across pages.
    for block in problem.statement.split("\n\n"):
        paragraph(block)
    paragraph("File I/O and resource constraints", heading)
    paragraph(
        f"Read {manifest.input_filename}; write {manifest.output_filename}. "
        f"Submit {manifest.entry_file}.\n"
        f"Wall time: {manifest.limits.time_seconds:g} seconds per test. "
        f"Memory: {manifest.limits.memory_mb} MiB. "
        f"Maximum output: {manifest.limits.output_bytes} bytes.\n"
        f"Output comparison: {manifest.comparison}. Input constraints are given in the statement."
    )
    paragraph("Public examples", heading)
    for index, example in enumerate(problem.examples, 1):
        paragraph(f"Example {index} — input", heading)
        sample(example.input)
        paragraph(f"Example {index} — output", heading)
        sample(example.output)
        if example.explanation:
            paragraph(example.explanation)
    paragraph(
        "Sample display wraps long lines and expands tabs for print. "
        "The .in/.out files contain the exact example bytes."
    )
    story.append(Spacer(1, 4))

    def footer(canvas, document):
        if document.page > MAX_PDF_PAGES:
            raise PageLimit("PDF page limit exceeded.")
        canvas.saveState()
        canvas.setFont(BODY_FONT, 8)
        canvas.setFillColor(colors.HexColor("#475569"))
        footer_id = manifest.task_id[:32] + ("..." if len(manifest.task_id) > 32 else "")
        canvas.drawString(44, 25, "ContestCheck AI | " + footer_id)
        canvas.drawRightString(A4[0] - 44, 25, f"Page {document.page}")
        canvas.restoreState()

    with PDFBuffer() as buffer:
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=44,
            rightMargin=44,
            topMargin=40,
            bottomMargin=42,
            title="Programming challenge",
            author="ContestCheck AI",
            invariant=1,
        )
        try:
            document.build(story, onFirstPage=footer, onLaterPages=footer)
        except PageLimit:
            raise PackageError("package_size") from None
        return buffer.getvalue()
