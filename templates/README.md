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
    - `{{ tokens.university_name }}`
    - `{{ tokens.plan_code }} - {{ tokens.intake }}`
- `pdf.header_right_lines`
  - Optional lines for the right side of the PDF header.
  - Accepts either an array of strings or a newline-separated string.
  - Defaults to:
    - `Program: {{ tokens.program_name }}`
    - `Majors: {{ tokens.majors }}`
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
- `pdf.period_label_y_offset_pt`
  - Optional vertical offset in points from the year heading to term/semester labels.
  - Increase this to move term/semester labels lower.
- `pdf.second_page`
  - Optional second-page configuration block.
  - `enabled` controls whether a second PDF page is rendered.
  - `top_disclaimer` optionally overrides the top disclaimer on page 2 only.
  - If `top_disclaimer` is omitted under `pdf.second_page`, page 2 reuses `pdf.top_disclaimer`.
  - Set `pdf.second_page.top_disclaimer` to an empty string to suppress the page-2 top disclaimer.
  - `info_box_title` and `info_box_text` render in a bordered info box.
  - `bottom_disclaimer` renders in a full-width bordered box near the bottom of page 2.
  - `footer_left` and `footer_right` optionally override page-2 footer lines.
  - Optional sizing keys: `info_font_size_pt`, `info_line_height_pt`, `disclaimer_font_size_pt`, `disclaimer_line_height_pt`.
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

PDF text fields are rendered as Jinja templates. Use `{{ ... }}` and Jinja conditionals/loops.

Supported values under `tokens` include:

- `tokens.date`
- `tokens.year`
- `tokens.university_name`
- `tokens.plan_code`
- `tokens.plan_description` (short descriptor to distinguish plan variants)
- `tokens.plan_description_short` (alias of `tokens.plan_description`)
- `tokens.program_code` (canonical program identifier; sourced from `program_id` and mirrored by `tokens.program_id`)
- `tokens.program_id` (canonical program identifier)
- `tokens.intake`
- `tokens.intake_year`
- `tokens.intake_period`
- `tokens.program_name`
- `tokens.majors`
- `tokens.degree_code` (compatibility alias of `tokens.program_id`)
- `tokens.specialisation_code`
- `tokens.specialisation_codes` (comma-separated list of specialisation codes)
- `tokens.rule_file`
- `tokens.notes_graduate_outcome`
- `tokens.notes_adjustment_type`
- `tokens.notes_for_reviewers` (newline-separated)
- `tokens.notes_for_students` (newline-separated)

Additional top-level template variables are available in PDF text templates: `plan`, `rule`, `years`, `tweaks`, `plan_code`, `program_id`, `program_code`, `specialisation_code`, `specialisation_codes`, `degree_code`.

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
    "footer_right": "Information correct as at {{ tokens.date }}\\nCopyright © {{ tokens.year }} {{ tokens.university_name }}",
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
