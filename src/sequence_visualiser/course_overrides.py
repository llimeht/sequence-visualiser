"""
sequence_visualiser.course_overrides
====================================
Handles loading and applying course overrides from JSON config files.
Used to patch or suppress course codes and titles in plan data.
"""

from __future__ import annotations

import dataclasses
import json
from collections import deque
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .models import Course


class CourseOverrideError(ValueError):
    """Raised when a course-overrides file is malformed."""


_NAMESPACE_SEPARATOR = "::"
_ALIASES_FIELD = "aliases"


def _normalise_override_key(key: str) -> str:
    """Normalise keys for case-insensitive matching."""
    return key.strip().upper()


def _expand_aliases(
    entries: dict[str, dict[str, str]],
    aliases_by_key: dict[str, list[str]],
    path: Path,
) -> dict[str, dict[str, str]]:
    """Expand alias keys into the override map with collision protection."""
    expanded = dict(entries)
    explicit_keys = set(entries)
    queue: deque[tuple[str, dict[str, str], list[str]]] = deque(
        (key, entry, aliases_by_key.get(key, [])) for key, entry in entries.items()
    )

    while queue:
        _source_key, entry, aliases = queue.popleft()
        if not aliases:
            continue
        for raw_alias in aliases:
            alias_key = _normalise_override_key(raw_alias)
            if not alias_key:
                continue
            if alias_key in explicit_keys:
                continue
            if alias_key in expanded:
                existing_entry = expanded[alias_key]
                if existing_entry is entry:
                    continue
                raise CourseOverrideError(
                    f"Alias {alias_key!r} in {path} maps to multiple entries"
                )
            expanded[alias_key] = entry
            queue.append((alias_key, entry, aliases))

    return expanded


def _build_override_lookup_keys(
    course_code: str,
    namespace_candidates: list[str] | None,
) -> list[str]:
    """Build lookup keys from most specific (namespaced) to plain code."""
    code_key = _normalise_override_key(course_code)
    keys: list[str] = []
    seen: set[str] = set()
    for namespace in namespace_candidates or []:
        namespace_key = _normalise_override_key(namespace)
        if not namespace_key:
            continue
        candidate = f"{namespace_key}{_NAMESPACE_SEPARATOR}{code_key}"
        if candidate not in seen:
            keys.append(candidate)
            seen.add(candidate)
    if code_key not in seen:
        keys.append(code_key)
    return keys


def resolve_course_override(
    course_code: str,
    overrides: dict[str, dict[str, str]],
    namespace_candidates: list[str] | None = None,
) -> dict[str, str] | None:
    """Resolve an override entry for a course code with namespace fallbacks."""
    for key in _build_override_lookup_keys(course_code, namespace_candidates):
        entry = overrides.get(key)
        if entry is not None:
            return entry
    return None


def has_course_override(
    course_code: str,
    overrides: dict[str, dict[str, str]],
    namespace_candidates: list[str] | None = None,
) -> bool:
    """Return True when any override entry applies to a course code."""
    return resolve_course_override(course_code, overrides, namespace_candidates) is not None


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
    aliases_by_key: dict[str, list[str]] = {}
    for raw_key, value in typed_data.items():
        if raw_key.startswith("_"):
            continue  # skip comment-style keys
        if not isinstance(value, Mapping):
            raise CourseOverrideError(
                f"Entry for {raw_key!r} in {path} must be a JSON object"
            )
        entry: dict[str, str] = {}
        key = _normalise_override_key(raw_key)
        for field, field_value in cast(Mapping[object, Any], value).items():
            if not isinstance(field, str):
                raise CourseOverrideError(
                    f"Entry keys for {raw_key!r} in {path} must be strings"
                )
            if field == _ALIASES_FIELD:
                if not isinstance(field_value, list):
                    raise CourseOverrideError(
                        f"Entry value for {raw_key!r}.{field} in {path} must be a JSON array of strings"
                    )
                aliases: list[str] = []
                for index, alias_value in enumerate(cast(list[Any], field_value)):
                    if not isinstance(alias_value, str):
                        raise CourseOverrideError(
                            f"Entry value for {raw_key!r}.{field}[{index}] in {path} must be a string"
                        )
                    if alias_value.strip():
                        aliases.append(alias_value)
                aliases_by_key[key] = aliases
                continue
            if not isinstance(field_value, str):
                raise CourseOverrideError(
                    f"Entry value for {raw_key!r}.{field} in {path} must be a string"
                )
            entry[field] = field_value
        result[key] = entry
    return _expand_aliases(result, aliases_by_key, path)


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
    namespace_candidates: list[str] | None = None,
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
        entry = resolve_course_override(
            course.code,
            overrides,
            namespace_candidates=namespace_candidates,
        )
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
