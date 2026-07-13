"""Renders plan data to HTML using Jinja2 templates. Supports template overrides."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .models import RenderContext
from .render_tokens import expand_runtime_tokens, runtime_token_values
from .text_markup import parse_inline_bold_with_warnings

logger = logging.getLogger(__name__)


def _build_html_metadata(context: RenderContext, university_name: str) -> dict[str, str]:
    """Build HTML metadata values."""
    stream_names = context.rule_metadata.specialisation_names
    degree_and_streams = context.rule_metadata.program_name
    if stream_names:
        degree_and_streams = f"{degree_and_streams} - {', '.join(stream_names)}"

    tokens = runtime_token_values(context, university_name)
    information_date = tokens["date"]
    copyright_year = tokens["year"]

    source_filename = context.plan.source_path.name
    rules_filename = context.rule_metadata.rule_file.name

    return {
        "title": f"Enrolment Sequence for {context.plan_code} - {context.plan.intake} - {university_name}",
        "subject": (
            f"Enrolment Sequence for {context.plan_code} - {degree_and_streams}"
            f" - {context.plan.intake} - {university_name}"
        ),
        "author": (
            f"{university_name} / {source_filename} / {rules_filename}"
            f" / Information correct as at {information_date}"
        ),
        "creator": f"Copyright © {copyright_year} {university_name} / sequence-visualiser",
    }


def _render_long_form_html(text: str, *, field_name: str) -> Markup:
    """Render safe long-form HTML text with inline <b>...</b> support."""
    parsed = parse_inline_bold_with_warnings(text)
    for warning in parsed.warnings:
        logger.warning("HTML long-form markup warning in %s: %s", field_name, warning)

    output: list[str] = []
    for run in parsed.runs:
        escaped = Markup.escape(run.text)
        if run.bold:
            output.append(f"<strong>{escaped}</strong>")
        else:
            output.append(str(escaped))
    return Markup("".join(output))


def render_html(context: RenderContext, templates_dir: Path, output_path: Path) -> None:
    """Render the plan context to an HTML file using Jinja2 templates.

    Args:
        context: RenderContext containing plan and rendering data.
        templates_dir: Directory containing Jinja2 templates.
        output_path: Path to write the rendered HTML file.
    """
    # Support parallel template search paths: template-overrides (never in git), then templates (default)
    overrides_dir = templates_dir.parent / "template-overrides"
    env = Environment(
        loader=FileSystemLoader([str(overrides_dir), str(templates_dir)]),
        autoescape=select_autoescape(enabled_extensions=(".html",)),
    )
    template = env.get_template("sequence.html.j2")

    branding = context.tweaks.get("branding", {})
    branding_mapping = cast(dict[str, object], branding) if isinstance(branding, dict) else {}
    university_name = str(branding_mapping.get("university_name", "")).strip() or "University"
    tokens = runtime_token_values(context, university_name)
    html_metadata = _build_html_metadata(context, university_name)
    html_tweaks = context.tweaks.get("html", {})
    html_mapping = cast(dict[str, object], html_tweaks) if isinstance(html_tweaks, dict) else {}
    top_disclaimer = expand_runtime_tokens(
        str(html_mapping.get("top_disclaimer", "")), context, university_name
    )
    footer = expand_runtime_tokens(
        str(html_mapping.get("footer", "")), context, university_name
    )

    css_variables: dict[str, str] = {
        "period-term-1": "#f2f2f2",
        "period-term-2": "#e8e8e8",
        "period-term-3": "#dedede",
        "period-semester-1": "#ededed",
        "period-semester-2": "#e2e2e2",
        "period-summer-term": "#fff5d6",
        "period-winter-term": "#dff1ff",
    }
    if isinstance(context.tweaks.get("pdf"), dict):
        pdf_mapping = cast(dict[str, object], context.tweaks["pdf"])
        colours = pdf_mapping.get("colours")
        if isinstance(colours, dict):
            colours_mapping = cast(dict[str, object], colours)
            terms = colours_mapping.get("terms")
            if isinstance(terms, dict):
                terms_mapping = cast(dict[str, object], terms)
                for key in ("Term 1", "Term 2", "Term 3", "Summer Term"):
                    value = terms_mapping.get(key)
                    if isinstance(value, str):
                        css_variables[f"period-{key.lower().replace(' ', '-')}"] = value
            semesters = colours_mapping.get("semesters")
            if isinstance(semesters, dict):
                semesters_mapping = cast(dict[str, object], semesters)
                for key in ("Semester 1", "Semester 2", "Summer Term", "Winter Term"):
                    value = semesters_mapping.get(key)
                    if isinstance(value, str):
                        css_variables[f"period-{key.lower().replace(' ', '-')}"] = value

    custom_css_variables = html_mapping.get("css_variables")
    if isinstance(custom_css_variables, dict):
        css_mapping = cast(dict[str, object], custom_css_variables)
        for key, value in css_mapping.items():
            if isinstance(value, str):
                css_variables[str(key)] = value

    html = template.render(
        plan=context.plan,
        rule=context.rule_metadata,
        tweaks=context.tweaks,
        years=context.years,
        plan_code=context.plan_code,
        program_id=context.rule_metadata.program_id or context.degree_code,
        program_code=context.rule_metadata.program_id or context.degree_code,
        specialisation_code=context.specialisation_code,
        specialisation_codes=context.specialisation_codes,
        degree_code=context.degree_code,
        tokens=tokens,
        top_disclaimer=top_disclaimer,
        footer_lines=footer.splitlines() if footer else [],
        top_disclaimer_html=_render_long_form_html(
            top_disclaimer, field_name="html.top_disclaimer"
        ),
        footer_lines_html=[
            _render_long_form_html(line, field_name="html.footer")
            for line in footer.splitlines()
        ]
        if footer
        else [],
        html_metadata=html_metadata,
        css_variables=css_variables,
    )

    output_path.write_text(html, encoding="utf-8")
