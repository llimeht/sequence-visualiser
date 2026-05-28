"""
sequence_visualiser.html_renderer
================================
Renders plan data to HTML using Jinja2 templates. Supports template overrides.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import RenderContext


def _build_html_metadata(context: RenderContext, university_name: str) -> dict[str, str]:
    """Build HTML metadata values."""
    stream_names = context.rule_metadata.specialisation_names
    degree_and_streams = context.rule_metadata.program_name
    if stream_names:
        degree_and_streams = f"{degree_and_streams} - {', '.join(stream_names)}"

    runtime = context.tweaks.get("runtime", {})
    runtime_mapping = runtime if isinstance(runtime, dict) else {}
    information_date = str(runtime_mapping.get("date", "")).strip() or date.today().isoformat()
    copyright_year = str(runtime_mapping.get("year", "")).strip() or information_date[:4]

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
    branding_mapping = branding if isinstance(branding, dict) else {}
    university_name = str(branding_mapping.get("university_name", "")).strip() or "University"
    html_metadata = _build_html_metadata(context, university_name)

    html = template.render(
        plan=context.plan,
        rule=context.rule_metadata,
        tweaks=context.tweaks,
        years=context.years,
        plan_code=context.plan_code,
        specialisation_code=context.specialisation_code,
        degree_code=context.degree_code,
        html_metadata=html_metadata,
    )

    output_path.write_text(html, encoding="utf-8")
