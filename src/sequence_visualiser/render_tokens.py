from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from datetime import date
from typing import cast
from urllib.parse import urlparse

from jinja2 import Environment, StrictUndefined

from .course_overrides import resolve_course_override
from .models import Course, RenderContext


logger = logging.getLogger(__name__)
_ALLOWED_COURSE_LINK_SCHEMES = frozenset({"http", "https"})
_CANONICAL_COURSE_CODE_PATTERN = re.compile(r"^[A-Z]{4}\d{4}$")


class TokenExpansionError(ValueError):
    """Raised when text still contains unexpanded token placeholders."""


_BRACE_TOKEN_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _coerce_int_if_decimal(value: str) -> str | int:
    """Return an int for decimal text, otherwise return the original string."""
    stripped = value.strip()
    return int(stripped) if stripped.isdecimal() else value


def _notes_token_values(context: RenderContext) -> dict[str, str]:
    notes = context.plan.notes if isinstance(context.plan.notes, dict) else {}

    def _string_value(field_name: str) -> str:
        value = notes.get(field_name, "")
        return str(value).strip() if value is not None else ""

    def _list_value(field_name: str) -> str:
        value = notes.get(field_name)
        if not isinstance(value, list):
            return ""
        items = cast(list[object], value)
        return "\n".join(str(item).strip() for item in items if str(item).strip())

    return {
        "notes_graduate_outcome": _string_value("graduate_outcome"),
        "notes_adjustment_type": _string_value("adjustment_type"),
        "notes_for_reviewers": _list_value("for_reviewers"),
        "notes_for_students": _list_value("for_students"),
    }


def runtime_token_values(
    context: RenderContext, university_name: str
) -> dict[str, object]:
    """Return shared token values used by renderers and templates."""
    runtime = context.tweaks.get("runtime", {})
    runtime_mapping: dict[str, object] = (
        {str(key): value for key, value in cast(dict[object, object], runtime).items()}
        if isinstance(runtime, dict)
        else {}
    )
    date_value = str(runtime_mapping.get("date", "")).strip() or date.today().isoformat()
    year_value = str(runtime_mapping.get("year", "")).strip() or date_value[:4]
    intake_value = context.plan.intake.strip()
    intake_parts = intake_value.split(maxsplit=1)
    intake_year_value = intake_parts[0] if intake_parts else ""
    intake_period_value = intake_parts[1] if len(intake_parts) > 1 else ""
    program_id_value = context.rule_metadata.program_id or context.degree_code
    specialisation_codes_text = (
        ", ".join(context.specialisation_codes)
        if context.specialisation_codes
        else context.specialisation_code
    )
    majors_text = ", ".join(context.rule_metadata.specialisation_names)
    return {
        "date": date_value,
        "year": _coerce_int_if_decimal(year_value),
        "university_name": university_name,
        "plan_code": context.plan_code,
        "plan_description": context.rule_metadata.plan_description,
        "plan_description_short": context.rule_metadata.plan_description,
        "program_code": _coerce_int_if_decimal(program_id_value),
        "program_id": _coerce_int_if_decimal(program_id_value),
        "intake": intake_value,
        "intake_year": _coerce_int_if_decimal(intake_year_value),
        "intake_period": intake_period_value,
        "program_name": context.rule_metadata.program_name,
        "majors": majors_text,
        "degree_code": program_id_value,
        "specialisation_code": context.specialisation_code,
        "specialisation_codes": specialisation_codes_text,
        "rule_file": context.rule_metadata.rule_file.name,
        **_notes_token_values(context),
    }


def expand_tokens_with_values(text: str, tokens: Mapping[str, object]) -> str:
    """Expand supported {token} placeholders in text."""
    expanded = text
    for token, value in tokens.items():
        expanded = expanded.replace(f"{{{token}}}", str(value))

    unresolved: set[str] = set()
    unresolved.update(match.group(0) for match in _BRACE_TOKEN_PATTERN.finditer(expanded))
    if unresolved:
        unresolved_list = ", ".join(sorted(unresolved))
        raise TokenExpansionError(f"Unexpanded token placeholder(s): {unresolved_list}")

    return expanded


