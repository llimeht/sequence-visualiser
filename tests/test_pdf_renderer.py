from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from sequence_visualiser.models import (
    Course,
    PeriodLayout,
    Plan,
    RenderContext,
    RuleMetadata,
    YearLayout,
)
from sequence_visualiser.pdf_renderer import build_pdf_metadata, render_pdf


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
        self.drawn_strings: list[str] = []
        self.drawn_text: list[tuple[float, float, str]] = []
        self.drawn_right_text: list[tuple[float, float, str]] = []
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
        _ = (width, height, preserveAspectRatio)

    def setFont(self, _name: str, _size: float) -> None:  # noqa: N802
        return

    def drawString(self, _x: float, _y: float, text: str) -> None:  # noqa: N802
        self.drawn_strings.append(text)
        self.drawn_text.append((_x, _y, text))

    def drawRightString(self, _x: float, _y: float, text: str) -> None:  # noqa: N802
        self.drawn_strings.append(text)
        self.drawn_right_text.append((_x, _y, text))

    def setStrokeColor(self, _value: object) -> None:  # noqa: N802
        return

    def setLineWidth(self, _value: float) -> None:  # noqa: N802
        return

    def setFillColor(self, _value: object) -> None:  # noqa: N802
        return

    def rect(
        self, x: float, y: float, width: float, height: float, fill: int = 0
    ) -> None:
        self.rect_calls.append((x, y, width, height, fill))

    def showPage(self) -> None:  # noqa: N802
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
                "top_disclaimer": "Guide only for {university_name} on {date}.",
                "footer_left": "Check handbook.",
                "footer_right": "Information correct as at {date}\\nCopyright © {university_name} {year}",
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
    assert "Guide only for UNSW Sydney on 2026-05-28." in fake.drawn_strings
    assert "Check handbook." in fake.drawn_strings
    assert any(
        "Information correct as at 2026-05-28" in text for text in fake.drawn_strings
    )
    assert any("Copyright © UNSW Sydney 2026" in text for text in fake.drawn_strings)
    assert fake.author.endswith("Information correct as at 2026-05-28")
    assert fake.creator.startswith("Copyright © 2026 UNSW Sydney / sequence-visualiser")


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
