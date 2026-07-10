from pathlib import Path

from sequence_visualiser.config_loader import load_tweaks
from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.metadata_resolver import extract_program_identity


def test_local_overrides_supersede_committed_layers(tmp_path: Path) -> None:
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

    config_root = tmp_path / "templates" / "config"
    (config_root / "degree").mkdir(parents=True)
    override_root = tmp_path / "template-overrides" / "config"
    (override_root / "degree").mkdir(parents=True)

    (config_root / "defaults.json").write_text(
        '{"branding": {"university_name": "Base Uni", "logo_path": "base.png"}, "html": {"top_disclaimer": "Base {date}"}, "pdf": {"footer_left": "Base left", "footer_right": "Info {date} {university_name} {year}"}}',
        encoding="utf-8",
    )
    (config_root / "degree" / "3707.json").write_text(
        '{"branding": {"university_name": "Degree Uni"}}',
        encoding="utf-8",
    )
    (override_root / "degree" / "3707.json").write_text(
        '{"branding": {"university_name": "Local Uni"}, "pdf": {"footer_left": "Override left"}}',
        encoding="utf-8",
    )

    plan = load_plan(plan_path)
    identity = extract_program_identity(plan)
    tweaks = load_tweaks(plan, identity, config_root, override_root)

    assert tweaks["branding"]["university_name"] == "Local Uni"
    assert tweaks["branding"]["logo_path"] == "base.png"
    assert tweaks["html"]["top_disclaimer"] == "Base {date}"
    assert tweaks["pdf"]["footer_left"] == "Override left"
    assert tweaks["pdf"]["footer_right"] == "Info {date} {university_name} {year}"
