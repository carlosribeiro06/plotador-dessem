# ticket-031 Render the computational time bar charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-030 and strictly before ticket-032.** It adds one function
> to the `dashboard/scalars.py` module ticket-030 creates, relies on the bar-render path and the
> `category` X axis ticket-030 adds to the asset, and edits the same
> `tests/test_payload.py` test function ticket-030 edits. It writes **no JavaScript**: if this ticket
> finds itself editing `dashboard.js`, ticket-030's bar path was built chart-specific instead of
> kind-driven, and that is a defect to report there rather than to work around here.

## Context

### Background

`TEMPO` is spec item 23 of master plan Appendix A.6, `Tempo computacional`, the chart the legacy
scripts plotted and the reason the plan added a synthesis file the spec's minimum list does not name.
`TEMPO.parquet` holds nine rows per deck over five distinct `etapa` values —
`Leitura de Dados e Impressão`, `MILP`, `PL` three times, `PL.Int.Fix` twice and `PL.CalcCMO` twice —
with `tempo` in **seconds**. The chart is a grouped bar chart by deck date, one bar per scenario,
independent of the view mode, showing the groups `time.stage_groups` declares plus a total, in
**minutes**.

Two settings keys govern it and neither may be bypassed: `time.stage_groups`, which defaults to
`{"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"], "Leitura": ["Leitura de Dados e
Impressão"]}`, and `time.unit_divisor`, which defaults to `60.0`. The `PL` group is the interesting
one: it maps **three distinct etapas** into one displayed bar, which is what the legacy did and what
makes `stage_groups` a mapping rather than a list.

There is a boundary defect from Epic 2 that this ticket must not undo and must not duplicate. The
store keys a scalar by `(series_name, scenario, deck_date)`, so `TEMPO.parquet`'s nine rows over five
etapas originally overwrote each other and destroyed **67.8 percent of the PL time** — `PL` alone
executes three times. The fix sums the rows that share an `etapa` inside
`consolidate._load_scalars`, before the store ever sees them, and its docstring states the division
of labour exactly: that sum collapses *repeated executions of the very same stage*, while
`stage_groups` later groups *distinct* etapas for display. Both must hold at once, and they compose
only in that order. **This ticket receives a mapping that already holds one value per distinct
etapa; it groups those, and it must not attempt to recover repeated executions again.**

`TEMPO`'s unit is already `min`, in `FALLBACK_UNITS` and in the fixture's
`METADADOS_OPERACAO.parquet`, and ticket-025's `buildLayout` writes that unit onto the Y axis from
data. The axis therefore already claims minutes while the payload still carries seconds: the division
by `time.unit_divisor` is not an embellishment here, it is what makes the axis label true.
`tests/test_payload.py` currently asserts that no division has happened — an assertion that pinned
ticket-020's scope boundary and that this ticket is chartered to cross.

The three original key decisions and the three open questions resolve as follows.

- **The grouping and the division happen in Python, at payload build time**, in the
  `dashboard/scalars.py` module ticket-030 created, for the same three reasons recorded there: the
  uncovered-etapa warning of requirement 5 must be Portuguese and operator-facing, which the browser
  cannot do; E3-1 keeps the JavaScript free of data shaping; and shipping `stage_groups` to the
  browser would need a tenth chart key or a new top-level payload key, both of which break the
  nine-key contract `tests/test_payload.py` asserts as a set. Configurable means
  `settings.json`-driven, not interactively re-derivable.
- **The total is the sum of the emitted groups, never the sum of every `etapa` row.** The two differ
  only when an etapa is covered by no group, and in that case a row-wise total would exceed the sum
  of the bars beside it — a figure whose own composition does not add up, which an operator reading
  the chart cannot reconcile. The risk the outline worried about, a new DESSEM stage silently
  dropped, is answered directly by requirement 5's warning rather than by inflating the total.
- **An `etapa` present in the file and named by no group is a Portuguese warning**, once per chart,
  naming the etapa and `time.stage_groups`. On the default settings and the real file this never
  fires, because the three groups cover all five etapas; that is exactly why the test for it must
  regenerate the settings rather than the data.
- **Four category groups in one chart, not four charts, and not a stacked bar.** The catalogue has
  exactly one `TEMPO` spec and `enabled_specs()` returns 23, both pinned, and one spec renders one
  `<section class="chart">` with one plot `<div>`. Stacking would put the total on top of the groups
  that constitute it and double the height; ticket-030 sets `barmode` to `group` explicitly for that
  reason. The legacy's four separate charts become four category groups in one figure, with the
  total beside its own composition.
