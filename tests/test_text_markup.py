from sequence_visualiser.text_markup import (
    parse_inline_bold,
    parse_inline_bold_with_warnings,
    render_inline_bold_html,
)


def test_parse_inline_bold_splits_plain_and_bold_runs() -> None:
    runs = parse_inline_bold("Guide <b>important</b> text")

    assert [(run.text, run.bold) for run in runs] == [
        ("Guide ", False),
        ("important", True),
        (" text", False),
    ]


def test_parse_inline_bold_treats_malformed_markup_as_literal() -> None:
    runs = parse_inline_bold("Guide </b> text")

    assert [(run.text, run.bold) for run in runs] == [("Guide </b> text", False)]


def test_render_inline_bold_html_escapes_text_and_wraps_strong() -> None:
    rendered = render_inline_bold_html("Use <b>5 < 6</b> always")

    assert str(rendered) == "Use <strong>5 &lt; 6</strong> always"


def test_parse_inline_bold_with_warnings_reports_unclosed_tag() -> None:
    parsed = parse_inline_bold_with_warnings("Guide <b>important text")

    assert [(run.text, run.bold) for run in parsed.runs] == [
        ("Guide <b>important text", False)
    ]
    assert parsed.warnings == ["Unclosed <b> tag found; rendering text literally"]


def test_parse_inline_bold_with_warnings_reports_unmatched_closing_tag() -> None:
    parsed = parse_inline_bold_with_warnings("Guide </b> text")

    assert [(run.text, run.bold) for run in parsed.runs] == [("Guide </b> text", False)]
    assert parsed.warnings == [
        "Closing </b> tag without matching opening <b>; rendering text literally"
    ]
