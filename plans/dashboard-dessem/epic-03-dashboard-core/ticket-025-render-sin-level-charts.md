# ticket-025 Render the SIN level charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The five SIN-level charts of master plan Appendix A.6 — `GTER_SIN` Geração Térmica, `GHID_SIN`
Geração Hidrelétrica, `GUNS_SIN` Geração Não Simulada, `EARMF_SIN` EARMF and `VARMF_SIN` Volume
Armazenado — are the simplest charts in the catalogue: one entity, `entity_id` `""` labelled
`Sistema Interligado`, no selector, one curve per scenario. They are therefore the natural place to
close the last gap in the renderer and to verify the whole chain end to end, which is milestone M3.

The gap is the **per-chart layout**. Ticket-019 built the chart-independent layout template — Arial,
white background, the 20 percent gray grid, `hovermode` set to `x unified`, a true date axis with
`tickformat` and `hoverformat` from `dashboard.date_format`, a 450 pixel height, `autosize`, a
`zeroline` and deliberately **no** `title` key — and ticket-022 passes a deep copy of it straight to
`Plotly.react`. What is missing is the one part that depends on the chart: the Y-axis title, which
spec goal 5 and this ticket objective require to carry the unit, plus the ` (diferença)` suffix that
ticket-024 decided and left to this ticket because this is where the layout is assembled.

The three original key decisions and the three open questions resolve as follows.

- **The heading is the curated `ChartSpec.title`**, which ticket-020 exported as the chart `title` and
  ticket-021 rendered as the `<h2>`; the registry long name is the additive `<p class="chart-subtitle">`
  when it differs. That is epic decision E3-2, and it is why the Plotly layout carries no `title`:
  a Plotly title would duplicate the HTML heading.
- **The height is fixed at the legacy 450 pixels and the width is responsive.** The legacy 1400 by
  450 was chosen for one specific screen; a fixed width would overflow a laptop and waste space on a
  wide monitor. `autosize` in the layout template, `responsive: true` in the Plotly config from
  ticket-022, and `max-width: 1400px` in `dashboard.css` together keep the legacy proportions where
  there is room and shrink gracefully where there is not.
- **No custom hover template.** `hovermode: "x unified"` is the legacy look and already groups the
  scenarios at one timestamp; `xaxis.hoverformat` already renders that timestamp as
  `%d/%m/%Y %H:%M`. A per-trace `hovertemplate` would be a second formatting path for no gain.
- **All five SIN charts render stacked**, one below the other, following the ruling ticket-023
  recorded: the legacy scripts produced one file per chart and the analyst scrolls.
- **No forced zero baseline.** `rangemode: "tozero"` on a generation chart whose values sit around
  50 000 MW would compress the scenario differences into a hairline. The `zeroline` from the layout
  template draws zero whenever it is inside the range, which is the honest middle and is what the
  Diferença view needs.
- **No `limite_inferior` and `limite_superior` bands.** This is settled upstream rather than decided
  here: ticket-018 stores only `valor`, so the payload carries no bounds at all. Adding them would
  mean reopening the data layer and roughly doubling the plant-level payload for something the spec
  does not request.

### Relation to Epic

The ticket that completes the rendering path and reaches milestone M3: a single offline HTML with the
ONS identity rendering SIN charts for every scenario, with the mode toggle, the deck selector and the
Absoluto and Diferença toggle all working. It consumes ticket-023 `setGroup` and ticket-024
`state.valueMode`, and it hands ticket-026 a finished `buildLayout` that the submarket and
interchange charts reuse without change.

### Current State

`dashboard.js` exposes `payload`, `state`, `axisKey`, `buildTraces`, `renderChart`,
`renderActiveGroup`, `init`, `setMode`, `setDeck`, `setGroup` and `setValueMode`. `renderChart`
currently calls
`Plotly.react(container, buildTraces(chartKey), JSON.parse(JSON.stringify(payload[KEYS.THEME][KEYS.LAYOUT])), config)`
— the shared template with no per-chart part. `buildTraces` already handles both value modes, skips a
scenario whose series entry is absent, appends the terminal `end` point, and sets
`connectgaps: false` and `line.shape: "hv"`. Every payload read goes through the frozen `KEYS`
object, which currently declares the keys needed by tickets 022 and 024 but **not** `unit`, `labels`
or `y_axis_difference_suffix`.

