# ticket-018 Implement series consolidation

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

This ticket assembles everything the data layer built: it walks the discovered scenarios and decks,
reads each enabled chart source file once per deck, pivots the long rows into per-entity arrays
aligned on that deck timeline, and pushes them into `DashboardData` for both view modes. Three
decisions of the master plan shape it. Decision 16 says the entity list of a chart comes from its own
file, because `GHID_UHE` covers 165 plants while `VARMF_UHE` covers 118. Decision 17 says the pivot
fills missing (entity, stage) combinations with `null`, because coverage is not guaranteed
rectangular, as `VCALHA_UHE` proves with 7 616 rows over 92 plants. Decision 18 says a missing file
or a missing deck is a Portuguese warning and a gap, never a crash, so a partially comparable
dashboard is still produced.

### Relation to Epic

Final ticket of the epic and milestone M2. Everything before it is a component; this is the function
that ticket-033 will call from the pipeline and that ticket-020 will serialise.

### Current State

Available and tested: `discovery.discover_scenarios`, `readers.read_series`, `readers.read_costs`,
`readers.read_times`, `registries.load_registries` with `visible_submarket_codes`,
`timeline.load_deck_timeline`, `chaining_window`, `order_timelines`, `validate_chaining` and
`align_deck_dates`, `charts.enabled_specs`, and `models.store.DashboardData` with `EntityRef`,
`TimeAxis`, `add_series`, `add_scalar`, `set_entities` and `add_warning`. Nothing joins them yet.

## Specification

### Requirements

1. Create `src/dessem_dashboard/data/consolidate.py` exposing
   `build_dashboard_data(scenarios: Sequence[ScenarioRef], *, settings: Settings, reference: str)
   -> DashboardData`.
2. Phase 1, timelines: load every deck timeline, order them per scenario, compute the deck-date
   union and the alignment warnings with `align_deck_dates`, and the chaining warnings with
   `validate_chaining` per scenario. Push every warning into the store.
3. Phase 2, axes: for each deck date, set a `TimeAxis` from the first scenario that has that deck,
   and set the chained axis by concatenating each deck chaining window in deck-date order. The
   chained axis key is `None`.
4. Phase 3, registries: load the registries of the first available deck of the first scenario and
   pass them to the `DashboardData` constructor. Log a warning when a later deck registry disagrees
   on a plant name, but keep the first.
5. Phase 4, series: for every scenario, every deck and every enabled `ChartSpec` with
   `kind == SERIES`, read the source file and pivot it. Store one array per entity for the deck axis,
   and one array per entity for the chained axis assembled from the chaining windows across decks.
6. Entity identity: `entity_id` is `""` for `SIN`, `str(codigo_submercado)` for `SBM`,
   `f"{de}-{para}"` for `SBP`, and `str(codigo_usina)` for `UHE` and `UTE`. Labels come from
   `Registries`: `submarket_label`, `hydro_name`, `thermal_name`, and
   `f"{submarket_label(de)} para {submarket_label(para)}"` for a pair. `sort_key` is the numeric code
   tuple for plants and pairs, and the plant name for the plant charts so the dashboard list is
   alphabetical.
7. Submarket filtering: for `SBM`-level specs, keep only
   `visible_submarket_codes(registries, include_fictitious=settings.submarkets.include_fictitious)`.
   For `SBP`, keep every pair present in the file.
8. Phase 5, scalars: read `CUSTOS.parquet` and `TEMPO.parquet` per deck and store the raw parcels and
   the raw stage times through `add_scalar`, one entry per (`parcela` or `etapa`, scenario, deck).
   Do **not** compute the total or the group sums here; tickets 030 and 031 own those.
9. Degradation: a missing source file, a deck missing from a scenario, or an entity absent from a
   file produces exactly one Portuguese warning naming the chart, the scenario and the deck, and the
   corresponding series is simply not stored.
