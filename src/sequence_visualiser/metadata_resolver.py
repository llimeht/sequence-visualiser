"""
sequence_visualiser.metadata_resolver
==================================
Resolves rules metadata and program identity for plans. Handles rules file selection
and extraction of program/specialisation codes and validity periods.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
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
    specialisation_codes: list[str]


def _identity_from_plan_code(candidate: str) -> ProgramIdentity | None:
    """Build ProgramIdentity from a candidate plan code string, if valid."""
    normalized = re.sub(r"\s+", "", candidate).upper()

    match = _PROGRAM_RE.match(normalized)
    if match:
        specialisation_code = match.group("specialisation")
        degree_code = match.group("degree")
        return ProgramIdentity(
            plan_code=normalized,
            specialisation_code=specialisation_code,
            degree_code=degree_code,
            specialisation_codes=[specialisation_code],
        )

    composite_match = _COMPOSITE_PROGRAM_RE.match(normalized)
    if composite_match:
        left_code = composite_match.group("left")
        specialisation_code = left_code[:-4]
        degree_code = composite_match.group("degree")
        return ProgramIdentity(
            plan_code=normalized,
            specialisation_code=specialisation_code,
            degree_code=degree_code,
            specialisation_codes=[part[:-4] for part in normalized.split("+")],
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
    plan_description = str(payload.get("plan_description", "")).strip()

    return RuleMetadata(
        rule_file=rule_file,
        program_name=program_name,
        specialisation_names=specialisation_names,
        validity_from=validity_from,
        validity_to=validity_to,
        program_id=program_id,
        plan_description=plan_description,
    )


class MetadataSource(str, Enum):
    """Supported metadata source modes."""

    RULES = "rules"
    PLAN = "plan"
    SPREADSHEET = "spreadsheet"


def _parse_listish(value: object, field_name: str) -> list[str]:
    """Parse a list-like metadata field from JSON array or semicolon-delimited text."""
    if isinstance(value, list):
        items = cast(list[object], value)
        parsed = [text for item in items if (text := str(item).strip())]
        if parsed:
            return parsed
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RuleResolutionError(
                    f"Invalid {field_name}: expected JSON array or ';'-delimited text"
                ) from exc
            if isinstance(payload, list):
                items = cast(list[object], payload)
                parsed = [text for item in items if (text := str(item).strip())]
                if parsed:
                    return parsed
        parsed = [item.strip() for item in text.split(";") if item.strip()]
        if parsed:
            return parsed
    return []


def _program_id_from_metadata(metadata: Mapping[str, object]) -> str:
    """Resolve canonical program_id from metadata with degree_code alias compatibility."""
    program_id = str(metadata.get("program_id", "")).strip()
    degree_code_alias = str(metadata.get("degree_code", "")).strip()

    if program_id and degree_code_alias and program_id != degree_code_alias:
        raise RuleResolutionError(
            "program_id and degree_code must match when both are provided"
        )
    return program_id or degree_code_alias


def _identity_from_metadata_map(
    *,
    plan_code: str,
    specialisation_codes: list[str],
    program_id: str,
) -> ProgramIdentity:
    """Build ProgramIdentity from normalized metadata values."""
    primary_specialisation = specialisation_codes[0] if specialisation_codes else ""
    return ProgramIdentity(
        plan_code=plan_code,
        specialisation_code=primary_specialisation,
        degree_code=program_id,
        specialisation_codes=specialisation_codes,
    )


def _resolve_plan_embedded_metadata(plan: Plan) -> tuple[ProgramIdentity, RuleMetadata]:
    """Resolve metadata from plan.program_metadata block.

    Expects the nested format used in plan files::

        "program_metadata": {
            "plan_code": "CEICKS8338(48RPL)",
            "plan_description": "standard enrolment plan with 48 UoC of RPL",
            "program": {"id": "8338", "name": "Master of Engineering Science"},
            "specialisation": [
                {"id": "CEICKS", "name": "Chemical Engineering"}
            ]
        }
    """
    if not plan.program_metadata:
        raise RuleResolutionError(
            f"Plan {plan.source_path} missing program_metadata for metadata-source=plan"
        )
    metadata = cast(Mapping[str, object], plan.program_metadata)

    plan_code = str(metadata.get("plan_code", "")).strip()
    plan_description = str(metadata.get("plan_description", "")).strip()

    program_obj = metadata.get("program")
    program_id = ""
    program_name = ""
    if isinstance(program_obj, Mapping):
        typed_program = cast(Mapping[str, object], program_obj)
        program_id = str(typed_program.get("id", "")).strip()
        program_name = str(typed_program.get("name", "")).strip()

    specialisation_codes: list[str] = []
    specialisation_names: list[str] = []
    specialisation_raw = metadata.get("specialisation")
    if isinstance(specialisation_raw, list):
        for item in cast(list[object], specialisation_raw):
            if isinstance(item, Mapping):
                item_map = cast(Mapping[str, object], item)
                code = str(item_map.get("id", "")).strip()
                name = str(item_map.get("name", "")).strip()
                if code:
                    specialisation_codes.append(code)
                if name:
                    specialisation_names.append(name)

    missing: list[str] = []
    if not plan_code:
        missing.append("program_metadata.plan_code")
    if not program_id:
        missing.append("program_metadata.program.id")
    if not program_name:
        missing.append("program_metadata.program.name")
    if missing:
        raise RuleResolutionError(
            f"Missing embedded metadata keys in {plan.source_path}: {', '.join(missing)}"
        )

    identity = _identity_from_metadata_map(
        plan_code=plan_code,
        specialisation_codes=specialisation_codes,
        program_id=program_id,
    )
    metadata_payload = RuleMetadata(
        rule_file=plan.source_path,
        program_name=program_name,
        specialisation_names=specialisation_names,
        validity_from="",
        validity_to="",
        program_id=program_id,
        plan_description=plan_description,
    )
    return identity, metadata_payload


def _normalize_plan_filename_key(value: str) -> str:
    """Normalize spreadsheet plan key for robust lookups."""
    text = value.strip()
    if text.lower().endswith(".json"):
        text = text[:-5]
    return text.lower()


def _spreadsheet_row_for_plan(plan: Plan, mapping_path: Path) -> Mapping[str, object]:
    """Load mapping CSV/TSV and return matched row for this plan."""
    if not mapping_path.exists():
        raise RuleResolutionError(f"Spreadsheet mapping file not found: {mapping_path}")

    delimiter = "\t" if mapping_path.suffix.lower() == ".tsv" else ","
    with mapping_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise RuleResolutionError(
                f"Spreadsheet mapping has no header row: {mapping_path}"
            )

        required = {
            "plan_filename",
            "plan_code",
            "program_id",
            "program_name",
            "specialisation_codes",
            "specialisation_names",
        }
        header = {name.strip() for name in reader.fieldnames if name}
        missing_columns = sorted(required.difference(header))
        if missing_columns:
            raise RuleResolutionError(
                f"Spreadsheet mapping missing required columns in {mapping_path}: "
                + ", ".join(missing_columns)
            )

        matches: list[Mapping[str, object]] = []
        target_keys = {
            _normalize_plan_filename_key(plan.source_path.stem),
            _normalize_plan_filename_key(plan.source_path.name),
        }
        for row in reader:
            plan_filename = str(row.get("plan_filename", ""))
            if _normalize_plan_filename_key(plan_filename) in target_keys:
                matches.append(cast(Mapping[str, object], row))

    if not matches:
        raise RuleResolutionError(
            f"No spreadsheet metadata row found for plan {plan.source_path.name}"
        )
    if len(matches) > 1:
        raise RuleResolutionError(
            f"Multiple spreadsheet metadata rows matched for plan {plan.source_path.name}"
        )
    return matches[0]


def _resolve_spreadsheet_metadata(
    plan: Plan, mapping_path: Path
) -> tuple[ProgramIdentity, RuleMetadata]:
    """Resolve metadata from spreadsheet mapping row."""
    row = _spreadsheet_row_for_plan(plan, mapping_path)

    plan_code = str(row.get("plan_code", "")).strip()
    program_id = _program_id_from_metadata(row)
    program_name = str(row.get("program_name", "")).strip()
    specialisation_codes = _parse_listish(
        row.get("specialisation_codes", ""), "specialisation_codes"
    )
    specialisation_names = _parse_listish(
        row.get("specialisation_names", ""), "specialisation_names"
    )
    plan_description = str(row.get("plan_description", "")).strip() or plan.plan_description

    missing: list[str] = []
    if not plan_code:
        missing.append("plan_code")
    if not program_id:
        missing.append("program_id")
    if not program_name:
        missing.append("program_name")
    if not specialisation_codes:
        missing.append("specialisation_codes")
    if not specialisation_names:
        missing.append("specialisation_names")
    if missing:
        raise RuleResolutionError(
            f"Missing required values in spreadsheet row for {plan.source_path.name}: "
            + ", ".join(missing)
        )

    identity = _identity_from_metadata_map(
        plan_code=plan_code,
        specialisation_codes=specialisation_codes,
        program_id=program_id,
    )
    metadata_payload = RuleMetadata(
        rule_file=mapping_path,
        program_name=program_name,
        specialisation_names=specialisation_names,
        validity_from="",
        validity_to="",
        program_id=program_id,
        plan_description=plan_description,
    )
    return identity, metadata_payload


def _with_plan_description_fallback(plan: Plan, metadata: RuleMetadata) -> RuleMetadata:
    """Use plan-level description when source metadata does not provide one."""
    if metadata.plan_description or not plan.plan_description:
        return metadata
    return RuleMetadata(
        rule_file=metadata.rule_file,
        program_name=metadata.program_name,
        specialisation_names=metadata.specialisation_names,
        validity_from=metadata.validity_from,
        validity_to=metadata.validity_to,
        program_id=metadata.program_id,
        plan_description=plan.plan_description,
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
            return direct_identity, _with_plan_description_fallback(
                plan, _load_rule_metadata(exact_rule)
            )

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
    return identity, _with_plan_description_fallback(plan, _load_rule_metadata(selected))


def resolve_metadata(
    *,
    plan: Plan,
    source: MetadataSource,
    rules_dir: Path,
    spreadsheet_path: Path | None = None,
) -> tuple[ProgramIdentity, RuleMetadata]:
    """Resolve metadata from the selected source mode."""
    if source is MetadataSource.RULES:
        return resolve_rule_metadata(plan, rules_dir)
    if source is MetadataSource.PLAN:
        return _resolve_plan_embedded_metadata(plan)
    if source is MetadataSource.SPREADSHEET:
        if spreadsheet_path is None:
            raise RuleResolutionError(
                "Spreadsheet metadata source requires --metadata-map"
            )
        return _resolve_spreadsheet_metadata(plan, spreadsheet_path)
    raise RuleResolutionError(f"Unsupported metadata source: {source}")