The payload gives each chart entry a `unit` from `Registries.unit_for` and a
`labels.y_axis_difference_suffix` equal to ` (diferença)`. Ticket-021 rendered one
`<section class="chart" data-group="SIN">` per SIN chart, unhidden because `SIN` is the group of the
first enabled spec, each holding an `<h2>`, no `<select>` because the selector is `NONE`, and a
`<div class="plot" id="plot-KEY">`.

Measured on the `scenario_tree` fixture, in `enabled_specs` order: `GTER_SIN` titled
`Geração Térmica` with unit `MW`; `GHID_SIN` titled `Geração Hidrelétrica`, `MW`; `GUNS_SIN` titled
`Geração Não Simulada`, `MW`; `EARMF_SIN` titled `EARMF`, `MWh`; `VARMF_SIN` titled
`Volume Armazenado`, `hm3`. Each has exactly one entity, `{"id": "", "label": "Sistema Interligado"}`.
Both deck axes have 50 positions and the chained axis 96, so each SIN chart holds 50, 50 and 96
values per scenario. Note that `VARMF_SBM` carries the **same** curated title `Volume Armazenado`, so
any assertion on that heading must be scoped to the `data-group="SIN"` section slices.

## Specification

### Requirements

1. In `assets/dashboard.js`, add `buildLayout(chartKey)`. It returns a **fresh deep copy** of
   `payload[KEYS.THEME][KEYS.LAYOUT]`, obtained with `JSON.parse(JSON.stringify(...))` because
   `Plotly.react` writes computed properties into the layout it receives and 23 charts must not share
   one object.
2. `buildLayout` sets the Y-axis title text to `chart[KEYS.UNIT]` in Absoluto mode, and to
   `chart[KEYS.UNIT] + payload[KEYS.LABELS][KEYS.Y_AXIS_DIFFERENCE_SUFFIX]` when `state.valueMode` is
   `"diferenca"`, implementing the suffix ticket-024 decided. The suffix text is never written into
   this file: it comes from the payload, which is what keeps the asset pure ASCII.
3. `buildLayout` changes nothing else. It must not add a `title`, a `rangemode`, an `annotations`
   entry, a second Y axis or a `hovertemplate`, and it must not touch `xaxis`: the tick format, the
   hover format, the grid, the font, the height and `autosize` all come from the template and are
   already correct.
4. `renderChart(chartKey)` calls `buildLayout(chartKey)` instead of copying the template inline, so
   the layout is assembled in exactly one place. After this change the asset assigns `yaxis` in
   exactly one function.
5. Expose `buildLayout` on `window.DessemDashboard` in addition to the eleven members present after
   ticket-024, and add `"unit"`, `"labels"` and `"y_axis_difference_suffix"` to the frozen `KEYS`
   object. Every payload read still goes through `KEYS`, and the file stays pure ASCII.
6. Write no unit literal into the asset. The strings `"MW"`, `"MWh"`, `"hm3"` and `"m3/s"` must not
   appear: the unit is per chart data, and a hard-coded default would silently mislabel `EARMF_SIN`,
   whose unit is `MWh` rather than the `MW` of the other four SIN charts.
7. Create `tests/test_charts_sin.py`, the end-to-end verification of the SIN view: it builds the
   document from the `scenario_tree` fixture and asserts the chart-by-chart facts listed under
   Acceptance Criteria and Testing Requirements, always scoping a heading assertion to the
   `data-group="SIN"` section slice so a same-titled chart in another group cannot satisfy it.
8. Change no Python module. This ticket touches one asset and one new test file; `builder.py`,
   `payload.py` and `theme.py` are already complete for the SIN view.

### Inputs

At run time, `state.valueMode`, the chart entry `unit`, and the shared layout and labels from the
payload. At test time, the asset text and a document built from the fixture.

### Outputs and Behavior

Every rendered chart carries its unit on the Y axis, `dd/mm/yyyy hh:mm` tick and hover labels on the
X axis, one step-interpolated curve per scenario in its scenario colour, a visible hole wherever a
value is `null`, and a 450 pixel height at up to 1400 pixels of width. In Diferença mode the Y-axis
title gains ` (diferença)`. Opening the built file shows the five SIN charts stacked, because `SIN`
is the initially active group.

### Error Handling

No new error path. A chart key absent from the payload would make `buildLayout` fail on an undefined
chart entry, which is a programming error and must reach the console rather than be swallowed:
`renderActiveGroup` only ever passes keys taken from the `data-chart` attributes that `builder.py`
generated from that same payload. No `try`/`catch` is added.

