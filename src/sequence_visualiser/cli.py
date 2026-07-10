"""
sequence_visualiser.cli
======================
Command-line interface for the sequence visualiser tool. Handles argument parsing,
batch processing of plan files, and rendering to HTML/PDF formats.
"""

from __future__ import annotations

import argparse
import dataclasses
import sys
from collections.abc import Mapping
from datetime import date
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .config_loader import ConfigError, load_tweaks
from .course_overrides import (
    CourseOverrideError,
    apply_course_overrides,
    load_course_overrides,
)
from .html_renderer import render_html
from .models import RenderContext
from .pdf_renderer import PdfRenderError, render_pdf
from .plan_loader import PlanParseError, load_plan
from .metadata_resolver import MetadataSource, RuleResolutionError, resolve_metadata
from .render_tokens import TokenExpansionError
from .timeline import TimelineError, build_year_layouts


@dataclass(frozen=True)
class PlanFailure:
    """Represents a failed plan rendering attempt, with the file and reason."""

    plan: Path
    reason: str


def _parse_formats(value: str) -> set[str]:
    """Parse the formats argument, ensuring only allowed values are accepted.

    Args:
        value: Comma-separated string of format names.
    Returns:
        Set of valid format names (html, pdf).
    Raises:
        argparse.ArgumentTypeError: If unknown or missing formats are provided.
    """
    values = {item.strip().lower() for item in value.split(",") if item.strip()}
    allowed = {"html", "pdf", "both"}
    unknown = values.difference(allowed)
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Unknown format value(s): {', '.join(sorted(unknown))}"
        )
    if "both" in values:
        return {"html", "pdf"}
    if not values:
        raise argparse.ArgumentTypeError("At least one format is required")
    return values


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="Visualise enrolment sequences as HTML and PDF"
    )
    parser.add_argument("plan_files", nargs="+", type=Path, help="Plan JSON file(s)")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--rules-dir", type=Path)
    parser.add_argument(
        "--metadata-source",
        type=str,
        default=MetadataSource.RULES.value,
        choices=[source.value for source in MetadataSource],
        help="Metadata source mode",
    )
    parser.add_argument(
        "--metadata-map",
        type=Path,
        default=None,
        help="CSV/TSV mapping file used when metadata source is spreadsheet",
    )
    parser.add_argument("--templates-dir", type=Path)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument(
        "--template-overrides-dir",
        type=Path,
        default=None,
        help="Template override config directory",
    )
    parser.add_argument(
        "--datestamp",
        type=str,
        help="Date token value in YYYY-mm-dd format (defaults to today)",
    )
    parser.add_argument("--formats", type=_parse_formats, default={"html", "pdf"})
    return parser


def _resolve_datestamp(value: str | None) -> str:
    """Resolve and validate the effective datestamp in YYYY-mm-dd format."""
    if value is None:
        return date.today().isoformat()
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid --datestamp value '{value}': expected YYYY-mm-dd"
        ) from exc
    return parsed.isoformat()


def _project_root() -> Path:
    """Return the project root for resolving bundled defaults."""
    return Path(__file__).resolve().parents[2]


