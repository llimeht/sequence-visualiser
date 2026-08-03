import dataclasses
from pathlib import Path

from sequence_visualiser.course_overrides import (
    CourseOverrideError,
    apply_course_overrides,
    has_course_override,
    load_course_overrides,
    resolve_course_override,
)
from sequence_visualiser.models import Course, Plan
from sequence_visualiser.timeline import build_year_layouts


def _course(code: str) -> Course:
    return Course(
        enrol_year="Y1",
        year=1,
        period="T1",
        course_n="1",
        code=code,
        title="Original title",
        uoc=6,
        prerequisites="",
    )


def test_resolve_prefers_namespaced_over_plain() -> None:
    overrides = {
        "CEICAH3707::FLEX-A": {"code": "SPEC1", "title": "Plan-specific"},
        "CEICAH::FLEX-A": {"code": "SPEC2", "title": "Spec-specific"},
        "3707::FLEX-A": {"code": "DEG", "title": "Degree-specific"},
        "FLEX-A": {"code": "GEN", "title": "Generic"},
    }

    entry = resolve_course_override(
        "flex-a",
        overrides,
        namespace_candidates=["ceicah3707", "ceicah", "3707"],
    )

    assert entry is not None
    assert entry["code"] == "SPEC1"
    assert entry["title"] == "Plan-specific"


def test_resolve_falls_back_to_plain_key() -> None:
    overrides = {
        "FLEX-A": {"code": "GEN", "title": "Generic"},
    }

    entry = resolve_course_override(
        "FLEX-A",
        overrides,
        namespace_candidates=["UNKNOWN", "OTHER"],
    )

    assert entry is not None
    assert entry["code"] == "GEN"


def test_apply_course_overrides_uses_namespace_candidates() -> None:
    overrides = {
        "CEICAH3707::FLEX-A": {"code": "MATH1131", "title": "Mathematics 1A"},
        "FLEX-A": {"code": "GENERIC", "title": "Generic"},
    }

    patched = apply_course_overrides(
        [_course("FLEX-A")],
        overrides,
        namespace_candidates=["CEICAH3707", "CEICAH", "3707"],
    )

    assert patched[0].code == "MATH1131"
    assert patched[0].title == "Mathematics 1A"


def test_has_course_override_checks_namespaces() -> None:
    overrides = {
        "CEICAH::FLEX-A": {"code": "MATH1131", "title": "Math"},
    }

    assert has_course_override(
        "FLEX-A",
        overrides,
        namespace_candidates=["CEICAH3707", "CEICAH", "3707"],
    )


def test_load_course_overrides_expands_aliases(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "Elective", "aliases": ["FLEX_A", "CEICAH::FLEX-A"]}}',
        encoding="utf-8",
    )

    overrides = load_course_overrides(config_dir)

    assert "FLEX-A" in overrides
    assert "FLEX_A" in overrides
    assert "CEICAH::FLEX-A" in overrides
    assert overrides["FLEX_A"]["code"] == "Elective"


def test_load_course_overrides_alias_collision_raises(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "course-overrides.json").write_text(
        """
        {
                    "PSEUDO-A": {"code": "A", "aliases": ["SHARED"]},
                    "PSEUDO-B": {"code": "B", "aliases": ["SHARED"]}
        }
        """,
        encoding="utf-8",
    )

    try:
        load_course_overrides(config_dir)
    except CourseOverrideError as exc:
        assert "maps to multiple entries" in str(exc)
    else:
        raise AssertionError("Expected CourseOverrideError")


def test_load_course_overrides_aliases_must_be_string_list(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "Elective", "aliases": "FLEX_A"}}',
        encoding="utf-8",
    )

    try:
        load_course_overrides(config_dir)
    except CourseOverrideError as exc:
        assert "must be a JSON array of strings" in str(exc)
    else:
        raise AssertionError("Expected CourseOverrideError")


def test_load_course_overrides_merges_split_files(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "GENERIC1000", "title": "Generic elective"}}',
        encoding="utf-8",
    )
    (config_dir / "course-overrides-ceic.json").write_text(
        '{"CEICAH3707::FLEX-A": {"code": "MATH1131", "title": "Mathematics 1A"}}',
        encoding="utf-8",
    )
    (config_dir / "course-overrides-mech.json").write_text(
        '{"MANFBH3707::FLEX-A": {"code": "MMAN1130", "title": "Engineering Mechanics"}}',
        encoding="utf-8",
    )

    overrides = load_course_overrides(config_dir)

    assert overrides["FLEX-A"]["code"] == "GENERIC1000"
    assert overrides["CEICAH3707::FLEX-A"]["code"] == "MATH1131"
    assert overrides["MANFBH3707::FLEX-A"]["code"] == "MMAN1130"