10. Log at INFO the start and end of each phase with `log_step`, including the number of files read,
    the number of series stored and the elapsed time, and log the final `value_count()`.

### Inputs

The discovered scenarios, the validated `Settings` and the reference scenario label.

### Outputs and Behavior

A populated `DashboardData`. Each source file is read at most once per deck. The function writes
nothing to disk.

### Error Handling

`SchemaError`, `DataFileError` and `StoreError` from the components propagate for genuine contract
violations, with one exception: a `DataFileError` raised because a chart **source** file is absent is
caught, converted to a warning, and the chart is skipped for that deck. A missing registry or a
missing `EST.parquet` is not caught, because the deck then has no axis and no labels. Catch
`DataFileError` only, never a bare `except`.

## Dependencies

- **Blocked By**: `ticket-011-declare-enabled-chart-specs.md`,
  `ticket-013-implement-scenario-and-deck-discovery.md`,
  `ticket-015-implement-registry-loading-and-labels.md`,
  `ticket-016-implement-deck-timeline-and-chaining.md`,
  `ticket-017-define-dashboard-data-store.md`
- **Blocks**: `ticket-020-export-compact-json-payload.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture discovered into two `ScenarioRef` and a `Settings` with
      `chaining.stages_per_deck = 4`, when `build_dashboard_data(scenarios, settings=settings,
      reference="caso_a")` is called, then `data.scenarios` equals `("caso_a", "caso_b")`,
      `len(data.deck_dates)` equals `2`, and
      `len(data.series("GHID_SIN", "", "caso_a", data.deck_dates[0]))` equals the stage count of
      that deck.
- [ ] Given the same call, when `data.chained_axis()` is read, then its `length` equals `8`, which
      is `stages_per_deck` times the number of decks, and its `starts` tuple is strictly increasing.
- [ ] Given a `scenario_tree` where the second deck of `caso_b` was generated with
      `omit=("GTER_UTE.parquet",)`, when `build_dashboard_data` is called, then it returns normally,
      `data.warnings()` contains exactly one message naming `GTER_UTE` and `caso_b`, and
      `data.has_series("GTER_UTE", "1", "caso_b", data.deck_dates[1])` is `False`.
- [ ] Given the fixture default where `VARMF_UHE` covers only `reservoir_codes` while `GHID_UHE`
      covers all `hydro_codes`, when `build_dashboard_data` is called, then
      `{e.entity_id for e in data.entities("VARMF_UHE")}` equals `{"1", "2"}` and
      `{e.entity_id for e in data.entities("GHID_UHE")}` equals `{"1", "2", "3"}`.
- [ ] Given a `Settings` with `submarkets.include_fictitious = False` and a fixture whose submarket
      files include code 11, when `build_dashboard_data` is called, then no `CMO_SBM` series exists
      for `entity_id == "11"`, and
      `.venv/bin/pytest tests/test_consolidate.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write the function as five private phase helpers called in sequence from
   `build_dashboard_data`, each taking and returning explicit values so each phase is unit testable:
   `_load_timelines`, `_build_axes`, `_load_registries`, `_load_series`, `_load_scalars`.
2. Pivot with `frame.pivot(index="estagio", columns=entity_keys, values="valor")`, then
   `reindex(index=range(1, axis.length + 1))` so missing stages become `NaN`, and finally convert
   each column to a value tuple replacing `NaN` with `None` through
   `[None if pandas.isna(v) else float(v) for v in column]`. This is the only place a Python-level
   loop over values is acceptable, because the `None` conversion has no vectorised equivalent that
   produces JSON-safe output; keep the loop inside a single helper.
3. For the chained arrays, slice each deck frame to its chaining window stage indices before
   pivoting, then concatenate the per-deck lists in deck-date order, inserting a run of `None` of
   the right length for a deck the scenario lacks, so every chained array has the chained axis
   length.
4. Build the entity list per chart from the union of entity keys seen across decks for that
   scenario set, so a plant present in only one deck still appears with `None` elsewhere.
