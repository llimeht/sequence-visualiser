from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import cast

from .models import RenderContext


def runtime_token_values(
    context: RenderContext, university_name: str
) -> dict[str, str]:
    """Return shared token values used by renderers and templates."""
    runtime = context.tweaks.get("runtime", {})
    runtime_mapping = cast(dict[str, object], runtime) if isinstance(runtime, dict) else {}
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
    majors_text = (
        ", ".join(context.rule_metadata.specialisation_names)
        if context.rule_metadata.specialisation_names
        else "None"
    )
    return {
        "date": date_value,
        "year": year_value,
        "university_name": university_name,
        "plan_code": context.plan_code,
        "plan_description": context.rule_metadata.plan_description,
        "plan_description_short": context.rule_metadata.plan_description,
        "program_code": program_id_value,
        "program_id": program_id_value,
        "intake": intake_value,
        "intake_year": intake_year_value,
        "intake.year": intake_year_value,
        "intake_period": intake_period_value,
        "intake.period": intake_period_value,
        "program_name": context.rule_metadata.program_name,
        "majors": majors_text,
        "degree_code": program_id_value,
        "specialisation_code": context.specialisation_code,
        "specialisation_codes": specialisation_codes_text,
        "rule_file": context.rule_metadata.rule_file.name,
    }


def expand_tokens_with_values(text: str, tokens: Mapping[str, str]) -> str:
    """Expand supported {token} placeholders in text."""
    expanded = text
    for token, value in tokens.items():
        expanded = expanded.replace(f"{{{token}}}", value)
    return expanded


def expand_runtime_tokens(
    text: str, context: RenderContext, university_name: str
) -> str:
    """Expand shared runtime and branding tokens from render context."""
    return expand_tokens_with_values(text, runtime_token_values(context, university_name))