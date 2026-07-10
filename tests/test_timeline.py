from pathlib import Path

import pytest

from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.timeline import TimelineError, build_year_layouts


def test_dynamic_year_period_layout(tmp_path: Path) -> None:
    plan_path = tmp_path / "mixed_structure.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 2", "course_n": "Course 2", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 3", "course_n": "Course 3", "code": "C", "title": "C", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 2", "year": 2027, "period": "Semester 1", "course_n": "Course 1", "code": "D", "title": "D", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 2", "year": 2027, "period": "Semester 2", "course_n": "Course 2", "code": "E", "title": "E", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    layouts = build_year_layouts(plan)
    assert [year.year for year in layouts] == [2026, 2027]
    assert [year.calendar_type for year in layouts] == ["term", "semester"]
    assert [period.period for period in layouts[0].periods] == [
        "Term 1",
        "Term 2",
        "Term 3",
    ]
    assert [period.period for period in layouts[1].periods] == [
        "Semester 1",
        "Semester 2",
    ]


def test_unexpected_period_fails_for_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "bad_period.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Block A", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    with pytest.raises(TimelineError):
        build_year_layouts(plan)


def test_trimesters_extended_expands_all_years(tmp_path: Path) -> None:
    plan_path = tmp_path / "extended_trimesters.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 2", "year": 2027, "period": "Summer Term", "course_n": "Course 1", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    layouts = build_year_layouts(plan)

    assert [year.calendar_model for year in layouts] == [
        "trimesters_extended",
        "trimesters_extended",
    ]
    assert [period.period for period in layouts[0].periods] == [
        "Summer Term",
        "Term 1",
        "Term 2",
        "Term 3",
    ]
    assert [period.period for period in layouts[1].periods] == [
        "Summer Term",
        "Term 1",
        "Term 2",
        "Term 3",
    ]
    assert len(layouts[0].periods[0].courses) == 0


def test_semesters_extended_expands_all_years(tmp_path: Path) -> None:
    plan_path = tmp_path / "extended_semesters.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2028 S1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2028, "period": "Semester 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 2", "year": 2029, "period": "Winter Term", "course_n": "Course 1", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    layouts = build_year_layouts(plan)

    assert [year.calendar_model for year in layouts] == [
        "semesters_extended",
        "semesters_extended",
    ]
    assert [period.period for period in layouts[0].periods] == [
        "Summer Term",
        "Semester 1",
        "Winter Term",
        "Semester 2",
    ]
    assert [period.period for period in layouts[1].periods] == [
        "Summer Term",
        "Semester 1",
        "Winter Term",
        "Semester 2",
    ]


def test_mixed_standard_and_extended_auto_upgrades(tmp_path: Path) -> None:
    plan_path = tmp_path / "mixed_standard_extended.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 2", "year": 2027, "period": "Summer Term", "course_n": "Course 1", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    layouts = build_year_layouts(plan)
    assert all(year.calendar_model == "trimesters_extended" for year in layouts)


def test_mixed_calendar_years_uses_dominant_year(tmp_path: Path) -> None:
    plan_path = tmp_path / "mixed_years.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 2", "course_n": "Course 2", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2027, "period": "Term 3", "course_n": "Course 3", "code": "C", "title": "C", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    layouts = build_year_layouts(plan)
    assert [year.year for year in layouts] == [2026]


def test_ambiguous_calendar_years_still_fail(tmp_path: Path) -> None:
    plan_path = tmp_path / "ambiguous_years.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 1", "code": "A", "title": "A", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 2", "course_n": "Course 2", "code": "B", "title": "B", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2027, "period": "Term 3", "course_n": "Course 3", "code": "C", "title": "C", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2027, "period": "Term 1", "course_n": "Course 4", "code": "D", "title": "D", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    with pytest.raises(TimelineError, match="Ambiguous calendar years"):
        build_year_layouts(plan)