def _resolve_resource_dirs(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    """Resolve rules/templates/config/override directories.

    When flags are not provided, defaults are resolved relative to the package's
    project root so CLI execution from any working directory behaves consistently.
    """
    root = _project_root()

    rules_dir = args.rules_dir if args.rules_dir is not None else root / "rules"
    templates_dir = (
        args.templates_dir if args.templates_dir is not None else root / "templates"
    )
    config_dir = (
        args.config_dir
        if args.config_dir is not None
        else templates_dir / "config"
    )
    template_overrides_dir = (
        args.template_overrides_dir
        if args.template_overrides_dir is not None
        else Path("template-overrides") / "config"
    )

    return rules_dir, templates_dir, config_dir, template_overrides_dir


def _render_single_plan(
    plan_file: Path,
    output_dir: Path,
    rules_dir: Path,
    templates_dir: Path,
    config_dir: Path,
    template_overrides_dir: Path,
    formats: set[str],
    datestamp: str,
    metadata_source: MetadataSource,
    metadata_map: Path | None,
) -> None:
    """Render a single plan file to the specified formats (HTML/PDF).

    Args:
        plan_file: Path to the plan JSON file.
        output_dir: Directory to write output files.
        rules_dir: Directory containing rules files.
        templates_dir: Directory containing Jinja2 templates.
        config_dir: Directory containing config files.
        template_overrides_dir: Directory for template override configs.
        formats: Set of formats to render (html, pdf).
    """
    plan = load_plan(plan_file)
    identity, rule_metadata = resolve_metadata(
        plan=plan,
        source=metadata_source,
        rules_dir=rules_dir,
        spreadsheet_path=metadata_map,
    )

    course_overrides = load_course_overrides(config_dir, template_overrides_dir)
    patched_courses = apply_course_overrides(plan.courses, course_overrides)
    if patched_courses is not plan.courses:
        plan = dataclasses.replace(plan, courses=patched_courses)

    years = build_year_layouts(plan)
    tweaks = load_tweaks(plan, identity, config_dir, template_overrides_dir)
    runtime_tweaks = {
        "date": datestamp,
        "year": datestamp[:4],
    }
    existing_runtime = tweaks.get("runtime")
    if isinstance(existing_runtime, Mapping):
        runtime_mapping = cast(Mapping[object, object], existing_runtime)
        merged_runtime: dict[str, object] = {
            str(key): value for key, value in runtime_mapping.items()
        }
        merged_runtime.update(runtime_tweaks)
    else:
        merged_runtime = dict[str, object](runtime_tweaks)
    tweaks = dict(tweaks)
    tweaks["runtime"] = merged_runtime

    context = RenderContext(
        plan=plan,
        rule_metadata=rule_metadata,
        tweaks=tweaks,
        years=years,
        plan_code=identity.plan_code,
        specialisation_code=identity.specialisation_code,
        degree_code=identity.degree_code,
        specialisation_codes=identity.specialisation_codes,
    )

    if "html" in formats:
        render_html(
            context,
            templates_dir=templates_dir,
            output_path=output_dir / f"{plan_file.stem}.html",
        )
    if "pdf" in formats:
        render_pdf(
            context,
            output_path=output_dir / f"{plan_file.stem}.pdf",
            templates_dir=templates_dir,
        )


def main(argv: list[str] | None = None) -> int:
    """Main entry point for the CLI tool.

    Args:
        argv: Optional list of command-line arguments.
    Returns:
        Exit code (0 for success, 1 for any failures).
    """
    args = _build_parser().parse_args(argv)
    metadata_source = MetadataSource(args.metadata_source)
    datestamp = _resolve_datestamp(args.datestamp)
    rules_dir, templates_dir, config_dir, template_overrides_dir = _resolve_resource_dirs(
        args
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    failures: list[PlanFailure] = []
    successes = 0

    for plan_file in args.plan_files:
        try:
            _render_single_plan(
                plan_file=plan_file,
                output_dir=args.output_dir,
                rules_dir=rules_dir,
                templates_dir=templates_dir,
                config_dir=config_dir,
                template_overrides_dir=template_overrides_dir,
                formats=args.formats,
                datestamp=datestamp,
                metadata_source=metadata_source,
                metadata_map=args.metadata_map,
            )
            successes += 1
            print(f"OK: {plan_file}")
        except (
            PlanParseError,
            RuleResolutionError,
            TimelineError,
            ConfigError,
            CourseOverrideError,
            PdfRenderError,
            TokenExpansionError,
        ) as exc:
            failures.append(PlanFailure(plan=plan_file, reason=str(exc)))
            print(f"FAIL: {plan_file} -> {exc}", file=sys.stderr)

    print(f"Summary: {successes} succeeded, {len(failures)} failed")
    if failures:
        for failure in failures:
            print(f"  - {failure.plan}: {failure.reason}", file=sys.stderr)
        return 1
    return 0