- **Minutes are rounded to `output.decimals`**, i.e. two decimals, not one. A per-chart decimals
  setting is out of scope (it would need a payload contract change, since the browser reads a single
  `formats.decimals` to round the differences it computes), and two decimals on a value between about
  1 and 300 minutes is finer than the outline's suggestion at no cost.
- **`execucao` is not a dimension.** `schemas.SCALAR_COLUMNS["TEMPO"]` declares it,
  `consolidate._SCALAR_VALUE_COLUMNS` deliberately reads only `("etapa", "tempo")`, and the groupby
  over `etapa` aggregates across executions — which is precisely the epic-02 fix. It is always zero
  in the sample; if a future file made it meaningful, exposing it would be a data-layer change.

### Relation to Epic

The second and lighter of the two scalar tickets: it adds one function and one dispatch branch to the
module ticket-030 built, and no renderer change at all, which is the test that ticket-030's bar path
really is kind-driven rather than `CUSTOS`-specific. It also writes the single manual-checklist
section covering **both** bar charts, so that section is written once rather than twice, and it is
the second of the two tickets ticket-032 waits for.

### Current State

`consolidate._load_scalars` stores, for each `(scenario, deck)`, one value per distinct `etapa`,
summing the rows that share one with `min_count=1` so an all-missing group stays `None` instead of
becoming `0.0`. It divides nothing and groups nothing, and its docstring names this ticket as the
owner of both.

`payload._build_scalars` returns `{series_name: {scenario: {deck_key: rounded_value}}}` and, after
ticket-030, routes that result through `scalars.aggregate(chart_key, raw, settings=settings)`, whose
dispatch sends `CUSTOS` to `aggregate_costs` and **every other key straight through unchanged** —
which is why `TEMPO` still carries five raw etapa names in seconds today.

`dashboard.js`, after ticket-030, reads `chart[KEYS.KIND]`, dispatches in `renderChart` to
`buildBarTraces` for `SCALAR_BY_DECK`, builds one `{type: "bar"}` trace per scenario over the
`deck_dates` × series-name grid in deck-major order, computes the Diferença view through
`valuesForMode`, and gives the scalar charts a `category` X axis with an explicit `barmode` in
`buildLayout`. None of that is chart-specific, so `TEMPO` renders as soon as its series names change.

`tests/test_payload.py` pins, in the test ticket-030 renamed or left named
`..._custos_and_tempo_scalars_shape_and_no_division_by_unit_divisor`: `len(custos) == 3` after
ticket-030, `len(tempo) == 5`, that every series of both charts has both scenarios and both deck
keys, that `tempo["PL"]["caso_a"]["03/03/2024"]` equals the **raw second** sum of the three `PL` rows
recomputed from the parquet with pandas, and that this figure exceeds 60. A second test asserts
`len(tempo["scalars"]) == 5` alongside the nine-key set. Three of those assertions are this ticket's
to amend, and they are the only assertions in the repository that this ticket's requirements force to
change.

`docs/checklist-manual-dashboard.md` holds, after ticket-028, seven original sections plus the plant
filter section, with numbered steps running past 19. `tests/test_renderer_contract.py` asserts the
file has at least one numbered step, mentions `console` and `file://`, and quotes the exact footer
text.

Measured on the `scenario_tree` fixture: `TEMPO.parquet` carries the nine rows above with values from
`uniform(10, 2000)` seconds and a distinct seed per (scenario, deck) — 42, 43, 44, 45 — so every cell
differs and a value stored under the wrong scenario or deck is detectable. Consolidated, that gives
five etapa values per (scenario, deck); grouped by the default `stage_groups`, three groups covering
`1 + 7 + 1 = 9` rows; converted, a `PL` bar of roughly 50 to 230 minutes and a total that is
**arithmetically identical** to the sum of all nine rows divided by 60, because the three default
groups happen to cover every etapa the file holds. That identity is why requirement 4's
"sum of the emitted groups" cannot be distinguished from "sum of every row" on the default settings,
and why the test that proves it must drop a group from `stage_groups`.

## Specification

### Requirements

1. Add `aggregate_times(raw, *, stage_groups, unit_divisor, decimals)` to
   `src/dessem_dashboard/dashboard/scalars.py`, and route `TEMPO` to it from that module's
   `aggregate` dispatch. Change nothing else in the module: `aggregate_costs`, its warning, its
   `ConfigError` and the pass-through default all stay as ticket-030 wrote them.
