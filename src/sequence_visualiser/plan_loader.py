"""
sequence_visualiser.plan_loader
==============================
Loads and validates plan JSON files, converting them to Plan objects.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .models import Course, Plan


class PlanParseError(ValueError):
    """Raised when a plan file cannot be parsed."""


def _normalise_plan_notes(plan_path: Path, raw_notes: object) -> dict[str, Any] | None:
    if raw_notes is None:
        return None
    if not isinstance(raw_notes, Mapping):
        raise PlanParseError(f"Invalid notes in plan file {plan_path}: must be an object")

    raw_notes_mapping = cast(Mapping[object, object], raw_notes)
    notes: dict[str, Any] = {
        str(key): cast(Any, value) for key, value in raw_notes_mapping.items()
    }
    list_fields = ("for_reviewers", "for_students")
    for field_name in list_fields:
        field_value = notes.get(field_name)
        if field_value is None:
            continue
        if not isinstance(field_value, list):
            raise PlanParseError(
                f"Invalid notes.{field_name} in plan file {plan_path}: must be an array"
            )
        notes[field_name] = [
            str(item).strip() for item in cast(list[object], field_value)
        ]

    scalar_fields = ("graduate_outcome", "adjustment_type")
    for field_name in scalar_fields:
        field_value = notes.get(field_name)
        if field_value is None:
            continue
        notes[field_name] = str(field_value).strip()

    return notes


def load_plan(plan_path: Path) -> Plan:
    """Load and validate a plan JSON file, returning a Plan object.

    Args:
        plan_path: Path to the plan JSON file.
    Returns:
        Plan object parsed from the file.
    Raises:
        PlanParseError: If the file is missing, invalid, or incomplete.
    """
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanParseError(f"Plan file not found: {plan_path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"Invalid JSON in plan file: {plan_path}") from exc

    required_keys = {"sheet", "program", "career", "uoc", "intake", "courses"}
    missing = sorted(required_keys.difference(payload.keys()))
    if missing:
        raise PlanParseError(
            f"Missing keys in plan file {plan_path}: {', '.join(missing)}"
        )

    courses: list[Course] = []
    for index, raw in enumerate(payload["courses"], start=1):
        try:
            course = Course(
                enrol_year=str(raw["enrol_year"]).strip(),
                year=int(raw["year"]),
                period=str(raw["period"]).strip(),
                course_n=str(raw["course_n"]).strip(),
                code=str(raw["code"]).strip(),
                title=str(raw["title"]).strip(),
                uoc=int(raw["uoc"]),
                prerequisites=str(raw.get("prerequisites", "")).strip(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlanParseError(
                f"Invalid course entry at index {index} in {plan_path}: {exc}"
            ) from exc
        courses.append(course)

    program_metadata: dict[str, object] | None = None
    raw_program_metadata = payload.get("program_metadata")
    if raw_program_metadata is not None:
        if not isinstance(raw_program_metadata, Mapping):
            raise PlanParseError(
                f"Invalid program_metadata in plan file {plan_path}: must be an object"
            )
        raw_program_metadata_mapping = cast(Mapping[object, object], raw_program_metadata)
        program_metadata = {
            str(key): cast(Any, value)
            for key, value in raw_program_metadata_mapping.items()
        }

    notes = _normalise_plan_notes(plan_path, payload.get("notes"))

    return Plan(
        sheet=str(payload["sheet"]),
        program=str(payload["program"]),
        career=str(payload["career"]),
        uoc=int(payload["uoc"]),
        intake=str(payload["intake"]),
        plan_description=str(payload.get("plan_description", "")).strip(),
        notes=notes,
        courses=courses,
        source_path=plan_path,
        program_metadata=program_metadata,
    )


def load_catalogue(catalogue_path: Path) -> dict[str, dict[str, Any]]:
    """Load a catalogue JSON file, returning a dict keyed by course code.

    Args:
        catalogue_path: Path to the catalogue JSON file (flat array of course objects).
    Returns:
        Dict mapping course code to a dict with at least ``title`` and ``uoc`` keys.
    Raises:
        PlanParseError: If the file is missing, invalid JSON, or not a list.
    """
    try:
        payload = json.loads(catalogue_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanParseError(f"Catalogue file not found: {catalogue_path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanParseError(f"Invalid JSON in catalogue file: {catalogue_path}") from exc

    if not isinstance(payload, list):
        raise PlanParseError(
            f"Catalogue file {catalogue_path} must contain a JSON array at the top level"
        )

    catalogue: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(cast(list[Any], payload), start=1):
        if not isinstance(entry, Mapping):
            raise PlanParseError(
                f"Invalid entry at index {index} in catalogue {catalogue_path}: must be an object"
            )
        entry_mapping = cast(Mapping[str, Any], entry)
        code = str(entry_mapping.get("code", "")).strip().upper()
        if not code:
            continue
        catalogue[code] = {
            "title": str(entry_mapping.get("title", "")).strip(),
            "uoc": int(entry_mapping.get("uoc", 0) or 0),
        }

    return catalogue


def merge_catalogue_overrides(
    catalogue: dict[str, dict[str, Any]],
    overrides_path: Path,
) -> dict[str, dict[str, Any]]:
    """Merge a catalogue overrides file into an existing catalogue dict.

    The overrides file has the same format as the base catalogue (a flat JSON
    array of course objects).  For each entry in the overrides file:

    * If the course code already exists in *catalogue*, any non-empty ``title``
      and non-zero ``uoc`` values in the override entry replace the
      corresponding base values (field-level merge).
    * If the course code is new, the entry is added to *catalogue*.

    Args:
        catalogue: Existing catalogue dict (modified in-place and returned).
        overrides_path: Path to the overrides JSON file.
    Returns:
        The updated catalogue dict (same object as the input).
    Raises:
        PlanParseError: If the file is missing, invalid JSON, or not a list.
    """
    try:
        payload = json.loads(overrides_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PlanParseError(f"Catalogue overrides file not found: {overrides_path}") from exc
    except json.JSONDecodeError as exc:
        raise PlanParseError(
            f"Invalid JSON in catalogue overrides file: {overrides_path}"
        ) from exc

    if not isinstance(payload, list):
        raise PlanParseError(
            f"Catalogue overrides file {overrides_path} must contain a JSON array at the top level"
        )

    for index, entry in enumerate(cast(list[Any], payload), start=1):
        if not isinstance(entry, Mapping):
            raise PlanParseError(
                f"Invalid entry at index {index} in catalogue overrides {overrides_path}: "
                "must be an object"
            )
        entry_mapping = cast(Mapping[str, Any], entry)
        code = str(entry_mapping.get("code", "")).strip().upper()
        if not code:
            continue
        override_title = str(entry_mapping.get("title", "")).strip()
        override_uoc = int(entry_mapping.get("uoc", 0) or 0)
        if code in catalogue:
            if override_title:
                catalogue[code]["title"] = override_title
            if override_uoc:
                catalogue[code]["uoc"] = override_uoc
        else:
            catalogue[code] = {"title": override_title, "uoc": override_uoc}

    return catalogue


def enrich_courses_from_catalogue(
    courses: list[Course],
    catalogue: dict[str, dict[str, Any]],
) -> list[Course]:
    """Fill in missing ``title`` and ``uoc`` values from a catalogue lookup.

    Only fields that are considered missing (empty string for ``title``,
    zero for ``uoc``) are replaced.  Courses whose code is absent from the
    catalogue are left unchanged.

    Args:
        courses: List of Course objects to enrich.
        catalogue: Dict returned by :func:`load_catalogue`.
    Returns:
        A new list if any courses were enriched, otherwise the original list.
    """
    result: list[Course] = []
    changed = False
    for course in courses:
        entry = catalogue.get(course.code.strip().upper())
        if entry is None:
            result.append(course)
            continue
        needs_title = course.title == "" and entry["title"]
        needs_uoc = course.uoc == 0 and entry["uoc"]
        if needs_title or needs_uoc:
            patches: dict[str, Any] = {}
            if needs_title:
                patches["title"] = entry["title"]
            if needs_uoc:
                patches["uoc"] = entry["uoc"]
            result.append(dataclasses.replace(course, **patches))
            changed = True
        else:
            result.append(course)
    return result if changed else courses