## Dependencies

- **Blocked By**: `ticket-023-implement-view-mode-and-deck-selector.md`,
  `ticket-024-implement-absolute-difference-toggle.md`
- **Blocks**: `ticket-026-render-submarket-and-interchange-charts.md`

## Acceptance Criteria

- [ ] Given `assets/dashboard.js`, when its text is inspected, then `window.DessemDashboard`
      names `buildLayout` in
      addition to the eleven members present after ticket-024, `buildLayout` contains
      `JSON.parse(JSON.stringify(`, it assigns a Y-axis title from `KEYS.UNIT`, and the asset
      contains none of the quoted literals `"MW"`, `"MWh"`, `"hm3"` and `"m3/s"`; and on the fixture
      payload the five SIN units are `MW`, `MW`, `MW`, `MWh` and `hm3` for `GTER_SIN`, `GHID_SIN`,
      `GUNS_SIN`, `EARMF_SIN` and `VARMF_SIN` respectively.
- [ ] Given the same text, when the Diferença branch is inspected, then the suffix is read as
      `payload[KEYS.LABELS][KEYS.Y_AXIS_DIFFERENCE_SUFFIX]` and appears nowhere as a literal,
      `text.isascii()` is `True`, and on the fixture payload
      `payload["labels"]["y_axis_difference_suffix"]` equals `" (diferença)"`, so the accented text
      reaches the browser from Python and not from the asset.
- [ ] Given the same text, when the render path is inspected, then `renderChart` calls
      `buildLayout(` exactly once and no longer copies
      `payload[KEYS.THEME][KEYS.LAYOUT]` inline, the string `yaxis` is assigned in exactly one
      function, and the asset contains none of `rangemode`, `annotations`, `hovertemplate` or a
      second `Plotly.react(` call.
- [ ] Given the same text and the document built from the fixture, when both are inspected, then
      the `KEYS` object declares `"unit"`, `"labels"` and
      `"y_axis_difference_suffix"`, each occurring exactly once in the asset; and given the document
      built from the fixture, the five `data-group="SIN"` section slices carry, in `enabled_specs`
      order, the headings `Geração Térmica`, `Geração Hidrelétrica`, `Geração Não Simulada`, `EARMF`
      and `Volume Armazenado`, none of them contains `<select`, and each contains exactly one
      `<div class="plot" id="plot-KEY">`.