2. The value of group `G` at `(scenario, deck_key)` is the sum of `raw[etapa][scenario][deck_key]`
   over the etapas `stage_groups[G]` names **that exist in `raw`**, divided by `unit_divisor`, then
   rounded to `decimals` — divided once, rounded once, in that order. The input already holds one
   value per distinct etapa, summed across its repeated executions by
   `consolidate._load_scalars`; do not attempt to recover those executions again and do not read
   `TEMPO.parquet` here.
3. Groups are emitted in `stage_groups` insertion order — `MILP`, `PL`, `Leitura` on the shipped
   settings, which `config._require_stage_groups` preserves by building a plain `dict` — and a group
   whose members are **all** absent from `raw` is omitted entirely, with one Portuguese
   `logger.warning` naming the group and the dotted key `time.stage_groups`. A group cell is omitted
   for a `(scenario, deck_key)` where every present member lacks a value, rather than being written
   as `0`.
4. A `TOTAL` series follows the groups. Its value at `(scenario, deck_key)` is the sum of the
   **emitted, already rounded and already converted** group values there, rounded once more, so the
   total bar equals the sum of the group bars beside it exactly as an operator reads them off the
   chart. It is emitted only when every emitted group has a non-`None` value for that
   `(scenario, deck_key)`; otherwise that key is absent from `TOTAL`. It is never the sum of every
   `etapa` row.
5. An `etapa` present in `raw` but named by no group in `stage_groups` is logged **once** as a
   Portuguese `logger.warning` naming the etapa and `time.stage_groups`, and contributes to no bar
   and to no total. No exception is raised: a new DESSEM stage must be reported, not fatal, which is
   master plan decision 18's degradation rule applied to a configuration gap.
6. `TOTAL` appearing as a group name in `stage_groups` raises `ConfigError` with a Portuguese message
   naming `time.stage_groups`, mirroring ticket-030 requirement 5 exactly: the computed series would
   otherwise overwrite a configured one. Add no eighth class to `errors.py`.
7. In `tests/test_payload.py`, amend exactly three assertions and one test name: `len(tempo) == 5`
   becomes `== 4`; `len(tempo["scalars"]) == 5` in the nine-key test becomes `== 4`; the raw-second
   `tempo["PL"]` assertion becomes the converted equivalent, recomputed from `TEMPO.parquet` with
   pandas as `round(sum of the PL, PL.Int.Fix and PL.CalcCMO rows / 60.0, 2)`, with a companion
   assertion that the payload value is **not** equal to the raw second figure so the division is
   proven rather than assumed; and the test's name loses its `and_no_division_by_unit_divisor`
   clause, which its own requirements now make false. Leave the `custos` assertions ticket-030 set,
   the deck-key shape loop and every other test in the file untouched.
8. Create `tests/test_charts_times.py`, covering `aggregate_times` directly, the payload it produces,
   and the `TEMPO` section slice, with the non-vacuity cases listed under Testing Requirements.
9. Append one section to `docs/checklist-manual-dashboard.md` covering **both** bar charts, with
   numbered steps continuing the file's list: navigate to `Execução`; confirm the cost chart draws
   grouped bars whose category labels combine the deck date and the parcel name and are **not**
   timestamps or reparsed dates; confirm the total bar equals the sum of the parcel bars on a unified
   hover; confirm the same for the time chart's `MILP`, `PL`, `Leitura` and `TOTAL` bars, in minutes;
   switch to Diferença and confirm the reference scenario's bars fall to zero while the Y axis title
   gains ` (diferença)`; and switch the view mode and the deck selector and confirm the bars do not
   change, per decision 5. Record explicitly, as a known and accepted caveat, that on real data
   `FUTURO` is about 2.3e8 R$ while `PRESENTE` is about 5.9e4 R$, so the present-cost bar is
   invisible at the default zoom and is read through the unified hover or a box zoom on the Y axis;
   state that a log axis was rejected because it cannot render the signed Diferença view.
10. Change no JavaScript, no CSS, no HTML template, no `payload.py`, no `builder.py`, no `theme.py`
    and no epic-02 module. In particular do not divide by 60 in `consolidate.py`, which ticket-018
    deliberately leaves in seconds, and do not divide in the asset, which E3-1 keeps free of data
    shaping.
11. Add no `ChartSpec`, no settings key, no stacked or percentage geometry, no per-chart decimals, no
    `execucao` dimension and no second Y axis.

### Inputs

