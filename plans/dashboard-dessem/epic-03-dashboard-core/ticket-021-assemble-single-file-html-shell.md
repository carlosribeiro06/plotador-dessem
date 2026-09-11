# ticket-021 Assemble the single-file HTML shell

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The deliverable of the whole feature is **one HTML file that opens offline**, with no server and no
network access at build time or view time (master plan goal 6 and decision 6). This ticket produces
that document: the ONS header, the level navigation, the control panel, the warning list, one
container per enabled chart, the mandatory footer, and the four inlined payloads — `plotly.min.js`
from `plotly.offline.get_plotlyjs()`, the stylesheet, the renderer script and the JSON data block.
Everything an operator will ever see is decided here; tickets 022 to 026 and all of Epic 4 only
attach behaviour to the elements this ticket emits, which is what keeps the JavaScript thin as epic
decision E3-1 requires.

The three original key decisions and the three open questions of this ticket are resolved as
follows.

- **The document is a package-data template file substituted with `string.Template`.** Not
  `str.format`, because HTML, CSS and JavaScript are full of braces and every one would have to be
  doubled; and not an f-string, because a template in its own file is reviewable as HTML. The
  template must contain no literal `$` other than its placeholders, which `Template.is_valid()`
  verifies.
- **`plotly.min.js` is inlined verbatim and no reduced bundle is pursued.** Measured on the installed
  stack: `plotly.offline.get_plotlyjs()` from plotly 7.0.0 returns 4 293 280 characters of
  plotly.js v4.0.0 and contains no `</script` sequence, so it needs no escaping. A partial bundle
  would require either a new dependency or a build step, both forbidden. Together with the 72 648
  base64 characters of the logo this sets a fixed floor of about 4.37 MB per output file, well inside
  the `output.size_warning_mb` default of 50.
- **The logo protection area comes from the theme constants** `LOGO_MIN_WIDTH_PX = 393`, which is
  exactly 50 percent of the 786 pixel natural width and therefore the largest reduction the brand
  manual permits, and `LOGO_PADDING_PX = 24`, about 0.63 cm at 96 dpi against the 0.5 cm minimum.
- **The footer carries only `dashboard.footer_text`.** `planning-context.md` decision 13 makes that
  text mandatory and exact, and the audit trail an operator needs — git sha, parameters, volumes,
  elapsed time — is already written to `run_manifest.json` by `manifest.write_run_manifest`.
  Duplicating a sha inside a brand-controlled element buys nothing.
- **The payload goes into a `<script id="dashboard-payload" type="application/json">` element**, not
  a JavaScript assignment, so the accented Portuguese labels need no JavaScript string escaping; the
  only hazard left is a literal `<`, which ticket-020 already replaced with `\u003C`.
- **A missing `paths.logo_file` is fatal**, raised as `ConfigError` naming the dotted settings key.
  Master plan decision 18 makes *data* gaps degrade to warnings, but this is a configuration error,
  and goal 7 makes the ONS visual identity a requirement: a text-only header would silently ship a
  brand-non-compliant artifact into an official process. `ConfigError` also gives the operator the
  established experience — `cli.main` exits 2 with the Portuguese message and no traceback — without
  adding an eighth class to `errors.py`.

### Relation to Epic

The hinge of the epic. It consumes ticket-019 (colours, fonts, layout template, CSS custom
properties) and ticket-020 (the JSON payload and its serialisation), and it defines the **DOM
contract** every later ticket depends on: element ids, `data-` attributes and Portuguese labels.
Ticket-022 inlines its renderer through the `$dashboard_js` placeholder created here; ticket-023 adds
the mode and level initial state to this builder; ticket-024 adds the value-mode initial state;
tickets 025, 026 and all of Epic 4 render into the `div.plot` elements created here.

### Current State

