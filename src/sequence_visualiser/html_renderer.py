"""Renders plan data to HTML using Jinja2 templates. Supports template overrides."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import RenderContext
from .render_tokens import expand_runtime_tokens, runtime_token_values


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
        html_metadata=html_metadata,
    )

    output_path.write_text(html, encoding="utf-8")
