from __future__ import annotations

"""
sequence_visualiser.models
=========================
Data models for plans, courses, rules, layouts, and rendering context.
Defines the core dataclasses used throughout the sequence visualiser.
"""
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any


def _empty_str_list() -> list[str]:
    return []


def _empty_course_overrides() -> dict[str, dict[str, Any]]:
    return {}


@dataclass(frozen=True)
class Course:
    """Represents a single course in a plan."""

    enrol_year: str
    year: int
    period: str
    course_n: str
    code: str
    title: str
    uoc: int
    prerequisites: str


@dataclass(frozen=True)
class Plan:
    """Represents a plan, including its metadata and list of courses."""

    sheet: str
    program: str
    career: str
    uoc: int
    intake: str
    courses: list[Course]
    source_path: Path
    plan_description: str = ""
    notes: dict[str, Any] | None = None
    program_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class RuleMetadata:
    """Metadata about the rules file used for a plan."""

    rule_file: Path
    program_name: str
    specialisation_names: list[str]
    validity_from: str
    validity_to: str
    program_id: str = ""
    plan_description: str = ""


@dataclass(frozen=True)
class PeriodLayout:
    """Layout of courses for a single period (term/semester) in a year."""

    period: str
    courses: list[Course]


@dataclass(frozen=True)
class YearLayout:
    """Layout of periods and courses for a single enrolment year."""

    enrol_year: str
    year: int
    calendar_type: str
    periods: list[PeriodLayout]
    calendar_family: str = ""
    calendar_model: str = ""


@dataclass(frozen=True)
class RenderContext:
    """Context object passed to renderers, containing all data for output."""

    plan: Plan
    rule_metadata: RuleMetadata
    tweaks: dict[str, Any]
    years: list[YearLayout]
    plan_code: str
    specialisation_code: str
    degree_code: str
    specialisation_codes: list[str] = field(default_factory=_empty_str_list)
    course_overrides: dict[str, dict[str, Any]] = field(
        default_factory=_empty_course_overrides
    )
