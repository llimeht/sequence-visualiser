# Templates Guide

This directory controls presentation and display tweaks.

## Files and folders

- `sequence.html.j2`
  - Top-level HTML template used by the renderer.
  - This is where HTML structure and CSS are defined.
- `config/`
  - Layered JSON tweak files (defaults, degree, specialisation, plan, intake).
- `assets/`
  - Shared git-tracked assets (for example a default logo file).
- `local-assets/`
  - Local, non-git assets (machine-specific or confidential files).
- `../template-overrides/config/`
  - Local, non-git JSON tweak overrides.

## What to put in sequence.html.j2

Use this file for:

- Page-level HTML structure.
- CSS theme, spacing, and typography.
- Jinja rendering logic for year and period sections.

Template variables currently provided:

- `plan`
  - plan metadata from the input JSON (`intake`, etc.)
- `rule`
  - resolved rule metadata (`program_name`, `specialisation_names`, validity)
- `years`
  - normalized year/period structure used for rendering
- `tweaks`
  - merged configuration object from `config/` and `../template-overrides/config/`
- `plan_code`, `specialisation_code`, `degree_code`
  - identifiers derived from plan metadata and file naming

Current HTML direction:

- No branding block in HTML output.
- Vertical layout: Year sections, then stacked period subsections.
- Year sections default to expanded (`<details ... open>`).

## What to put in config files

Config files are JSON objects merged in precedence order (later wins).

Supported keys in the current implementation:

- `branding.university_name`
  - Used by PDF header text.
- `branding.logo_path`
  - Used by PDF logo lookup.
  - Relative paths are checked in `templates/local-assets/` first, then `templates/assets/`.
  - Absolute paths are used directly.
- `html.title`
  - HTML `<title>` value.
- `html.heading`
  - HTML heading shown at the top of the page.

Example minimal config:

```json
{
  "branding": {
    "university_name": "Example University",
    "logo_path": "example-logo.png"
  },
  "html": {
    "title": "Chemical Engineering Sequence",
    "heading": "Chemical Engineering Sequence"
  }
}
```

## Config layering order

1. `config/defaults.json`
2. `config/degree/<DEGREE>.json`
3. `config/specialisation/<SPECIALISATION>.json`
4. `config/plan/<PLAN_CODE>.json`
5. `config/intake/<PLAN_FILE_STEM>.json`
6. `../template-overrides/config/` with the same relative paths

If two files set the same field, the later layer wins.

## Example override strategy

- Commit shared defaults in `config/defaults.json`.
- Commit stable program rules in `config/degree/` and `config/specialisation/`.
- Commit exceptional one-off tweaks in `config/intake/`.
- Keep local/testing/private values in `../template-overrides/config/`.

## File naming examples

For input file:

- `plans/CEIC/CEICAH3707_2026_T1.json`

Expected config candidates include:

- `config/degree/3707.json`
- `config/specialisation/CEICAH.json`
- `config/plan/CEICAH3707.json`
- `config/intake/CEICAH3707_2026_T1.json`
- `../template-overrides/config/intake/CEICAH3707_2026_T1.json`
