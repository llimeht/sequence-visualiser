from pathlib import Path

from sequence_visualiser.cli import main


HTML_TEMPLATE = """<!doctype html><html><body>{% for year in years %}<details class=\"year\" open><summary>{{ year.enrol_year }}</summary></details>{% endfor %}</body></html>"""


def _write_plan(path: Path, period: str) -> None:
    path.write_text(
        f"""
        {{
          "sheet": "CEICAH3707",
          "program": "CEICAH3707",
          "career": "Undergraduate",
          "uoc": 192,
          "intake": "2026 T1",
          "courses": [
            {{"enrol_year": "Year 1", "year": 2026, "period": "{period}", "course_n": "Course 1", "code": "MATH1131", "title": "Math", "uoc": 6, "prerequisites": "."}}
          ]
        }}
        """,
        encoding="utf-8",
    )


def test_cli_continues_after_plan_failure(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    good_plan = tmp_path / "CEICAH3707_2026_T1.json"
    bad_plan = tmp_path / "CEICAH3707_2026_T2.json"
    _write_plan(good_plan, "Term 1")
    _write_plan(bad_plan, "Summer Term")

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(good_plan),
            str(bad_plan),
            "--output-dir",
            str(output_dir),
            "--rules-dir",
            str(rules_dir),
            "--templates-dir",
            str(templates_dir),
            "--config-dir",
            str(templates_dir / "config"),
            "--formats",
            "html",
        ]
    )

    assert rc == 1
    assert (output_dir / "CEICAH3707_2026_T1.html").exists()
    assert not (output_dir / "CEICAH3707_2026_T2.html").exists()


def test_html_template_renders_expanded_sections(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan(plan, "Term 1")

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(plan),
            "--output-dir",
            str(output_dir),
            "--rules-dir",
            str(rules_dir),
            "--templates-dir",
            str(templates_dir),
            "--config-dir",
            str(templates_dir / "config"),
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    html = (output_dir / "CEICAH3707_2026_T1.html").read_text(encoding="utf-8")
    assert '<details class="year" open>' in html


def test_pdf_renders_with_custom_colour_config(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text(
        """
                {
                    "pdf": {
                        "colours": {
                            "years": {"Year 1": "#f7f7f7", "1": "#f6f6f6"},
                            "terms": {"Term 1": "#eeeeee", "Term 2": "#e5e5e5", "Term 3": "#dcdcdc"},
                            "semesters": {"Semester 1": [240, 240, 240], "Semester 2": [0.9, 0.9, 0.9]}
                        }
                    }
                }
                """,
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T2.json"
    _write_plan(plan, "Term 2")

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(plan),
            "--output-dir",
            str(output_dir),
            "--rules-dir",
            str(rules_dir),
            "--templates-dir",
            str(templates_dir),
            "--config-dir",
            str(templates_dir / "config"),
            "--formats",
            "pdf",
        ]
    )

    assert rc == 0
    pdf = output_dir / "CEICAH3707_2026_T2.pdf"
    assert pdf.exists()
    assert pdf.stat().st_size > 0
