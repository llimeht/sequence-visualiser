from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFError

from sequence_visualiser.models import (
    Course,
    PeriodLayout,
    Plan,
    RenderContext,
    RuleMetadata,
    YearLayout,
)
from sequence_visualiser.pdf_renderer import PdfRenderError, build_pdf_metadata, render_pdf


def _build_context(tmp_path: Path, stream_names: list[str]) -> RenderContext:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    plan = Plan(
        sheet="CEICAH3707",
        program="CEICAH3707",
        career="Undergraduate",
        uoc=192,
        intake="2026 T1",
        courses=[],
        source_path=plan_path,
    )
    metadata = RuleMetadata(
        rule_file=Path("rules/3707-3778.json"),
        program_name="Bachelor of Advanced Computing",
        specialisation_names=stream_names,
        validity_from="2026",
        validity_to="2028",
    )
    return RenderContext(
        plan=plan,
        rule_metadata=metadata,
        tweaks={"runtime": {"date": "2026-05-28", "year": "2026"}},
        years=[],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )


def test_build_pdf_metadata_with_streams(tmp_path: Path) -> None:
    context = _build_context(tmp_path, ["Artificial Intelligence", "Security"])

    metadata = build_pdf_metadata(context, "UNSW Sydney")

    assert (
        metadata["title"] == "Enrolment Sequence for CEICAH3707 - 2026 T1 - UNSW Sydney"
    )
    assert (
        metadata["subject"]
        == "Enrolment Sequence for CEICAH3707 - Bachelor of Advanced Computing"
        " - Artificial Intelligence, Security - 2026 T1 - UNSW Sydney"
    )
    assert (
        metadata["author"]
        == "UNSW Sydney / CEICAH3707_2026_T1.json / 3707-3778.json"
        " / Information correct as at 2026-05-28"
    )
    assert metadata["creator"] == "Copyright © 2026 UNSW Sydney / sequence-visualiser"


def test_build_pdf_metadata_without_streams(tmp_path: Path) -> None:
    context = _build_context(tmp_path, [])

    metadata = build_pdf_metadata(context, "UNSW Sydney")

    assert (
        metadata["subject"]
        == "Enrolment Sequence for CEICAH3707 - Bachelor of Advanced Computing"
        " - 2026 T1 - UNSW Sydney"
    )


