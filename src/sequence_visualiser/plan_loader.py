"""
sequence_visualiser.plan_loader
==============================
Loads and validates plan JSON files, converting them to Plan objects.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from .models import Course, Plan


class PlanParseError(ValueError):
    """Raised when a plan file cannot be parsed."""


def load_plan(plan_path: Path) -> Plan:
    """Load and validate a plan JSON file, returning a Plan object.

    Args:
        plan_path: Path to the plan JSON file.
    Returns:
        Plan object parsed from the file.
    Raises:
        PlanParseError: If the file is missing, invalid, or incomplete.
    """
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanParseError(f"Plan file not found: {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"Invalid JSON in plan file: {plan_path}") from exc

    required_keys = {"sheet", "program", "career", "uoc", "intake", "courses"}
    missing = sorted(required_keys.difference(payload.keys()))
    if missing:
        raise PlanParseError(
            f"Missing keys in plan file {plan_path}: {', '.join(missing)}"
        )

    courses: list[Course] = []
    for index, raw in enumerate(payload["courses"], start=1):
        try:
            course = Course(
                enrol_year=str(raw["enrol_year"]).strip(),
                year=int(raw["year"]),
                period=str(raw["period"]).strip(),
                course_n=str(raw["course_n"]).strip(),
                code=str(raw["code"]).strip(),
                title=str(raw["title"]).strip(),
                uoc=int(raw["uoc"]),
                prerequisites=str(raw.get("prerequisites", "")).strip(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanParseError(
                f"Invalid course entry at index {index} in {plan_path}: {exc}"
            ) from exc
        courses.append(course)

    program_metadata: dict[str, object] | None = None
    raw_program_metadata = payload.get("program_metadata")
    if raw_program_metadata is not None:
        if not isinstance(raw_program_metadata, Mapping):
            raise PlanParseError(
                f"Invalid program_metadata in plan file {plan_path}: must be an object"
            )
        program_metadata = {
            str(key): value for key, value in raw_program_metadata.items()
        }

    return Plan(
        sheet=str(payload["sheet"]),
        program=str(payload["program"]),
        career=str(payload["career"]),
        uoc=int(payload["uoc"]),
        intake=str(payload["intake"]),
        courses=courses,
        source_path=plan_path,
        program_metadata=program_metadata,
    )
