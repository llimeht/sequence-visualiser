from __future__ import annotations

"""
sequence_visualiser.config_loader
=================================
Configuration loader for the sequence visualiser. Handles merging and validation
of layered JSON config files for plans, degrees, specialisations, and intakes.
"""
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from .models import Plan
from .metadata_resolver import ProgramIdentity


class ConfigError(ValueError):
    """Raised when a config file exists but is malformed."""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries, with overlay taking precedence."""
    merged = dict(base)
    for key, value in overlay.items():
        existing_value = merged.get(key)
        if isinstance(existing_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(
                cast(dict[str, Any], existing_value), cast(dict[str, Any], value)
            )
        else:
            merged[key] = value
    return merged


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    """Read a JSON file if it exists, returning an empty dict if not found.

    Args:
        path: Path to the JSON file.
    Returns:
        Parsed JSON as a dict, or empty dict if file does not exist.
    Raises:
        ConfigError: If the file exists but is not valid JSON or not a dict.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in config file {path}") from exc
    if not isinstance(data, Mapping):
        raise ConfigError(f"Config file {path} must contain a JSON object")
    return {str(key): value for key, value in cast(Mapping[object, Any], data).items()}


def _layer_paths(
    config_root: Path, identity: ProgramIdentity, plan: Plan
) -> list[Path]:
    """Return the list of config file paths to layer for a given plan and identity."""
    specialisation_layers = [
        config_root / "specialisation" / f"{code}.json"
        for code in identity.specialisation_codes
    ]
    if not specialisation_layers:
        specialisation_layers = [
            config_root / "specialisation" / f"{identity.specialisation_code}.json"
        ]

    return [
        config_root / "defaults.json",
        config_root / "degree" / f"{identity.degree_code}.json",
        *specialisation_layers,
        config_root / "plan" / f"{identity.plan_code}.json",
        config_root / "intake" / f"{plan.source_path.stem}.json",
    ]


def load_tweaks(
    plan: Plan,
    identity: ProgramIdentity,
    config_root: Path,
    local_overrides_root: Path,
) -> dict[str, Any]:
    """Load and merge all tweak config layers for a plan, including local overrides."""
    merged: dict[str, Any] = {}
    for path in _layer_paths(config_root, identity, plan):
        merged = _deep_merge(merged, _read_json_if_exists(path))

    if local_overrides_root.exists():
        local_specialisation_layers = [
            Path("specialisation") / f"{code}.json"
            for code in identity.specialisation_codes
        ]
        if not local_specialisation_layers:
            local_specialisation_layers = [
                Path("specialisation") / f"{identity.specialisation_code}.json"
            ]

        for relative in (
            Path("defaults.json"),
            Path("degree") / f"{identity.degree_code}.json",
            *local_specialisation_layers,
            Path("plan") / f"{identity.plan_code}.json",
            Path("intake") / f"{plan.source_path.stem}.json",
        ):
            merged = _deep_merge(
                merged, _read_json_if_exists(local_overrides_root / relative)
            )

    return merged