At build time, `data.scalars("TEMPO")` through `_build_scalars`, and `settings.time.stage_groups`,
`settings.time.unit_divisor` and `settings.output.decimals`. At run time, nothing new: ticket-030's
`buildBarTraces` reads `chart[KEYS.SCALARS]` whatever the series names are. At test time, the
fixture tree, three `stage_groups` variants (the shipped default, one with `Leitura` dropped, one
naming a non-existent etapa), one with `TOTAL` as a group name, a raw mapping built by hand, and the
document built from the fixture.

### Outputs and Behavior

The `Execução` level shows the time chart as grouped bars: one category per (deck, group) in
deck-major order with `MILP`, `PL`, `Leitura` and `TOTAL` per deck, one bar per scenario in its
scenario colour, `min` on the Y axis, and exact values on a unified hover. `PL` carries the sum of
its three etapas, each already summed over its repeated executions upstream. Switching to Diferença
turns every bar into `scenario − reference`. The bars do not change with the view mode or the deck
selector. Editing `time.stage_groups` changes the bars and the total together, with no code change.

### Error Handling

One new raise and two new warnings, deliberately distinct. `ConfigError` for `TOTAL` used as a group
name (requirement 6): the configuration contradicts itself. A Portuguese `logger.warning` for a group
whose every member etapa is absent (requirement 3) and another for an etapa covered by no group
(requirement 5): both are reportable configuration-versus-data gaps that leave the run comparable, so
it continues. A missing `TEMPO.parquet` for one `(scenario, deck)` is already warned by `consolidate`
into the Avisos section and leaves the corresponding bars absent rather than zero. No `try`/`catch`
is added anywhere, and `build_payload` still never mutates `data`.

## Dependencies

- **Blocked By**: `ticket-030-render-cost-bar-charts.md`
- **Blocks**: `ticket-032-enforce-output-size-strategy.md`

## Acceptance Criteria

- [ ] Given a raw mapping holding the fixture's five consolidated etapa values for two scenarios and
      two deck keys, when `aggregate_times` runs with the shipped `stage_groups`,
      `unit_divisor=60.0` and `decimals=2`, then the result keys are exactly
      `["MILP", "PL", "Leitura", "TOTAL"]` in that order; every `PL` cell equals the sum of its
      three member etapas divided by 60 and rounded to two decimals; every `TOTAL` cell equals its
      three group cells summed within `0.01`; and no emitted value equals the raw second figure of
      its own group, so the division is proven and not assumed.
- [ ] Given the same raw mapping, when `aggregate_times` runs with `stage_groups` reduced to
      `{"MILP": ["MILP"], "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"]}`, then the result keys are
      exactly `["MILP", "PL", "TOTAL"]`, every `TOTAL` cell equals `MILP + PL` within `0.01` and is
      strictly less than the sum of all five etapas divided by 60, and exactly one WARNING record of
      the `dessem_dashboard.dashboard.scalars` logger names both
      `Leitura de Dados e Impressão` and `time.stage_groups`.
- [ ] Given the same raw mapping, when `aggregate_times` runs with
      `{"MILP": ["MILP"], "FANTASMA": ["INEXISTENTE"]}`, then no exception is raised, the result keys
      are exactly `["MILP", "TOTAL"]`, every `TOTAL` cell equals its `MILP` cell, and one WARNING
      record names `FANTASMA` and `time.stage_groups`; and when a group is named `TOTAL`, a
      `ConfigError` naming `time.stage_groups` is raised.
- [ ] Given the `scenario_tree` fixture and the repository `settings.json`, when the payload is
      built, then `charts["TEMPO"]["scalars"]` has exactly the four keys `MILP`, `PL`, `Leitura` and
      `TOTAL`, each with both scenarios and both deck keys `03/03/2024` and `04/03/2024`;
      `charts["TEMPO"]["unit"]` is `min`; `charts["TEMPO"]["entities"]` is `[]`; and
      `charts["CUSTOS"]["scalars"]` still has the three keys ticket-030 produced, so this ticket is
      proven not to have disturbed the other scalar chart.
