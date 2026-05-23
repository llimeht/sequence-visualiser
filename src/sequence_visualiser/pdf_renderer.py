"""
sequence_visualiser.pdf_renderer
===============================
Renders plan data to PDF using ReportLab. Handles layout, colours, and branding.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .models import Course, RenderContext, YearLayout

CODE_FONT = "Helvetica-Bold"
TEXT_FONT = "Helvetica"
COURSE_CODE_FONT = "Courier-Bold"
CODE_FONT_SIZE = 8
COURSE_CODE_CHARS = 8
COURSE_CODE_GAP = 4
TITLE_FONT_MAX = 8
TITLE_FONT_MIN = 5
LINE_HEIGHT = 11
TERM_PERIODS = ("Term 1", "Term 2", "Term 3")
SEMESTER_PERIODS = ("Semester 1", "Semester 2")
PERIOD_BOX_GAP = 6
PERIOD_LABEL_Y_OFFSET = 20
PERIOD_BOX_TOP_GAP = 6
PERIOD_BOX_BOTTOM_PADDING = 3
PERIOD_TEXT_TOP_PADDING = 10
PERIOD_TEXT_BOTTOM_PADDING = 4
HEADER_META_BOX_WIDTH = 280
HEADER_META_BOX_HEIGHT = 34
HEADER_META_BOX_TOP_PADDING = 6
HEADER_META_BOX_RIGHT_PADDING = 8
HEADER_META_BOX_LINE_GAP = 12
DEFAULT_YEAR_FILL = colors.white
DEFAULT_TERM_FILLS: dict[str, colors.Color] = {
    "Term 1": colors.HexColor("#f2f2f2"),
    "Term 2": colors.HexColor("#e8e8e8"),
    "Term 3": colors.HexColor("#dedede"),
}
DEFAULT_SEMESTER_FILLS: dict[str, colors.Color] = {
    "Semester 1": colors.HexColor("#ededed"),
    "Semester 2": colors.HexColor("#e2e2e2"),
}
DEFAULT_YEAR_FILLS: dict[str, colors.Color] = {
    "Year 1": colors.HexColor("#fafafa"),
    "Year 2": colors.HexColor("#f5f5f5"),
    "Year 3": colors.HexColor("#f0f0f0"),
    "Year 4": colors.HexColor("#ebebeb"),
    "Year 5": colors.HexColor("#e6e6e6"),
}


class PdfRenderError(ValueError):
    """Raised when a PDF cannot be rendered within the required constraints."""


def _display_course(course: Course) -> tuple[str, str]:
    """Return the course code and display title (with UoC suffix if needed)."""
    uoc_suffix = "" if course.uoc == 6 else f" ({course.uoc} UoC)"
    return course.code, f"{course.title}{uoc_suffix}"


def _course_code_field(code: str) -> str:
    """Pad the course code to a fixed width for display alignment."""
    return code.ljust(COURSE_CODE_CHARS)


def _fit_text_size(text: str, max_width: float, max_size: int = TITLE_FONT_MAX) -> int:
    """Find the largest font size that fits the text within max_width."""
    for size in range(max_size, TITLE_FONT_MIN - 1, -1):
        if pdfmetrics.stringWidth(text, TEXT_FONT, size) <= max_width:
            return size
    return TITLE_FONT_MIN


def _period_slots(year: YearLayout) -> list[tuple[str, list[Course]]]:
    """Return a list of (period label, courses) for the given year layout."""
    labels = TERM_PERIODS if year.calendar_type == "term" else SEMESTER_PERIODS
    period_lookup = {period.period: period.courses for period in year.periods}
    return [(label, period_lookup.get(label, [])) for label in labels]


def _colour_mapping(config: object, key: str) -> dict[str, Any]:
    """Extract a mapping for a given key from a config object, if present."""
    if not isinstance(config, Mapping):
        return {}
    typed_config = cast(Mapping[str, Any], config)
    mapping = typed_config.get(key)
    if isinstance(mapping, Mapping):
        typed_mapping = cast(Mapping[object, Any], mapping)
        return {str(map_key): map_value for map_key, map_value in typed_mapping.items()}
    return {}


def _to_color(value: object, fallback: colors.Color) -> colors.Color:
    """Convert a value to a ReportLab color, or return fallback if invalid."""
    if isinstance(value, str):
        try:
            return colors.HexColor(value)
        except ValueError:
            return fallback
    triple: tuple[object, object, object] | None = None
    if isinstance(value, tuple):
        tuple_value = cast(tuple[object, ...], value)
        if len(tuple_value) == 3:
            triple = (tuple_value[0], tuple_value[1], tuple_value[2])
    elif isinstance(value, list):
        list_value = cast(list[object], value)
        if len(list_value) == 3:
            triple = (list_value[0], list_value[1], list_value[2])

    if triple is not None:
        channels: list[float] = []
        try:
            for channel in triple:
                if not isinstance(channel, (int, float, str)):
                    return fallback
                channels.append(float(channel))
        except (TypeError, ValueError):
            return fallback
        if all(0 <= channel <= 1 for channel in channels):
            return colors.Color(channels[0], channels[1], channels[2])
        if all(0 <= channel <= 255 for channel in channels):
            return colors.Color(channels[0] / 255, channels[1] / 255, channels[2] / 255)
    return fallback


def _year_fill_color(colours_config: dict[str, Any], year_label: str) -> colors.Color:
    """Get the fill color for a year label from config, or use fallback."""
    year_overrides = _colour_mapping(colours_config, "years")
    fallback = DEFAULT_YEAR_FILLS.get(year_label, DEFAULT_YEAR_FILL)
    if year_label in year_overrides:
        return _to_color(year_overrides[year_label], fallback)

    match = re.search(r"(\d+)", year_label)
    if not match:
        return fallback
    year_number = match.group(1)
    if year_number in year_overrides:
        return _to_color(year_overrides[year_number], fallback)
    return fallback


def _period_fill_color(
    colours_config: dict[str, Any], calendar_type: str, period_label: str
) -> colors.Color:
    """Get the fill color for a period label from config, or use fallback."""
    if calendar_type == "term":
        term_overrides = _colour_mapping(colours_config, "terms")
        return _to_color(
            term_overrides.get(
                period_label, DEFAULT_TERM_FILLS.get(period_label, colors.white)
            ),
            DEFAULT_TERM_FILLS.get(period_label, colors.white),
        )

    semester_overrides = _colour_mapping(colours_config, "semesters")
    return _to_color(
        semester_overrides.get(
            period_label, DEFAULT_SEMESTER_FILLS.get(period_label, colors.white)
        ),
        DEFAULT_SEMESTER_FILLS.get(period_label, colors.white),
    )


def build_pdf_metadata(context: RenderContext, university_name: str) -> dict[str, str]:
    """Build PDF metadata fields for the document from context and branding."""
    stream_names = context.rule_metadata.specialisation_names
    degree_and_streams = context.rule_metadata.program_name
    if stream_names:
        degree_and_streams = f"{degree_and_streams} - {', '.join(stream_names)}"

    plan = context.plan_code
    intake = context.plan.intake
    source_filename = context.plan.source_path.name
    rules_filename = context.rule_metadata.rule_file.name

    return {
        "title": f"Enrolment Sequence for {plan} - {intake} - {university_name}",
        "subject": (
            f"Enrolment Sequence for {plan} - {degree_and_streams}"
            f" - {intake} - {university_name}"
        ),
        "author": f"{university_name} / {source_filename} / {rules_filename}",
        "creator": f"{university_name} / sequence-visualiser",
    }


def render_pdf(context: RenderContext, output_path: Path, templates_dir: Path) -> None:
    """Render the plan context to a PDF file using ReportLab.

    Args:
        context: RenderContext containing plan and rendering data.
        output_path: Path to write the rendered PDF file.
        templates_dir: Directory containing templates (for future use).
    """
    page_width, page_height = landscape(A4)
    c = canvas.Canvas(str(output_path), pagesize=(page_width, page_height))

    margin = 20
    top = page_height - margin

    branding = _colour_mapping(context.tweaks, "branding")
    pdf_tweaks = _colour_mapping(context.tweaks, "pdf")
    colours_tweaks = _colour_mapping(pdf_tweaks, "colours")
    university_name = str(branding.get("university_name", ""))
    if not university_name:
        university_name = "University"

    metadata = build_pdf_metadata(context, university_name)
    c.setTitle(metadata["title"])
    c.setSubject(metadata["subject"])
    c.setAuthor(metadata["author"])
    c.setCreator(metadata["creator"])

    logo_path = str(branding.get("logo_path", "")).strip()

    if logo_path:
        logo = Path(logo_path)
        if not logo.is_absolute():
            # Only use 'assets' (in overrides or templates)
            candidate = templates_dir / "assets" / logo
            if not candidate.exists():
                # Try parallel template-overrides/assets
                overrides_candidate = (
                    templates_dir.parent / "template-overrides" / "assets" / logo
                )
                if overrides_candidate.exists():
                    candidate = overrides_candidate
            if candidate.exists():
                logo = candidate
        if logo.exists():
            canvas_any = cast(Any, c)
            canvas_any.drawImage(
                str(logo),
                margin,
                top - 22,
                width=24,
                height=24,
                preserveAspectRatio=True,
            )

    title_x = margin + 30
    c.setFont(CODE_FONT, 12)
    c.drawString(title_x, top - 6, university_name)
    c.setFont(TEXT_FONT, 10)
    c.drawString(title_x, top - 22, f"{context.plan_code} - {context.plan.intake}")

    majors_text = (
        ", ".join(context.rule_metadata.specialisation_names)
        if context.rule_metadata.specialisation_names
        else "None"
    )

    meta_right_x = page_width - margin - HEADER_META_BOX_RIGHT_PADDING
    program_line = f"Program: {context.rule_metadata.program_name}"
    majors_line = f"Majors: {majors_text}"

    meta_inner_width = HEADER_META_BOX_WIDTH - (2 * HEADER_META_BOX_RIGHT_PADDING)
    program_size = _fit_text_size(program_line, meta_inner_width, max_size=9)
    majors_size = _fit_text_size(majors_line, meta_inner_width, max_size=9)

    c.setFont(TEXT_FONT, program_size)
    c.drawRightString(
        meta_right_x,
        top - HEADER_META_BOX_TOP_PADDING,
        program_line,
    )
    c.setFont(TEXT_FONT, majors_size)
    c.drawRightString(
        meta_right_x,
        top - HEADER_META_BOX_TOP_PADDING - HEADER_META_BOX_LINE_GAP,
        majors_line,
    )

    available_top = top - 46
    available_bottom = margin
    available_height = available_top - available_bottom

    if not context.years:
        raise PdfRenderError("No year data to render")

    row_height = available_height / len(context.years)

    for index, year in enumerate(context.years):
        y_top = available_top - (index * row_height)
        y_bottom = y_top - row_height + 5

        c.setStrokeColor(colors.black)
        c.setLineWidth(0.8)
        c.setFillColor(_year_fill_color(colours_tweaks, year.enrol_year))
        c.rect(margin, y_bottom, page_width - (2 * margin), row_height - 5, fill=1)
        c.setFillColor(colors.black)

        c.setFont(CODE_FONT, 9)
        c.drawString(margin + 4, y_top - 12, f"{year.enrol_year} ({year.year})")

        period_label_y = y_top - PERIOD_LABEL_Y_OFFSET
        period_box_top = period_label_y - PERIOD_BOX_TOP_GAP
        period_box_bottom = y_bottom + PERIOD_BOX_BOTTOM_PADDING
        period_height = period_box_top - period_box_bottom
        if period_height <= 0:
            continue
        slots = _period_slots(year)
        slot_count = len(slots)
        box_gap = PERIOD_BOX_GAP
        total_gap = box_gap * (slot_count + 1)
        period_width = ((page_width - (2 * margin)) - total_gap) / slot_count

        for p_index, (period_label, courses) in enumerate(slots):
            x = margin + box_gap + (p_index * (period_width + box_gap))
            if not courses:
                continue
            c.setLineWidth(0.4)
            c.setFillColor(
                _period_fill_color(colours_tweaks, year.calendar_type, period_label)
            )
            c.rect(x, period_box_bottom, period_width, period_height, fill=1)
            c.setFillColor(colors.black)
            c.setFont(CODE_FONT, 8)
            c.drawString(x + 3, period_label_y, period_label)

            text_y = period_box_top - PERIOD_TEXT_TOP_PADDING
            for course in courses:
                code, title = _display_course(course)
                code_field = _course_code_field(code)
                c.setFont(COURSE_CODE_FONT, CODE_FONT_SIZE)
                c.drawString(x + 3, text_y, code_field)

                code_width = pdfmetrics.stringWidth(
                    " " * COURSE_CODE_CHARS, COURSE_CODE_FONT, CODE_FONT_SIZE
                )
                title_x = x + 3 + code_width + COURSE_CODE_GAP
                max_title_width = (x + period_width - 3) - title_x
                if max_title_width <= 5:
                    continue
                title_size = _fit_text_size(title, max_title_width)
                c.setFont(TEXT_FONT, title_size)
                c.drawString(title_x, text_y, title)
                text_y -= LINE_HEIGHT
                if text_y < (period_box_bottom + PERIOD_TEXT_BOTTOM_PADDING):
                    break

    c.showPage()
    c.save()
