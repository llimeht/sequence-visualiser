"""
sequence_visualiser.course_overrides
====================================
Handles loading and applying course overrides from JSON config files.
Used to patch or suppress course codes and titles in plan data.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .models import Course


class CourseOverrideError(ValueError):
    """Raised when a course-overrides file is malformed."""


def _load_file(path: Path) -> dict[str, dict[str, str]]:
    """Load and validate a course-overrides JSON file.

    Args:
        path: Path to the JSON file.
    Returns:
        Dictionary mapping course codes to override dicts.
    Raises:
        CourseOverrideError: If the file is malformed or entries are invalid.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CourseOverrideError(f"Invalid JSON in {path}") from exc
    if not isinstance(data, Mapping):
        raise CourseOverrideError(f"{path} must contain a JSON object")

    typed_data = {
        str(key): value for key, value in cast(Mapping[object, Any], data).items()
    }
    result: dict[str, dict[str, str]] = {}
    for raw_key, value in typed_data.items():
        if raw_key.startswith("_"):
            continue  # skip comment-style keys
        if not isinstance(value, Mapping):
            raise CourseOverrideError(
                f"Entry for {raw_key!r} in {path} must be a JSON object"
            )
        entry: dict[str, str] = {}
        for field, field_value in cast(Mapping[object, Any], value).items():
            if not isinstance(field, str):
                raise CourseOverrideError(
                    f"Entry keys for {raw_key!r} in {path} must be strings"
                )
            if not isinstance(field_value, str):
                raise CourseOverrideError(
                    f"Entry value for {raw_key!r}.{field} in {path} must be a string"
                )
            entry[field] = field_value
        result[raw_key.upper()] = entry
    return result


def load_course_overrides(
    config_dir: Path,
    local_config_dir: Path | None = None,
) -> dict[str, dict[str, str]]:
    """Load course-overrides.json, optionally overlaid with a local copy.

    The canonical file is ``config_dir / "course-overrides.json"``.
    If *local_config_dir* is given and contains its own ``course-overrides.json``,
    those entries are merged on top (local entries win on conflict).

    All keys are normalised to uppercase so matching is case-insensitive.
    """
    overrides: dict[str, dict[str, str]] = {}

    canonical = config_dir / "course-overrides.json"
    if canonical.exists():
        overrides.update(_load_file(canonical))

    if local_config_dir is not None:
        local = local_config_dir / "course-overrides.json"
        if local.exists():
            overrides.update(_load_file(local))

    return overrides


def apply_course_overrides(
    courses: list[Course],
    overrides: dict[str, dict[str, str]],
) -> list[Course]:
    """Return a new list with any matching courses substituted.

    Each override entry may contain:
    - ``"code"``: replacement course code (use ``""`` to suppress it)
    - ``"title"``: replacement display title

    Fields absent from the entry are left unchanged.
    """
    if not overrides:
        return courses

    result: list[Course] = []
    for course in courses:
        entry = overrides.get(course.code.upper())
        if entry is None:
            result.append(course)
        else:
            result.append(
                dataclasses.replace(
                    course,
                    code=entry.get("code", course.code),
                    title=entry.get("title", course.title),
                )
            )
    return result
