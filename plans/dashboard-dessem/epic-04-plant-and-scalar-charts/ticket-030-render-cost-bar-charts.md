# ticket-030 Render the cost bar charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-029 and strictly before ticket-031.** The epic graph
> allows this ticket to run in parallel with the 027-to-029 chain, and it must not: it modifies
> `dashboard/payload.py`, which ticket-027 also modifies, and `dashboard/builder.py`, which
> ticket-028 also modifies. ticket-031 then extends the module and the bar-render path this ticket
> creates, and edits the same `tests/test_payload.py` test function.
> **This is the heaviest ticket of the epic** — seven files across four layers. It is not split only
> because the epic's ticket numbering is fixed and ticket-033 already owns the next number; if the
> orchestrator prefers to split it, the natural seam is the Python aggregation (requirements 1 to 5)
> against the renderer changes (requirements 6 to 9).

## Context

### Background

`CUSTOS` is spec item 22 of master plan Appendix A.6, `Custo presente, futuro e total`, and one of
the two `SCALAR_BY_DECK` charts in the catalogue. `CUSTOS.parquet` holds four rows —
`parcela ∈ {PRESENTE, FUTURO, VIOLACOES, PEQUENAS PENALIDADES}`, `valor_esperado` in R$ — one file
per deck, and the chart is a grouped bar chart by deck date with one bar per scenario, independent of
the view mode (`planning-context.md` decision 5).

The data is already in the payload and the section is already in the document, but **no bar has ever
been drawn**. `consolidate._load_scalars` stores one value per (parcela, scenario, deck), summing
rows that share a `parcela` and dividing nothing; ticket-020's `_build_scalars` exports them as
`scalars[series_name][scenario][deck_key]` and deliberately computes **no total**, because
requirement 9 of that ticket assigned the cost total and the `TEMPO` grouping to tickets 030 and 031
so that both stay configurable. ticket-021 renders the `EXECUCAO` sections with an empty
`<div class="plot">`, and ticket-025 recorded that it leaves those containers empty. The renderer's
`buildTraces` reads only `chart[KEYS.SERIES]` and hard-codes `type: "scatter"`, so a scalar chart
currently produces an empty figure rather than an error.

Epic decision **E4-1** fixes the arithmetic: the total is the sum of the parcels named by
`costs.total_parcels`, never a hard-coded `PRESENTE + FUTURO` anywhere, and a parcel named in
settings but absent from `CUSTOS.parquet` is a **Portuguese warning plus omission**, never a crash —
the same degradation rule as master plan decision 18, because a study that omits a parcel is still
worth comparing. Master plan Appendix A.7 describes the legacy parity target as "presente, futuro and
total as presente plus futuro"; that is the *outcome* of the default configuration, not a mechanism,
and the parity check in ticket-038 must compare against the default settings rather than assume a
literal pair.

The epic-03 boundary review found four further mechanics missing, all verified by reading and none
observable from Python:

- **The shared layout would mislabel the axis outright.** `theme.plotly_layout_template()` fixes
  `xaxis.type` at `"date"` with `tickformat` and `hoverformat` from `dashboard.date_format`, and
  `buildLayout` deep-copies it unconditionally for every chart. A bar chart's categories are the deck
  keys, which are already `%d/%m/%Y` strings (`03/03/2024`, `04/03/2024`). Fed to a date axis, Plotly
  falls back to JavaScript date parsing, which is **month-first**: `04/03/2024` would render as
  3 April rather than 4 March, two decks one day apart would sit a month apart, and the tick would
  read `03/04/2024 00:00`. Every test would stay green, because the defect exists only in the
  browser.
- **The layout carries no `barmode`**, so the geometry depends on a library default. Plotly's
  documented default is `group`, but a stacked default would draw the total on top of its own
  parcels and lie by exactly a factor of two; the value is load-bearing enough to be written down.
- **`line.shape: "hv"` and `connectgaps: false` are trace-level series settings.** A bar trace simply
  does not set them, so nothing must be overridden — but neither may `buildBarTraces` copy the
  scatter trace wholesale.
- **The renderer cannot read a chart's kind at all.** `KEYS` has no `kind` entry, and
  `builder._chart_sections` emits `data-chart`, `data-group` and `data-selector` but no `data-kind`.
  Both are added here: `KEYS.KIND` because the branch needs it, and `data-kind` because the DOM
  contract already describes every chart by its attributes and `data-selector` has exactly the same
  status — emitted by Python, never read by the asset, and the handle every test slices on.

The three original key decisions and the three open questions resolve as follows.

- **The aggregation happens in Python, at payload build time.** Three reasons converge. E4-1 demands
  a **Portuguese** warning for a missing parcel, and the payload has no `warnings` key while the
  browser has no operator-facing channel but the console. E3-1's whole pattern is to move every
  decidable thing into Python and assert the artefact, which is why `buildTraces` shapes no data
  beyond naming a trace. And doing it in the browser would need `costs.total_parcels` shipped as a
  tenth chart key or a new top-level key, both of which break the nine-key contract
  `tests/test_payload.py` asserts as a set. "Configurable" in ticket-020 requirement 9 means
  `settings.json`-driven, not interactively re-derivable: an operator who wants `VIOLACOES` in the
  total edits one settings key and rebuilds, which is the whole point of the key existing.
