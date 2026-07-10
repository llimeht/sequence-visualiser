"""
sequence_visualiser.pdf_renderer
===============================
Renders plan data to PDF using ReportLab. Handles layout, colours, and branding.
"""

from __future__ import annotations

import logging
import re
from importlib import import_module
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from jinja2 import Environment
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, TTFError
from reportlab.pdfgen import canvas

from .models import Course, RenderContext, YearLayout
from .render_tokens import runtime_token_values

logger = logging.getLogger(__name__)

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
DEFAULT_PERIOD_LABEL_Y_OFFSET_PT = float(PERIOD_LABEL_Y_OFFSET)
HEADER_META_BOX_WIDTH = 280
HEADER_META_BOX_HEIGHT = 34
HEADER_META_BOX_TOP_PADDING = 6
HEADER_META_BOX_RIGHT_PADDING = 8
HEADER_META_BOX_LINE_GAP = 12
TOP_DISCLAIMER_FONT_SIZE = 8
TOP_DISCLAIMER_LINE_HEIGHT = 10
TOP_DISCLAIMER_BOTTOM_GAP = 6
FOOTER_FONT_SIZE = 8
FOOTER_LINE_HEIGHT = 10
FOOTER_TOP_GAP = 4
DEFAULT_LOGO_WIDTH_PT = 24.0
DEFAULT_LOGO_HEIGHT_PT = 24.0
DEFAULT_LOGO_RIGHT_SPACING_PT = 6.0
DEFAULT_HEADER_RIGHT_WIDTH_PT = float(HEADER_META_BOX_WIDTH)
DEFAULT_HEADER_LEFT_MIN_WIDTH_PT = 80.0
DEFAULT_HEADER_LINE_GAP_PT = float(HEADER_META_BOX_LINE_GAP)
DEFAULT_HEADER_HEIGHT_PT = 66.0
DEFAULT_HEADER_BOTTOM_SPACING_PT = 0.0
DEFAULT_HEADER_PRIMARY_FONT_SIZE = 12
DEFAULT_HEADER_SECONDARY_FONT_SIZE = 10
DEFAULT_HEADER_RIGHT_FONT_SIZE = 9
DEFAULT_HEADER_LEFT_LINES = [
    "{{ tokens.university_name }}",
    "{{ tokens.plan_code }} - {{ tokens.intake }}",
]
DEFAULT_HEADER_RIGHT_LINES = [
    "Program: {{ tokens.program_name }}",
    "Majors: {{ tokens.majors }}",
]
SECOND_PAGE_DEFAULT_INFO_FONT_SIZE = 10
SECOND_PAGE_DEFAULT_INFO_LINE_HEIGHT = 12
SECOND_PAGE_DEFAULT_DISCLAIMER_FONT_SIZE = 8
SECOND_PAGE_DEFAULT_DISCLAIMER_LINE_HEIGHT = 10
SECOND_PAGE_BOX_PADDING = 8
SECOND_PAGE_BOX_GAP = 10
SECOND_PAGE_DISCLAIMER_GAP = 8
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
    tokens = runtime_token_values(context, university_name)
    information_date = tokens["date"]
    copyright_year = tokens["year"]

    return {
        "title": f"Enrolment Sequence for {plan} - {intake} - {university_name}",
        "subject": (
            f"Enrolment Sequence for {plan} - {degree_and_streams}"
            f" - {intake} - {university_name}"
        ),
        "author": (
            f"{university_name} / {source_filename} / {rules_filename}"
            f" / Information correct as at {information_date}"
        ),
        "creator": (
            f"Copyright © {copyright_year} {university_name} / sequence-visualiser"
        ),
    }


def _text_lines(value: object) -> list[str]:
    """Normalise config text into non-empty lines.

    Supported forms:
    - string (split by lines)
    - list/tuple (each item converted to string)
    """
    if isinstance(value, str):
        return [line.strip() for line in value.splitlines() if line.strip()]
    if isinstance(value, (list, tuple)):
        lines: list[str] = []
        for item in value:
            line = str(item).strip()
            if line:
                lines.append(line)
        return lines
    return []


def _resolve_asset_path(asset_path: str, templates_dir: Path) -> Path | None:
    """Resolve an asset path against templates assets and local override assets."""
    candidate = Path(asset_path)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    templates_candidate = templates_dir / "assets" / candidate
    if templates_candidate.exists():
        return templates_candidate

    overrides_candidate = templates_dir.parent / "template-overrides" / "assets" / candidate
    if overrides_candidate.exists():
        return overrides_candidate

    return candidate if candidate.exists() else None


