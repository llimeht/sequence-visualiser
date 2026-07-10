"""
sequence_visualiser.timeline
===========================
Builds year and period layouts for plans, classifies periods, and validates timeline structure.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .models import Course, PeriodLayout, Plan, YearLayout


@dataclass(frozen=True)
class CalendarModel:
    key: str
    family: str
    calendar_type: str
    periods: tuple[str, ...]
    extended: bool


CALENDAR_MODELS: dict[str, CalendarModel] = {
    "trimesters_standard": CalendarModel(
        key="trimesters_standard",
        family="trimesters",
        calendar_type="term",
        periods=("Term 1", "Term 2", "Term 3"),
        extended=False,
    ),
    "trimesters_extended": CalendarModel(
        key="trimesters_extended",
        family="trimesters",
        calendar_type="term",
        periods=("Summer Term", "Term 1", "Term 2", "Term 3"),
        extended=True,
    ),
    "semesters_standard": CalendarModel(
        key="semesters_standard",
        family="semesters",
        calendar_type="semester",
        periods=("Semester 1", "Semester 2"),
        extended=False,
    ),
    "semesters_extended": CalendarModel(
        key="semesters_extended",
        family="semesters",
        calendar_type="semester",
        periods=("Summer Term", "Semester 1", "Winter Term", "Semester 2"),
        extended=True,
    ),
}

TERM_LABELS = {"Term 1", "Term 2", "Term 3"}
SEMESTER_LABELS = {"Semester 1", "Semester 2"}
WINTER_LABELS = {"Winter Term"}
KNOWN_PERIOD_LABELS = set().union(*(model.periods for model in CALENDAR_MODELS.values()))


class TimelineError(ValueError):
    """Raised when a plan cannot be represented in the expected timeline format."""


def _course_slot_number(course_n: str) -> int:
    """Extract the slot number from a course_n string, or return 999 if not found."""
    match = re.search(r"(\d+)$", course_n.strip())
    return int(match.group(1)) if match else 999


def _calendar_family_from_periods(periods: set[str], *, strict: bool = True) -> str | None:
    """Infer the calendar family from a set of period labels.

    Returns:
        "trimesters", "semesters", or None if only ambiguous labels are present.
    """
    has_term = bool(periods.intersection(TERM_LABELS))
    has_semester = bool(periods.intersection(SEMESTER_LABELS.union(WINTER_LABELS)))

    if has_term and has_semester:
        if not strict:
            return None
        raise TimelineError(f"Mixed period families: {sorted(periods)}")
    if has_term:
        return "trimesters"
    if has_semester:
        return "semesters"
    return None


def _target_model_key_for_family(family: str, use_extended: bool) -> str:
    if family == "trimesters":
        return "trimesters_extended" if use_extended else "trimesters_standard"
    return "semesters_extended" if use_extended else "semesters_standard"


def _is_extended_period_for_family(period: str, family: str) -> bool:
    if family == "trimesters":
        return period == "Summer Term"
    return period in {"Summer Term", "Winter Term"}


def build_year_layouts(plan: Plan) -> list[YearLayout]:
    """Build a list of YearLayout objects for the plan, grouping courses by year and period.

    Args:
        plan: Plan object containing courses.
    Returns:
        List of YearLayout objects, one per enrolment year.
    Raises:
        TimelineError: If periods or years are ambiguous or mixed.
    """
    year_to_courses: dict[str, list[Course]] = defaultdict(list)
    for course in plan.courses:
        year_to_courses[course.enrol_year].append(course)

    ordered_years = sorted(
        year_to_courses,
        key=lambda year_label: min(
            course.year for course in year_to_courses[year_label]
        ),
    )

    plan_labels = {course.period for course in plan.courses}
    unexpected_labels = sorted(plan_labels.difference(KNOWN_PERIOD_LABELS))
    if unexpected_labels:
        raise TimelineError(f"Unexpected period label: {', '.join(unexpected_labels)}")

    plan_family_hint = _calendar_family_from_periods(plan_labels, strict=False)

    layout_parts: list[tuple[str, int, str, str, dict[str, list[Course]]]] = []
    for year_label in ordered_years:
        courses = year_to_courses[year_label]
        year_counts = Counter(course.year for course in courses)
        if len(year_counts) == 1:
            calendar_year = next(iter(year_counts))
        else:
            # Cope with occasional data errors by selecting the dominant calendar year.
            most_common = year_counts.most_common()
            if len(most_common) > 1 and most_common[0][1] == most_common[1][1]:
                raise TimelineError(
                    f"Ambiguous calendar years in {plan.source_path.name} for {year_label}: "
                    f"{sorted(year_counts)}"
                )
            calendar_year = most_common[0][0]

        year_period_labels = {course.period for course in courses}
        year_family = _calendar_family_from_periods(year_period_labels)
        if year_family is None:
            year_family = plan_family_hint
        if year_family is None:
            raise TimelineError(
                f"Ambiguous period family in {plan.source_path.name} for {year_label}: "
                f"{sorted(year_period_labels)}"
            )

        period_to_courses: dict[str, list[Course]] = defaultdict(list)
        for course in courses:
            period_to_courses[course.period].append(course)

        family_allowed = set(CALENDAR_MODELS[_target_model_key_for_family(year_family, True)].periods)
        unexpected_periods = sorted(set(period_to_courses).difference(family_allowed))
        if unexpected_periods:
            raise TimelineError(
                f"Unexpected periods in {plan.source_path.name} for {year_label}: "
                f"{', '.join(unexpected_periods)}"
            )

        year_uses_extended = any(
            _is_extended_period_for_family(period, year_family)
            for period in period_to_courses
        )
        initial_model = _target_model_key_for_family(year_family, year_uses_extended)
        calendar_type = CALENDAR_MODELS[initial_model].calendar_type
        layout_parts.append(
            (year_label, calendar_year, year_family, calendar_type, period_to_courses)
        )

    family_requires_extended: dict[str, bool] = {}
    for _, _, family, _, period_to_courses in layout_parts:
        family_requires_extended[family] = family_requires_extended.get(family, False) or any(
            _is_extended_period_for_family(period, family)
            for period in period_to_courses
        )

    layouts: list[YearLayout] = []
    for year_label, calendar_year, family, calendar_type, period_to_courses in layout_parts:
        model_key = _target_model_key_for_family(
            family, family_requires_extended.get(family, False)
        )
        model = CALENDAR_MODELS[model_key]
        period_layouts = [
            PeriodLayout(
                period=period,
                courses=sorted(
                    period_to_courses.get(period, []),
                    key=lambda c: (_course_slot_number(c.course_n), c.code),
                ),
            )
            for period in model.periods
        ]

        layouts.append(
            YearLayout(
                enrol_year=year_label,
                year=calendar_year,
                calendar_type=calendar_type,
                calendar_family=family,
                calendar_model=model_key,
                periods=period_layouts,
            )
        )

    return layouts