- **The bars are exactly the configured parcels plus their total.** The displayed series are the
  parcels named in `costs.total_parcels`, in configured order, followed by `TOTAL`. This answers the
  outline's second question without a second setting: with the default
  `["PRESENTE", "FUTURO"]` the chart is precisely spec item 22 and the legacy parity target, and a
  developer who adds `VIOLACOES` to the key gets both its bar and its contribution to the total, so
  the composition on screen always adds up to the total on screen. Showing an unconfigured parcel as
  a bar that the total ignores would be the more confusing of the two options, and
  `VIOLACOES ≈ 0 R$` with `PEQUENAS PENALIDADES ≈ 40 R$` would render as two invisible bars anyway.
- **The three series are one chart, not three.** The catalogue has exactly one `CUSTOS` spec and
  `enabled_specs()` returns 23 — both pinned — and `builder._chart_sections` renders one
  `<section class="chart">` with one plot `<div>` per spec. Three separate charts would mean three
  new registry entries and a new document contract; the legacy's three files are reproduced as three
  category groups in one figure.
- **The X axis is a flat `category` axis whose labels combine the deck key and the series name**, in
  deck-major order, with one bar trace per scenario in payload order. That keeps the legend at one
  entry per scenario (decision 5) and the grouping by deck date (decision 5 again) while showing
  every parcel at once as the legacy did. A two-level `multicategory` axis would render prettier tick
  labels and was rejected: it needs a two-dimensional `x` array, a second data shape in an asset
  whose thinness is the reason it can be tested at all, for a cosmetic gain. A parcel selector was
  also rejected: `CUSTOS`'s spec fixes `selector=NONE` and its payload `entities` is asserted empty,
  so a selector would reopen two pinned contracts and hide two thirds of the chart behind a control.
- **The Diferença toggle applies to the bars.** `planning-context.md` decision 8 is unambiguous —
  *every* chart gets the toggle — and a bar chart that silently ignored it would show identical bars
  in both modes, which is worse than not having it. The difference of a cost total between two
  scenarios is arguably the single most interesting number in the dashboard. It is computed in the
  browser from the absolute values, through the **existing** `valuesForMode`, which already handles
  `null` on either side and rounds by `formats.decimals`. Requirement 8 records the cross-ticket
  collision this creates and its sanctioned resolution.
- **The scale divergence is accepted, documented and not worked around.** `PRESENTE` and `FUTURO`
  are expected to differ by orders of magnitude, so on one linear axis the present-cost bar may be a
  fraction of a percent of the future-cost bar and effectively invisible. The three available fixes
  are all worse: a log axis cannot render the signed Diferença view and `rangemode` is a token
  `tests/test_charts_sin.py` forbids outright; a second Y axis is forbidden by the same file's
  single-`yaxis`-function assertion; and a per-parcel chart needs three registry entries, which this
  ticket's Out of Scope forbids. The exact values stay readable through `hovermode: "x unified"`,
  which the layout already sets, and through Plotly's box zoom. ticket-031 records the caveat as a
  manual checklist step so the developer sees it on real data and can decide then whether it is
  worth a further ticket.

  > **Corrected 2026-09-11 — spec defect 17, and a third new shape for the catalogue: a
  > quantitative claim attributed to a source its author could not reach.** This bullet originally
  > read "In the real data `FUTURO` is about 2.3e8 R$ while `PRESENTE` is about 5.9e4 R$, so ... is
  > about 0.03 percent". Those figures appear nowhere in the repository outside this sentence:
  > `planning-context.md` records the `CUSTOS` schema and the legacy total but no magnitudes, and
  > the real data lives under `exemplo/`, which every agent on this plan is forbidden to read. The
  > refinement therefore could not have measured them. The **direction** of the claim is sound and
  > the reasoning it supports still holds, so the design decision stands unchanged; only the false
  > precision is removed. Do not restore a specific figure here without measuring it, and do not
  > quote these numbers to the developer as if they were observed.

- **A legacy-parity tension this ticket does not resolve, recorded for ticket-035.** The tool this
  project replaces, `Plotadores/Custos.py`, does **not** put the three cost quantities on one axis:
  it emits three separate figures, with the Y-axis titles `Custo Presente (R$)`,
  `Custo Futuro (R$)` and `Custo Total de Operação (R$)`. This ticket deliberately ships one
  grouped bar chart instead, which is what the single registry entry
  `_scalar("CUSTOS", "Custo Presente, Futuro e Total")` and `planning-context.md`'s "bars per deck"
  describe, and a three-chart split is explicitly out of this ticket's scope because it needs three
  new `ChartSpec` entries in the epic-02 `charts/specs.py`. The consequence is that the new
  dashboard shows one chart where the legacy showed three, with one series possibly invisible where
  the legacy gave it its own axis. **ticket-035 is the legacy parity check and is the right place
  for this to surface, against real data and in front of the developer.** It is recorded here so
  that the parity check is not read as passing merely because the totals agree.