5. Read each file once per (scenario, deck, chart) and derive both the per-deck and the chained
   arrays from the same frame, which halves the I/O.
6. Write `tests/test_consolidate.py` using the `scenario_tree` fixture and regenerated variants for
   the degradation cases.

### Key Files to Create/Modify

- `src/dessem_dashboard/data/consolidate.py` (create)
- `tests/test_consolidate.py` (create)

### Patterns to Follow

- Vectorised pandas for the pivot and the reindex; the only value loop is the `None` conversion.
- `log_step` from `logging_setup` for every phase boundary, with `elapsed_s` and volume fields, so an
  official run is auditable, per `CLAUDE.md`.
- Warnings accumulate in the store rather than being logged and forgotten, so ticket-020 can embed
  them and the manifest can record them.

### Pitfalls to Avoid

- Do not reuse the deck axis length for the chained arrays or vice versa: `add_series` will raise a
  `StoreError` naming both lengths, which is the intended safety net, but the bug is easier to avoid
  than to debug.
- Do not assume the pivot yields the entities in a useful order; sort them through `EntityRef`
  `sort_key` in `set_entities`.
- Do not filter fictitious submarkets out of `INT_SBP`: only the `SBM`-level specs are filtered,
  because interchange pairs legitimately involve codes 11 and 99.
- Do not compute the cost total or the `TEMPO` groups here, and do not divide `tempo` by 60: the raw
  values go into the store and tickets 030 and 031 aggregate them, so the grouping stays
  configurable.
- Do not catch `SchemaError`: a malformed file is a contract violation that must stop the run, unlike
  an absent file which is a legitimate gap.
- Reading the registries of every deck and comparing them is O(decks); keep the comparison to plant
  names only and log at WARNING, since a renamed plant between decks is worth knowing but must not
  fail the run.
- With 30 decks times 3 scenarios times 23 charts the loop performs about 2 000 reads. Log the
  elapsed time per scenario so a slow run is diagnosable, and do not add caching in this ticket.

### Out of Scope

- JSON serialisation, rounding and key naming (ticket-020).
- Cost totals and `TEMPO` groupings (tickets 030 and 031).
- Output size measurement and warnings (ticket-032).
- Any Plotly, HTML or theme concern.
- Wiring this function into `pipeline.run` (ticket-033).

## Testing Requirements

### Unit Tests

`tests/test_consolidate.py`:

- happy path on the two-scenario, two-deck fixture: scenarios, deck dates, per-deck series lengths
  for one chart per level;
- chained axis length, monotonicity, and that a chained array length equals the chained axis length;
- missing source file yields one warning and no series, for a series chart and for `CUSTOS`;
- a deck missing from one scenario yields a warning and a chained array padded with `None`;
- per-chart entity lists differ between `GHID_UHE` and `VARMF_UHE`;
- entity labels come from the registries, spot-checking a hydro plant, a thermal plant, a submarket
  and an interchange pair;
- entity order follows `sort_key`, alphabetical by plant name for the plant charts;
- fictitious submarket 11 excluded from `CMO_SBM` when `include_fictitious` is false and included
  when true;
- `INT_SBP` keeps pairs involving code 11 in both settings;
- scalars: `CUSTOS` stores four parcels per scenario and deck, `TEMPO` stores the raw stage rows with
  no division by 60;
- a plant present in one deck and absent from the other appears in the entity list with `None`
  values for the missing deck;
- a malformed file raises `SchemaError` and is not swallowed;
- `value_count()` equals the manually computed expected total for the fixture;
- `caplog` assertions on the five phase INFO lines.

### Integration Tests

None inside this ticket. The run against a real tree is ticket-034, which reuses this function
unchanged.

## Definition of Done

- [ ] Both files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] No missing value is stored as `float('nan')`, verified by a test asserting `None`.
- [ ] Every degradation path produces a Portuguese warning naming the chart, the scenario and the
      deck.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes
