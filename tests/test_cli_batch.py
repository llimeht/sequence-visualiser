from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from pytest import CaptureFixture

from sequence_visualiser.cli import main
from sequence_visualiser.metadata_resolver import resolve_rule_metadata
from sequence_visualiser.plan_loader import load_plan
from sequence_visualiser.render_tokens import (
    TokenExpansionError,
    expand_runtime_tokens,
    runtime_token_values,
)
from sequence_visualiser.timeline import build_year_layouts
from sequence_visualiser.models import RenderContext


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
          "plan_description": "Flex",
          "courses": [
            {{"enrol_year": "Year 1", "year": 2026, "period": "{period}", "course_n": "Course 1", "code": "MATH1131", "title": "Math", "uoc": 6, "prerequisites": "."}}
          ]
        }}
        """,
        encoding="utf-8",
    )


def _write_plan_with_code(path: Path, period: str, code: str) -> None:
        path.write_text(
                f"""
                {{
                    "sheet": "CEICAH3707",
                    "program": "CEICAH3707",
                    "career": "Undergraduate",
                    "uoc": 192,
                    "intake": "2026 T1",
                    "plan_description": "Flex",
                    "courses": [
                        {{"enrol_year": "Year 1", "year": 2026, "period": "{period}", "course_n": "Course 1", "code": "{code}", "title": "Math", "uoc": 6, "prerequisites": "."}}
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
            "--metadata-source",
            "rules",
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
            "--metadata-source",
            "rules",
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
            "--metadata-source",
            "rules",
            "--formats",
            "pdf",
        ]
    )

    assert rc == 0
    pdf = output_dir / "CEICAH3707_2026_T2.pdf"
    assert pdf.exists()
    assert pdf.stat().st_size > 0


def test_html_disclaimer_uses_datestamp_tokens(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    local_overrides = tmp_path / "template-overrides" / "config"
    local_overrides.mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text(
        '{"branding":{"university_name":"Test Uni"},"html":{"top_disclaimer":"Guide for {university_name} as at {date} ({year}) in {intake_year} {intake_period}","footer":"Issued for {program_code} {plan_description} in {intake_year}"}}',
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body><section class=\"intro\"><div>{{ top_disclaimer_html }}</div></section><footer>{% for line in footer_lines_html %}<div>{{ line }}</div>{% endfor %}</footer></body></html>""",
        encoding="utf-8",
    )

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
            "--template-overrides-dir",
            str(local_overrides),
            "--metadata-source",
            "rules",
            "--formats",
            "html",
            "--datestamp",
            "2026-05-28",
        ]
    )

    assert rc == 0
    html = (output_dir / "CEICAH3707_2026_T1.html").read_text(encoding="utf-8")
    assert "Guide for Test Uni as at 2026-05-28 (2026) in 2026 T1" in html
    assert "Issued for 3707 Flex in 2026" in html


def test_html_long_form_markup_renders_only_in_long_form(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    local_overrides = tmp_path / "template-overrides" / "config"
    local_overrides.mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text(
        '{"html":{"top_disclaimer":"Guide <b><i>Important</i></b> notice","footer":"Contact <a href=\\"https://example.edu\\">The Nucleus</a> today"}}',
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body><section class=\"intro\"><div>{{ top_disclaimer_html }}</div></section><main>{% for year in years %}{% for period in year.periods %}{% for course in period.courses %}<div class=\"course\">{{ course.title }}</div>{% endfor %}{% endfor %}{% endfor %}</main><footer>{% for line in footer_lines_html %}<div>{{ line }}</div>{% endfor %}</footer></body></html>""",
        encoding="utf-8",
    )

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
            "--template-overrides-dir",
            str(local_overrides),
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    html = (output_dir / "CEICAH3707_2026_T1.html").read_text(encoding="utf-8")
    assert "Guide <strong><em>Important</em></strong> notice" in html
    assert (
        'Contact <a href="https://example.edu">The Nucleus</a> today' in html
    )
    assert "<strong>Math</strong>" not in html


def test_html_long_form_unclosed_bold_tag_logs_warning(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    local_overrides = tmp_path / "template-overrides" / "config"
    local_overrides.mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text(
        '{"html":{"top_disclaimer":"Guide <b>Important notice"}}',
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body><section class=\"intro\"><div>{{ top_disclaimer_html }}</div></section></body></html>""",
        encoding="utf-8",
    )

    warnings: list[str] = []

    def _capture_warning(msg: str, *args: object, **kwargs: object) -> None:
        _ = kwargs
        warnings.append(msg % args)

    monkeypatch.setattr("sequence_visualiser.html_renderer.logger.warning", _capture_warning)

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
            "--template-overrides-dir",
            str(local_overrides),
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    assert any("Unclosed <b> tag found" in warning for warning in warnings)


def test_html_disclaimer_fails_for_unexpanded_token(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    local_overrides = tmp_path / "template-overrides" / "config"
    local_overrides.mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text(
        '{"branding":{"university_name":"Test Uni"},"html":{"top_disclaimer":"Guide for {unknown_token}"}}',
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body><section><div>{{ top_disclaimer }}</div></section></body></html>""",
        encoding="utf-8",
    )

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
            "--template-overrides-dir",
            str(local_overrides),
            "--formats",
            "html",
            "--datestamp",
            "2026-05-28",
        ]
    )

    assert rc == 1
    assert not (output_dir / "CEICAH3707_2026_T1.html").exists()


def test_expand_runtime_tokens_raises_for_unexpanded_placeholders(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan(plan, "Term 1")
    loaded_plan = load_plan(plan)
    identity, metadata = resolve_rule_metadata(loaded_plan, rules_dir)
    context = RenderContext(
        plan=loaded_plan,
        rule_metadata=metadata,
        tweaks={"runtime": {"date": "2026-05-28", "year": "2026"}},
        years=build_year_layouts(loaded_plan),
        plan_code=identity.plan_code,
        specialisation_code=identity.specialisation_code,
        degree_code=identity.degree_code,
        specialisation_codes=identity.specialisation_codes,
    )

    try:
        expand_runtime_tokens(
            "Guide for {unknown_token}",
            context,
            "Test Uni",
        )
        raise AssertionError("Expected TokenExpansionError")
    except TokenExpansionError as exc:
        message = str(exc)
        assert "{unknown_token}" in message


def test_runtime_tokens_include_plan_notes_fields(tmp_path: Path) -> None:
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / "CEICDH3707-2024-2029.json").write_text(
                '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2024","to":"2029"}}',
                encoding="utf-8",
        )

        plan_path = tmp_path / "CEICDH3707_2024_T2.json"
        plan_path.write_text(
                """
                {
                    "sheet": "CEICDH3707",
                    "program": "CEICDH3707",
                    "career": "Undergraduate",
                    "uoc": 192,
                    "intake": "2024 T2",
                    "notes": {
                        "graduate_outcome": "Student graduates late: one teaching period",
                        "adjustment_type": "Other",
                        "for_reviewers": [
                            "Nucleus Study Guide PDF 2024",
                            "nb - Student needs to take courses in summer terms to graduate on time."
                        ],
                        "for_students": [
                            "Completing courses in summer terms permits on-time graduation"
                        ]
                    },
                    "courses": []
                }
                """,
                encoding="utf-8",
        )

        plan = load_plan(plan_path)
        identity, metadata = resolve_rule_metadata(plan, rules_dir)
        context = RenderContext(
                plan=plan,
                rule_metadata=metadata,
                tweaks={"runtime": {"date": "2026-05-28", "year": "2026"}},
                years=build_year_layouts(plan),
                plan_code=identity.plan_code,
                specialisation_code=identity.specialisation_code,
                degree_code=identity.degree_code,
                specialisation_codes=identity.specialisation_codes,
        )

        tokens = runtime_token_values(context, "Test Uni")

        assert tokens["notes_graduate_outcome"] == "Student graduates late: one teaching period"
        assert tokens["notes_adjustment_type"] == "Other"
        assert tokens["notes_for_reviewers"] == (
                "Nucleus Study Guide PDF 2024\n"
                "nb - Student needs to take courses in summer terms to graduate on time."
        )
        assert tokens["notes_for_students"] == (
                "Completing courses in summer terms permits on-time graduation"
        )


def test_cli_defaults_resolve_from_project_root_not_cwd(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    fake_root = tmp_path / "repo"
    templates_dir = fake_root / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    rules_dir = fake_root / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan(plan, "Term 1")

    monkeypatch.setattr("sequence_visualiser.cli._project_root", lambda: fake_root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(plan),
            "--output-dir",
            str(output_dir),
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0


def test_cli_warns_for_noncanonical_course_code_without_override(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
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
    _write_plan_with_code(plan, "Term 1", "FLEX-A")

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
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN:" in err
    assert "FLEX-A" in err


def test_cli_does_not_warn_for_noncanonical_code_when_overridden(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "config" / "course-overrides.json").write_text(
        '{"FLEX-A": {"code": "MATH1131", "title": "Math"}}',
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan_with_code(plan, "Term 1", "FLEX-A")

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
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN:" not in err
    assert (output_dir / "CEICAH3707_2026_T1.html").exists()


def test_cli_uses_namespaced_override_before_plain_fallback(
    tmp_path: Path, capsys: CaptureFixture[str]
) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "config" / "course-overrides.json").write_text(
        """
        {
          "FLEX-A": {"code": "GENERIC1000", "title": "Generic elective"},
          "CEICAH3707::FLEX-A": {"code": "MATH1131", "title": "Mathematics 1A"}
        }
        """,
        encoding="utf-8",
    )
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body>{% for year in years %}{% for period in year.periods %}{% for course in period.courses %}<div class=\"course\">{{ course.code }}|{{ course.title }}</div>{% endfor %}{% endfor %}{% endfor %}</body></html>""",
        encoding="utf-8",
    )

    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan_with_code(plan, "Term 1", "FLEX-A")

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
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    err = capsys.readouterr().err
    assert "WARN:" not in err
    html = (output_dir / "CEICAH3707_2026_T1.html").read_text(encoding="utf-8")
    assert "MATH1131" in html
    assert "Mathematics 1A" in html


def test_default_overrides_remain_cwd_relative(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    fake_root = tmp_path / "repo"
    templates_dir = fake_root / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "sequence.html.j2").write_text(
        """<!doctype html><html><body>{{ tweaks.get(\"branding\", {}).get(\"university_name\", \"\") }}</body></html>""",
        encoding="utf-8",
    )

    rules_dir = fake_root / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "CEICAH3707-2026-2029.json").write_text(
        '{"program":{"name":"BE(Hons)"},"specialisations":[{"name":"Chemical Engineering"}],"validity":{"from":"2026","to":"2029"}}',
        encoding="utf-8",
    )

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan(plan, "Term 1")

    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "template-overrides" / "config").mkdir(parents=True)
    (elsewhere / "template-overrides" / "config" / "defaults.json").write_text(
        '{"branding":{"university_name":"CWD Override Uni"}}',
        encoding="utf-8",
    )

    monkeypatch.setattr("sequence_visualiser.cli._project_root", lambda: fake_root)
    monkeypatch.chdir(elsewhere)

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(plan),
            "--output-dir",
            str(output_dir),
            "--metadata-source",
            "rules",
            "--formats",
            "html",
        ]
    )

    assert rc == 0
    html = (output_dir / "CEICAH3707_2026_T1.html").read_text(encoding="utf-8")
    assert "CWD Override Uni" in html


def test_cli_uses_spreadsheet_metadata_source(tmp_path: Path) -> None:
    templates_dir = tmp_path / "templates"
    (templates_dir / "config").mkdir(parents=True)
    (templates_dir / "config" / "defaults.json").write_text("{}", encoding="utf-8")
    (templates_dir / "sequence.html.j2").write_text(HTML_TEMPLATE, encoding="utf-8")

    plan = tmp_path / "CEICAH3707_2026_T1.json"
    _write_plan(plan, "Term 1")

    mapping = tmp_path / "mapping.csv"
    mapping.write_text(
        "\n".join(
            [
                "plan_filename,plan_code,program_id,program_name,specialisation_codes,specialisation_names",
                "CEICAH3707_2026_T1,CEICAH3707,3707,Bachelor of Engineering (Honours),CEICAH,Chemical Engineering",
            ]
        ),
        encoding="utf-8",
    )

    output_dir = tmp_path / "out"
    rc = main(
        [
            str(plan),
            "--output-dir",
            str(output_dir),
            "--templates-dir",
            str(templates_dir),
            "--config-dir",
            str(templates_dir / "config"),
            "--formats",
            "html",
            "--metadata-source",
            "spreadsheet",
            "--metadata-map",
            str(mapping),
        ]
    )

    assert rc == 0
    assert (output_dir / "CEICAH3707_2026_T1.html").exists()
