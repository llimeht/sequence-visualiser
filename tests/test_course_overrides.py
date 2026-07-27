from pathlib import Path

from sequence_visualiser.course_overrides import (
    CourseOverrideError,
    apply_course_overrides,
    has_course_override,
    load_course_overrides,
    resolve_course_override,
)
from sequence_visualiser.models import Course


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