- [ ] Given the fixture payload, when the five SIN chart entries are read, then for each of them
      `entities` equals
      `[{"id": "", "label": "Sistema Interligado"}]` and the series arrays hold 50, 50 and 96 values
      for `03/03/2024`, `04/03/2024` and `encadeado` in both `caso_a` and `caso_b`; and
      `.venv/bin/pytest tests/test_charts_sin.py tests/test_renderer_contract.py
      tests/test_renderer_value_mode.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Add the three `KEYS` entries first, then write `buildLayout` immediately above `renderChart`, then
   replace the inline copy inside `renderChart` with the call. The whole JavaScript change is about
   a dozen lines.
2. Build the Y-axis title as a single expression, with the suffix concatenated only in the Diferença
   branch, so there is one assignment rather than a mutation followed by an append.
3. Set the title through `layout.yaxis.title = {text: ...}`, matching the shape the layout template
   already uses for its empty title, rather than the deprecated bare-string form.
4. Write `tests/test_charts_sin.py` by slicing the document on `<section class="chart"` boundaries
   and filtering the slices on `data-group="SIN"`, then asserting inside each slice. Scoping is
   mandatory, not stylistic: `Volume Armazenado` is also the curated title of `VARMF_SBM`, so a
   document-wide substring assertion would pass even if the SIN heading were missing.
5. Use the `tmp_path/settings.json` copy pattern, so no test writes into the repository `output/`.
6. Walk items 1, 2 and 5 of `docs/checklist-manual-dashboard.md` by hand after the change: the
   offline console check, the ONS identity, and the Absoluto and Diferença case whose Y-axis title
   this ticket completes.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: `buildLayout` plus the `renderChart`
  call and three `KEYS` entries)
- `tests/test_charts_sin.py` (create)

### Patterns to Follow

- The frozen `KEYS` discipline: three new entries, no payload key literal anywhere else.
- The deep-copy-per-render rule ticket-022 established, now centralised in `buildLayout`.
- English identifiers and comments in the asset; every operator-visible string comes from the payload
  or from the HTML.
- The document-slicing test pattern: assert inside the slice of the section under test, never over
  the whole 4.5 MB document.

### Pitfalls to Avoid

- Do not assert a heading over the whole document. `Volume Armazenado` belongs to both `VARMF_SIN`
  and `VARMF_SBM`, and `Geração Térmica` to both `GTER_SIN` and `GTER_SBM`, so an unscoped assertion
  would be satisfied by the wrong section.
- Do not hard-code a unit. `EARMF_SIN` is `MWh` while the other four SIN charts are `MW`, so a
  group-level default is wrong on the very first group.
- Do not write ` (diferença)` into the asset. It is the reason `payload.labels` exists, and an
  accented literal would break the pure-ASCII invariant that keeps operator text out of the
  JavaScript.
- Do not add a Plotly `title`. Epic decision E3-2 makes the HTML `<h2>` the heading, and a Plotly
  title would render a second one inside the plot area, on top of the 10 pixel top margin the
  template leaves.
- Do not set `rangemode: "tozero"`. On a generation chart it flattens exactly the scenario difference
  the dashboard exists to show.
- Do not reintroduce a shared layout object. `Plotly.react` mutates it, and with five stacked charts
  the symptom is one chart adopting another axis range, which looks like a data bug.
- Do not add the `limite_inferior` and `limite_superior` bands. The payload carries no bounds, so
  this would require reopening ticket-018 and the data layer contract.
- Do not modify `builder.py`, `payload.py` or `theme.py`. The SIN view needs nothing further from
  them, and ticket-026 depends on their current behaviour.

### Out of Scope

- The submarket and interchange charts and the entity-selector behaviour (ticket-026).
- The hydro and thermal plant charts and their filters (tickets 027 to 029).
- The `CUSTOS` and `TEMPO` bar charts, whose kind is `SCALAR_BY_DECK` and whose containers this
  ticket leaves empty (tickets 030 and 031).
- Any change to the layout template, the CSS, the HTML template or the payload.
- Confidence bands, a percentage view or any derived series.

## Testing Requirements

### Unit Tests

`tests/test_charts_sin.py`:

- the five acceptance criteria;
- the set of `data-group="SIN"` chart keys in the document equals
  `{"GTER_SIN", "GHID_SIN", "GUNS_SIN", "EARMF_SIN", "VARMF_SIN"}`, so a chart silently dropped from
  the group fails here;
- each of the five SIN section slices contains exactly one `<h2>` and no `<p class="chart-subtitle">`
  on the unmodified fixture, whose `METADADOS_OPERACAO.parquet` writes `nome_longo_variavel` equal
  to the curated title for every key;
- the same document with `charts.disabled = ["EARMF_SIN"]`: four SIN sections, no
  `id="chart-EARMF_SIN"`, and the remaining four headings unchanged;
- the payload series values for `GHID_SIN` are all either `None` or equal to themselves rounded to
  two decimals, so the Y axis plots pre-rounded data;
- the asset assertions of the first four criteria, each confirmed able to fail by temporarily
  breaking the asset before restoring it — in particular the `"MW"` literal check, by inserting the
  literal, observing the failure, and removing it.

### Integration Tests

None automated, by epic decision E3-1. Items 1, 2 and 5 of `docs/checklist-manual-dashboard.md`
cover the offline console check, the ONS identity and the Absoluto and Diferença case; the run
against real data is ticket-034.

## Definition of Done

- [ ] Both files exist, one modified and one created, and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] The Y-axis title is per chart and data-driven, and the asset contains no unit literal.
- [ ] The layout is assembled in exactly one function, from a fresh deep copy per render.
- [ ] `tests/test_builder.py`, `tests/test_renderer_contract.py`, `tests/test_renderer_controls.py`
      and `tests/test_renderer_value_mode.py` all pass unchanged.
- [ ] Milestone M3 is demonstrable: the built file, opened offline, shows the five SIN charts for
      both scenarios with working mode, deck and value controls.

## Effort Estimate

**Points**: 2 · **Confidence**: Medium · **Agent time**: about 25 minutes. The JavaScript change is
small; the effort is in the end-to-end assertions, and confidence is Medium because the rendered
result itself is verified by the manual checklist under epic decision E3-1.