def _resolve_logo_path(branding: dict[str, Any], templates_dir: Path) -> Path | None:
    """Resolve the best logo path for PDF output.

    Preference order for PDF rendering:
    1. branding.logo_path_pdf
    2. branding.logo_path
    """
    logo_path_pdf = str(branding.get("logo_path_pdf", "")).strip()
    logo_path = str(branding.get("logo_path", "")).strip()
    selected_logo = logo_path_pdf or logo_path
    if not selected_logo:
        return None

    return _resolve_asset_path(selected_logo, templates_dir)


def _register_font_file(font_path: Path, alias: str) -> str | None:
    """Register a font file under an alias, returning alias on success."""
    try:
        pdfmetrics.getFont(alias)
        return alias
    except KeyError:
        pass

    try:
        pdfmetrics.registerFont(TTFont(alias, str(font_path)))
        return alias
    except (TTFError, ValueError, OSError, TypeError):
        return None


def _configured_font(
    role_config: dict[str, Any],
    style: str,
    fallback_name: str,
    templates_dir: Path,
    role_name: str,
) -> str:
    """Resolve and register a configured font file, or fallback to built-in font."""
    configured = str(role_config.get(style, "")).strip()
    if not configured:
        return fallback_name

    font_path = _resolve_asset_path(configured, templates_dir)
    if font_path is None:
        logger.warning(
            "Configured PDF font not found for %s.%s: %s (using fallback %s)",
            role_name,
            style,
            configured,
            fallback_name,
        )
        return fallback_name

    alias = f"sv_{role_name}_{style}_{abs(hash(str(font_path.resolve())))}"
    registered = _register_font_file(font_path, alias)
    if registered is None:
        logger.warning(
            "Configured PDF font failed to register for %s.%s: %s (using fallback %s)",
            role_name,
            style,
            str(font_path),
            fallback_name,
        )
        return fallback_name
    return registered


def _configured_font_size(
    role_config: dict[str, Any], key: str, fallback: int
) -> int:
    """Read a positive integral font size from role config."""
    configured = _float_config(role_config.get(key))
    if configured is None:
        return fallback
    return max(1, int(round(configured)))


def _font_roles(pdf_tweaks: dict[str, Any], templates_dir: Path) -> dict[str, Any]:
    """Build resolved font families and size settings for PDF rendering."""
    fonts_config = _colour_mapping(pdf_tweaks, "fonts")
    header_config = _colour_mapping(fonts_config, "header")
    course_codes_config = _colour_mapping(fonts_config, "course_codes")
    footer_config = _colour_mapping(fonts_config, "footer")
    body_config = _colour_mapping(fonts_config, "body")

    body_regular = _configured_font(
        body_config,
        "regular",
        TEXT_FONT,
        templates_dir,
        "body",
    )
    body_bold = _configured_font(
        body_config,
        "bold",
        CODE_FONT,
        templates_dir,
        "body",
    )
    body_italic = _configured_font(
        body_config,
        "italic",
        body_regular,
        templates_dir,
        "body",
    )
    body_bold_italic = _configured_font(
        body_config,
        "bold_italic",
        body_bold,
        templates_dir,
        "body",
    )

    header_regular = _configured_font(
        header_config,
        "regular",
        body_regular,
        templates_dir,
        "header",
    )
    header_bold = _configured_font(
        header_config,
        "bold",
        header_regular,
        templates_dir,
        "header",
    )

    course_codes_regular = _configured_font(
        course_codes_config,
        "regular",
        COURSE_CODE_FONT,
        templates_dir,
        "course_codes",
    )
    course_codes_bold = _configured_font(
        course_codes_config,
        "bold",
        course_codes_regular,
        templates_dir,
        "course_codes",
    )
    course_codes_italic = _configured_font(
        course_codes_config,
        "italic",
        course_codes_regular,
        templates_dir,
        "course_codes",
    )
    course_codes_bold_italic = _configured_font(
        course_codes_config,
        "bold_italic",
        course_codes_bold,
        templates_dir,
        "course_codes",
    )

    footer_regular = _configured_font(
        footer_config,
        "regular",
        body_regular,
        templates_dir,
        "footer",
    )
    footer_bold = _configured_font(
        footer_config,
        "bold",
        body_bold,
        templates_dir,
        "footer",
    )
    footer_italic = _configured_font(
        footer_config,
        "italic",
        footer_regular,
        templates_dir,
        "footer",
    )
    footer_bold_italic = _configured_font(
        footer_config,
        "bold_italic",
        footer_bold,
        templates_dir,
        "footer",
    )

    header_primary_size = _configured_font_size(
        header_config, "size", DEFAULT_HEADER_PRIMARY_FONT_SIZE
    )
    header_secondary_size = _configured_font_size(
        header_config,
        "secondary_size",
        DEFAULT_HEADER_SECONDARY_FONT_SIZE,
    )
    header_right_size = _configured_font_size(
        header_config,
        "right_size",
        DEFAULT_HEADER_RIGHT_FONT_SIZE,
    )

    return {
        "body_regular": body_regular,
        "body_bold": body_bold,
        "body_italic": body_italic,
        "body_bold_italic": body_bold_italic,
        "header_regular": header_regular,
        "header_bold": header_bold,
        "course_codes_regular": course_codes_regular,
        "course_codes_bold": course_codes_bold,
        "course_codes_italic": course_codes_italic,
        "course_codes_bold_italic": course_codes_bold_italic,
        "footer_regular": footer_regular,
        "footer_bold": footer_bold,
        "footer_italic": footer_italic,
        "footer_bold_italic": footer_bold_italic,
        "header_primary_size": header_primary_size,
        "header_secondary_size": header_secondary_size,
        "header_right_size": header_right_size,
    }