class _FakeCanvas:
    last: "_FakeCanvas | None" = None

    def __init__(self, _output_path: str, pagesize: tuple[float, float]) -> None:
        self.pagesize = pagesize
        self.rect_calls: list[tuple[float, float, float, float, int]] = []
        self.fill_color_calls: list[object] = []
        self.drawn_strings: list[str] = []
        self.drawn_text: list[tuple[float, float, str]] = []
        self.drawn_right_text: list[tuple[float, float, str]] = []
        self.set_font_calls: list[tuple[str, float]] = []
        self.link_url_calls: list[tuple[str, tuple[float, float, float, float], int]] = []
        self.line_calls: list[tuple[float, float, float, float]] = []
        self.drawn_images: list[str] = []
        self.form_draw_calls = 0
        self.show_page_calls = 0
        self.author = ""
        self.creator = ""
        _FakeCanvas.last = self

    def setTitle(self, _value: str) -> None:  # noqa: N802
        return

    def setSubject(self, _value: str) -> None:  # noqa: N802
        return

    def setAuthor(self, _value: str) -> None:  # noqa: N802
        self.author = _value

    def setCreator(self, _value: str) -> None:  # noqa: N802
        self.creator = _value

    def drawImage(
        self,
        _image: str,
        _x: float,
        _y: float,
        width: float,
        height: float,
        preserveAspectRatio: bool = False,  # noqa: N803
    ) -> None:
        self.drawn_images.append(_image)
        _ = (width, height, preserveAspectRatio)

    def saveState(self) -> None:  # noqa: N802
        return

    def restoreState(self) -> None:  # noqa: N802
        return

    def translate(self, _x: float, _y: float) -> None:
        return

    def scale(self, _x: float, _y: float) -> None:
        return

    def doForm(self, _form: object) -> None:  # noqa: N802
        self.form_draw_calls += 1

    def setFont(self, _name: str, _size: float) -> None:  # noqa: N802
        self.set_font_calls.append((_name, _size))

    def drawString(self, _x: float, _y: float, text: str) -> None:  # noqa: N802
        self.drawn_strings.append(text)
        self.drawn_text.append((_x, _y, text))

    def drawRightString(self, _x: float, _y: float, text: str) -> None:  # noqa: N802
        self.drawn_strings.append(text)
        self.drawn_right_text.append((_x, _y, text))

    def linkURL(  # noqa: N802
        self,
        url: str,
        rect: tuple[float, float, float, float],
        relative: int = 0,
    ) -> None:
        self.link_url_calls.append((url, rect, relative))

    def setStrokeColor(self, _value: object) -> None:  # noqa: N802
        return

    def line(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.line_calls.append((x1, y1, x2, y2))

    def setLineWidth(self, _value: float) -> None:  # noqa: N802
        return

    def setFillColor(self, _value: object) -> None:  # noqa: N802
        self.fill_color_calls.append(_value)

    def rect(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        fill: int = 0,
        stroke: int = 1,
    ) -> None:
        _ = stroke
        self.rect_calls.append((x, y, width, height, fill))

    def showPage(self) -> None:  # noqa: N802
        self.show_page_calls += 1
        return

    def save(self) -> None:
        return


def test_render_pdf_omits_empty_period_boxes_and_headers(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T2.json"
    term2_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 2",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T2",
            courses=[term2_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 2", courses=[term2_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Term 1" not in fake.drawn_strings
    assert "Term 3" not in fake.drawn_strings
    assert "Term 2" in fake.drawn_strings
    assert "Rules: 3707-3778.json" not in fake.drawn_strings

    period_rects = [rect for rect in fake.rect_calls if rect[2] < 500 and rect[4] == 1]
    assert len(period_rects) == 1


def test_render_pdf_period_box_sits_below_heading(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T2.json"
    term2_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 2",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T2",
            courses=[term2_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 2", courses=[term2_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    term_headings = [item for item in fake.drawn_text if item[2] == "Term 2"]
    assert len(term_headings) == 1
    heading_y = term_headings[0][1]

    period_rects = [rect for rect in fake.rect_calls if rect[2] < 500 and rect[4] == 1]
    assert len(period_rects) == 1
    _, rect_y, _, rect_h, _ = period_rects[0]
    rect_top = rect_y + rect_h

    assert rect_top < heading_y


def test_render_pdf_uses_padded_monospace_course_code_field(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    empty_code_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="",
        title="Placeholder Title",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[empty_code_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[empty_code_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    code_rows = [item for item in fake.drawn_text if item[2] == " " * 8]
    title_rows = [item for item in fake.drawn_text if item[2] == "Placeholder Title"]

    assert len(code_rows) == 1
    assert len(title_rows) == 1
    assert title_rows[0][0] > code_rows[0][0]


def test_render_pdf_renders_disclaimer_and_footers(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "runtime": {"date": "2026-05-28", "year": "2026"},
            "pdf": {
                "top_disclaimer": (
                    "Guide only for {{ tokens.university_name }} in {{ tokens.intake_year }} {{ tokens.intake_period }} "
                    "on {{ tokens.date }}."
                ),
                "footer_left": "Check handbook for {{ tokens.intake_year }}.",
                "footer_right": "Information correct as at {{ tokens.date }}\\nCopyright © {{ tokens.university_name }} {{ tokens.year }}",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert (
        "Guide only for UNSW Sydney in 2026 T1 on 2026-05-28."
        in fake.drawn_strings
    )
    assert "Check handbook for 2026." in fake.drawn_strings
    assert any(
        "Information correct as at 2026-05-28" in text for text in fake.drawn_strings
    )
    assert any("Copyright © UNSW Sydney 2026" in text for text in fake.drawn_strings)
    assert fake.author.endswith("Information correct as at 2026-05-28")
    assert fake.creator.startswith("Copyright © 2026 UNSW Sydney / sequence-visualiser")


def test_render_pdf_footer_normalises_multiline_separator_variants(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "footer_left": "Footer A\n \nFooter B\n\n\nFooter C",
                "footer_right": "",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    footer_a = [item for item in fake.drawn_text if item[2] == "Footer A"]
    footer_b = [item for item in fake.drawn_text if item[2] == "Footer B"]
    footer_c = [item for item in fake.drawn_text if item[2] == "Footer C"]
    assert footer_a
    assert footer_b
    assert footer_c

    # Each paragraph separator should create exactly one blank footer row.
    assert abs(footer_a[0][1] - footer_b[0][1] - 20) < 1e-6
    assert abs(footer_b[0][1] - footer_c[0][1] - 20) < 1e-6


def test_render_pdf_long_form_markup_uses_styles_only_for_long_form(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "top_disclaimer": "Guide <b><i>Important</i></b> notice.",
                "footer_left": "Contact <a href=\"https://example.edu\">The Nucleus</a>.",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Guide" in fake.drawn_strings
    assert "Important" in fake.drawn_strings
    assert "notice." in fake.drawn_strings
    assert any("Contact" in text for text in fake.drawn_strings)
    assert any("The" in text for text in fake.drawn_strings)
    assert any("Nucleus" in text for text in fake.drawn_strings)
    assert "Math" in fake.drawn_strings

    font_names = [name for name, _size in fake.set_font_calls]
    assert "Helvetica-Bold" in font_names
    assert "Helvetica" in font_names
    assert any("Important" in text for _x, _y, text in fake.drawn_text)
    assert any(url == "https://example.edu" for url, _rect, _relative in fake.link_url_calls)


def test_render_pdf_wraps_long_link_into_multiple_clickable_fragments(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "top_disclaimer": (
                    'See <a href="https://example.edu/handbook/very/long/path">'
                    "the very long official handbook link for enrolment guidance and policy updates"
                    "</a> before enrolling."
                ),
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    matching = [
        (url, rect, relative)
        for url, rect, relative in fake.link_url_calls
        if url == "https://example.edu/handbook/very/long/path"
    ]
    assert len(matching) >= 2
    assert all(relative == 0 for _url, _rect, relative in matching)


def test_render_pdf_link_style_applies_underline_and_colour(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "link_style": {"underline": True, "colour": "#cc0000"},
                "top_disclaimer": "See <a href=\"https://example.edu\">Handbook</a>.",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert len(fake.link_url_calls) >= 1
    assert len(fake.line_calls) >= 1
    assert colors.HexColor("#cc0000") in fake.fill_color_calls


def test_render_pdf_does_not_link_or_underline_space_before_link(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "link_style": {"underline": True, "colour": "#cc0000"},
                "top_disclaimer": "See <a href=\"https://example.edu\">Handbook</a> now.",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    matching = [
        (url, rect)
        for url, rect, _relative in fake.link_url_calls
        if url == "https://example.edu"
    ]
    assert len(matching) == 1


def test_render_pdf_course_grid_links_code_and_display_title(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=0,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "course_link_template": "https://handbook.example.org/{{ career }}/courses/current/{{ code }}",
                "course_link_style": {"underline": True, "colour": "#cc0000"},
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    expected_url = "https://handbook.example.org/Undergraduate/courses/current/MATH1131"
    matching = [
        (url, rect)
        for url, rect, _relative in fake.link_url_calls
        if url == expected_url
    ]
    assert len(matching) == 2
    assert "Math (0 UoC)" in fake.drawn_strings
    assert len(fake.line_calls) >= 2


def test_render_pdf_course_grid_uses_explicit_handbook_link_override(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="FLEX-A",
        title="Placeholder",
        uoc=0,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "course_link_template": "https://handbook.example.org/{{ career }}/courses/current/{{ code }}",
                "course_link_style": {"underline": True, "colour": "#cc0000"},
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
        course_overrides={"FLEX-A": {"handbook_link": " https://example.edu/custom "}},
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    expected_url = "https://example.edu/custom"
    matching = [
        (url, rect)
        for url, rect, _relative in fake.link_url_calls
        if url == expected_url
    ]
    assert len(matching) == 2


def test_render_pdf_footer_page_tokens_are_expanded(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "footer_left": "Page {{ tokens.page_number }} of {{ tokens.total_pages }}.",
                "second_page": {
                    "enabled": True,
                    "footer_left": "Page {{ tokens.page_number }} of {{ tokens.total_pages }}.",
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Page 1 of 2." in fake.drawn_strings
    assert "Page 2 of 2." in fake.drawn_strings


def test_render_pdf_raises_for_unexpanded_token_placeholder(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "footer_left": "Bad token: {{ tokens.does_not_exist }}",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)

    try:
        render_pdf(context, tmp_path / "out.pdf", tmp_path)
        raise AssertionError("Expected PdfRenderError")
    except PdfRenderError as exc:
        assert "does_not_exist" in str(exc)


def test_render_pdf_header_includes_program_and_majors(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=["Artificial Intelligence", "Security"],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={"branding": {"university_name": "UNSW Sydney"}},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    right_aligned = {item[2] for item in fake.drawn_right_text}
    assert "Program: Bachelor of Advanced Computing" in right_aligned
    assert "Majors: Artificial Intelligence, Security" in right_aligned


def test_render_pdf_header_lines_can_be_swapped_via_config(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=["Artificial Intelligence", "Security"],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
            plan_description="Flex",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_left_lines": [
                    "Program: {{ tokens.program_name }}",
                    "Majors: {{ tokens.majors }}",
                ],
                "header_right_lines": [
                    "{{ tokens.university_name }}",
                    "{{ tokens.program_code }} {{ tokens.plan_description }} - {{ tokens.intake }}",
                ],
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    left_aligned = {item[2] for item in fake.drawn_text}
    right_aligned = {item[2] for item in fake.drawn_right_text}

    assert "Program: Bachelor of Advanced Computing" in left_aligned
    assert "Majors: Artificial Intelligence, Security" in left_aligned
    assert "UNSW Sydney" in right_aligned
    assert "3707 Flex - 2026 T1" in right_aligned

def test_render_pdf_respects_year_row_max_height_mm(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "pdf": {
                "year_row_max_height_mm": 30,
            }
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    year_rects = [rect for rect in fake.rect_calls if rect[2] > 500 and rect[4] == 1]
    assert len(year_rects) == 1

    expected_height = (30 * mm) - 5
    assert abs(year_rects[0][3] - expected_height) < 0.1


def test_render_pdf_raises_when_year_row_min_height_mm_cannot_fit(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "pdf": {
                "year_row_min_height_mm": 150,
            }
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            ),
            YearLayout(
                enrol_year="Year 2",
                year=2027,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            ),
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)

    try:
        render_pdf(context, tmp_path / "out.pdf", tmp_path)
        raise AssertionError("Expected PdfRenderError")
    except PdfRenderError as exc:
        assert "year_row_min_height_mm" in str(exc)


def test_render_pdf_year_label_includes_calendar_year(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Year 1 (2026)" in fake.drawn_strings


def test_render_pdf_prefers_logo_path_pdf_when_present(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand-logo.pdf").write_text("%PDF-1.4", encoding="utf-8")
    (assets_dir / "brand-logo.png").write_bytes(b"png")

    called_logo: list[Path] = []

    def _fake_draw_pdf_logo(
        _canvas: _FakeCanvas,
        logo: Path,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        called_logo.append(logo)
        _ = (x, y, width, height)

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {
                "logo_path": "brand-logo.png",
                "logo_path_pdf": "brand-logo.pdf",
            }
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._draw_pdf_logo", _fake_draw_pdf_logo
    )
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert called_logo == [assets_dir / "brand-logo.pdf"]
    assert fake.drawn_images == []


def test_render_pdf_uses_raster_logo_when_pdf_logo_not_configured(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand-logo.png").write_bytes(b"png")

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={"branding": {"logo_path": "brand-logo.png"}},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert fake.drawn_images == [str(assets_dir / "brand-logo.png")]


def test_render_pdf_logo_height_mm_scales_width_and_applies_spacing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand-logo.png").write_bytes(b"png")

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {
                "university_name": "UNSW Sydney",
                "logo_path": "brand-logo.png",
            },
            "pdf": {
                "logo_height_mm": 12,
                "logo_right_spacing_mm": 9,
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    def _fixed_aspect_ratio(_logo: object) -> float:
        return 2.0

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._logo_aspect_ratio", _fixed_aspect_ratio
    )
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert len(fake.drawn_images) == 1

    logo_call = next(item for item in fake.drawn_text if item[2] == "UNSW Sydney")
    expected_logo_width = (12 * mm) * 2.0
    expected_spacing = 9 * mm
    expected_title_x = 20 + expected_logo_width + expected_spacing
    assert abs(logo_call[0] - expected_title_x) < 1e-6


def test_render_pdf_logo_width_mm_passed_to_pdf_logo_draw(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "brand-logo.pdf").write_text("%PDF-1.4", encoding="utf-8")

    captured: list[tuple[float, float]] = []

    def _fake_draw_pdf_logo(
        _canvas: _FakeCanvas,
        _logo: Path,
        _x: float,
        _y: float,
        width: float,
        height: float,
    ) -> None:
        captured.append((width, height))

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "branding": {
                "logo_path_pdf": "brand-logo.pdf",
            },
            "pdf": {
                "logo_width_mm": 25,
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    def _fixed_aspect_ratio(_logo: object) -> float:
        return 2.0

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._draw_pdf_logo", _fake_draw_pdf_logo
    )
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._logo_aspect_ratio", _fixed_aspect_ratio
    )
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    assert len(captured) == 1
    assert abs(captured[0][0] - (25 * mm)) < 1e-6
    assert abs(captured[0][1] - ((25 * mm) / 2.0)) < 1e-6


def test_render_pdf_header_widths_are_configurable(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_left_lines": ["Left"],
                "header_right_lines": ["Right"],
                "header_right_width_mm": 200,
                "header_left_min_width_mm": 120,
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    fit_widths: list[float] = []

    def _fake_fit_text_size(
        text: str,
        max_width: float,
        font_name: str,
        max_size: int = 8,
    ) -> int:
        _ = (text, font_name, max_size)
        fit_widths.append(max_width)
        return 9

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._fit_text_size_for_font", _fake_fit_text_size
    )
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    assert len(fit_widths) >= 2
    # First call: left header width uses configured minimum width.
    assert abs(fit_widths[0] - (120 * mm)) < 1e-6
    # Second call: right header width uses configured right box width minus paddings.
    assert abs(fit_widths[1] - ((200 * mm) - (2 * 8))) < 1e-6


def test_render_pdf_header_line_gap_is_configurable(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_left_lines": ["L1", "L2"],
                "header_right_lines": ["R1", "R2"],
                "header_line_gap_pt": 20,
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    l1 = next(item for item in fake.drawn_text if item[2] == "L1")
    l2 = next(item for item in fake.drawn_text if item[2] == "L2")
    r1 = next(item for item in fake.drawn_right_text if item[2] == "R1")
    r2 = next(item for item in fake.drawn_right_text if item[2] == "R2")

    assert abs((l1[1] - l2[1]) - 20) < 1e-6
    assert abs((r1[1] - r2[1]) - 20) < 1e-6


def test_render_pdf_uses_configured_font_roles(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    for name in (
        "Clancy-Regular.ttf",
        "Roboto-Regular.ttf",
        "Roboto-Bold.ttf",
        "RobotoMono-Regular.ttf",
    ):
        (fonts_dir / name).write_bytes(b"font")

    def _fake_register_font_file(font_path: Path, alias: str) -> str | None:
        _ = font_path
        return alias

    def _fit_text_size_stub(
        _text: str,
        _max_width: float,
        _font_name: str,
        max_size: int = 8,
    ) -> int:
        return max_size

    def _string_width_stub(text: str, _font_name: str, font_size: float) -> float:
        return float(len(text) * font_size)

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=["Chemical Engineering"],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {
                "university_name": "UNSW Sydney",
            },
            "pdf": {
                "header_left_lines": ["{{ tokens.university_name }}"],
                "header_right_lines": ["{{ tokens.program_name }}"],
                "fonts": {
                    "header": {
                        "regular": "fonts/Clancy-Regular.ttf",
                        "size": 13,
                    },
                    "course_codes": {
                        "regular": "fonts/RobotoMono-Regular.ttf",
                    },
                    "footer": {
                        "regular": "fonts/Roboto-Regular.ttf",
                    },
                    "body": {
                        "regular": "fonts/Roboto-Regular.ttf",
                        "bold": "fonts/Roboto-Bold.ttf",
                    },
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._register_font_file", _fake_register_font_file
    )
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer._fit_text_size_for_font",
        _fit_text_size_stub,
    )
    monkeypatch.setattr(
        "sequence_visualiser.pdf_renderer.pdfmetrics.stringWidth",
        _string_width_stub,
    )
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    font_names = {name for name, _size in fake.set_font_calls}
    assert any(name.startswith("sv_header_regular_") for name in font_names)
    assert any(name.startswith("sv_course_codes_regular_") for name in font_names)
    assert any(name.startswith("sv_footer_regular_") for name in font_names)
    assert any(name.startswith("sv_body_regular_") for name in font_names)
    assert any(name.startswith("sv_body_bold_") for name in font_names)

    header_font_sizes = [
        size
        for name, size in fake.set_font_calls
        if name.startswith("sv_header_regular_")
    ]
    assert any(size <= 13 for size in header_font_sizes)


def test_render_pdf_warns_and_falls_back_when_font_missing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_left_lines": ["UNSW Sydney"],
                "header_right_lines": ["Program"],
                "fonts": {
                    "header": {
                        "regular": "fonts/does-not-exist.ttf",
                    }
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    warnings: list[str] = []

    def _capture_warning(msg: str, *args: object, **kwargs: object) -> None:
        _ = kwargs
        warnings.append(msg % args)

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr("sequence_visualiser.pdf_renderer.logger.warning", _capture_warning)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert any("header.regular" in warning for warning in warnings)
    # Fallback for header regular is body regular -> built-in Helvetica.
    assert any(name == "Helvetica" for name, _size in fake.set_font_calls)


def test_render_pdf_warns_and_falls_back_when_font_registration_fails(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    font_dir = tmp_path / "assets" / "fonts"
    font_dir.mkdir(parents=True)
    # Content does not matter here because TTFont is monkeypatched to fail.
    (font_dir / "Clancy-Regular.otf").write_bytes(b"otf")

    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_left_lines": ["UNSW Sydney"],
                "header_right_lines": ["Program"],
                "fonts": {
                    "header": {
                        "regular": "fonts/Clancy-Regular.otf",
                    }
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    warnings: list[str] = []

    def _capture_warning(msg: str, *args: object, **kwargs: object) -> None:
        _ = kwargs
        warnings.append(msg % args)

    def _raise_ttf_error(_alias: str, _path: str) -> object:
        raise TTFError("postscript outlines are not supported")

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    monkeypatch.setattr("sequence_visualiser.pdf_renderer.TTFont", _raise_ttf_error)
    monkeypatch.setattr("sequence_visualiser.pdf_renderer.logger.warning", _capture_warning)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert any("failed to register" in warning for warning in warnings)
    assert any(name == "Helvetica" for name, _size in fake.set_font_calls)


def test_render_pdf_header_background_spans_page_and_disclaimer_is_below(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_background_color": "#112233",
                "header_height_mm": 25,
                "top_disclaimer": "Disclaimer outside header",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    page_width, page_height = fake.pagesize
    header_height = 25 * mm
    header_bottom = page_height - header_height

    assert any(
        rect[0] == 0
        and abs(rect[1] - header_bottom) < 1e-6
        and abs(rect[2] - page_width) < 1e-6
        and abs(rect[3] - header_height) < 1e-6
        and rect[4] == 1
        for rect in fake.rect_calls
    )

    disclaimer = next(
        item for item in fake.drawn_text if item[2] == "Disclaimer outside header"
    )
    assert disclaimer[1] < header_bottom


def test_render_pdf_header_bottom_spacing_pushes_disclaimer_down(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "header_height_mm": 25,
                "header_bottom_spacing_mm": 8,
                "top_disclaimer": "Disclaimer with spacing",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    _page_width, page_height = fake.pagesize
    header_bottom = page_height - (25 * mm)
    disclaimer = next(item for item in fake.drawn_text if item[2] == "Disclaimer with spacing")

    # y = (header_bottom - spacing) - font_size
    expected_y = (header_bottom - (8 * mm)) - 8
    assert abs(disclaimer[1] - expected_y) < 1e-6


def test_render_pdf_period_label_y_offset_moves_label_down(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T2.json"
    term2_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 2",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )

    base_context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T2",
            courses=[term2_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={"pdf": {"period_label_y_offset_pt": 20}},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 2", courses=[term2_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    lower_context = RenderContext(
        plan=base_context.plan,
        rule_metadata=base_context.rule_metadata,
        tweaks={"pdf": {"period_label_y_offset_pt": 26}},
        years=base_context.years,
        plan_code=base_context.plan_code,
        specialisation_code=base_context.specialisation_code,
        degree_code=base_context.degree_code,
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)

    render_pdf(base_context, tmp_path / "base.pdf", tmp_path)
    base_fake = _FakeCanvas.last
    assert base_fake is not None
    base_label_y = next(item[1] for item in base_fake.drawn_text if item[2] == "Term 2")

    render_pdf(lower_context, tmp_path / "lower.pdf", tmp_path)
    lower_fake = _FakeCanvas.last
    assert lower_fake is not None
    lower_label_y = next(item[1] for item in lower_fake.drawn_text if item[2] == "Term 2")

    assert lower_label_y < base_label_y


def test_render_pdf_legacy_tokens_no_longer_expand(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "runtime": {"date": "2026-05-28", "year": "2026"},
            "pdf": {
                "footer_right": "Information correct as at {date}",
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Information correct as at {date}" in fake.drawn_strings
    assert "Information correct as at 2026-05-28" not in fake.drawn_strings


def test_render_pdf_second_page_renders_info_and_disclaimer_boxes(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=["Artificial Intelligence"],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "runtime": {"date": "2026-05-28", "year": "2026"},
            "pdf": {
                "header_left_lines": ["{{ tokens.university_name }}"],
                "header_right_lines": ["{{ tokens.program_name }}"],
                "second_page": {
                    "enabled": True,
                    "info_box_title": "Plan notes",
                    "info_box_text": "{% if tokens.intake_period == 'T1' %}Term-1 guidance for {{ tokens.program_code }}{% endif %}",
                    "bottom_disclaimer": "Bottom disclaimer for {{ tokens.plan_code }}",
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert fake.show_page_calls == 2
    assert "Plan notes" in fake.drawn_strings
    assert "Term-1 guidance for 3707" in fake.drawn_strings
    assert "Bottom disclaimer for CEICAH3707" in fake.drawn_strings
    assert fake.drawn_strings.count("UNSW Sydney") >= 2


def test_render_pdf_second_page_preserves_blank_line_spacing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "second_page": {
                    "enabled": True,
                    "info_box_title": "Spacing check",
                    "info_box_text": "Line A\n\nLine B",
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert fake.show_page_calls == 2

    line_a = [item for item in fake.drawn_text if item[2] == "Line A"]
    line_b = [item for item in fake.drawn_text if item[2] == "Line B"]
    assert line_a
    assert line_b

    # Blank line should create one additional line-height gap between adjacent lines.
    y_gap = line_a[0][1] - line_b[0][1]
    assert abs(y_gap - 24) < 1e-6


def test_render_pdf_second_page_top_disclaimer_can_be_overridden(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "top_disclaimer": "First page disclaimer",
                "second_page": {
                    "enabled": True,
                    "top_disclaimer": "Second page disclaimer",
                    "info_box_text": "Info text",
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert fake.drawn_strings.count("First page disclaimer") == 1
    assert fake.drawn_strings.count("Second page disclaimer") == 1


def test_render_pdf_second_page_top_disclaimer_can_be_suppressed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    term1_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Term 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[term1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
            program_id="3707",
        ),
        tweaks={
            "branding": {"university_name": "UNSW Sydney"},
            "pdf": {
                "top_disclaimer": "First page disclaimer",
                "second_page": {
                    "enabled": True,
                    "top_disclaimer": "",
                    "info_box_text": "Info text",
                },
            },
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Term 1", courses=[term1_course])],
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert fake.drawn_strings.count("First page disclaimer") == 1


def test_render_pdf_renders_extended_model_period_headers(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2028_S1.json"
    sem1_course = Course(
        enrol_year="Year 1",
        year=2028,
        period="Semester 1",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2028 S1",
            courses=[sem1_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2028",
            validity_to="2030",
        ),
        tweaks={},
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2028,
                calendar_type="semester",
                periods=[PeriodLayout(period="Semester 1", courses=[sem1_course])],
                calendar_family="semesters",
                calendar_model="semesters_extended",
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None
    assert "Summer Term" not in fake.drawn_strings
    assert "Winter Term" not in fake.drawn_strings
    assert "Semester 1" in fake.drawn_strings


def test_render_pdf_uses_model_colour_overrides_before_terms(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    summer_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Summer Term",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[summer_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "pdf": {
                "colours": {
                    "models": {
                        "trimesters_extended": {
                            "periods": {"Summer Term": "#11aa22"}
                        }
                    },
                    "terms": {"Summer Term": "#2211aa"},
                }
            }
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Summer Term", courses=[summer_course])],
                calendar_family="trimesters",
                calendar_model="trimesters_extended",
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    def _is_expected_model_green(fill: object) -> bool:
        red = getattr(fill, "red", None)
        green = getattr(fill, "green", None)
        blue = getattr(fill, "blue", None)
        if red is None or green is None or blue is None:
            return False
        return (
            abs(float(red) - (17 / 255)) < 1e-6
            and abs(float(green) - (170 / 255)) < 1e-6
            and abs(float(blue) - (34 / 255)) < 1e-6
        )

    assert any(_is_expected_model_green(fill) for fill in fake.fill_color_calls)


def test_render_pdf_falls_back_to_terms_when_model_period_missing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "CEICAH3707_2026_T1.json"
    summer_course = Course(
        enrol_year="Year 1",
        year=2026,
        period="Summer Term",
        course_n="Course 1",
        code="MATH1131",
        title="Math",
        uoc=6,
        prerequisites=".",
    )
    context = RenderContext(
        plan=Plan(
            sheet="CEICAH3707",
            program="CEICAH3707",
            career="Undergraduate",
            uoc=192,
            intake="2026 T1",
            courses=[summer_course],
            source_path=plan_path,
        ),
        rule_metadata=RuleMetadata(
            rule_file=Path("rules/3707-3778.json"),
            program_name="Bachelor of Advanced Computing",
            specialisation_names=[],
            validity_from="2026",
            validity_to="2028",
        ),
        tweaks={
            "pdf": {
                "colours": {
                    "models": {
                        "trimesters_extended": {
                            "periods": {"Term 1": "#11aa22"}
                        }
                    },
                    "terms": {"Summer Term": "#2211aa"},
                }
            }
        },
        years=[
            YearLayout(
                enrol_year="Year 1",
                year=2026,
                calendar_type="term",
                periods=[PeriodLayout(period="Summer Term", courses=[summer_course])],
                calendar_family="trimesters",
                calendar_model="trimesters_extended",
            )
        ],
        plan_code="CEICAH3707",
        specialisation_code="3778",
        degree_code="3707",
    )

    monkeypatch.setattr("sequence_visualiser.pdf_renderer.canvas.Canvas", _FakeCanvas)
    render_pdf(context, tmp_path / "out-fallback.pdf", tmp_path)

    fake = _FakeCanvas.last
    assert fake is not None

    def _is_expected_terms_blue(fill: object) -> bool:
        red = getattr(fill, "red", None)
        green = getattr(fill, "green", None)
        blue = getattr(fill, "blue", None)
        if red is None or green is None or blue is None:
            return False
        return (
            abs(float(red) - (34 / 255)) < 1e-6
            and abs(float(green) - (17 / 255)) < 1e-6
            and abs(float(blue) - (170 / 255)) < 1e-6
        )

    assert any(_is_expected_terms_blue(fill) for fill in fake.fill_color_calls)
