from __future__ import annotations

import re
from dataclasses import dataclass

from markupsafe import Markup, escape


_BOLD_TAG_PATTERN = re.compile(r"</?b>", re.IGNORECASE)


@dataclass(frozen=True)
class TextRun:
    text: str
    bold: bool = False


@dataclass(frozen=True)
class ParsedInlineBold:
    runs: list[TextRun]
    warnings: list[str]


def parse_inline_bold_with_warnings(text: str) -> ParsedInlineBold:
    """Parse <b>...</b> runs and return any malformed-tag warnings."""
    if not text:
        return ParsedInlineBold(runs=[], warnings=[])

    parts: list[TextRun] = []
    warnings: list[str] = []
    current_bold = False
    cursor = 0

    for match in _BOLD_TAG_PATTERN.finditer(text):
        chunk = text[cursor:match.start()]
        if chunk:
            parts.append(TextRun(chunk, current_bold))

        tag = match.group(0).lower()
        if tag == "<b>":
            if current_bold:
                warnings.append("Nested or repeated <b> opening tag found; rendering text literally")
                return ParsedInlineBold(runs=[TextRun(text)], warnings=warnings)
            current_bold = True
        else:
            if not current_bold:
                warnings.append("Closing </b> tag without matching opening <b>; rendering text literally")
                return ParsedInlineBold(runs=[TextRun(text)], warnings=warnings)
            current_bold = False
        cursor = match.end()

    tail = text[cursor:]
    if tail:
        parts.append(TextRun(tail, current_bold))

    if current_bold:
        warnings.append("Unclosed <b> tag found; rendering text literally")
        return ParsedInlineBold(runs=[TextRun(text)], warnings=warnings)

    merged: list[TextRun] = []
    for part in parts:
        if not part.text:
            continue
        if merged and merged[-1].bold == part.bold:
            previous = merged[-1]
            merged[-1] = TextRun(previous.text + part.text, previous.bold)
        else:
            merged.append(part)
    return ParsedInlineBold(runs=merged, warnings=warnings)


def parse_inline_bold(text: str) -> list[TextRun]:
    """Parse <b>...</b> runs; malformed markup is returned as plain text.

    Only <b> and </b> are recognised. Any malformed sequence (for example stray
    closing tags or unclosed opening tags) is treated as literal text.
    """
    return parse_inline_bold_with_warnings(text).runs


def render_inline_bold_html(text: str) -> Markup:
    """Render parsed <b>...</b> runs as safe HTML markup.

    Plain text is always escaped. Bold runs are wrapped in <strong> tags.
    """
    runs = parse_inline_bold(text)
    if not runs:
        return Markup("")

    output: list[str] = []
    for run in runs:
        escaped = escape(run.text)
        if run.bold:
            output.append(f"<strong>{escaped}</strong>")
        else:
            output.append(str(escaped))
    return Markup("".join(output))