def _fit_text_size_for_font(
    text: str,
    max_width: float,
    font_name: str,
    max_size: int = TITLE_FONT_MAX,
) -> int:
    """Find the largest font size that fits text using a specific font face."""
    for size in range(max_size, TITLE_FONT_MIN - 1, -1):
        if pdfmetrics.stringWidth(text, font_name, size) <= max_width:
            return size
    return TITLE_FONT_MIN


def _float_config(value: object) -> float | None:
    """Return a positive float for numeric config values, otherwise None."""
    if isinstance(value, bool):
        return None
    if not isinstance(value, (int, float, str)):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if numeric > 0 else None


def _bool_config(value: object) -> bool:
    """Return a permissive boolean interpretation for config values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalised = value.strip().lower()
        if normalised in {"1", "true", "yes", "on"}:
            return True
        if normalised in {"0", "false", "no", "off", ""}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _pdf_template_context(
    context: RenderContext,
    university_name: str,
    tokens: Mapping[str, str],
) -> dict[str, Any]:
    """Build the Jinja context used for PDF text fields."""
    program_id = context.rule_metadata.program_id or context.degree_code
    return {
        "plan": context.plan,
        "rule": context.rule_metadata,
        "years": context.years,
        "tweaks": context.tweaks,
        "tokens": dict(tokens),
        "plan_code": context.plan_code,
        "program_id": program_id,
        "program_code": program_id,
        "specialisation_code": context.specialisation_code,
        "specialisation_codes": context.specialisation_codes,
        "degree_code": context.degree_code,
    }


def _render_pdf_template_text(
    value: object,
    template_env: Environment,
    template_context: Mapping[str, Any],
) -> str:
    """Render a config value using Jinja and return stripped text."""
    if isinstance(value, (list, tuple)):
        template_text = "\n".join(str(item) for item in value)
    else:
        template_text = str(value)
    if not template_text.strip():
        return ""
    try:
        rendered = template_env.from_string(template_text).render(**template_context)
    except Exception as exc:  # pragma: no cover - exact exception depends on Jinja internals.
        raise PdfRenderError(f"Invalid PDF text template: {exc}") from exc
    return str(rendered).strip()


def _render_pdf_template_lines(
    value: object,
    template_env: Environment,
    template_context: Mapping[str, Any],
) -> list[str]:
    """Render a config value using Jinja and split into non-empty lines."""
    rendered = _render_pdf_template_text(value, template_env, template_context)
    return [line.strip() for line in rendered.splitlines() if line.strip()]


def _pdf_logo_aspect_ratio(logo: Path) -> float:
    """Return width/height ratio of the first page of a PDF logo."""
    pdfrw = import_module("pdfrw")
    reader: Any = getattr(pdfrw, "PdfReader")

    pages = reader(str(logo)).pages
    if not pages:
        raise PdfRenderError(f"Logo PDF has no pages: {logo}")
    page = pages[0]
    media_box = cast(list[float], getattr(page, "MediaBox", []))
    if len(media_box) < 4:
        raise PdfRenderError(f"Logo PDF has invalid page bounds: {logo}")
    src_x0, src_y0, src_x1, src_y1 = (
        float(media_box[0]),
        float(media_box[1]),
        float(media_box[2]),
        float(media_box[3]),
    )
    src_width = src_x1 - src_x0
    src_height = src_y1 - src_y0
    if src_width <= 0 or src_height <= 0:
        raise PdfRenderError(f"Logo PDF has non-positive dimensions: {logo}")
    return src_width / src_height


def _image_logo_aspect_ratio(logo: Path) -> float:
    """Return width/height ratio for a raster logo."""
    image = ImageReader(str(logo))
    width, height = cast(tuple[float, float], image.getSize())
    if width <= 0 or height <= 0:
        raise PdfRenderError(f"Logo image has non-positive dimensions: {logo}")
    return width / height


def _logo_aspect_ratio(logo: Path) -> float:
    """Return width/height ratio for a logo asset."""
    if logo.suffix.lower() == ".pdf":
        return _pdf_logo_aspect_ratio(logo)
    return _image_logo_aspect_ratio(logo)


def _logo_layout(pdf_tweaks: dict[str, Any], logo: Path | None) -> tuple[float, float, float]:
    """Calculate logo width/height and right-side spacing in points.

    Width and height config values are in mm.
    If exactly one dimension is set and a logo exists, the other is scaled to preserve
    the logo aspect ratio.
    """
    logo_width_mm = _float_config(pdf_tweaks.get("logo_width_mm"))
    logo_height_mm = _float_config(pdf_tweaks.get("logo_height_mm"))
    logo_spacing_mm = _float_config(pdf_tweaks.get("logo_right_spacing_mm"))

    logo_width = logo_width_mm * mm if logo_width_mm is not None else None
    logo_height = logo_height_mm * mm if logo_height_mm is not None else None
    spacing = (
        logo_spacing_mm * mm
        if logo_spacing_mm is not None
        else DEFAULT_LOGO_RIGHT_SPACING_PT
    )

    if logo_width is None and logo_height is None:
        return DEFAULT_LOGO_WIDTH_PT, DEFAULT_LOGO_HEIGHT_PT, spacing

    if logo is None:
        return (
            logo_width if logo_width is not None else DEFAULT_LOGO_WIDTH_PT,
            logo_height if logo_height is not None else DEFAULT_LOGO_HEIGHT_PT,
            spacing,
        )

    if logo_width is not None and logo_height is not None:
        return logo_width, logo_height, spacing

    ratio = _logo_aspect_ratio(logo)
    if logo_width is not None:
        return logo_width, logo_width / ratio, spacing
    if logo_height is not None:
        return logo_height * ratio, logo_height, spacing

    return DEFAULT_LOGO_WIDTH_PT, DEFAULT_LOGO_HEIGHT_PT, spacing


def _header_layout(pdf_tweaks: dict[str, Any]) -> tuple[float, float, float]:
    """Calculate right header width, left minimum width (mm), and line gap (pt)."""
    header_right_width_mm = _float_config(pdf_tweaks.get("header_right_width_mm"))
    header_left_min_width_mm = _float_config(pdf_tweaks.get("header_left_min_width_mm"))
    header_line_gap_pt = _float_config(pdf_tweaks.get("header_line_gap_pt"))

    right_width = (
        header_right_width_mm * mm
        if header_right_width_mm is not None
        else DEFAULT_HEADER_RIGHT_WIDTH_PT
    )
    left_min_width = (
        header_left_min_width_mm * mm
        if header_left_min_width_mm is not None
        else DEFAULT_HEADER_LEFT_MIN_WIDTH_PT
    )
    line_gap = (
        header_line_gap_pt
        if header_line_gap_pt is not None
        else DEFAULT_HEADER_LINE_GAP_PT
    )
    return right_width, left_min_width, line_gap


def _period_layout(pdf_tweaks: dict[str, Any]) -> float:
    """Calculate period label vertical offset from the year heading in points."""
    configured = _float_config(pdf_tweaks.get("period_label_y_offset_pt"))
    if configured is None:
        return DEFAULT_PERIOD_LABEL_Y_OFFSET_PT
    return configured


def _header_background_layout(
    pdf_tweaks: dict[str, Any],
) -> tuple[colors.Color | None, float, float]:
    """Calculate optional header background color, height, and bottom spacing."""
    color_value = pdf_tweaks.get("header_background_color")
    header_height_mm = _float_config(pdf_tweaks.get("header_height_mm"))
    header_bottom_spacing_mm = _float_config(pdf_tweaks.get("header_bottom_spacing_mm"))
    header_height = (
        header_height_mm * mm
        if header_height_mm is not None
        else DEFAULT_HEADER_HEIGHT_PT
    )
    header_bottom_spacing = (
        header_bottom_spacing_mm * mm
        if header_bottom_spacing_mm is not None
        else DEFAULT_HEADER_BOTTOM_SPACING_PT
    )

    if color_value is None:
        return None, header_height, header_bottom_spacing

    return _to_color(color_value, colors.white), header_height, header_bottom_spacing


def _draw_pdf_logo(
    c: canvas.Canvas,
    logo: Path,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    """Draw the first page of a PDF logo as vector content into the target box."""
    pdfrw = import_module("pdfrw")
    reader: Any = getattr(pdfrw, "PdfReader")
    buildxobj: Any = import_module("pdfrw.buildxobj")
    toreportlab: Any = import_module("pdfrw.toreportlab")

    pages = reader(str(logo)).pages
    if not pages:
        raise PdfRenderError(f"Logo PDF has no pages: {logo}")

    page_xobj = buildxobj.pagexobj(pages[0])
    bbox = cast(list[float], page_xobj.BBox)
    if len(bbox) < 4:
        raise PdfRenderError(f"Logo PDF has invalid page bounds: {logo}")

    src_x0, src_y0, src_x1, src_y1 = bbox[0], bbox[1], bbox[2], bbox[3]
    src_width = src_x1 - src_x0
    src_height = src_y1 - src_y0
    if src_width <= 0 or src_height <= 0:
        raise PdfRenderError(f"Logo PDF has non-positive dimensions: {logo}")

    scale = min(width / src_width, height / src_height)
    draw_width = src_width * scale
    draw_height = src_height * scale
    draw_x = x + ((width - draw_width) / 2)
    draw_y = y + ((height - draw_height) / 2)

    c.saveState()
    c.translate(draw_x, draw_y)
    c.scale(scale, scale)
    c.translate(-src_x0, -src_y0)
    c.doForm(toreportlab.makerl(c, page_xobj))
    c.restoreState()


def _draw_page_header(
    c: canvas.Canvas,
    *,
    page_width: float,
    page_height: float,
    margin: float,
    top: float,
    fonts: Mapping[str, Any],
    logo: Path | None,
    logo_width: float,
    logo_height: float,
    logo_spacing: float,
    right_header_width: float,
    left_header_min_width: float,
    header_line_gap: float,
    header_background_color: colors.Color | None,
    header_height: float,
    left_header_lines: list[str],
    right_header_lines: list[str],
) -> None:
    """Draw the shared page header region, including logo and header text."""
    header_height = min(max(header_height, 1.0), page_height)
    header_bottom = page_height - header_height

    if header_background_color is not None:
        c.setFillColor(header_background_color)
        c.rect(0, header_bottom, page_width, header_height, stroke=0, fill=1)
        c.setFillColor(colors.black)

    if logo is not None:
        logo_y = top - logo_height + 2
        if logo.suffix.lower() == ".pdf":
            _draw_pdf_logo(c, logo, margin, logo_y, width=logo_width, height=logo_height)
        else:
            canvas_any = cast(Any, c)
            canvas_any.drawImage(
                str(logo),
                margin,
                logo_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
            )

    title_x = margin + logo_width + logo_spacing if logo is not None else margin
    meta_right_x = page_width - margin - HEADER_META_BOX_RIGHT_PADDING
    meta_inner_width = max(
        10.0,
        right_header_width - (2 * HEADER_META_BOX_RIGHT_PADDING),
    )
    left_max_width = max(
        left_header_min_width,
        (meta_right_x - meta_inner_width) - title_x - 8,
    )

    left_line_y = top - HEADER_META_BOX_TOP_PADDING
    for index, line in enumerate(left_header_lines):
        line_max_size = (
            fonts["header_primary_size"]
            if index == 0
            else fonts["header_secondary_size"]
        )
        line_font = fonts["header_bold"] if index == 0 else fonts["header_regular"]
        line_size = _fit_text_size_for_font(
            line,
            left_max_width,
            cast(str, line_font),
            max_size=cast(int, line_max_size),
        )
        c.setFont(cast(str, line_font), line_size)
        c.drawString(title_x, left_line_y - (index * header_line_gap), line)

    right_line_y = top - HEADER_META_BOX_TOP_PADDING
    for index, line in enumerate(right_header_lines):
        line_size = _fit_text_size_for_font(
            line,
            meta_inner_width,
            cast(str, fonts["header_regular"]),
            max_size=cast(int, fonts["header_right_size"]),
        )
        c.setFont(cast(str, fonts["header_regular"]), line_size)
        c.drawRightString(meta_right_x, right_line_y - (index * header_line_gap), line)


def _draw_footer(
    c: canvas.Canvas,
    *,
    page_width: float,
    margin: float,
    footer_left_lines: list[str],
    footer_right_lines: list[str],
    fonts: Mapping[str, Any],
) -> None:
    """Draw footer lines on the current page."""
    if not footer_left_lines and not footer_right_lines:
        return

    footer_line_count = max(len(footer_left_lines), len(footer_right_lines))
    c.setFont(cast(str, fonts["footer_regular"]), FOOTER_FONT_SIZE)
    baseline = margin + 2
    for i in range(footer_line_count):
        y = baseline + ((footer_line_count - 1 - i) * FOOTER_LINE_HEIGHT)
        if i < len(footer_left_lines):
            c.drawString(margin, y, footer_left_lines[i])
        if i < len(footer_right_lines):
            c.drawRightString(page_width - margin, y, footer_right_lines[i])


def _footer_block_height(footer_left_lines: list[str], footer_right_lines: list[str]) -> float:
    """Return reserved footer block height in points."""
    if not footer_left_lines and not footer_right_lines:
        return 0.0
    footer_line_count = max(len(footer_left_lines), len(footer_right_lines))
    return (footer_line_count * FOOTER_LINE_HEIGHT) + FOOTER_TOP_GAP


def _wrapped_lines_preserving_blank_lines(
    text: str,
    *,
    font_name: str,
    font_size: int,
    max_width: float,
) -> list[str]:
    """Wrap text while preserving explicit blank lines from newline-separated paragraphs."""
    if not text:
        return []

    wrapped: list[str] = []
    for raw_line in text.splitlines():
        if not raw_line.strip():
            wrapped.append("")
            continue
        wrapped.extend(
            simpleSplit(  # type: ignore[no-untyped-call]
                raw_line,
                font_name,
                font_size,
                max_width,
            )
        )
    return wrapped


def _draw_second_page_content(
    c: canvas.Canvas,
    *,
    page_width: float,
    margin: float,
    available_top: float,
    available_bottom: float,
    fonts: Mapping[str, Any],
    second_page: Mapping[str, Any],
    template_env: Environment,
    template_context: Mapping[str, Any],
) -> None:
    """Draw second page info and disclaimer boxes within the content area."""
    content_width = page_width - (2 * margin)
    content_height = available_top - available_bottom
    if content_height <= 0:
        return

    info_title = _render_pdf_template_text(
        second_page.get("info_box_title", ""), template_env, template_context
    )
    info_text = _render_pdf_template_text(
        second_page.get("info_box_text", ""), template_env, template_context
    )
    bottom_disclaimer_text = _render_pdf_template_text(
        second_page.get("bottom_disclaimer", ""), template_env, template_context
    )

    info_font_size = _configured_font_size(
        cast(dict[str, Any], second_page),
        "info_font_size_pt",
        SECOND_PAGE_DEFAULT_INFO_FONT_SIZE,
    )
    disclaimer_font_size = _configured_font_size(
        cast(dict[str, Any], second_page),
        "disclaimer_font_size_pt",
        SECOND_PAGE_DEFAULT_DISCLAIMER_FONT_SIZE,
    )
    info_line_height = _configured_font_size(
        cast(dict[str, Any], second_page),
        "info_line_height_pt",
        SECOND_PAGE_DEFAULT_INFO_LINE_HEIGHT,
    )
    disclaimer_line_height = _configured_font_size(
        cast(dict[str, Any], second_page),
        "disclaimer_line_height_pt",
        SECOND_PAGE_DEFAULT_DISCLAIMER_LINE_HEIGHT,
    )

    disclaimer_lines = _wrapped_lines_preserving_blank_lines(
        bottom_disclaimer_text,
        font_name=cast(str, fonts["body_regular"]),
        font_size=disclaimer_font_size,
        max_width=content_width - (2 * SECOND_PAGE_BOX_PADDING),
    )
    disclaimer_box_height = (
        (2 * SECOND_PAGE_BOX_PADDING)
        + (len(disclaimer_lines) * disclaimer_line_height)
        if disclaimer_lines
        else 0
    )

    disclaimer_bottom = available_bottom
    disclaimer_top = disclaimer_bottom + disclaimer_box_height

    info_box_bottom = (
        disclaimer_top + SECOND_PAGE_DISCLAIMER_GAP if disclaimer_box_height > 0 else available_bottom
    )
    info_box_top = available_top
    info_box_height = max(0.0, info_box_top - info_box_bottom)

    if info_box_height > 0 and (info_title or info_text):
        c.setLineWidth(0.8)
        c.setStrokeColor(colors.black)
        c.rect(margin, info_box_bottom, content_width, info_box_height, stroke=1, fill=0)

        text_y = info_box_top - SECOND_PAGE_BOX_PADDING
        text_left = margin + SECOND_PAGE_BOX_PADDING
        text_width = content_width - (2 * SECOND_PAGE_BOX_PADDING)

        if info_title:
            c.setFont(cast(str, fonts["body_bold"]), info_font_size)
            c.drawString(text_left, text_y - info_font_size, info_title)
            text_y -= info_line_height

        info_lines = _wrapped_lines_preserving_blank_lines(
            info_text,
            font_name=cast(str, fonts["body_regular"]),
            font_size=info_font_size,
            max_width=text_width,
        )
        c.setFont(cast(str, fonts["body_regular"]), info_font_size)
        for line in info_lines:
            if text_y - info_font_size < (info_box_bottom + SECOND_PAGE_BOX_PADDING):
                break
            if line:
                c.drawString(text_left, text_y - info_font_size, line)
            text_y -= info_line_height

    if disclaimer_box_height > 0:
        c.setLineWidth(0.8)
        c.setStrokeColor(colors.black)
        c.rect(
            margin,
            disclaimer_bottom,
            content_width,
            disclaimer_box_height,
            stroke=1,
            fill=0,
        )
        c.setFont(cast(str, fonts["body_regular"]), disclaimer_font_size)
        text_y = disclaimer_top - SECOND_PAGE_BOX_PADDING
        text_left = margin + SECOND_PAGE_BOX_PADDING
        for line in disclaimer_lines:
            if line:
                c.drawString(text_left, text_y - disclaimer_font_size, line)
            text_y -= disclaimer_line_height


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
    fonts = _font_roles(pdf_tweaks, templates_dir)
    university_name = str(branding.get("university_name", ""))
    if not university_name:
        university_name = "University"
    tokens = runtime_token_values(context, university_name)
    template_env = Environment(autoescape=False)
    template_context = _pdf_template_context(context, university_name, tokens)

    metadata = build_pdf_metadata(context, university_name)
    c.setTitle(metadata["title"])
    c.setSubject(metadata["subject"])
    c.setAuthor(metadata["author"])
    c.setCreator(metadata["creator"])

    logo = _resolve_logo_path(branding, templates_dir)
    logo_width, logo_height, logo_spacing = _logo_layout(pdf_tweaks, logo)
    right_header_width, left_header_min_width, header_line_gap = _header_layout(
        pdf_tweaks
    )
    period_label_y_offset = _period_layout(pdf_tweaks)
    header_background_color, header_height, header_bottom_spacing = _header_background_layout(
        pdf_tweaks
    )
    left_header_lines = _render_pdf_template_lines(
        pdf_tweaks.get("header_left_lines", list(DEFAULT_HEADER_LEFT_LINES)),
        template_env,
        template_context,
    )
    if not left_header_lines:
        left_header_lines = _render_pdf_template_lines(
            list(DEFAULT_HEADER_LEFT_LINES), template_env, template_context
        )
    right_header_lines = _render_pdf_template_lines(
        pdf_tweaks.get("header_right_lines", list(DEFAULT_HEADER_RIGHT_LINES)),
        template_env,
        template_context,
    )
    if not right_header_lines:
        right_header_lines = _render_pdf_template_lines(
            list(DEFAULT_HEADER_RIGHT_LINES), template_env, template_context
        )

    _draw_page_header(
        c,
        page_width=page_width,
        page_height=page_height,
        margin=margin,
        top=top,
        fonts=fonts,
        logo=logo,
        logo_width=logo_width,
        logo_height=logo_height,
        logo_spacing=logo_spacing,
        right_header_width=right_header_width,
        left_header_min_width=left_header_min_width,
        header_line_gap=header_line_gap,
        header_background_color=header_background_color,
        header_height=header_height,
        left_header_lines=left_header_lines,
        right_header_lines=right_header_lines,
    )

    content_width = page_width - (2 * margin)
    top_disclaimer = _render_pdf_template_text(
        pdf_tweaks.get("top_disclaimer", ""), template_env, template_context
    )
    top_disclaimer_lines = (
        simpleSplit(  # type: ignore[no-untyped-call]
            top_disclaimer,
            cast(str, fonts["body_regular"]),
            TOP_DISCLAIMER_FONT_SIZE,
            content_width,
        )
        if top_disclaimer
        else []
    )

    footer_left_lines = _render_pdf_template_lines(
        pdf_tweaks.get(
            "footer_left",
            "Check the Handbook and Class Timetable for details.",
        ),
        template_env,
        template_context,
    )
    footer_right_lines = _render_pdf_template_lines(
        pdf_tweaks.get(
            "footer_right",
            "Information correct as at {{ tokens.date }}\\nCopyright © {{ tokens.year }} {{ tokens.university_name }}",
        ),
        template_env,
        template_context,
    )

    footer_block_height = _footer_block_height(footer_left_lines, footer_right_lines)

    header_height = min(max(header_height, 1.0), page_height)
    header_bottom = page_height - header_height
    available_top = max(margin, header_bottom - header_bottom_spacing)
    if top_disclaimer_lines:
        c.setFont(cast(str, fonts["body_regular"]), TOP_DISCLAIMER_FONT_SIZE)
        disclaimer_y = available_top - TOP_DISCLAIMER_FONT_SIZE
        for line in top_disclaimer_lines:
            c.drawString(margin, disclaimer_y, line)
            disclaimer_y -= TOP_DISCLAIMER_LINE_HEIGHT
        available_top -= (
            (len(top_disclaimer_lines) * TOP_DISCLAIMER_LINE_HEIGHT)
            + TOP_DISCLAIMER_BOTTOM_GAP
        )

    available_bottom = margin + footer_block_height
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

        c.setFont(cast(str, fonts["body_bold"]), 9)
        c.drawString(margin + 4, y_top - 12, f"{year.enrol_year} ({year.year})")

        period_label_y = y_top - period_label_y_offset
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
            c.setFont(cast(str, fonts["body_bold"]), 8)
            c.drawString(x + 3, period_label_y, period_label)

            text_y = period_box_top - PERIOD_TEXT_TOP_PADDING
            for course in courses:
                code, title = _display_course(course)
                code_field = _course_code_field(code)
                c.setFont(cast(str, fonts["course_codes_regular"]), CODE_FONT_SIZE)
                c.drawString(x + 3, text_y, code_field)

                code_width = pdfmetrics.stringWidth(
                    " " * COURSE_CODE_CHARS,
                    cast(str, fonts["course_codes_regular"]),
                    CODE_FONT_SIZE,
                )
                title_x = x + 3 + code_width + COURSE_CODE_GAP
                max_title_width = (x + period_width - 3) - title_x
                if max_title_width <= 5:
                    continue
                title_size = _fit_text_size_for_font(
                    title,
                    max_title_width,
                    cast(str, fonts["body_regular"]),
                )
                c.setFont(cast(str, fonts["body_regular"]), title_size)
                c.drawString(title_x, text_y, title)
                text_y -= LINE_HEIGHT
                if text_y < (period_box_bottom + PERIOD_TEXT_BOTTOM_PADDING):
                    break

    _draw_footer(
        c,
        page_width=page_width,
        margin=margin,
        footer_left_lines=footer_left_lines,
        footer_right_lines=footer_right_lines,
        fonts=fonts,
    )

    second_page = _colour_mapping(pdf_tweaks, "second_page")
    if _bool_config(second_page.get("enabled", False)):
        c.showPage()

        _draw_page_header(
            c,
            page_width=page_width,
            page_height=page_height,
            margin=margin,
            top=top,
            fonts=fonts,
            logo=logo,
            logo_width=logo_width,
            logo_height=logo_height,
            logo_spacing=logo_spacing,
            right_header_width=right_header_width,
            left_header_min_width=left_header_min_width,
            header_line_gap=header_line_gap,
            header_background_color=header_background_color,
            header_height=header_height,
            left_header_lines=left_header_lines,
            right_header_lines=right_header_lines,
        )

        second_page_top_disclaimer_lines = (
            simpleSplit(  # type: ignore[no-untyped-call]
                top_disclaimer,
                cast(str, fonts["body_regular"]),
                TOP_DISCLAIMER_FONT_SIZE,
                content_width,
            )
            if top_disclaimer
            else []
        )

        second_available_top = max(margin, header_bottom - header_bottom_spacing)
        if second_page_top_disclaimer_lines:
            c.setFont(cast(str, fonts["body_regular"]), TOP_DISCLAIMER_FONT_SIZE)
            disclaimer_y = second_available_top - TOP_DISCLAIMER_FONT_SIZE
            for line in second_page_top_disclaimer_lines:
                c.drawString(margin, disclaimer_y, line)
                disclaimer_y -= TOP_DISCLAIMER_LINE_HEIGHT
            second_available_top -= (
                (len(second_page_top_disclaimer_lines) * TOP_DISCLAIMER_LINE_HEIGHT)
                + TOP_DISCLAIMER_BOTTOM_GAP
            )

        second_footer_left_lines = _render_pdf_template_lines(
            second_page.get("footer_left", "\n".join(footer_left_lines)),
            template_env,
            template_context,
        )
        second_footer_right_lines = _render_pdf_template_lines(
            second_page.get("footer_right", "\n".join(footer_right_lines)),
            template_env,
            template_context,
        )
        second_available_bottom = margin + _footer_block_height(
            second_footer_left_lines, second_footer_right_lines
        )

        _draw_second_page_content(
            c,
            page_width=page_width,
            margin=margin,
            available_top=second_available_top,
            available_bottom=second_available_bottom,
            fonts=fonts,
            second_page=second_page,
            template_env=template_env,
            template_context=template_context,
        )

        _draw_footer(
            c,
            page_width=page_width,
            margin=margin,
            footer_left_lines=second_footer_left_lines,
            footer_right_lines=second_footer_right_lines,
            fonts=fonts,
        )

    c.showPage()
    c.save()