### Relation to Epic

The first of the two scalar tickets and the one that builds the machinery: a Python aggregation
module, the payload route into it, the `data-kind` attribute, the `KEYS.KIND` entry, the bar trace
builder and the categorical layout branch. ticket-031 then adds one function to that module and
changes nothing else in the renderer, which is what makes it a 2-point ticket.

### Current State

`consolidate._load_scalars` stores, per `SCALAR_BY_DECK` chart, `scenario` and deck, one value per
distinct `parcela` or `etapa`, summing rows that share it with `min_count=1` so an all-missing group
stays `None` rather than becoming `0.0`. It applies **no total, no grouping and no division**, and
its docstring says so explicitly, naming tickets 030 and 031 as the owners.

`payload._build_scalars(data, chart_key, *, decimals)` returns
`{series_name: {scenario: {deck_key: rounded_value}}}`, built from `data.scalars(chart_key)` whose
keys are `(series_name, scenario, deck_date)` triples, with `deck_key = data.deck_axis(deck_date).key`
— already `%d/%m/%Y`, never reformatted through `dashboard.date_format`, which carries `%H:%M` and
would render a deck as `03/03/2024 00:00`. `_build_chart_entry`'s `SCALAR_BY_DECK` branch sets
`entities` to `[]` and `series` to `{}`.

`tests/test_payload.py` pins, in `test_build_payload_custos_and_tempo_scalars_shape_and_no_division_by_unit_divisor`:
`len(custos) == 4`, `len(tempo) == 5`, that every series of both charts has both scenarios and both
deck keys, that `tempo["PL"]["caso_a"]["03/03/2024"]` equals the **raw second** sum of the three `PL`
rows, and that this figure exceeds 60. A second test asserts `len(tempo["scalars"]) == 5` alongside
the nine-key set. Those assertions pin ticket-020's scope boundary, which this ticket and ticket-031
are chartered to cross — one chart each.

`dashboard.js` exposes thirteen members after ticket-026. `renderChart(chartKey)` calls
`buildTraces(chartKey)`, then `buildLayout(chartKey)`, then `Plotly.react`. `buildTraces` reads
`state.entities[chartKey]`, `payload[KEYS.AXES][axisKey()]` and `chart[KEYS.SERIES]`, resolves the
reference series inside `if (state.valueMode === "diferenca") {`, and returns `[]` when that
reference read is `undefined`. `valuesForMode(values, referenceValues)` is the one place the
difference arithmetic lives: `null` when either side is `null`, otherwise the difference rounded by
`payload[KEYS.FORMATS][KEYS.DECIMALS]`.

Pinned asset invariants this ticket must keep: `text.count("Plotly.react(") == 1`;
`Plotly.newPlot(` absent; `renderChart`'s body calls `buildLayout(` exactly once and does not
contain `payload[KEYS.THEME][KEYS.LAYOUT]`; `yaxis` is assigned in exactly one function; the tokens
`rangemode`, `annotations` and `hovertemplate` are absent from the whole asset;
`text.count("Object.freeze({") == 1`; `text.count('"absoluto"') == 0`; `text.isascii() is True`;
every `KEYS` value's quoted literal occurs exactly once inside the `KEYS` declaration and never as a
raw index; every `payload[` is followed by `KEYS.`; and — the assertion being added at the epic-03
boundary, to be assumed in force — **dot access on a payload-derived object is forbidden**, so a
chart entry's field is read as `chart[KEYS.KIND]`, never as `chart.kind`.

Two assertions of `tests/test_renderer_value_mode.py` are **over-broad rather than wrong**, and
block requirement 6: `text.count('"diferenca"') == 1` and `text.count("KEYS.REFERENCE") == 1`. Both
express "`buildTraces` decides the value mode once" but enforce "appears once in the whole file", and
a third assertion of the same file requires `payload[KEYS.REFERENCE]` to appear **inside**
`buildTraces`'s difference branch, so the single occurrence cannot be hoisted into a shared helper
either. The epic-03 learnings recorded this exact situation, prescribed the fix — narrow the
assertion to the function body, do not invent a second workaround — and noted that ticket-025 already
paid a workaround to the first of the two.

`tests/test_builder.py` asserts `all(tag.endswith(" hidden>") for tag in other_tags)` over the
section opening tags, and `tests/test_charts_submarket.py` asserts
`_opening_tag(section).endswith(" hidden>")`. The new `data-kind` attribute must therefore be
inserted **before** the optional ` hidden`, not appended after it.

Measured on the `scenario_tree` fixture: `CUSTOS.parquet` holds the four parcelas with values drawn
from `uniform(0, 1_000_000)` and a distinct seed per (scenario, deck) — 42, 43, 44, 45 — so no two
cells are equal and a value stored under the wrong scenario or deck is detectable. `deck_dates` is
`["03/03/2024", "04/03/2024"]`, the chart's `unit` is `R$` from `METADADOS_OPERACAO`, and its curated
title is `Custo Presente, Futuro e Total`.

