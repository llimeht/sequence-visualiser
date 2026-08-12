from __future__ import annotations

import re
from html import unescape
from dataclasses import dataclass
from urllib.parse import urlparse

from markupsafe import Markup, escape


_TAG_PATTERN = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_SIMPLE_OPEN_TAG_PATTERN = re.compile(r"<\s*(b|i)\s*>", re.IGNORECASE)
_CLOSE_TAG_PATTERN = re.compile(r"<\s*/\s*(b|i|a)\s*>", re.IGNORECASE)
_ANCHOR_OPEN_TAG_PATTERN = re.compile(r"<\s*a\s+([^>]*)>", re.IGNORECASE)
_ATTRIBUTE_PATTERN = re.compile(
    r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(\"[^\"]*\"|'[^']*')"
)
_BLANK_LINE_RUN_PATTERN = re.compile(r"\n(?:[ \t\f\v]*\n)+")
_ALLOWED_URL_SCHEMES = frozenset({"http", "https", "mailto"})


@dataclass(frozen=True)
class TextRun:
    text: str
    bold: bool = False
    italic: bool = False
    href: str | None = None


@dataclass(frozen=True)
class ParsedInlineMarkup:
    runs: list[TextRun]
    warnings: list[str]


@dataclass(frozen=True)
class ParsedInlineBold:
    """Backward-compatible alias for code paths still referring to bold-only parsing."""

    runs: list[TextRun]
    warnings: list[str]


def _literal_result(text: str, warning: str | None = None) -> ParsedInlineMarkup:
    warnings = [warning] if warning else []
    return ParsedInlineMarkup(runs=[TextRun(text)], warnings=warnings)


def _parse_anchor_attributes(attribute_text: str) -> str | None:
    cursor = 0
    href: str | None = None
    for match in _ATTRIBUTE_PATTERN.finditer(attribute_text):
        gap = attribute_text[cursor : match.start()]
        if gap.strip():
            return None
        attribute_name = match.group(1).lower()
        attribute_value = match.group(2)
        unquoted = attribute_value[1:-1]
        if attribute_name != "href" or href is not None:
            return None
        href = unquoted
        cursor = match.end()

    if attribute_text[cursor:].strip():
        return None
    return href


def _normalise_and_validate_href(raw_href: str) -> str | None:
    href = unescape(raw_href).strip()
    if not href:
        return None

    parsed = urlparse(href)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_URL_SCHEMES:
        return None

    if scheme in {"http", "https"} and not parsed.netloc:
        return None
    if scheme == "mailto" and not parsed.path:
        return None
    return href


def _merge_adjacent_runs(runs: list[TextRun]) -> list[TextRun]:
    merged: list[TextRun] = []
    for run in runs:
        if not run.text:
            continue
        if (
            merged
            and merged[-1].bold == run.bold
            and merged[-1].italic == run.italic
            and merged[-1].href == run.href
        ):
            previous = merged[-1]
            merged[-1] = TextRun(
                previous.text + run.text,
                bold=previous.bold,
                italic=previous.italic,
                href=previous.href,
            )
        else:
            merged.append(run)
    return merged


def _active_styles(stack: list[tuple[str, str | None]]) -> tuple[bool, bool, str | None]:
    bold = any(tag == "b" for tag, _href in stack)
    italic = any(tag == "i" for tag, _href in stack)
    href = next((href_value for tag, href_value in reversed(stack) if tag == "a"), None)
    return bold, italic, href


def parse_inline_markup_with_warnings(text: str) -> ParsedInlineMarkup:
    """Parse limited inline markup and return any malformed-tag warnings.

    Supported tags are <b>...</b>, <i>...</i>, and <a href="...">...</a>.
    Any malformed or unsupported markup is treated as literal text.
    """
    if not text:
        return ParsedInlineMarkup(runs=[], warnings=[])

    parts: list[TextRun] = []
    stack: list[tuple[str, str | None]] = []
    cursor = 0

    for match in _TAG_PATTERN.finditer(text):
        chunk = text[cursor:match.start()]
        if chunk:
            bold, italic, href = _active_styles(stack)
            parts.append(TextRun(chunk, bold=bold, italic=italic, href=href))

        tag = match.group(0)
        simple_open = _SIMPLE_OPEN_TAG_PATTERN.fullmatch(tag)
        close_tag = _CLOSE_TAG_PATTERN.fullmatch(tag)
        anchor_open = _ANCHOR_OPEN_TAG_PATTERN.fullmatch(tag)

        if simple_open:
            opened = simple_open.group(1).lower()
            stack.append((opened, None))
        elif anchor_open:
            if any(opened_tag == "a" for opened_tag, _href in stack):
                return _literal_result(text, "Nested or repeated <a> opening tag found; rendering text literally")

            href_raw = _parse_anchor_attributes(anchor_open.group(1))
            if href_raw is None:
                return _literal_result(text, "Invalid <a> attributes found; rendering text literally")

            href = _normalise_and_validate_href(href_raw)
            if href is None:
                return _literal_result(text, "Invalid or disallowed <a href> URL found; rendering text literally")
            stack.append(("a", href))
        elif close_tag:
            closing = close_tag.group(1).lower()
            if not stack:
                return _literal_result(
                    text,
                    f"Closing </{closing}> tag without matching opening <{closing}>; rendering text literally",
                )
            opened, _opened_href = stack[-1]
            if opened != closing:
                return _literal_result(text, "Mismatched closing tag order found; rendering text literally")
            stack.pop()
        else:
            return _literal_result(text, "Unsupported inline tag found; rendering text literally")
        cursor = match.end()

    tail = text[cursor:]
    if tail:
        bold, italic, href = _active_styles(stack)
        parts.append(TextRun(tail, bold=bold, italic=italic, href=href))

    if stack:
        unclosed_tag = stack[-1][0]
        return _literal_result(text, f"Unclosed <{unclosed_tag}> tag found; rendering text literally")

    return ParsedInlineMarkup(runs=_merge_adjacent_runs(parts), warnings=[])


def parse_inline_markup(text: str) -> list[TextRun]:
    """Parse limited inline markup; malformed markup is returned as plain text."""
    return parse_inline_markup_with_warnings(text).runs


def normalise_multiline_text(text: str) -> str:
    """Normalise newline separators for consistent paragraph and line-break rendering.

    Rules:
    - ``\n`` remains a single line break.
    - Any blank-line separator run (``\n\n``, ``\n \n``, ``\n\n\n``, etc.)
      collapses to exactly ``\n\n``.
    - ``\r\n`` and ``\r`` are converted to ``\n``.
    """
    if not text:
        return ""

    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    return _BLANK_LINE_RUN_PATTERN.sub("\n\n", normalised)


def render_inline_markup_html(text: str) -> Markup:
    """Render parsed limited inline markup as safe HTML markup."""
    runs = parse_inline_markup(text)
    if not runs:
        return Markup("")

    output: list[str] = []
    for run in runs:
        escaped_text = str(escape(run.text))
        if run.href:
            escaped_href = str(escape(run.href))
            escaped_text = f'<a href="{escaped_href}">{escaped_text}</a>'
        if run.italic:
            escaped_text = f"<em>{escaped_text}</em>"
        if run.bold:
            escaped_text = f"<strong>{escaped_text}</strong>"
        output.append(escaped_text)
    return Markup("".join(output))


def parse_inline_bold(text: str) -> list[TextRun]:
    """Parse <b>...</b> runs; malformed markup is returned as plain text.

    Only <b> and </b> are recognised. Any malformed sequence (for example stray
    closing tags or unclosed opening tags) is treated as literal text.
    """
    return parse_inline_markup_with_warnings(text).runs


def render_inline_bold_html(text: str) -> Markup:
    """Render parsed <b>...</b> runs as safe HTML markup.

    Plain text is always escaped. Bold runs are wrapped in <strong> tags.
    """
    return render_inline_markup_html(text)


def parse_inline_bold_with_warnings(text: str) -> ParsedInlineBold:
    """Backward-compatible wrapper around generic inline markup parsing."""
    parsed = parse_inline_markup_with_warnings(text)
    return ParsedInlineBold(runs=parsed.runs, warnings=parsed.warnings)