def expand_runtime_tokens(
    text: str, context: RenderContext, university_name: str
) -> str:
    """Expand shared runtime and branding tokens from render context."""
    return expand_tokens_with_values(text, runtime_token_values(context, university_name))


def _safe_course_link_or_none(url: str) -> str | None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in _ALLOWED_COURSE_LINK_SCHEMES:
        return None
    if not parsed.netloc:
        return None
    return url


def render_course_link_url(
    template_text: str,
    *,
    context: RenderContext,
    course: Course,
    tokens: Mapping[str, object],
) -> str | None:
    """Render and validate a per-course handbook URL from a Jinja template."""
    if not template_text.strip():
        return None

    display_title = (
        course.title if course.uoc == 6 else f"{course.title} ({course.uoc} UoC)"
    )
    template_context: dict[str, object] = {
        "plan": context.plan,
        "course": course,
        "rule": context.rule_metadata,
        "years": context.years,
        "tweaks": context.tweaks,
        "tokens": dict(tokens),
        "career": context.plan.career,
        "code": course.code,
        "title": course.title,
        "uoc": course.uoc,
        "display_title": display_title,
        "plan_code": context.plan_code,
        "program_code": context.rule_metadata.program_id or context.degree_code,
        "specialisation_code": context.specialisation_code,
        "degree_code": context.degree_code,
    }

    env = Environment(autoescape=False, undefined=StrictUndefined)
    try:
        rendered = env.from_string(template_text).render(**template_context)
    except Exception as exc:  # pragma: no cover - depends on Jinja internals.
        raise TokenExpansionError(f"Invalid course link template: {exc}") from exc

    url = str(rendered).strip()
    if not url:
        return None

    safe_url = _safe_course_link_or_none(url)
    if safe_url is None:
        logger.warning(
            "Course link URL omitted for %s due to unsupported URL: %s",
            course.code,
            url,
        )
        return None
    return safe_url


def _override_namespace_candidates(context: RenderContext) -> list[str]:
    return [
        context.plan_code,
        *context.specialisation_codes,
        context.degree_code,
    ]


def resolve_course_handbook_link(
    template_text: str,
    *,
    context: RenderContext,
    course: Course,
    tokens: Mapping[str, object],
) -> str | None:
    """Resolve handbook link URL using override semantics and fallback rules."""
    override_entry = resolve_course_override(
        course.code,
        context.course_overrides,
        namespace_candidates=_override_namespace_candidates(context),
    )

    if override_entry is not None:
        raw_override_value = override_entry.get("handbook_link")
        if raw_override_value is True:
            return render_course_link_url(
                template_text,
                context=context,
                course=course,
                tokens=tokens,
            )
        if isinstance(raw_override_value, str):
            explicit_url = raw_override_value.strip()
            if not explicit_url:
                return None
            if explicit_url.startswith(("http://", "https://")):
                safe_url = _safe_course_link_or_none(explicit_url)
                if safe_url is not None:
                    return safe_url
                logger.warning(
                    "Course link override ignored for %s due to invalid explicit URL: %s",
                    course.code,
                    explicit_url,
                )
                return None
            logger.warning(
                "Course link override for %s must be true or a valid http(s) URL; received: %s",
                course.code,
                explicit_url,
            )
            return None
        if raw_override_value:
            logger.warning(
                "Course link override for %s must be true or a valid http(s) URL; received type %s",
                course.code,
                type(raw_override_value).__name__,
            )
            return None
        return None

    if not template_text.strip():
        return None

    if not _CANONICAL_COURSE_CODE_PATTERN.fullmatch(course.code.strip().upper()):
        return None

    return render_course_link_url(
        template_text,
        context=context,
        course=course,
        tokens=tokens,
    )