- [ ] Given the document built from the fixture, when the `data-chart="TEMPO"` section slice is
      inspected, then it carries `data-group="EXECUCAO"`, `data-kind="SCALAR_BY_DECK"`,
      `data-selector="NONE"` and ` hidden`, holds exactly one `<h2>` reading `Tempo Computacional`,
      and contains neither `<select` nor `plant-filter`; and
      `.venv/bin/pytest tests/test_charts_times.py tests/test_charts_costs.py tests/test_payload.py
      tests/test_renderer_contract.py tests/test_builder.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `aggregate_times` against hand-built mappings first: like `aggregate_costs` it is pure data
   in, data out, and every rule of requirements 2 to 6 is decidable there.
2. Factor the shared shape rather than duplicating it. `aggregate_costs` and `aggregate_times` both
   emit "named series in configured order, then a `TOTAL` over the emitted ones, present only where
   every component is present": if ticket-030 left a private helper for the total, reuse it; if not,
   extracting one now is the right move, as long as `aggregate_costs`' behaviour and its tests stay
   identical.
3. Iterate the `(scenario, deck_key)` pairs the members actually cover rather than assuming a
   rectangle: a scenario missing a deck legitimately has fewer cells.
4. Divide before rounding, once per group, and never re-divide the total: summing already converted
   group values keeps the bars and their total consistent to the last displayed digit.
5. Detect the uncovered etapas as a set difference between `raw`'s keys and the union of the
   configured members, and log them sorted so the message is deterministic.
6. Amend `tests/test_payload.py` only after watching the three assertions fail, so the change is
   observed rather than assumed. Recompute the expected `PL` minutes with pandas from the parquet, as
   that test already recomputes the raw seconds — do not hard-code a number the seed happens to
   produce.
7. Write the checklist section last, after walking it in a browser, and keep the file's existing
   `**Expected result:**` convention. Continue the numbering from wherever ticket-028's section ended;
   do not renumber anything above it.
8. Prove the new assertions can fail: change `unit_divisor` to `1.0` in a variant and confirm
   criterion 1's division assertion fails; add `Leitura` back into the reduced `stage_groups` and
   confirm criterion 2's warning assertion fails; make `TOTAL` the sum of all five etapas and confirm
   criterion 2's strict inequality fails. Restore each. The default settings cannot distinguish the
   two total definitions, which is exactly why these mutations are the evidence.
9. Open the built file, click `Execução`, and walk the new steps with the console open. The minutes,
   the four bars per deck, the total-equals-composition property and the Diferença behaviour are all
   verified here and nowhere else, under epic decision E3-1.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/scalars.py` (modify: `aggregate_times` plus one dispatch branch)
- `tests/test_payload.py` (modify: three assertions and one test name)
- `tests/test_charts_times.py` (create)
- `docs/checklist-manual-dashboard.md` (modify: append one section for both bar charts)

### Patterns to Follow

- ticket-030's `aggregate_costs`: the same signature shape, the same configured-order rule, the same
  rounded-components total, the same Portuguese `logger.warning` naming a dotted settings key, and
  the same `ConfigError` for a self-contradicting configuration.
- `consolidate._load_scalars`' docstring as the authority on the division of labour between summing
  repeated executions and grouping distinct etapas.
- The recompute-from-the-parquet assertion style `tests/test_payload.py` already uses for `PL`.
- The document-slicing assertion pattern through `tests/dashboard_document.py`.
- The checklist's existing section structure, numbered steps and `**Expected result:**` convention.

### Pitfalls to Avoid

- Do not re-sum repeated executions of one etapa. `consolidate._load_scalars` already did it, and
  doing it again would either double-count or, worse, tempt a re-read of `TEMPO.parquet` from the
  payload layer, which reads no file.
- Do not divide in `consolidate.py` or in the asset. ticket-018 stores seconds deliberately and
  `tests/test_consolidate.py` pins it; E3-1 keeps the JavaScript free of arithmetic beyond the
  difference `valuesForMode` already owns.
- Do not divide twice or round twice on the way to a group value. Divide once, round once; the total
  then sums already converted values.
- Do not define the total over every `etapa` row. It would exceed the sum of the bars beside it
  whenever a stage is uncovered, and requirement 5's warning is the intended answer to that risk.
- Do not write the "total is the configured groups" test against the shipped settings. The three
  default groups cover all five etapas, so the two definitions coincide there and the assertion would
  pass while proving nothing — the vacuous shape recorded in Epic 2 learnings section 7.
- Do not write `0` for a missing cell. A zero-minute `MILP` bar reads as a solver that took no time,
  which is a data claim the run cannot support.
- Do not claim in the Definition of Done that `tests/test_payload.py` passes unchanged. Requirement 7
  forces three of its assertions to change, and a stale Definition-of-Done bullet contradicting its
  own requirement is a defect shape this plan has already paid for once.