`src/dessem_dashboard/dashboard/` contains `__init__.py`, `assets/__init__.py` and `theme.py` from
ticket-019, and `payload.py` from ticket-020. There is **no asset file yet**: `assets/` holds only
its package marker. `pyproject.toml` already declares
`[tool.setuptools.package-data]` for `"dessem_dashboard.dashboard.assets"` with the pattern `["*"]`,
so any file placed there ships with the package; do not edit `pyproject.toml`.

Available from ticket-019: `BRAND_GREEN`, `BRAND_GRAY`, `WHITE`, `GRID_COLOR`, `FONT_FAMILY`,
`FONT_SIZE_PX`, `CHART_HEIGHT_PX`, `LOGO_MIN_WIDTH_PX`, `LOGO_PADDING_PX`, `tint`,
`scenario_colors(scenarios, *, reference)`, `plotly_layout_template(*, date_format)` and
`css_root_block()`. Available from ticket-020: `build_payload(data, *, settings, scenario_colors,
plotly_layout)` and `payload_json(payload)`, whose payload carries `deck_dates` as `%d/%m/%Y`
strings, `charts` keyed by chart key with the nine documented keys, and no `warnings` key.

`.gitignore` ignores `/*.html` at the repository root only, so `assets/dashboard.html` is tracked —
verified with `git check-ignore`. `output/*` is ignored, so a generated dashboard is never committed.
Measured on the `scenario_tree` fixture: 23 enabled charts, of which 5 are in group `SIN`, 6 in
`SBM`, 1 in `SBP`, 8 in `UHE`, 1 in `UTE` and 2 in `EXECUCAO`; 7 charts have selector `NONE`, 6
`SUBMARKET`, 1 `SUBMARKET_PAIR`, 8 `HYDRO_PLANT` and 1 `THERMAL_PLANT`; `data.warnings()` is empty;
`CMO_SBM` has the two entities `1` labelled `SE (SUDESTE)` and `2` labelled `S (SUL)`. The payload
of that fixture, serialised exactly as ticket-020 specifies, measures **129 043 characters**, so the
whole document lands near **4 520 000 characters**: 4 293 280 of `plotly.min.js`, 72 648 of base64
logo, 129 043 of payload and about 25 000 of template, stylesheet, renderer and the 23 chart
sections. That is the measured basis of the size range in the first acceptance criterion.

## Specification

### Requirements

1. Create `src/dessem_dashboard/dashboard/assets/dashboard.html`, the `string.Template` document. Its
   placeholder set is exactly these fifteen names: `title`, `css`, `initial_mode`, `logo_data_uri`,
   `level_nav`, `mode_toggle`, `deck_selector`, `value_toggle`, `reference`, `warnings_section`,
   `chart_sections`, `footer`, `plotly_js`, `payload_json` and `dashboard_js`. `$title` may appear
   twice, in `<title>` and in
   `<h1>`. The document declares `<!DOCTYPE html>`, `<html lang="pt-BR">` and
   `<meta charset="utf-8">`, and contains no literal `$` outside those placeholders.
2. The DOM contract, fixed here and consumed unchanged by every later ticket. Element ids, classes
   and `data-` attribute names are identifiers and therefore **English**; every text node an operator
   reads is **Portuguese**:
   - `<body data-initial-mode="$initial_mode">`;
   - `<header id="header">` holding `<img id="logo" src="$logo_data_uri" alt="Logotipo do ONS">` and
     `<h1 id="title">$title</h1>`;
   - `<nav id="level-nav">$level_nav</nav>`;
   - `<div id="controls">` holding, in order, `<div id="mode-toggle">$mode_toggle</div>`, a
     `<label for="deck-selector">Deck</label>` followed by `$deck_selector`,
     `<div id="value-toggle">$value_toggle</div>`, and
     `<span id="reference-label">Referência: $reference</span>`. The three controls are **generated
     fragments rather than static markup**, because tickets 023 and 024 add their initial state
     (`aria-pressed`, `disabled`) to the generating helpers, and a placeholder set that grew later
     would invalidate the fifth acceptance criterion of this ticket;
   - `$warnings_section`;
   - `<main id="charts">$chart_sections</main>`;
   - `<footer id="footer">$footer</footer>`;
   - the three script elements last, in this order: `<script id="plotly-js">$plotly_js</script>`,
     `<script id="dashboard-payload" type="application/json">$payload_json</script>`, and
     `<script id="dashboard-js">$dashboard_js</script>`. The order is load-bearing: the renderer must
     find both Plotly and its data already present.
   No button carries `aria-pressed` and the deck selector carries no `disabled` attribute: the
   initial state of the mode and level controls belongs to ticket-023 and of the value control to
   ticket-024, so that each control initial state is verified by the ticket that defines what that
   control means.
