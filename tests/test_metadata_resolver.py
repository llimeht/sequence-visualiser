from pathlib import Path

from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.metadata_resolver import MetadataSource, resolve_metadata, resolve_rule_metadata


def test_resolve_rule_prefers_matching_year_range(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()

    (rules_dir / "CEICAH3707-2000-2099.json").write_text(
        '{"program":{"name":"Generic"},"specialisations":[{"name":"Generic"}],"validity":{"from":"2000","to":"2099"}}',
        encoding="utf-8",
    )
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
      '{"program":{"name":"Specific"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"},"plan_description":"Flex"}',
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
    assert metadata.plan_description == "Flex"
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


def test_resolve_metadata_from_plan_embedded_block(tmp_path: Path) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    plan_path.write_text(
        """
        {
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "program_metadata": {
            "plan_code": "CEICAH3707",
            "plan_description": "Standard sequence",
            "program": {
              "id": "3707",
              "name": "Bachelor of Engineering (Honours)"
            },
            "specialisation": [
              {"id": "CEICAH", "name": "Chemical Engineering"}
            ]
          },
          "courses": []
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    identity, metadata = resolve_metadata(
        plan=plan,
        source=MetadataSource.PLAN,
        rules_dir=tmp_path / "rules",
    )

    assert identity.plan_code == "CEICAH3707"
    assert identity.specialisation_codes == ["CEICAH"]
    assert identity.degree_code == "3707"
    assert metadata.program_id == "3707"
    assert metadata.program_name == "Bachelor of Engineering (Honours)"
    assert metadata.plan_description == "Standard sequence"
    assert metadata.rule_file == plan_path


def test_resolve_metadata_from_plan_embedded_block_no_specialisation(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "8717_2025_T2.json"
    plan_path.write_text(
        """
        {
          "sheet": "8717",
          "program": "8717",
          "career": "Postgraduate",
          "uoc": 96,
          "intake": "2025 T2",
          "program_metadata": {
            "plan_code": "8717",
            "plan_description": "Standard sequence",
            "program": {
              "id": "8717",
              "name": "Master of Engineering Science"
            },
            "specialisation": []
          },
          "courses": []
        }
        """,
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    identity, metadata = resolve_metadata(
        plan=plan,
        source=MetadataSource.PLAN,
        rules_dir=tmp_path / "rules",
    )

    assert identity.plan_code == "8717"
    assert identity.specialisation_codes == []
    assert identity.specialisation_code == ""
    assert identity.degree_code == "8717"
    assert metadata.program_id == "8717"
    assert metadata.program_name == "Master of Engineering Science"
    assert metadata.specialisation_names == []
    assert metadata.plan_description == "Standard sequence"
    assert metadata.rule_file == plan_path


def test_resolve_metadata_from_spreadsheet_row(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "\n".join(
            [
        "plan_filename,plan_code,program_id,program_name,specialisation_codes,specialisation_names,plan_description",
        "CEICAH3707_2026_T1,CEICAH3707,3707,Bachelor of Engineering (Honours),CEICAH,Chemical Engineering,Honours",
            ]
        ),
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
    identity, metadata = resolve_metadata(
        plan=plan,
        source=MetadataSource.SPREADSHEET,
        rules_dir=tmp_path / "rules",
        spreadsheet_path=mapping,
    )

    assert identity.plan_code == "CEICAH3707"
    assert identity.specialisation_codes == ["CEICAH"]
    assert identity.degree_code == "3707"
    assert metadata.program_id == "3707"
    assert metadata.program_name == "Bachelor of Engineering (Honours)"
    assert metadata.plan_description == "Honours"
    assert metadata.rule_file == mapping


def test_spreadsheet_requires_required_columns(tmp_path: Path) -> None:
    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "plan_filename,plan_code,program_id,program_name,specialisation_codes\n"
        "CEICAH3707_2026_T1,CEICAH3707,3707,Bachelor of Engineering (Honours),CEICAH\n",
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

    try:
        resolve_metadata(
            plan=plan,
            source=MetadataSource.SPREADSHEET,
            rules_dir=tmp_path / "rules",
            spreadsheet_path=mapping,
        )
    except ValueError as exc:
        assert "specialisation_names" in str(exc)
    else:
        assert False, "Expected missing-column error"