- Do not touch `dashboard.js`. If `TEMPO` does not render once its series names change, ticket-030's
  bar path was built chart-specific; report that rather than patching it here.
- Do not expose `execucao`. `consolidate` reads only `("etapa", "tempo")` and aggregates across
  executions by design.
- Do not renumber the existing checklist steps. `tests/test_renderer_contract.py` asserts the file
  still has numbered steps and names specific ones; renumbering would churn the file for nothing.

### Out of Scope

- Everything ticket-030 owns: the cost aggregation, the `data-kind` attribute, the `KEYS.KIND` and
  `KEYS.SCALARS` entries, `buildBarTraces`, the `renderChart` branch, the `category` X axis and
  `barmode`, and the narrowing of the two `tests/test_renderer_value_mode.py` assertions.
- The document size measurement, the threshold warning and the manifest volumes (ticket-032).
- The plant charts and their filters (tickets 027 to 029).
- A stacked or percentage geometry, four separate time charts, a log axis, a per-chart
  `output.decimals`, the `execucao` column as a dimension, and any `TEMPO` statistic beyond the
  configured groups and their total.
- Any change to `consolidate.py`, `store.py`, `payload.py`, `builder.py`, `theme.py`, the packaged
  assets, `pipeline.py` or `cli.py`.

## Testing Requirements

### Unit Tests

`tests/test_charts_times.py`:

- the five acceptance criteria;
- a group whose members exist but whose cells are all `None` for one `(scenario, deck_key)`: that
  cell is absent from the group and from `TOTAL`, while the other deck's cells are present;
- a raw mapping with a sixth etapa absent from every group: one warning, and the `TOTAL` unchanged
  from the five-etapa case, proving requirement 4 and requirement 5 compose;
- group order follows `stage_groups` insertion order, asserted with a reversed configured order so a
  sorted implementation fails;
- every emitted value is either `None` or equal to itself rounded to two decimals, and `-0.0` never
  appears;
- the fixture payload's `MILP` value for `caso_a`/`03/03/2024` recomputed from `TEMPO.parquet` with
  pandas as `round(row / 60.0, 2)`, proving the value reached the payload from the file;
- the three non-vacuity mutations of Suggested Approach step 8, each confirmed to fail before
  restoration.

`tests/test_payload.py`: three assertions and one test name amended, as requirement 7 states — this
ticket's requirements make the current text false, so it must change rather than be preserved.

### Integration Tests

None automated, by epic decision E3-1. The rendered bar geometry, the minutes, the
total-equals-composition property and the Diferença view on bars are covered by the checklist section
requirement 9 adds; the run against the real nine-row `TEMPO.parquet` is ticket-034, and the legacy
parity comparison — MILP, the PL group, Leitura and the total, in minutes — is ticket-038.

## Definition of Done

- [ ] The four files exist — three modified, one created — and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] The `PL` group sums three distinct etapas without re-summing their repeated executions, and the
      division by `time.unit_divisor` happens exactly once, in `dashboard/scalars.py`.
- [ ] An uncovered etapa and an empty group each produce one Portuguese warning naming
      `time.stage_groups`; `TOTAL` as a group name raises `ConfigError`.
- [ ] `grep -rn "unit_divisor" src/` names exactly two modules, `config.py` and
      `dashboard/scalars.py` — it names only `config.py` today — so a division that leaked into
      `consolidate.py`, `builder.py` or an asset fails this check.
- [ ] `tests/test_charts_costs.py`, `tests/test_charts_sin.py`, `tests/test_charts_submarket.py`,
      `tests/test_charts_hydro.py`, `tests/test_charts_thermal.py`, `tests/test_charts_filters.py`,
      `tests/test_builder.py`, `tests/test_renderer_contract.py`, `tests/test_renderer_controls.py`
      and `tests/test_renderer_value_mode.py` all pass unchanged. `tests/test_payload.py` passes
      **as amended** by requirement 7.
- [ ] The new checklist section was walked by hand in a browser with the console open, and it records
      the cost-scale caveat.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 30 minutes. The outline's 2 points hold,
for a different reason than it assumed: the grouping and the division are about forty lines in the
module ticket-030 created, and there is no renderer work at all, because ticket-030's bar path is
kind-driven. The weight is in the four test variants that prove the total is the sum of the
*configured* groups — a property the shipped settings cannot distinguish — and in the checklist
section. Confidence is High rather than the outline's Low because every rule is decidable in Python
and every expected number is recomputed from the fixture parquet rather than hard-coded.