3. Create `src/dessem_dashboard/dashboard/assets/dashboard.css`, hand-written, referencing every
   colour, font and logo dimension **only** through `var(--ons-*)`. It must contain **no colour
   literal**: no `#rrggbb`, no `#rgb`, no `rgb(`, no CSS named colour. Non-colour layout literals
   such as the responsive chart `max-width: 1400px` are allowed and expected, because the legacy
   1400 pixel width is a layout choice rather than a brand value. It must contain no `@import` and no
   `url(` pointing anywhere but a `data:` URI. Style at least: the `body` font from
   `var(--ons-font-family)` and `var(--ons-font-size)`; the header with the logo at
   `width: var(--ons-logo-width)` and `padding: var(--ons-logo-padding)`; left-aligned headings;
   `#level-nav` and the two toggles as button rows with a visible `[aria-pressed="true"]` state;
   `.chart[hidden] { display: none; }`; `.plot { width: 100%; max-width: 1400px; }`; and the footer.
4. Create `src/dessem_dashboard/dashboard/assets/dashboard.js` containing exactly one line, a
   comment naming ticket-022 as its implementer. The file must exist now so the template placeholder
   resolves and the shell is testable end to end; ticket-022 replaces its content.
5. Create `src/dessem_dashboard/dashboard/builder.py` exposing
   `build_html(data: DashboardData, *, settings: Settings, initial_mode: str = "encadeado") -> str`
   and `write_dashboard(data: DashboardData, *, settings: Settings, output_file: Path,
   initial_mode: str = "encadeado") -> Path`. `build_html` reads the three assets through
   `importlib.resources.files("dessem_dashboard.dashboard.assets")`, never through a path relative to
   `__file__`, so the package works installed as well as editable. `write_dashboard` creates the
   parent directory of `output_file`, writes the document as UTF-8, and returns `output_file`.
6. `build_html` substitutes: `title` and `footer` from `settings.dashboard.title` and
   `settings.dashboard.footer_text`; `css` from `theme.css_root_block()` concatenated with
   `dashboard.css`; `initial_mode` from the argument; `reference` from `data.reference`;
   `payload_json` from `payload.payload_json(payload.build_payload(data, settings=settings,
   scenario_colors=theme.scenario_colors(data.scenarios, reference=data.reference),
   plotly_layout=theme.plotly_layout_template(date_format=settings.dashboard.date_format)))`;
   `plotly_js` from `plotly.offline.get_plotlyjs()`; and `dashboard_js` from the asset.
7. `logo_data_uri` is `f"data:{mime};base64,{encoded}"` where `encoded` is the base64 of
   `settings.paths.logo_file` and `mime` comes from the file suffix: `.png` maps to `image/png`,
   `.jpg` and `.jpeg` to `image/jpeg`, `.svg` to `image/svg+xml`. Any other suffix, and a file that
   does not exist, raise `ConfigError` in Portuguese naming the dotted key `paths.logo_file` and the
   resolved absolute path.
