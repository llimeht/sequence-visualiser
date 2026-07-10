# Template Config Layers

Config is loaded from JSON objects in this precedence order:

1. `defaults.json`
2. `degree/<DEGREE>.json`
3. `specialisation/<SPECIALISATION>.json`
4. `plan/<PLAN_CODE>.json`
5. `intake/<PLAN_FILE_STEM>.json`
6. `../../template-overrides/config/<same relative paths>`

If the same field appears in more than one file, later layers win.

Example plan file stem:

- `plans/CEIC/CEICAH3707_2026_T1.json` -> intake config file `intake/CEICAH3707_2026_T1.json`

## PDF colour config

The PDF renderer supports configurable background colours under `pdf.colours`:

- `years`: per-year row background (`Year 1` to `Year 5`; numeric keys `1` to `5` are also accepted)
- `models`: per-calendar-model period colours
	- `trimesters_standard`: `Term 1`, `Term 2`, `Term 3`
	- `trimesters_extended`: `Summer Term`, `Term 1`, `Term 2`, `Term 3`
	- `semesters_standard`: `Semester 1`, `Semester 2`
	- `semesters_extended`: `Summer Term`, `Semester 1`, `Winter Term`, `Semester 2`
- `families`: per-calendar-family fallback period colours
	- `trimesters`
	- `semesters`
- `terms`: per-term box background (`Term 1`, `Term 2`, `Term 3`)
- `semesters`: per-semester box background (`Semester 1`, `Semester 2`)

Colour precedence for period boxes:

1. `pdf.colours.models.<calendar_model>.periods.<period_label>`
2. `pdf.colours.families.<calendar_family>.periods.<period_label>`
3. Existing `pdf.colours.terms` / `pdf.colours.semesters`
4. Built-in defaults

Accepted values:

- Hex string (for example, `"#e8e8e8"`)
- RGB triplet as `[r, g, b]` where each value is either `0..255` or `0..1`

Invalid values fall back to built-in defaults.

## Calendar models and period labels

Period labels are inferred from course `period` values in plan JSON (no explicit model field required).

- Trimesters standard: `Term 1`, `Term 2`, `Term 3`
- Trimesters extended: `Summer Term`, `Term 1`, `Term 2`, `Term 3`
- Semesters standard: `Semester 1`, `Semester 2`
- Semesters extended: `Summer Term`, `Semester 1`, `Winter Term`, `Semester 2`

When any extended label appears for a family, all in-scope year boxes for that family use the extended sequence. Empty periods are rendered as empty slots.

## PDF text templating and second page

Configured PDF text values are rendered using Jinja syntax (`{{ ... }}` and `{% ... %}`).

- Use `tokens.*` values (for example `{{ tokens.date }}` or `{{ tokens.program_name }}`).
- Enable an optional second PDF page with `pdf.second_page.enabled`.
- `pdf.second_page.info_box_title`, `pdf.second_page.info_box_text`, and `pdf.second_page.bottom_disclaimer` control page-2 content.
