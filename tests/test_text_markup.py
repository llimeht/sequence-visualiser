from sequence_visualiser.text_markup import (
    normalise_multiline_text,
    parse_inline_bold,
    parse_inline_bold_with_warnings,
    parse_inline_markup,
    parse_inline_markup_with_warnings,
    render_inline_bold_html,
    render_inline_markup_html,
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


def test_parse_inline_markup_supports_italic_and_links() -> None:
    runs = parse_inline_markup('Read <i>carefully</i> at <a href="https://example.edu">Handbook</a>')

    assert [
        (run.text, run.bold, run.italic, run.href)
        for run in runs
    ] == [
        ("Read ", False, False, None),
        ("carefully", False, True, None),
        (" at ", False, False, None),
        ("Handbook", False, False, "https://example.edu"),
    ]


def test_parse_inline_markup_treats_disallowed_href_as_literal() -> None:
    parsed = parse_inline_markup_with_warnings(
        '<a href="javascript:alert(1)">Bad</a>'
    )

    assert [(run.text, run.bold, run.italic, run.href) for run in parsed.runs] == [
        ('<a href="javascript:alert(1)">Bad</a>', False, False, None)
    ]
    assert parsed.warnings == ["Invalid or disallowed <a href> URL found; rendering text literally"]


def test_render_inline_markup_html_renders_strong_em_and_anchor() -> None:
    rendered = render_inline_markup_html(
        'Use <b><i>care</i></b> and <a href="https://example.edu">Guide & Tips</a>'
    )

    assert str(rendered) == (
        "Use <strong><em>care</em></strong> and "
        '<a href="https://example.edu">Guide &amp; Tips</a>'
    )


def test_normalise_multiline_text_collapses_blank_separator_variants() -> None:
    text = "Line A\n \nLine B\n\n\nLine C"

    assert normalise_multiline_text(text) == "Line A\n\nLine B\n\nLine C"


def test_normalise_multiline_text_converts_carriage_return_newlines() -> None:
    text = "Line A\r\nLine B\rLine C"

    assert normalise_multiline_text(text) == "Line A\nLine B\nLine C"


def test_normalise_multiline_text_preserves_single_line_breaks() -> None:
    text = "Line A\nLine B\nLine C"

    assert normalise_multiline_text(text) == text