8. `level_nav` is one `<button type="button" data-group="G">Label</button>` per chart group that has
   at least one enabled chart, in the order the groups first appear in
   `enabled_specs(disabled=settings.charts.disabled)`. The labels are Portuguese and come from a
   `GROUP_LABELS` mapping declared in this module: `SIN` maps to `SIN`, `SBM` to `Submercado`, `SBP`
   to `Intercâmbio`, `UHE` to `Usinas hidrelétricas`, `UTE` to `Usinas termelétricas` and
   `EXECUCAO` to `Execução`. The group labels are plural and the selector labels of requirement 9
   singular, so the two sets never collide and both stay in the sentence case the brand manual
   requires.
9. `chart_sections` is one section per entry of `payload["charts"]`, in `enabled_specs` order:
   `<section class="chart" id="chart-KEY" data-chart="KEY" data-group="GROUP"
   data-selector="SELECTOR">`, carrying the `hidden` attribute unless its group equals the group of
   the **first** enabled spec, which is the initially active level. Each section holds an `<h2>` with
   the payload `title`; a `<p class="chart-subtitle">` with the payload `subtitle` **only when that
   value is not null** — epic decision E3-2, which keeps the curated catalogue title as the heading
   and the registry long name additive; when `selector` is not `NONE`, a `<label class="entity-label">` whose
   Portuguese text comes from a `SELECTOR_LABELS` mapping (`SUBMARKET` maps to `Submercado`,
   `SUBMARKET_PAIR` to `Par de submercados`, `HYDRO_PLANT` to `Usina hidrelétrica`, `THERMAL_PLANT`
   to `Usina termelétrica`) followed by `<select class="entity-selector" id="entity-KEY">` with one
   `<option value="ID">LABEL</option>` per payload entity, in payload order; and finally
   `<div class="plot" id="plot-KEY"></div>`. Generating the options in Python rather than in the
   browser follows E3-1: the list is fully known at build time.
10. `deck_selector` is `<select id="deck-selector">` holding one `<option value="D">D</option>` per
    entry of `payload["deck_dates"]`, which are already `%d/%m/%Y` strings. Do not re-format a deck
    date with `settings.dashboard.date_format`: that pattern carries `%H:%M` and would render the
    deck of 3 March as `03/03/2024 00:00`. `mode_toggle` is one
    `<button type="button" data-mode="M">Label</button>` per entry of a module-level
    `MODE_LABELS` mapping (`deck` maps to `Por deck`, `encadeado` to `Encadeado`), and
    `value_toggle` likewise from `VALUE_LABELS` (`absoluto` maps to `Absoluto`, `diferenca` to
    `Diferença`), both in that declared order.
11. `warnings_section` is `<section id="warnings"><h2>Avisos</h2><ul>` with one `<li>` per entry of
    `data.warnings()`, in order, `</ul></section>`; and the **empty string** when `data.warnings()`
    is empty, so the section is absent rather than an empty box. The messages are already Portuguese
    and already carry their dates as `%d/%m/%Y`; render them verbatim.
12. Escape every dynamic text node and attribute value with `html.escape`, including chart titles,
    subtitles, entity labels, warnings, the reference label, the dashboard title and the footer, so a
    plant name containing `&` cannot break the document.
13. Log at INFO through `log_step`: one line when the payload has been embedded, with the chart count
    and `data.value_count()`, and one from `write_dashboard` with the output path, the document size
    in bytes and `elapsed_s`. Measuring the size is in scope; **warning above
    `output.size_warning_mb` is not** — ticket-032 owns enforcement. Messages are Portuguese; the
    module uses `logging.getLogger(__name__)` and adds no handler.

### Inputs

A populated `DashboardData`, the validated `Settings`, the initial view mode, and for
`write_dashboard` the destination path. The logo is read from `settings.paths.logo_file`, which
`config.load_settings` already resolved to an absolute path against the settings file directory.

### Outputs and Behavior