## Specification

### Requirements

1. Create `src/dessem_dashboard/dashboard/scalars.py` with one public entry point,
   `aggregate(chart_key, raw, *, settings)`, taking and returning the
   `{series_name: {scenario: {deck_key: value}}}` shape `_build_scalars` builds. It dispatches on the
   chart key: `CUSTOS` to `aggregate_costs`, and **any other key straight through, unchanged**, so
   `TEMPO` keeps ticket-020's raw shape until ticket-031 adds its branch. The module reads no file,
   logs through its own module logger, and imports nothing from `builder` or `theme`.
2. `aggregate_costs(raw, *, parcels, decimals)` emits one series per parcel named in `parcels` that
   is present in `raw`, in the order `parcels` gives, each carrying exactly the `{scenario:
   {deck_key: value}}` mapping `raw` held for it, followed by one `TOTAL` series. Never compute the
   total as a literal `PRESENTE + FUTURO` and never hard-code the pair: E4-1's whole point is that
   including `VIOLACOES` is a configuration edit rather than a code change.
3. The `TOTAL` value for a given `(scenario, deck_key)` is the sum of the **already rounded** parcel
   values, rounded once more to `decimals`, so the total bar equals the sum of the parcel bars exactly
   as an operator reads them off the chart. It is emitted **only** when every emitted parcel has a
   non-`None` value for that `(scenario, deck_key)`; otherwise that key is absent from `TOTAL`, and
   the browser draws no total bar there. A total summed over a subset would be a wrong number rather
   than a degraded one, and no extra warning is emitted for it: the cause is already reported by the
   `consolidate` warning naming the chart, the scenario and the deck.
4. A parcel named in `parcels` but absent from `raw` altogether is logged **once** as a Portuguese
   `logger.warning` naming the parcel and the dotted settings key `costs.total_parcels`, is omitted
   from the bars, and contributes nothing to the total, which is then the sum of the remaining
   configured parcels. No exception is raised — this is E4-1's explicit degradation rule, and it is a
   different case from requirement 3's missing cell, governed by a different rule and implemented
   separately.
5. `TOTAL` appearing in `parcels` is a configuration contradiction — the computed series would
   overwrite a data series of the same name — and raises `ConfigError` with a Portuguese message
   naming `costs.total_parcels`. `ConfigError` already exists in `errors.py`; add no eighth class to
   that module.