def test_load_course_overrides_split_files_overlay_in_order(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    local_dir = tmp_path / "local-config"
    local_dir.mkdir()

    (config_dir / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "GENERIC1000", "title": "Generic elective"}}',
        encoding="utf-8",
    )
    (config_dir / "course-overrides-ceic.json").write_text(
        '{"FLEX-A": {"code": "MATH1131", "title": "Mathematics 1A"}}',
        encoding="utf-8",
    )
    (local_dir / "course-overrides-mech.json").write_text(
        '{"FLEX-A": {"code": "MMAN1130", "title": "Engineering Mechanics"}}',
        encoding="utf-8",
    )

    warnings: list[str] = []

    def _capture_warning(message: str, *args: object, **kwargs: object) -> None:
        warnings.append(message % args if args else message)

    from sequence_visualiser import course_overrides as co

    original_warning = co.logger.warning
    co.logger.warning = _capture_warning  # type: ignore[assignment]
    try:
        overrides = load_course_overrides(config_dir, local_dir)
    finally:
        co.logger.warning = original_warning  # type: ignore[method-assign]

    assert overrides["FLEX-A"]["code"] == "MMAN1130"
    assert overrides["FLEX-A"]["title"] == "Engineering Mechanics"
    assert len(warnings) == 1
    assert "Duplicate course override keys detected" in warnings[0]


def test_load_course_overrides_warns_on_duplicate_keys(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    (config_dir / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "GENERIC1000", "title": "Generic elective"}}',
        encoding="utf-8",
    )
    (config_dir / "course-overrides-ceic.json").write_text(
        '{"FLEX-A": {"code": "MATH1131", "title": "Mathematics 1A"}}',
        encoding="utf-8",
    )

    warnings: list[str] = []

    def _capture_warning(message: str, *args: object, **kwargs: object) -> None:
        warnings.append(message % args if args else message)

    from sequence_visualiser import course_overrides as co

    original_warning = co.logger.warning
    co.logger.warning = _capture_warning  # type: ignore[assignment]
    try:
        overrides = load_course_overrides(config_dir)
    finally:
        co.logger.warning = original_warning  # type: ignore[method-assign]

    assert overrides["FLEX-A"]["code"] == "MATH1131"
    assert overrides["FLEX-A"]["title"] == "Mathematics 1A"
    assert len(warnings) == 1
    assert "Duplicate course override keys detected" in warnings[0]


def test_apply_course_overrides_drops_fully_blank_course() -> None:
    courses = [_course("FLEX-A")]
    overrides = {"FLEX-A": {"code": "", "title": ""}}

    patched = apply_course_overrides(courses, overrides)

    assert patched == []


def test_apply_course_overrides_keeps_course_when_only_code_is_blank() -> None:
    courses = [_course("FLEX-A")]
    overrides = {"FLEX-A": {"code": "", "title": "Mapped title"}}

    patched = apply_course_overrides(courses, overrides)

    assert len(patched) == 1
    assert patched[0].code == ""
    assert patched[0].title == "Mapped title"


def test_blank_override_removes_extended_period_pressure(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {"enrol_year": "Year 1", "year": 2026, "period": "Summer Term", "course_n": "Course 1", "code": "SUMMER-PLACEHOLDER", "title": "Placeholder", "uoc": 6, "prerequisites": "."},
            {"enrol_year": "Year 1", "year": 2026, "period": "Term 1", "course_n": "Course 2", "code": "MATH1131", "title": "Math", "uoc": 6, "prerequisites": "."}
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = Plan(
        sheet="CEICAH3707",
        program="CEICAH3707",
        career="Undergraduate",
        uoc=192,
        intake="2026 T1",
        courses=[
            Course(
                enrol_year="Year 1",
                year=2026,
                period="Summer Term",
                course_n="Course 1",
                code="SUMMER-PLACEHOLDER",
                title="Placeholder",
                uoc=6,
                prerequisites=".",
            ),
            Course(
                enrol_year="Year 1",
                year=2026,
                period="Term 1",
                course_n="Course 2",
                code="MATH1131",
                title="Math",
                uoc=6,
                prerequisites=".",
            ),
        ],
        source_path=plan_path,
    )

    patched_courses = apply_course_overrides(
        plan.courses,
        {"SUMMER-PLACEHOLDER": {"code": "", "title": ""}},
    )
    patched_plan = dataclasses.replace(plan, courses=patched_courses)
    layouts = build_year_layouts(patched_plan)

    assert [year.calendar_model for year in layouts] == ["trimesters_standard"]
    assert [period.period for period in layouts[0].periods] == [
        "Term 1",
        "Term 2",
        "Term 3",
    ]