`build_html` returns the complete document as a `str` and touches no disk beyond reading the three
assets and the logo. `write_dashboard` writes exactly one file. The document opens from `file://`
with no network access: apart from the base64 logo it contains no external reference of any kind.

### Error Handling

`ConfigError` in Portuguese for a missing or unsupported `paths.logo_file`, per the ruling under
Background. `KeyError` from `Template.substitute` if a placeholder is unsupplied, which is a
programming error and must not be softened with `safe_substitute`: a silently unsubstituted
`$payload_json` would ship a dashboard with no data. `StoreError` and `RegistryError` propagate from
the payload layer. No bare `except`; do not catch `OSError` while reading the assets, because a
package missing its own data is unrecoverable.

## Dependencies

- **Blocked By**: `ticket-019-build-brand-theme-module.md`,
  `ticket-020-export-compact-json-payload.md`
- **Blocks**: `ticket-022-implement-js-chart-renderer-core.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture consolidated with the repository `settings.json` and
      `reference="caso_a"`, when `build_html(data, settings=settings)` is called, then the returned
      text contains `plotly.offline.get_plotlyjs()` verbatim as a substring, contains
      `f"data:image/png;base64,{base64.b64encode(settings.paths.logo_file.read_bytes()).decode()}"`,
      places `<script id="plotly-js">` before `<script id="dashboard-payload"` and that before
      `<script id="dashboard-js">`, and `len(html)` lies between `4_300_000` and `5_242_880`.
- [ ] Given the same document with the `<script id="plotly-js">` element and its content removed by
      slicing from that opening tag to the first following `</script>`, when the remainder is
      searched, then it contains no `http://`, no `https://`, no `<link` and no `@import`, and every
      value matched by `re.findall(r'(?:src|href)="([^"]*)"', remainder)` begins with `data:` or `#`.
      The excision is mandatory and measured: `get_plotlyjs()` itself contains 52 `https://`,
      71 `http://`, 9 `src=` and 17 `href=` occurrences inside its own string literals, so the same
      search over the whole document can never pass.
- [ ] Given the same document, when its chart containers are counted, then `html.count('<section
      class="chart"')` equals `23`, the five sections whose `data-group="SIN"` carry no `hidden`
      attribute while the other eighteen do, `id="chart-CMO_SBM"` carries `data-selector="SUBMARKET"`
      and a `<select class="entity-selector" id="entity-CMO_SBM">` holding exactly the two options
      `<option value="1">SE (SUDESTE)</option>` and `<option value="2">S (SUL)</option>`, and the
      `id="chart-GHID_SIN"` section contains no `<select` and no `<p class="chart-subtitle">`.
- [ ] Given the same document, when its header, footer and warning area are inspected, then it
      contains
      `<h1 id="title">Comparação de Resultados do DESSEM</h1>`, the exact footer text
      `Gerência de Ferramentas Energéticas - FEN`, `Referência: caso_a` inside
      `id="reference-label"`, six `data-group=` buttons inside the `<nav id="level-nav">` slice, including
      `>Usinas hidrelétricas<` and `>Execução<`, and **no** `<section id="warnings"` element, because
      `data.warnings()` is empty on this fixture; and given the same store after
      `data.add_warning("Cenário 'caso_b' não possui deck para a data 04/03/2024, presente em
      outro(s) cenário(s)")`, the rebuilt document contains one `<section id="warnings"` with exactly
      one `<li>` carrying `04/03/2024`.
