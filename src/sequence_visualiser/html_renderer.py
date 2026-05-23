"""
sequence_visualiser.html_renderer
================================
Renders plan data to HTML using Jinja2 templates. Supports template overrides.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import RenderContext


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

    html = template.render(
        plan=context.plan,
        rule=context.rule_metadata,
        tweaks=context.tweaks,
        years=context.years,
        plan_code=context.plan_code,
        specialisation_code=context.specialisation_code,
        degree_code=context.degree_code,
    )

    output_path.write_text(html, encoding="utf-8")
