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
- `terms`: per-term box background (`Term 1`, `Term 2`, `Term 3`)
- `semesters`: per-semester box background (`Semester 1`, `Semester 2`)

Colour precedence for period boxes:

1. `pdf.colours.models.<calendar_model>.periods.<period_label>`
2. Existing `pdf.colours.terms` / `pdf.colours.semesters`
3. Built-in defaults

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

## Course handbook links

Both HTML and PDF course grids can generate handbook links per course.

- `html.course_link_template`: Jinja template used for each course link in HTML output.
- `pdf.course_link_template`: Jinja template used for each course link in PDF output.

Available template variables include:

- `career`: plan career value (for example `undergraduate`; use `career | lower` to force lowercase)
- `code`: course code (for example `MATH1131`)
- `title`: course title
- `uoc`: numeric UoC value
- `display_title`: rendered title text including optional UoC suffix

Example:

- `https://handbook.example.org/{{ career }}/courses/current/{{ code }}`

Link styling is configurable separately from long-form disclaimer/footer links:

- `html.course_link_style`: supports `underline` and `colour`/`color`.
- `pdf.course_link_style`: supports `underline` and `colour`/`color`.

If no course link template is set, no grid course links are generated.

### Per-course override control (`course-overrides*.json`)

Course override entries support an optional `handbook_link` field to control whether
grid links are emitted for that course.

- Omitted, `false`, `null`, or empty string: no course grid link.
- `true`: generate the normal link from `html.course_link_template` / `pdf.course_link_template`.
- String starting with `http://` or `https://`: use that explicit URL directly.

String values are trimmed before evaluation.

If `handbook_link` is present but neither `true` nor a valid explicit `http(s)` URL,
the renderer logs a warning and treats it as disabled (no link).