- [ ] Given `assets/dashboard.html` read as text and `assets/dashboard.css` read as text, when the
      first is parsed with `string.Template`, then `is_valid()` is `True`,
      `set(get_identifiers())` equals the fifteen documented placeholder names,
      `re.search(r"#[0-9A-Fa-f]{3,8}\b", css)` is `None` and `"@import" not in css`, and
      `.venv/bin/pytest tests/test_builder.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `dashboard.html` first, as a readable HTML document with the thirteen placeholders, and
   check it with `.venv/bin/python -c` calling `Template(...).is_valid()` before writing any Python.
2. Write `dashboard.css` next, driving every colour through `var(--ons-*)`, then run the no-colour
   regex over it once by hand so the later test is not the first time it is checked.
3. Write the one-line `dashboard.js` stub.
4. Write `builder.py` as a small set of private fragment builders — `_logo_data_uri`, `_level_nav`,
   `_mode_toggle`, `_deck_selector`, `_value_toggle`, `_chart_sections`, `_warnings_section`,
   `_read_asset` — each returning a string,
   plus `build_html` doing exactly one `Template.substitute` call and `write_dashboard` doing the
   I/O. One substitution call means no fragment is ever re-scanned for placeholders, which matters
   because the `CMO_SBM` unit `R$/MWh` and any `$` in the inlined JavaScript would otherwise be
   mistaken for a placeholder.
5. Declare `GROUP_LABELS`, `SELECTOR_LABELS`, `MODE_LABELS` and `VALUE_LABELS` as module-level
   `Mapping` constants keyed by the `ChartGroup` and `EntitySelector` string values and by the two
   mode and two value identifiers, so an unknown key raises rather than silently rendering an empty
   label.
6. Write `tests/test_builder.py`, always pointing `paths.output_dir` and `logging.file` at
   `tmp_path` through a `tmp_path/settings.json` copy, as Epic 1 established, so no test writes into
   the repository `output/` or `logs/`.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/assets/dashboard.html` (create)
- `src/dessem_dashboard/dashboard/assets/dashboard.css` (create)
- `src/dessem_dashboard/dashboard/assets/dashboard.js` (create, one comment line; ticket-022
  implements it)
- `src/dessem_dashboard/dashboard/builder.py` (create)
- `tests/test_builder.py` (create)

### Patterns to Follow

- `importlib.resources.files(...).joinpath(name).read_text(encoding="utf-8")` for package data.
- `log_step` with volume fields and `elapsed_s` at each phase boundary, as `consolidate.py` does.
- Portuguese UI text and log messages, English identifiers and docstrings; reuse the shipped
  vocabulary (`cenário`, `deck`, `gráfico`, `aviso`) rather than new synonyms.
- The settings copy in `tmp_path` pattern from `tests/test_config.py` and `tests/test_manifest.py`.

### Pitfalls to Avoid

- Do not use `str.format` or an f-string for the document. Every `{` in the CSS and the inlined
  JavaScript would need doubling, and one missed brace produces a corrupt 4 MB file.
- Do not call `Template.substitute` more than once, and never on a fragment that already contains
  substituted content. `R$/MWh` and the JavaScript both contain `$`.
- Do not use `safe_substitute`. A typo in a placeholder name would then ship a dashboard containing
  the literal text `$payload_json`.
- Do not assert the absence of `https://` over the whole document. The measured counts under the
  second acceptance criterion make that assertion unsatisfiable; excise the plotly block first.
- Do not read the assets with `Path(__file__).parent / "assets"`. It happens to work in an editable
  install and breaks in a wheel.
- Do not re-derive the deck labels or the axis keys. They arrive from the payload already formatted
  `%d/%m/%Y`, and `dashboard.date_format` includes `%H:%M`.
- Do not write a colour literal into `dashboard.css`, not even for a hover state. Add a new
  `--ons-*` property to `theme.css_root_block()` instead — and note that doing so changes the
  ordered name list in ticket-019 fifth acceptance criterion, so amend that ticket rather than
  quietly diverging.
- Do not set `aria-pressed` or `disabled` anywhere in this ticket; requirement 2 assigns those to
  tickets 023 and 024 so their acceptance criteria cannot pass before they are implemented.
- Do not let a test write into the repository `output/`: `write_dashboard` creates directories, and
  a 4.5 MB stray file under a gitignored path is easy to miss and slow to notice.

### Out of Scope

