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
  - Used by PDF logo lookup when `branding.logo_path_pdf` is not set.
  - Relative paths are checked in `templates/assets/`, then `template-overrides/assets/`.
  - Absolute paths are used directly.
- `branding.logo_path_pdf`
  - Preferred logo for PDF rendering.
  - Supports PDF assets (vector) and is used ahead of `branding.logo_path` when present.
  - Relative paths are checked in `templates/assets/`, then `template-overrides/assets/`.
  - Absolute paths are used directly.
- `pdf.logo_width_mm`
  - Optional logo width for PDF rendering, in millimetres.
  - If `pdf.logo_height_mm` is omitted, the renderer scales height from the logo aspect ratio.
- `pdf.logo_height_mm`
  - Optional logo height for PDF rendering, in millimetres.
  - If `pdf.logo_width_mm` is omitted, the renderer scales width from the logo aspect ratio.
- `pdf.logo_right_spacing_mm`
  - Optional horizontal whitespace (in millimetres) between the logo and the left header text.
  - If omitted, a small built-in spacing is used.
- `pdf.header_left_lines`
  - Optional lines for the left side of the PDF header.
  - Accepts either an array of strings or a newline-separated string.
  - Defaults to:
    - `{university_name}`
    - `{plan_code} - {intake}`
- `pdf.header_right_lines`
  - Optional lines for the right side of the PDF header.
  - Accepts either an array of strings or a newline-separated string.
  - Defaults to:
    - `Program: {program_name}`
    - `Majors: {majors}`
- `pdf.header_right_width_mm`
  - Optional width of the right header text box in millimetres.
  - Larger values reserve more space for right-aligned header text.
- `pdf.header_left_min_width_mm`
  - Optional minimum width of the left header text area in millimetres.
  - Useful when the logo or right header box would otherwise squeeze left text.
- `pdf.header_line_gap_pt`
  - Optional vertical gap between header lines in points.
  - Applies to both left and right header lines.
- `pdf.header_background_color`
  - Optional full-width header background color.
  - Uses the same color formats as other PDF colours (hex string or RGB triple).
  - Drawn edge-to-edge across the page width.
- `pdf.header_height_mm`
  - Optional total header block height in millimetres.
  - Defines the bottom boundary of the header area.
  - The top disclaimer is rendered below this boundary.
- `pdf.header_bottom_spacing_mm`
  - Optional extra whitespace (in millimetres) below the header boundary.
  - Applied before rendering the top disclaimer/content.
- `pdf.fonts`
  - Optional role-based PDF font configuration.
  - Font file paths should be relative to `templates/assets/` or `template-overrides/assets/`, or absolute paths.
  - Supported role groups:
    - `pdf.fonts.header`
    - `pdf.fonts.course_codes`
    - `pdf.fonts.footer`
    - `pdf.fonts.body`
  - Supported style keys per role:
    - `regular`
    - `bold`
    - `italic`
    - `bold_italic`
  - Header role also supports size keys:
    - `size` (primary left header line)
    - `secondary_size` (additional left header lines)
    - `right_size` (right header lines)

Supported header/footer tokens include:

- `{date}`
- `{year}`
- `{university_name}`
- `{plan_code}`
- `{program_code}` (from rules `program.id`; falls back to `{plan_code}` if missing)
- `{intake}`
- `{program_name}`
- `{majors}`
- `{degree_code}`
- `{specialisation_code}`
- `{rule_file}`
- `html.title`
  - HTML `<title>` value.
- `html.heading`
  - HTML heading shown at the top of the page.

Example minimal config:

```json
{
  "branding": {
    "university_name": "Example University",
    "logo_path": "example-logo.png",
    "logo_path_pdf": "example-logo.pdf"
  },
  "pdf": {
    "logo_height_mm": 12,
    "logo_right_spacing_mm": 8,
    "fonts": {
      "header": {
        "regular": "fonts/Clancy-Regular.ttf",
        "size": 13
      },
      "course_codes": {
        "regular": "fonts/RobotoMono-Regular.ttf"
      },
      "footer": {
        "regular": "fonts/Roboto-Regular.ttf"
      },
      "body": {
        "regular": "fonts/Roboto-Regular.ttf",
        "bold": "fonts/Roboto-Bold.ttf"
      }
    }
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
