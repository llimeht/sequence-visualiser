"""
sequence_visualiser.timeline
===========================
Builds year and period layouts for plans, classifies periods, and validates timeline structure.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from .models import Course, PeriodLayout, Plan, YearLayout

TERM_ORDER = {"Term 1": 1, "Term 2": 2, "Term 3": 3}
SEMESTER_ORDER = {"Semester 1": 1, "Semester 2": 2}


class TimelineError(ValueError):
    """Raised when a plan cannot be represented in the expected timeline format."""


def _course_slot_number(course_n: str) -> int:
    """Extract the slot number from a course_n string, or return 999 if not found."""
    match = re.search(r"(\d+)$", course_n.strip())
    return int(match.group(1)) if match else 999


def _classify_period(period: str) -> str:
    """Classify a period label as 'term' or 'semester'.

    Args:
        period: The period label (e.g., 'Term 1', 'Semester 1').
    Returns:
        'term' or 'semester'.
    Raises:
        TimelineError: If the period label is not recognised.
    """
    if period in TERM_ORDER:
        return "term"
    if period in SEMESTER_ORDER:
        return "semester"
    raise TimelineError(f"Unexpected period label: {period}")


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

    layouts: list[YearLayout] = []
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

        period_type_set = {_classify_period(course.period) for course in courses}
        if len(period_type_set) != 1:
            raise TimelineError(
                f"Mixed period types in {plan.source_path.name} for {year_label}: "
                f"{sorted(period_type_set)}"
            )

        calendar_type = period_type_set.pop()
        order_map = TERM_ORDER if calendar_type == "term" else SEMESTER_ORDER

        period_to_courses: dict[str, list[Course]] = defaultdict(list)
        for course in courses:
            period_to_courses[course.period].append(course)

        unexpected_periods = sorted(set(period_to_courses).difference(order_map))
        if unexpected_periods:
            raise TimelineError(
                f"Unexpected periods in {plan.source_path.name} for {year_label}: "
                f"{', '.join(unexpected_periods)}"
            )

        periods = sorted(period_to_courses, key=lambda period: order_map[period])
        period_layouts = [
            PeriodLayout(
                period=period,
                courses=sorted(
                    period_to_courses[period],
                    key=lambda c: (_course_slot_number(c.course_n), c.code),
                ),
            )
            for period in periods
        ]

        layouts.append(
            YearLayout(
                enrol_year=year_label,
                year=calendar_year,
                calendar_type=calendar_type,
                periods=period_layouts,
            )
        )

    return layouts