- Every behaviour: the renderer core (ticket-022), the mode, deck and level controls and their
  initial state (ticket-023), the value-mode control and its initial state (ticket-024), and the
  chart rendering itself (tickets 025 and 026).
- The content of `dashboard.js` beyond the one-line stub.
- The plant name and code filter inputs (ticket-028) and the bar-chart containers rendering
  (tickets 030 and 031); their `section` elements are created here, but nothing draws into them.
- Warning above `output.size_warning_mb` (ticket-032); this ticket logs the size only.
- Threading `--modo-inicial` from the CLI into `initial_mode` (ticket-033 wires `pipeline.run`).
- Any change to `pyproject.toml`, `errors.py` or the data layer.

## Testing Requirements

### Unit Tests

`tests/test_builder.py`:

- the five acceptance criteria;
- `write_dashboard` into `tmp_path`, asserting the returned path exists, decodes as UTF-8 and equals
  `build_html` output character for character;
- `write_dashboard` creating a missing parent directory;
- a settings copy whose `paths.logo_file` points at a non-existent file: `ConfigError` whose message
  contains `paths.logo_file` and the resolved path, asserted with `re.escape`;
- a settings copy whose `paths.logo_file` has an unsupported suffix such as `.bmp`: `ConfigError`;
- a `.svg` logo producing `data:image/svg+xml;base64,`;
- `charts.disabled = ["GHID_SIN", "CMO_SBM"]`: 21 sections, no `id="chart-GHID_SIN"`, and the level
  navigation still lists six groups;
- a fixture whose `METADADOS_OPERACAO.parquet` gives `CMO_SBM` a differing `nome_longo_variavel`:
  the `CMO_SBM` section contains one `<p class="chart-subtitle">` with that text, and the
  `GHID_SIN` section contains none;
- an entity label containing `&` and `<` appearing escaped in the option text and unescaped nowhere;
- `initial_mode="deck"` and `initial_mode="encadeado"` both appearing in `data-initial-mode`, with no
  other document difference, asserted by comparing the two documents after removing that attribute;
- `get_plotlyjs()` contains no `</script` sequence, asserted directly, so a future plotly upgrade
  that breaks the no-escaping assumption fails here rather than corrupting an output file;
- `caplog` assertions on the two INFO lines and their volume fields.

### Integration Tests

None. Opening the file in a browser is the first item of the manual checklist created in ticket-022,
and the run against a real scenario tree is ticket-034.

## Definition of Done

- [ ] The five files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] `assets/dashboard.css` contains no colour literal and no `@import`, and every colour it applies
      resolves through a `var(--ons-*)` property emitted by `theme.css_root_block()`.
- [ ] The generated document contains no external reference other than the base64 logo, verified by
      the second acceptance criterion, so it opens with no network access.
- [ ] `aria-pressed` appears in neither `assets/dashboard.html` nor `builder.py`, verified with
      `grep -c "aria-pressed" src/dessem_dashboard/dashboard/assets/dashboard.html
      src/dessem_dashboard/dashboard/builder.py` printing `0` for both; and `disabled` appears
      nowhere in `assets/dashboard.html`, verified with
      `grep -c "disabled" src/dessem_dashboard/dashboard/assets/dashboard.html` printing `0`. Do
      **not** grep `builder.py` for `disabled`: it legitimately calls
      `enabled_specs(disabled=settings.charts.disabled)`. Do **not** grep the generated document
      either: the inlined `plotly.min.js` contains both words.
- [ ] `git status --porcelain output/` prints nothing, so no test left a generated dashboard behind.

## Effort Estimate

**Points**: 4 · **Confidence**: High · **Agent time**: about 40 minutes, the longest ticket of the
epic. If the orchestrator prefers to stay inside the 30-minute norm, the natural split is
`dashboard.html` plus `dashboard.css` in one ticket and `builder.py` in a second; the epic keeps its
eight-ticket shape only because the two halves share one acceptance surface.
