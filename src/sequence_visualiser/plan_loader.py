"""
sequence_visualiser.plan_loader
==============================
Loads and validates plan JSON files, converting them to Plan objects.
"""

from __future__ import annotations

import json
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
                enrol_year=str(raw["enrol_year"]),
                year=int(raw["year"]),
                period=str(raw["period"]),
                course_n=str(raw["course_n"]),
                code=str(raw["code"]),
                title=str(raw["title"]),
                uoc=int(raw["uoc"]),
                prerequisites=str(raw.get("prerequisites", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanParseError(
                f"Invalid course entry at index {index} in {plan_path}: {exc}"
            ) from exc
        courses.append(course)

    return Plan(
        sheet=str(payload["sheet"]),
        program=str(payload["program"]),
        career=str(payload["career"]),
        uoc=int(payload["uoc"]),
        intake=str(payload["intake"]),
        courses=courses,
        source_path=plan_path,
    )
