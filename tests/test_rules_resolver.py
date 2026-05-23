from pathlib import Path

from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.rules_resolver import resolve_rule_metadata


def test_resolve_rule_prefers_matching_year_range(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "CEICAH3707.json").write_text(
        '{"program":{"name":"Generic"},"specialisations":[{"name":"Generic"}],"validity":{"from":"2000","to":"2099"}}',
        encoding="utf-8",
    )
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"Specific"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {
              "enrol_year": "Year 1",
              "year": 2026,
              "period": "Term 1",
              "course_n": "Course 1",
              "code": "MATH1131",
              "title": "Math",
              "uoc": 6,
              "prerequisites": "."
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    _, metadata = resolve_rule_metadata(plan, rules_dir)
    assert metadata.program_name == "Specific"
    assert metadata.validity_from == "2026"
