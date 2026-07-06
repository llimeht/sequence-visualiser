from pathlib import Path

from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.rules_resolver import resolve_rule_metadata


def test_resolve_rule_prefers_matching_year_range(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "CEICAH3707-2000-2099.json").write_text(
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
    assert metadata.program_id == ""
    assert metadata.validity_from == "2026"


def test_resolve_rule_handles_composite_program_code(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "MATSM13132+CEICM13132.json").write_text(
      '{"program":{"name":"Bachelor of Engineering (Honours)"},"specialisations":[{"name":"Materials Science and Engineering"},{"name":"Chemical Engineering"}],"validity":{"from":"2024","to":"2029"}}',
      encoding="utf-8",
    )

    plan_path = tmp_path / "MATSM13132+CEICM13132_2024_T1.json"
    plan_path.write_text(
        """
        {
          "sheet": "MATSM13132+CEICM13132",
          "program": "MATSM13132 CEICM",
          "career": "Undergraduate",
          "uoc": 240,
          "intake": "2024 T1",
          "courses": []
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    identity, metadata = resolve_rule_metadata(plan, rules_dir)

    assert identity.plan_code == "MATSM13132+CEICM13132"
    assert identity.specialisation_code == "MATSM1"
    assert identity.degree_code == "3132"
    assert metadata.program_id == ""
    assert metadata.program_name == "Bachelor of Engineering (Honours)"


def test_resolve_rule_prefers_exact_filename_match(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "CEICAH3707.json").write_text(
      '{"program":{"name":"Exact"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"1900","to":"2099"}}',
      encoding="utf-8",
    )
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
      '{"program":{"name":"Year Ranged"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
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
          "courses": []
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    _, metadata = resolve_rule_metadata(plan, rules_dir)

    assert metadata.program_id == ""
    assert metadata.program_name == "Exact"


def test_resolve_rule_extracts_program_id_when_present(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "CEICAH3707.json").write_text(
      '{"program":{"id":"3707","name":"Exact"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"1900","to":"2099"}}',
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
          "courses": []
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    _, metadata = resolve_rule_metadata(plan, rules_dir)

    assert metadata.program_id == "3707"