6. In `payload.py`, route `_build_scalars`' result through `scalars.aggregate(spec.key, raw,
   settings=settings)`, passing `settings` down from `build_payload` in place of, or in addition to,
   the `decimals` argument. Change nothing else: the nine chart keys, the `scalars[series_name]
   [scenario][deck_key]` nesting, `_build_series`, the entity rules ticket-027 added, the rounding
   helper and the two INFO lines all stay.
7. In `builder._chart_sections`, add `data-kind="{spec.kind.value}"` to each section's opening tag,
   **between `data-selector` and the optional ` hidden`**. Two existing tests assert that a hidden
   section's opening tag ends with ` hidden>`, so appending the attribute after `hidden` would break
   them for no reason. The asset never reads this attribute; it exists for the same reason
   `data-selector` does — a document that describes its own charts, and a handle tests can slice on.
8. In `dashboard.js`:
   a. add `KIND` and `SCALARS` to the frozen `KEYS` object, and declare one plain
      `const` holding the scalar kind name `SCALAR_BY_DECK` (a second `Object.freeze({` is forbidden);
   b. add `buildBarTraces(chartKey)` returning one trace per scenario in `payload[KEYS.SCENARIOS]`
      order, each `{type: "bar", name: scenario, x: categories, y: values, marker: {color:
      scenarioColor}}`, where `categories` is the flat list of `deckKey + separator + seriesName`
      over `payload[KEYS.DECK_DATES]` × the series names of `chart[KEYS.SCALARS]`, in **deck-major**
      order, and `values` reads `chart[KEYS.SCALARS][name][scenario][deckKey]` with `null` wherever
      any level of that lookup is absent — never `0`. The separator is one module-level ASCII `const`
      so it lives in exactly one place;
   c. compute the Diferença view by reading the reference scenario's array over the same grid and
      passing both arrays to the existing `valuesForMode`, which needs no change; when the reference
      scenario contributes no value at all, return an empty trace list, mirroring `buildTraces`'
      early return rather than drawing a zero baseline;
   d. branch in `renderChart`: read the chart entry once, choose `buildBarTraces(chartKey)` when
      `chart[KEYS.KIND]` equals the scalar kind and `buildTraces(chartKey)` otherwise, then call
      `buildLayout(chartKey)` **exactly once** and `Plotly.react` exactly once, as today. Do not add
      a second `Plotly.react`, do not use `Plotly.newPlot`, and do not read
      `payload[KEYS.THEME][KEYS.LAYOUT]` inside `renderChart`;
   e. expose `buildBarTraces` on `window.DessemDashboard` in addition to the thirteen members present
      after ticket-026, and keep the asset pure ASCII: every operator-visible string in this chart
      comes from the payload or from `builder.py`.
9. In `buildLayout`, add a scalar-kind branch that sets `xaxis.type` to `"category"`, removes the
   `tickformat` and `hoverformat` entries the theme set from `dashboard.date_format`, and sets
   `barmode` to `"group"`. It must still assign `yaxis` in that one function only, add no second Y
   axis, and introduce none of `rangemode`, `annotations` or `hovertemplate`. `hovermode: "x unified"`
   is deliberately **kept** for bar charts: it groups every scenario at one category, which is the
   comparison the chart exists for. ticket-025 requirement 3 said `buildLayout` "must not touch
   `xaxis`"; that scoped to the series charts it was written for, no test enforces the wider claim,
   and leaving the date axis in place would silently reparse `04/03/2024` as 3 April.
10. Narrow the two over-broad assertions of `tests/test_renderer_value_mode.py`:
    `text.count('"diferenca"') == 1` and `text.count("KEYS.REFERENCE") == 1` each become "exactly
    once inside `buildTraces`'s body, exactly once inside `buildBarTraces`'s body, and nowhere else in
    the asset", using that file's existing `_function_body` helper. Change nothing else in it — in
    particular keep `text.count('"absoluto"') == 0`, the `Math.pow(10, payload[KEYS.FORMATS]
    [KEYS.DECIMALS])` assertion, the `* 100` and `/ 100` prohibitions, and the early-return assertion
    on the difference branch, which still holds because the branch keeps its exact text. Prove the
    narrowed form still fails when a third occurrence of either token is injected into a third
    function.
11. In `tests/test_payload.py`, change exactly one assertion — `assert len(custos) == 4` becomes
    `== 3` — and extend that test's comment to name the new `CUSTOS` series set. Leave every `tempo`
    assertion, the test's name and every other test in the file untouched: requirement 1's
    pass-through keeps them true, and ticket-031 owns them.
12. Create `tests/test_charts_costs.py`, covering `aggregate_costs` directly, the payload it produces,
    the asset text and the `EXECUCAO` section slices, with the non-vacuity mutations listed under
    Testing Requirements.
13. Add no `ChartSpec`, no registry entry, no settings key, no parcel selector, no log axis, no second
    Y axis, no stacked geometry and no percentage view. Do not touch `theme.py`, `consolidate.py`,
    `store.py`, `dashboard.css`, `dashboard.html` or `docs/checklist-manual-dashboard.md` — ticket-031
    writes the one manual-checklist section that covers both bar charts, so it is not written twice.

### Inputs

At build time, `data.scalars("CUSTOS")` through `_build_scalars`, and `settings.costs.total_parcels`
and `settings.output.decimals`. At run time, `payload.charts.CUSTOS.scalars`, `deck_dates`,
`scenarios`, `reference`, `theme.scenario_colors` and `formats.decimals`. At test time, the fixture
tree, three settings variants (the default pair, all four parcelas, a non-existent parcel), a raw
mapping built by hand, the asset text and documents built from the fixture.

### Outputs and Behavior

The `Execução` level shows the cost chart as grouped bars: one category per (deck, series) in
deck-major order, one bar per scenario in its scenario colour, the legend listing the scenarios in
`--casos` order, `R$` on the Y axis, and exact values on a unified hover. Switching to Diferença
turns every bar into `scenario − reference`, with the reference scenario's bars at zero and the Y
axis reading `R$ (diferença)`. The bars do not change with the view mode or the deck selector, per
decision 5. A missing parcel, a missing file or a missing deck leaves a gap rather than a zero bar,
and the Avisos section plus the run log explain it.

### Error Handling

One new raise and one new warning, deliberately different in kind. `ConfigError` for `TOTAL` listed
among `costs.total_parcels` (requirement 5): the configuration contradicts itself and no output
would be correct. A Portuguese `logger.warning` for a configured parcel absent from the data
(requirement 4): the study is still comparable, so the run continues, which is E4-1 and decision 18.
Everything else degrades silently by omission and is already reported upstream: a missing
`CUSTOS.parquet` for one (scenario, deck) is warned by `consolidate` into the Avisos section, and the
browser skips a missing key instead of substituting zero. No `try`/`catch` is added to the asset, and
`build_payload` still never mutates `data`.

## Dependencies

- **Blocked By**: `ticket-026-render-submarket-and-interchange-charts.md` (the epic graph's edge:
  this ticket needs only the renderer core, not the plant level)
- **Dispatch-order constraint, not a graph edge**: it must not start before
  `ticket-029-render-thermal-plant-charts.md` has completed. The graph permits this branch to run
  in parallel with the 027-to-029 chain, and the file sets forbid it: ticket-027 also modifies
  `dashboard/payload.py` and ticket-028 also modifies `dashboard/builder.py`. Parallel dispatch
  works in this plan only where file sets are disjoint.
- **Blocks**: `ticket-031-render-computational-time-bar-charts.md`

## Acceptance Criteria

- [ ] Given a raw mapping holding the fixture's four parcelas for two scenarios and two deck keys,
      when `aggregate_costs` runs with `parcels=["PRESENTE", "FUTURO"]` and `decimals=2`, then the
      result keys are exactly `["PRESENTE", "FUTURO", "TOTAL"]` in that order, every `TOTAL` cell
      equals its two parcel cells summed within `0.01`, and `TOTAL` is strictly less than the sum of
      all four parcelas; and when it runs with all four parcelas configured, `TOTAL` equals their sum
      within `0.01`.
- [ ] Given the same raw mapping, when `aggregate_costs` runs with
      `parcels=["PRESENTE", "FUTURO", "INEXISTENTE"]`, then no exception is raised, the result keys
      are exactly `["PRESENTE", "FUTURO", "TOTAL"]`, and exactly one WARNING record of the
      `dessem_dashboard.dashboard.scalars` logger names both `INEXISTENTE` and `costs.total_parcels`;
      and when it runs with `parcels=["PRESENTE", "TOTAL"]`, a `ConfigError` naming
      `costs.total_parcels` is raised.
- [ ] Given the `scenario_tree` fixture and the repository `settings.json`, when the payload is built,
      then `charts["CUSTOS"]["scalars"]` has exactly the three keys `PRESENTE`, `FUTURO` and `TOTAL`,
      each with both scenarios and both deck keys `03/03/2024` and `04/03/2024`, `entities` is `[]`
      and `series` is `{}`; and `charts["TEMPO"]["scalars"]` still has its five raw etapa names, so
      the pass-through branch is proven and ticket-031's work is still visibly owed.
- [ ] Given the `dashboard.js` asset text, when it is inspected, then `window.DessemDashboard` names
      `buildBarTraces` in addition to the thirteen members present after ticket-026; the `KEYS`
      declaration contains `"kind"` and `"scalars"` exactly once each and neither appears as a raw
      index anywhere; the asset contains `type: "bar"`, reads the kind as `chart[KEYS.KIND]`,
      contains `"category"` and `barmode` inside `buildLayout`'s body, and contains
      `text.count("Plotly.react(") == 1`, `text.count("Object.freeze({") == 1`,
      `text.count('"absoluto"') == 0`, no `Plotly.newPlot(`, no `rangemode`, no `annotations`, no
      `hovertemplate`, `yaxis` assigned in exactly one function, and `text.isascii() is True`.
- [ ] Given the document built from the fixture, when the `data-group="EXECUCAO"` slices are
      inspected, then there are exactly two, their `data-chart` values are `CUSTOS` and `TEMPO`, both
      carry `data-kind="SCALAR_BY_DECK"` before their ` hidden` attribute and
      `data-selector="NONE"`, the `CUSTOS` slice holds exactly one `<h2>` reading
      `Custo Presente, Futuro e Total` and contains neither `<select` nor `plant-filter`, and every
      other section's opening tag carries `data-kind="SERIES"`; and
      `.venv/bin/pytest tests/test_charts_costs.py tests/test_payload.py
      tests/test_renderer_value_mode.py tests/test_charts_sin.py tests/test_charts_submarket.py
      tests/test_builder.py tests/test_renderer_contract.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `scalars.py` first and drive it entirely from unit tests over hand-built mappings: it is
   pure data in, data out, and every rule of requirements 2 to 5 is decidable there. Keep
   `aggregate`'s dispatch a small mapping or an `if` chain with an explicit pass-through, so
   ticket-031 adds one branch and one function.
2. Give `aggregate_costs` the parcel order from `parcels`, not from `raw`: the configured order is the
   operator's stated preference and `raw`'s insertion order is whatever pandas' `groupby` produced.
3. Build `TOTAL` by iterating the union of `(scenario, deck_key)` pairs the emitted parcels cover,
   not by assuming a rectangle: a scenario missing a deck legitimately has fewer cells, and
   requirement 3's all-parcels-present condition is then a single `all(...)` over the emitted
   parcels.
4. Thread `settings` through `_build_chart_entry` into `_build_scalars`. If that makes the signature
   awkward, pass the two values it needs — `settings` is already available in `build_payload` and
   `Settings` is frozen, so passing it whole is safe and keeps the call site honest.
5. In `builder.py` the change is one f-string fragment. Write the attribute immediately after
   `data-selector` so the ` hidden` suffix stays last, and confirm with
   `grep -c "data-kind" ` on a built document that it appears once per enabled chart.
6. In the asset, write `buildBarTraces` immediately after `valuesForMode` and before `buildTraces`.
   Build the category list and the per-scenario value list in one pass over decks then series, so the
   two are aligned by construction rather than by a second loop. Resolve the reference array before
   the scenario loop, exactly as `buildTraces` does, and pass it to `valuesForMode` unchanged.
7. Add the `renderChart` branch as a single conditional expression assigned to `traces`, so the
   function keeps one `buildLayout(` call and one `Plotly.react(` call and the pinned assertions of
   `tests/test_charts_sin.py` hold verbatim.
8. In `buildLayout`, put the scalar branch **after** the Y-axis assignment, mutating only
   `layout.xaxis` and `layout.barmode`, and use `delete` on the two date-format entries rather than
   assigning an empty string, which Plotly would treat as a format.
9. Narrow the two `tests/test_renderer_value_mode.py` assertions with the file's own `_function_body`
   helper, and add the third-occurrence injection test in the same commit. Do not weaken anything
   else in that file: the collision is that the assertion is broader than its own intent, not that
   its intent is wrong.
10. Make the payload edit in `tests/test_payload.py` last, so the failure it is meant to fix is
    observed first. Leave the TEMPO half alone even though it will read oddly for one ticket's
    duration; ticket-031 completes it.
11. Prove the new assertions can fail: inject a third `"diferenca"` into a copy of the asset;
    stack-swap `"group"` for `"stack"` and confirm the layout assertion fails; drop the `TOTAL`
    emission and confirm criterion 1 fails; append `data-kind` after `hidden` in a copy of a built
    document and confirm criterion 5 fails. Restore each.
12. Open the built file and click `Execução`: confirm the cost chart draws grouped bars, that the
    category labels read `03/03/2024 - PRESENTE`-style rather than a reparsed date, that the tick
    labels are not timestamps, that Diferença zeroes the reference scenario, and that the console is
    clean. This is the only verification of the rendered geometry; ticket-031 turns it into numbered
    checklist steps.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/scalars.py` (create: `aggregate`, `aggregate_costs`)
- `src/dessem_dashboard/dashboard/payload.py` (modify: route `_build_scalars` through `aggregate`)
- `src/dessem_dashboard/dashboard/builder.py` (modify: the `data-kind` attribute)
- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: two `KEYS` entries, one `const`,
  `buildBarTraces`, the `renderChart` branch, the `buildLayout` scalar branch, one exposed member)
- `tests/test_renderer_value_mode.py` (modify: narrow two over-broad assertions, add one)
- `tests/test_payload.py` (modify: exactly one assertion and its comment)
- `tests/test_charts_costs.py` (create)

### Patterns to Follow

- ticket-020's `_build_scalars` shape and `_round_value` as the single rounding point.
- `_warn_omitted_charts`'s Portuguese `logger.warning` style, naming the dotted settings key, for
  requirement 4; `_logo_data_uri`'s `ConfigError` style, also naming the dotted key, for
  requirement 5.
- The frozen-`KEYS` discipline: two new entries, no payload key literal anywhere else, bracket access
  only.
- ticket-025's `buildLayout` shape: one fresh deep copy per call, one function that assigns `yaxis`,
  everything chart-specific decided there.
- `valuesForMode` reuse rather than a second difference implementation — the reason that helper takes
  two arrays instead of a chart key.
- The document-slicing assertion pattern through `tests/dashboard_document.py` (ticket-027).

### Pitfalls to Avoid

- Do not leave the X axis as `type: "date"`. Plotly's JavaScript date parsing is month-first, so
  `04/03/2024` becomes 3 April, the two fixture decks render a month apart, and no Python test can
  see it.
- Do not reformat the deck key with `dashboard.date_format`. That pattern carries `%H:%M` and would
  label a deck `03/03/2024 00:00`; `TimeAxis.key` is already `%d/%m/%Y` and is the only source.
- Do not rely on Plotly's default `barmode`. A stacked default would draw `TOTAL` on top of the
  parcels that constitute it and misstate the cost by a factor of two.
- Do not compute the total as `PRESENTE + FUTURO`, and do not hard-code the pair anywhere. E4-1 makes
  the parcel set configuration; Appendix A.7's "presente plus futuro" describes the default outcome,
  not the mechanism.
- Do not sum unrounded parcels into a rounded total. The total bar must equal the sum of the parcel
  bars an operator reads off the chart, which means summing the rounded values and rounding once more.
- Do not substitute `0` for a missing cell, and do not emit a total over a subset of the parcels.
  A zero bar and a short total are both wrong numbers; a missing bar is the honest gap decision 17
  and the payload's missing-key rule already establish.
- Do not treat the missing-parcel case and the missing-cell case with one rule. They are governed by
  E4-1 and by decision 17 respectively, which is exactly the "cases governed by different binding
  decisions bundled under one treatment" defect shape recorded in Epic 2 learnings section 6.
- Do not append `data-kind` after the ` hidden` attribute. Two existing tests assert a hidden
  section's opening tag ends with ` hidden>`.
- Do not add a second `Object.freeze({`, a second `Plotly.react(`, a `rangemode`, an `annotations`
  entry, a `hovertemplate` or a second Y axis. Each is pinned, and each pin has a reason recorded in
  ticket-024 or ticket-025.
- Do not use `axisKey()` in `buildBarTraces`. The chained key `encadeado` is not a scalar deck key,
  and decision 5 makes the bars independent of the view mode and of the deck selector.
- Do not read a payload-derived field with dot access. `chart.kind` evades the `KEYS` contract, which
  is the gap being closed at the epic-03 boundary.
- Do not weaken any other assertion of `tests/test_renderer_value_mode.py` while narrowing the two.
  The ticket-024 intent — one place decides the value mode per trace builder — is correct and must
  survive the narrowing.
- Do not add a log Y axis. It cannot render the signed Diferença values, and the scale caveat is
  accepted and documented instead.

### Out of Scope

- The `TEMPO` grouping, the `time.unit_divisor` division and the manual checklist section for both
  bar charts (ticket-031).
- The document size measurement, the threshold warning and the manifest volumes (ticket-032).
- Any new `ChartSpec`, any new settings key, any per-chart `output.decimals`, a parcel selector, a
  stacked or percentage view, a log axis, `desvio_padrao` error bars, and any currency conversion or
  unit scaling of `R$`.
- Any change to `theme.py`, `consolidate.py`, `store.py`, `registries.py`, `dashboard.css`,
  `dashboard.html`, `pipeline.py` or `cli.py`.
- The plant charts and their filters (tickets 027 to 029), whose section markup this ticket changes
  only by adding `data-kind`.

## Testing Requirements

### Unit Tests

`tests/test_charts_costs.py`:

- the five acceptance criteria;
- `aggregate("GHID_SIN", raw, settings=...)` returns `raw` unchanged and by identity where possible,
  proving the dispatch touches only the chart it owns;
- a raw mapping where `PRESENTE` lacks one `(scenario, deck)` cell that `FUTURO` has: that cell is
  absent from `TOTAL`, the other cells are present, and no warning is logged;
- a raw mapping where one cell is `None` rather than absent: same outcome, proving `None` and
  "missing key" are treated alike at the total;
- the parcel order follows `costs.total_parcels` and not `raw`'s insertion order, asserted with a
  reversed configured order;
- every emitted value is either `None` or equal to itself rounded to two decimals, and `-0.0` never
  appears;
- the `TOTAL` of the fixture payload for `caso_a`/`03/03/2024` recomputed from
  `CUSTOS.parquet` with pandas, proving the value reached the payload from the file rather than from
  a coincidence of the aggregation;
- the four non-vacuity mutations of Suggested Approach step 11, each confirmed to fail before
  restoration.

`tests/test_payload.py`: one assertion changed, as requirement 11 states. `tests/test_renderer_value_mode.py`:
two assertions narrowed and one injection test added, as requirement 10 states.

### Integration Tests

None automated, by epic decision E3-1: no test parses or runs `dashboard.js`, so the bar geometry,
the category axis and the Diferença view on bars are verified by hand here and turned into numbered
checklist steps by ticket-031. The run against the real four-parcela file is ticket-034, and the
legacy parity comparison is ticket-038.

## Definition of Done

- [ ] The seven files exist — five modified, two created — and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] The cost total is computed from `costs.total_parcels`, and no parcel name is written into the
      source at all: `grep -rn "PRESENTE" src/` and `grep -rn "FUTURO" src/` each return **no
      match**, as both do today, so a hard-coded pair fails this check instead of slipping through.
- [ ] A parcel named in settings and absent from the data produces one Portuguese warning and no
      exception; `TOTAL` named in settings raises `ConfigError`.
- [ ] The bar charts render on a `category` X axis with an explicit `barmode`, and the asset holds one
      `Plotly.react(`, one `Object.freeze({`, one function assigning `yaxis`, and is pure ASCII.
- [ ] `tests/test_charts_sin.py`, `tests/test_charts_submarket.py`, `tests/test_charts_hydro.py`,
      `tests/test_charts_thermal.py`, `tests/test_charts_filters.py`, `tests/test_builder.py`,
      `tests/test_renderer_contract.py` and `tests/test_renderer_controls.py` all pass unchanged.
      `tests/test_payload.py` and `tests/test_renderer_value_mode.py` pass **as amended** by
      requirements 10 and 11, which this ticket's own requirements force to change.
- [ ] The rendered `Execução` level was opened by hand with a clean console, and its category labels
      are deck-and-series strings rather than reparsed dates.

## Effort Estimate

**Points**: 4 · **Confidence**: Medium · **Agent time**: about 55 minutes. Re-estimated up from the
outline's 2 points, and the reason is measurement rather than caution: the outline assumed a
JavaScript-and-payload ticket, while the epic-03 boundary review found that the renderer cannot read
a chart's kind at all, that the shared layout would reparse the deck labels as month-first dates, and
that the difference view on bars collides with two over-broad ticket-024 assertions. The ticket
therefore spans seven files across four layers — a new Python module, the payload route, the DOM
contract, the asset, and two amended test modules. Confidence is Medium: every Python rule is
decidable and unit-tested, but the bar geometry, the category axis and the Diferença view on bars are
verified only by hand under epic decision E3-1.
