"""
sequence_visualiser.rules_resolver
==================================
Resolves rules metadata and program identity for plans. Handles rules file selection
and extraction of program/specialisation codes and validity periods.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .models import Plan, RuleMetadata

_RULE_FILE_RE = re.compile(
    r"^(?P<code>[^.]+?)(?:-(?P<from>\d{4})-(?P<to>\d{4}))?\.json$"
)
_PROGRAM_RE = re.compile(r"^(?P<specialisation>[A-Z]{4}[A-Z0-9]{2})(?P<degree>\d{4})$")
_COMPOSITE_PROGRAM_RE = re.compile(
    r"^(?P<left>[A-Z]{4}[A-Z0-9]{2}(?P<degree>\d{4}))\+(?P<right>[A-Z]{4}[A-Z0-9]{2}(?P=degree))$"
)


class RuleResolutionError(ValueError):
    """Raised when no suitable rule file can be found for a plan."""


@dataclass(frozen=True)
class ProgramIdentity:
    """Identifies a program by plan, specialisation, and degree codes."""

    plan_code: str
    specialisation_code: str
    degree_code: str


def _identity_from_plan_code(candidate: str) -> ProgramIdentity | None:
    """Build ProgramIdentity from a candidate plan code string, if valid."""
    normalized = re.sub(r"\s+", "", candidate).upper()

    match = _PROGRAM_RE.match(normalized)
    if match:
        return ProgramIdentity(
            plan_code=normalized,
            specialisation_code=match.group("specialisation"),
            degree_code=match.group("degree"),
        )

    composite_match = _COMPOSITE_PROGRAM_RE.match(normalized)
    if composite_match:
        left_code = composite_match.group("left")
        return ProgramIdentity(
            plan_code=normalized,
            specialisation_code=left_code[:-4],
            degree_code=composite_match.group("degree"),
        )

    return None


def extract_program_identity(plan: Plan) -> ProgramIdentity:
    """Extract program, specialisation, and degree codes from a plan.

    Args:
        plan: Plan object to extract identity from.
    Returns:
        ProgramIdentity with codes.
    Raises:
        RuleResolutionError: If identity cannot be derived from plan data.
    """
    candidates = [
        plan.program.strip(),
        plan.sheet.strip(),
        plan.source_path.stem.split("_")[0],
    ]
    for candidate in candidates:
        identity = _identity_from_plan_code(candidate)
        if identity is not None:
            return identity
    raise RuleResolutionError(
        f"Cannot derive program identity from program='{plan.program}' sheet='{plan.sheet}'"
    )


def _parse_intake_year(intake: str) -> int:
    """Extract the intake year as an integer from a string."""
    match = re.search(r"(\d{4})", intake)
    if not match:
        raise RuleResolutionError(f"Cannot parse intake year from '{intake}'")
    return int(match.group(1))


def _load_rule_metadata(rule_file: Path) -> RuleMetadata:
    """Load and validate a rules file, returning RuleMetadata."""
    payload_raw = json.loads(rule_file.read_text(encoding="utf-8"))
    if not isinstance(payload_raw, Mapping):
        raise RuleResolutionError(f"Rules file {rule_file} must contain a JSON object")
    payload = cast(Mapping[str, Any], payload_raw)

    specialisation_names: list[str] = []
    specialisations = payload.get("specialisations")
    if isinstance(specialisations, list):
        specialisations_list = cast(list[object], specialisations)
        for item in specialisations_list:
            if isinstance(item, Mapping):
                specialisation_names.append(
                    str(cast(Mapping[str, Any], item).get("name", ""))
                )

    program_name = ""
    program_id = ""
    program_payload = payload.get("program")
    if isinstance(program_payload, Mapping):
        typed_program = cast(Mapping[str, Any], program_payload)
        program_name = str(typed_program.get("name", ""))
        program_id = str(typed_program.get("id", ""))

    validity_payload = payload.get("validity")
    validity: Mapping[str, Any] = (
        cast(Mapping[str, Any], validity_payload)
        if isinstance(validity_payload, Mapping)
        else cast(Mapping[str, Any], {})
    )
    validity_from = str(validity.get("from", ""))
    validity_to = str(validity.get("to", ""))

    return RuleMetadata(
        rule_file=rule_file,
        program_name=program_name,
        specialisation_names=specialisation_names,
        validity_from=validity_from,
        validity_to=validity_to,
        program_id=program_id,
    )


def resolve_rule_metadata(
    plan: Plan, rules_dir: Path
) -> tuple[ProgramIdentity, RuleMetadata]:
    """Select the best rules file for a plan and return its metadata.

    Args:
        plan: Plan object to resolve rules for.
        rules_dir: Directory containing rules files.
    Returns:
        Tuple of (ProgramIdentity, RuleMetadata).
    Raises:
        RuleResolutionError: If no suitable rules file is found.
    """
    for direct_candidate in (
        plan.sheet.strip(),
        plan.source_path.stem.split("_")[0],
        plan.program.strip(),
    ):
        direct_identity = _identity_from_plan_code(direct_candidate)
        if direct_identity is None:
            continue

        exact_rule = rules_dir / f"{direct_identity.plan_code}.json"
        if exact_rule.exists():
            return direct_identity, _load_rule_metadata(exact_rule)

    identity = extract_program_identity(plan)
    intake_year = _parse_intake_year(plan.intake)

    candidates: list[tuple[Path, int]] = []
    for rule_path in sorted(rules_dir.glob("*.json")):
        match = _RULE_FILE_RE.match(rule_path.name)
        if not match:
            continue
        code = match.group("code")
        year_from = match.group("from")
        year_to = match.group("to")

        if code != identity.plan_code:
            continue

        if year_from is None or year_to is None:
            candidates.append((rule_path, 1_000_000))
            continue

        start = int(year_from)
        end = int(year_to)
        if start <= intake_year <= end:
            span = end - start
            candidates.append((rule_path, span))

    if not candidates:
        raise RuleResolutionError(
            f"No matching rules file found for {identity.plan_code} (intake {intake_year})"
        )

    selected = sorted(candidates, key=lambda item: item[1])[0][0]
    return identity, _load_rule_metadata(selected)
