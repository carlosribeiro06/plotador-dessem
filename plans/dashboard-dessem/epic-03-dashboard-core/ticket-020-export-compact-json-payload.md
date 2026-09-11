# ticket-020 Export the compact JSON payload

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The dashboard embeds one JSON object and the browser rebuilds every figure from it on demand, so
this object is the contract between the Python side and the hand-written renderer: master plan
decision 6 forbids pre-rendering one Plotly figure per chart, and decision 8 keeps only the
**absolute** series in the payload because the Diferença view is computed in the browser. The output
size strategy is mandatory and measured: columnar arrays keyed by chart, entity, scenario and deck;
one shared time axis per deck plus one chained axis instead of a timestamp per point; values rounded
to `output.decimals`.

The three original key decisions of this ticket and its three open questions are all resolved
below, each with its basis:

- **Key names are English**, values are Portuguese only where they are display text. Payload keys are
  identifiers, and `CLAUDE.md` puts identifiers and config keys in English in both modes. It also
  keeps every key ASCII, so no accent can be mangled by an escaping mistake.
- **Timestamps are embedded as naive `%Y-%m-%d %H:%M` strings**, one array per axis, never per point.
  Plotly parses that literal form on a `type: "date"` axis without applying any timezone, which is
  exactly what master plan decision 10 demands: the stamps are wall clock *labelled* UTC and the
  digits must survive untouched. The **display** format stays `dashboard.date_format`, applied by the
  Plotly `tickformat` that ticket-019 puts in the layout template — the payload never carries an
  operator-facing ISO date.
- **The chart catalogue, the entity lists and the per-chart scalars are folded into each chart
  entry**, keyed by chart key, because `DashboardData` already exposes them per chart and the
  renderer looks a chart up by the `data-chart` attribute of its container. There is no separate
  registry object: the Portuguese labels are already baked into `EntityRef.label` by ticket-018.
- **No shortened key scheme.** The arrays are columnar, so a key occurs once per
  (chart, entity, scenario, axis) leaf, not once per value. At the master plan volume of about 8 M
  values the leaf keys account for roughly 2 MB against roughly 56 MB of values, so abbreviating them
  would buy under 4 percent at the cost of an unreadable payload and a renderer nobody can debug.
- **A `schema_version` field is included.** It costs 20 bytes and lets a future renderer refuse a
  payload it cannot read.
- **The payload does not carry the warnings.** Epic decision E3-1 requires that everything computable
  in Python happens in Python, and nothing in the browser consumes them, so ticket-021 renders
  `data.warnings()` into the HTML directly. Carrying them in both places would create two sources for
  one list.

### Relation to Epic

First ticket of the epic alongside ticket-019, and independent of it: the theme values arrive as two
keyword arguments so the two tickets can be implemented in either order. Ticket-021 calls
`build_payload` and `payload_json` and inlines the result; tickets 022 to 026 and all of Epic 4 read
the keys defined here, and ticket-022 pins them with a renderer-contract test.

### Current State

The data layer is complete and test-pinned (288 tests, 99 percent coverage). `DashboardData` exposes
`scenarios`, `reference`, `deck_dates`, `registries`, `deck_axis(date)`, `chained_axis()`,
`series(chart_key, entity_id, scenario, deck_date)`, `has_series(...)`, `entities(chart_key)`,
`scalars(chart_key)`, `warnings()` and `value_count()`; `deck_date=None` addresses the chained axis.
`TimeAxis` carries `key`, `starts` and `durations_hours` plus the `length` property, and ticket-018
sets `key` to `deck_date.strftime("%d/%m/%Y")` for a deck and to `"encadeado"` for the chained axis.
`EntityRef` carries `entity_id`, `label` and `sort_key`, and `entities()` returns them sorted.
`charts.registry.enabled_specs(disabled=...)` returns the 23 enabled `ChartSpec` values, each with
`key`, `source_file`, `level`, `group`, `kind`, `selector`, `title`, `unit`, `enabled` and `notes`.
`Registries.unit_for(key)` and `Registries.title_for(key)` are available, the latter returning `None`
rather than `""`. **No `dashboard/` subpackage exists yet**; ticket-019 creates the package, but this
ticket may create it too if it runs first — a one-line docstring module either way.

Measured on the `scenario_tree` fixture (`caso_a` and `caso_b`, decks `deck_um` 2024-03-03 and
`deck_dois` 2024-03-04, `n_stages=50`, `half_hour_stages=48`, `long_stage_hours=6.0`, and
`chaining.stages_per_deck = 48` from the repository `settings.json`): both deck axes have length 50,
the chained axis has length 96, `value_count()` is 16 892, `warnings()` is empty, and the fixture
writes `METADADOS_OPERACAO.nome_longo_variavel` **equal to `ChartSpec.title` for every one of the 23
keys**, so `title_for` never differs from the curated title unless a test rewrites that file.

## Specification

### Requirements

1. Create `src/dessem_dashboard/dashboard/payload.py` exposing
   `build_payload(data: DashboardData, *, settings: Settings, scenario_colors: Mapping[str, str],
   plotly_layout: Mapping[str, object]) -> dict[str, object]` and
   `payload_json(payload: Mapping[str, object]) -> str`. The two theme arguments are supplied by the
   caller (ticket-021 passes `theme.scenario_colors(...)` and `theme.plotly_layout_template(...)`);
   this module must **not** import `dashboard.theme`, so it stays independent of ticket-019.
2. The returned mapping has exactly these ten top-level keys: `schema_version` (the integer `1`),
   `scenarios` (`list(data.scenarios)`), `reference` (`data.reference`), `deck_dates`,
   `chained_key`, `axes`, `charts`, `theme`, `formats` and `labels`. There is no `warnings` key, for
   the reason recorded under Background.
3. `deck_dates` is the list of `data.deck_axis(deck_date).key` values in `data.deck_dates` order, and
   `chained_key` is `data.chained_axis().key`. Read both from `TimeAxis.key` rather than formatting
   the date again, so the `%d/%m/%Y` convention has exactly one source. `axes` maps each of those
   keys to `{"starts": [...], "end": "..."}`, where `starts` holds one `%Y-%m-%d %H:%M` string per
   entry of `TimeAxis.starts` and `end` is `starts[-1] + Timedelta(hours=durations_hours[-1])` in the
   same format. `end` exists so the renderer can close the last stage with a terminal point and give
   it visible width under `line_shape: "hv"` (master plan decision 14); `durations_hours` is
   deliberately **not** exported, because `end` is the only thing the browser needs and computing it
   in Python keeps the JavaScript thin per E3-1.
3a. **Added 2026-09-11 from the epic-02 boundary review (finding M6).** Before building the payload,
   extend `src/dessem_dashboard/models/store.py` with three read-only accessors —
   `chart_keys() -> tuple[str, ...]`, `scalar_chart_keys() -> tuple[str, ...]` and
   `stored_deck_dates(chart_key, entity_id, scenario) -> tuple[datetime.date | None, ...]` — each
   returning deterministically sorted results, with `None` sorting last as the chained axis. The
   additions must be **additions only**: prove it with
   `git diff --numstat -- src/dessem_dashboard/models/store.py` showing zero deletions, exactly as
   six earlier tickets did for `errors.py`. Add their unit tests to `tests/test_store.py`.

   Requirement 4 below still iterates the catalogue, because the catalogue is what fixes the chart
   ORDER and supplies `group`, `kind`, `selector` and `title`. Use these accessors for the two things
   the catalogue cannot answer: assert that `chart_keys()` is a subset of the catalogue keys and
   **log a Portuguese warning naming any stored chart the payload is about to omit**, and enumerate
   the stored (scenario, deck) combinations of an entity instead of probing `has_series` for every
   cell of the cross product. Both matter. The review measured the probe approach at roughly 320 000
   `has_series` calls at 3 scenarios × 30 decks × 165 plants, but the real defect is the silent one:
   deriving the payload's chart list *solely* from `enabled_specs(disabled=settings.charts.disabled)`
   means that if this `disabled` list ever differs from the one consolidation used, charts present in
   the store are dropped from the HTML with nothing reporting it. The three degradation paths of
   ticket-018 deliberately leave holes in the store, so "absent" and "never stored" must stay
   distinguishable here.

4. `charts` maps each `enabled_specs(disabled=settings.charts.disabled)` key to an entry with exactly
   these nine keys, present for every chart regardless of kind: `group` (`spec.group.value`), `kind`
   (`spec.kind.value`), `selector` (`spec.selector.value`), `title`, `subtitle`, `unit`, `entities`,
   `series` and `scalars`. A `SERIES` chart carries `scalars` as an empty object; a
   `SCALAR_BY_DECK` chart carries `entities` as an empty list and `series` as an empty object. The
   uniform key set exists so the renderer and the tests never have to branch on kind to read a chart
   entry.
5. `title` is always `spec.title`, the curated catalogue text. `subtitle` is
   `data.registries.title_for(key)` when that value is neither `None` nor equal to `spec.title`, and
   `None` otherwise. This is epic decision E3-2: the registry long name is additive, and letting it
   win would replace `Volume Armazenado (hm3)` with `Volume Armazenado Absoluto Final` and collapse
   the hm3-versus-percent and afluente-versus-incremental distinctions the catalogue exists to
   preserve.
6. `unit` is `data.registries.unit_for(key)`, which prefers the `METADADOS_OPERACAO.unidade` value
   and falls back to `FALLBACK_UNITS`. The asymmetry with requirement 5 is deliberate and is not a
   contradiction: `planning-context.md` says to take units from the metadata with a static fallback,
   because a unit is a physical fact recorded in the file, whereas a title is a curated
   disambiguation that E3-2 protects from being overwritten.
7. `entities` is `[{"id": entity.entity_id, "label": entity.label} for entity in
   data.entities(key)]`, preserving the `sort_key` order the store already applied, so the renderer
   and the Epic 4 filters share one ordering. `sort_key` itself is not exported.
8. `series` nests `entity_id` then scenario then axis key:
   `series[entity_id][scenario][axis_key] = [values...]`. Emit an entry only when
   `data.has_series(key, entity_id, scenario, deck_date)` is true, addressing the chained axis with
   `deck_date=None` and the chained axis key; a scenario missing a deck therefore contributes no key
   at all rather than an array of nulls, and the renderer omits its trace. Each emitted array has the
   same length as `axes[axis_key]["starts"]`.
9. `scalars` nests series name then scenario then deck key:
   `scalars[series_name][scenario][deck_key] = value`, built from `data.scalars(key)`, whose keys are
   `(series_name, scenario, deck_date)` triples. Store the raw values: neither the cost total nor the
   `TEMPO` group sums nor the division by `time.unit_divisor` happen here, because tickets 030 and
   031 own those aggregations and the grouping must stay configurable.
10. Round every exported numeric value with `round(value, settings.output.decimals)`, map a stored
    `None` to JSON `null`, and normalise a rounded `-0.0` to `0.0`. `payload_json` serialises with
    `json.dumps(payload, allow_nan=False, ensure_ascii=False, separators=(",", ":"))` and then
    replaces every `<` with the six-character escape `\u003C`, so the text is safe inside a
    `<script type="application/json">` element and cannot terminate it. `allow_nan=False` turns a NaN
    or infinity leak into a loud `ValueError` instead of the invalid JSON token `NaN`.
11. `theme` is `{"scenario_colors": dict(scenario_colors), "layout": dict(plotly_layout)}`.
    `formats` is `{"decimals": settings.output.decimals}`, needed because the browser rounds the
    differences it computes. `labels` is
    `{"y_axis_difference_suffix": " (diferença)"}` — the one operator-visible string the renderer
    injects at run time, kept here so no Portuguese literal has to live in `dashboard.js`
    (consumed by ticket-025 requirement 4).
12. Log one INFO line from `build_payload` through `log_step` with the number of charts, the number
    of exported values and `elapsed_s`, and one from `payload_json` with the character count, so an
    official run records what was embedded. Messages are Portuguese; the module obtains its logger
    with `logging.getLogger(__name__)` and adds no handler.

### Inputs

A populated `DashboardData` from `consolidate.build_dashboard_data`, the validated `Settings`, and
the two theme values. The function reads no file and touches no disk.

### Outputs and Behavior

A plain nested `dict` of JSON-ready values from `build_payload`, and its serialisation from
`payload_json`. Neither function mutates `data`. Calling `build_payload` twice on the same store
returns equal payloads.

### Error Handling

`StoreError` propagates from `DashboardData.series` if a key that `has_series` reported as present
disappears, which would be an internal contradiction rather than a data problem. `RegistryError`
propagates from `unit_for` for a chart key absent from both the metadata and `FALLBACK_UNITS`; that
cannot happen for the 23 enabled specs, whose `unit` is `FALLBACK_UNITS[key]` by construction, so a
raise here means the catalogue and the schema table disagree and the run must stop. `ValueError` from
`payload_json` when a NaN or an infinity reached the store. Catch nothing; add no bare `except`.

## Dependencies

- **Blocked By**: `ticket-018-implement-series-consolidation.md`
- **Blocks**: `ticket-021-assemble-single-file-html-shell.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture consolidated with the repository `settings.json` values and
      `reference="caso_a"`, when `build_payload` is called with a two-entry `scenario_colors` and an
      empty `plotly_layout`, then `set(payload)` equals the ten documented top-level keys,
      `payload["schema_version"]` equals `1`, `payload["scenarios"]` equals `["caso_a", "caso_b"]`,
      `payload["deck_dates"]` equals `["03/03/2024", "04/03/2024"]` and `payload["chained_key"]`
      equals `"encadeado"`.
- [ ] Given the same payload, when `payload["axes"]` is read, then its key set equals
      `{"03/03/2024", "04/03/2024", "encadeado"}`, every value has the key set `{"starts", "end"}`,
      `len(payload["axes"]["03/03/2024"]["starts"])` equals `50`,
      `payload["axes"]["03/03/2024"]["starts"][0]` equals `"2024-03-03 00:00"`,
      `payload["axes"]["03/03/2024"]["end"]` equals `"2024-03-04 12:00"`,
      `len(payload["axes"]["encadeado"]["starts"])` equals `96` and
      `payload["axes"]["encadeado"]["end"]` equals `"2024-03-05 00:00"`.
- [ ] Given the same payload, when `payload["charts"]` is read, then it has 23 entries, every entry
      key set equals the nine documented keys,
      `payload["charts"]["GHID_SIN"]["entities"]` equals `[{"id": "", "label": "Sistema
      Interligado"}]`, `len(payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]["03/03/2024"])`
      equals `50`, `payload["charts"]["CMO_SBM"]["unit"]` equals `"R$/MWh"`,
      `payload["charts"]["INT_SBP"]["entities"][0]["label"]` equals `"SE (SUDESTE) para S (SUL)"`,
      and `payload["charts"]["TEMPO"]` has an empty `series`, an empty `entities` and exactly five
      `scalars` names.
- [ ] Given a copy of the fixture whose `METADADOS_OPERACAO.parquet` row for `CMO_SBM` was rewritten
      with `nome_longo_variavel = "Custo Marginal de Operação"`, when the payload is rebuilt, then
      `payload["charts"]["CMO_SBM"]["subtitle"]` equals `"Custo Marginal de Operação"` while
      `payload["charts"]["CMO_SBM"]["title"]` stays `"CMO"`, and
      `payload["charts"]["GHID_SIN"]["subtitle"]` is `None`, because the generator writes
      `nome_longo_variavel` equal to `ChartSpec.title` for every key it does not rewrite.
- [ ] Given `output.decimals = 2`, when `payload_json(payload)` is called, then every element of
      `payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]["encadeado"]` equals `round(element, 2)`,
      the returned text contains neither the substring `"NaN"` nor the character `<`, and
      `.venv/bin/pytest tests/test_payload.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Declare the module constants first: `_SCHEMA_VERSION = 1`,
   `_AXIS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M"` with a docstring line stating it is a machine format
   for Plotly and never operator-facing, and `_DIFFERENCE_SUFFIX = " (diferença)"`.
2. Write four private builders — `_build_axes`, `_build_chart_entry`, `_build_series`,
   `_build_scalars` — and let `build_payload` assemble their results. Keep the rounding in one
   `_round_value(value, decimals)` helper used by both the series and the scalar path, so the two
   cannot drift.
3. Build the axis `end` from `axis.starts[-1] + pandas.Timedelta(hours=axis.durations_hours[-1])` and
   format it with `strftime(_AXIS_TIMESTAMP_FORMAT)`. `strftime` drops the UTC label without shifting
   the clock, which is precisely the behaviour decision 10 requires.
4. Iterate charts over `enabled_specs(disabled=settings.charts.disabled)` — the identical call
   `consolidate` makes — so the payload chart set and the consolidated chart set cannot disagree.
5. For the series, loop entity, then scenario, then the deck dates plus the chained axis, guarding
   every read with `has_series`, and address the chained axis with `deck_date=None` while writing it
   under `payload["chained_key"]`.
6. Write `tests/test_payload.py` on the `scenario_tree` fixture, plus one variant that rewrites
   `METADADOS_OPERACAO.parquet` and one hand-built two-point `DashboardData` for the NaN and the
   `None` cases.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/payload.py` (create)
- `tests/test_payload.py` (create)
- `src/dessem_dashboard/models/store.py` (modify, **additions only** — the three read-only accessors
  of requirement 3a; prove it with `git diff --numstat` showing zero deletions)
- `tests/test_store.py` (modify — unit tests for those three accessors)

> **Resynced 2026-09-11.** Requirement 3a was added to this ticket after its first draft, to carry
> finding M6 of the epic-02 boundary review, and the amendment did not sweep these downstream
> sections: this list, the Testing Requirements and the Definition of Done all still described a
> two-file ticket. That is defect shape 6 of `epic-02-learnings.md` section 6 — a summary left stale
> by an amendment to the requirement it summarises — committed by the orchestrator one commit after
> recording the rule, and caught by readiness scoring, which put this ticket's boundary dimension at
> 0.60. Left unfixed it would have handed a guardian two undeclared modified files and a false scope
> violation.

### Patterns to Follow

- `log_step` from `logging_setup` with volume fields and `elapsed_s` at each function boundary, as
  `consolidate.py` does, because `CLAUDE.md` requires audit-grade logging of data volumes.
- Portuguese log messages, English identifiers and docstrings, reusing the vocabulary already shipped
  (`gráfico`, `cenário`, `deck`, `valor`) instead of new synonyms.
- Explicit typing with `Mapping` for parameters and concrete `dict`/`list` for returns, matching
  `registries.py` and `store.py`.

### Pitfalls to Avoid

- Do not format a deck label with `settings.dashboard.date_format`. That value is
  `"%d/%m/%Y %H:%M"`, so it would render the deck of 3 March as `03/03/2024 00:00`. Deck labels are
  `%d/%m/%Y`, which is why requirement 3 takes them from `TimeAxis.key`.
- Do not emit an ISO date anywhere an operator will read it. The `%Y-%m-%d %H:%M` axis strings are
  machine values consumed by Plotly and rendered through `tickformat`; the payload contains no other
  ISO date.
- Do not call `tz_convert` or `tz_localize` on `TimeAxis.starts`. A conversion would shift every point
  of every chart by hours without failing a single test (Epic 2 learnings, decision 10).
- Do not store a missing value as `float("nan")`. `add_series` already keeps `None`; the payload must
  carry `null`, and `allow_nan=False` is the net that catches a regression.
- Do not fill a scenario that lacks a deck with an array of nulls at this layer. Ticket-018 already
  padded the **chained** arrays and deliberately stores nothing per deck; requirement 8 keeps that
  distinction visible so the renderer drops the trace instead of drawing a line at zero.
- Do not iterate `charts.registry.all_specs()`: it returns all 42 declared specs, including the 19
  shipped disabled, and the store holds data for none of them.
- Do not sort or re-order `entities`: `set_entities` already sorted by `sort_key`, and plant charts
  are alphabetical by plant name.
- Do not add a `warnings` key "for completeness". Ticket-021 renders them, and a second copy is a
  second source of truth.

### Out of Scope

- The HTML document, the `<script type="application/json">` element and the inlining of this JSON
  (ticket-021).
- The theme values themselves: `scenario_colors` and `plotly_layout` arrive as arguments and this
  module neither validates nor interprets them (ticket-019).
- Rendering the warnings, which ticket-021 writes into the HTML from `data.warnings()`.
- Cost totals, `TEMPO` group sums and the `time.unit_divisor` division (tickets 030 and 031).
- Output size measurement and the `output.size_warning_mb` warning (ticket-032).
- Any browser-side concern: trace construction, the difference arithmetic and the axis choice per
  view mode (tickets 022 to 026).

## Testing Requirements

### Unit Tests

`tests/test_store.py` (added to the existing file, for requirement 3a):

- `chart_keys()` returns exactly the chart keys that hold at least one stored series, sorted, and an
  empty tuple on a store with none;
- `scalar_chart_keys()` returns only charts holding scalars, so `CUSTOS`/`TEMPO` appear and a series
  chart does not;
- `stored_deck_dates(chart_key, entity_id, scenario)` returns the deck dates actually stored for that
  triple with `None` sorting **last** as the chained axis, and an empty tuple for an absent triple —
  assert it against a store where one deck was deliberately skipped, so the result differs from
  `data.deck_dates` and the test cannot pass by accident;
- each accessor is read-only: calling it twice returns equal results and does not mutate
  `value_count()`.

`tests/test_payload.py`:

- the five acceptance criteria;
- a chart present in the store but absent from the catalogue produces the Portuguese omission warning
  of requirement 3a, asserted as a filtered count over the matching messages;
- every array length equals the length of the `starts` list of the axis it is filed under, checked
  for all 23 charts, all entities, both scenarios and all three axis keys;
- a fixture variant where `caso_b` lacks the second deck: the affected chart entries carry no
  `"04/03/2024"` key under `caso_b`, while the `"encadeado"` array is still present with length 96;
- a fixture variant generated with `omit=("GTER_UTE.parquet",)` for one deck: `GTER_UTE` still has an
  entry with its nine keys, and no series under the affected scenario and deck;
- rounding: a hand-built store whose value is `1.23456` exports `1.23` at `decimals=2` and `1.235` at
  `decimals=3`;
- `None` survives as `None` through `build_payload` and as `null` through `payload_json`;
- a hand-built store containing `float("nan")` makes `payload_json` raise `ValueError`, proving
  `allow_nan=False` is set rather than merely assumed;
- a hand-built store whose entity label contains `<` produces a `payload_json` text with no `<` and
  with the `\u003C` escape present, and that text round-trips through `json.loads` to the original
  label;
- `subtitle` is `None` when `title_for` returns `None`, asserted on a fixture whose
  `METADADOS_OPERACAO.parquet` row for one key carries a null `nome_longo_variavel`;
- `scalars` shape: `CUSTOS` exports four parcel names and `TEMPO` five stage names, each with two
  scenarios and two deck keys, and no value was divided by 60;
- `caplog` assertions on the two INFO lines and their volume fields.

### Integration Tests

None. The payload built from a real scenario tree is exercised end to end by ticket-034.

## Definition of Done

- [ ] All four files exist or are modified as listed under "Key Files to Create/Modify", and all five
      acceptance criteria pass.
- [ ] `git diff --numstat -- src/dessem_dashboard/models/store.py` shows additions and **zero
      deletions**: `EntityRef`, `TimeAxis` and every existing `DashboardData` method are a committed
      contract that ticket-018 already populates and tickets 021 to 026 consume.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] `payload.py` does not import `dashboard.theme`, verified with
      `grep -n "theme" src/dessem_dashboard/dashboard/payload.py` printing nothing, so tickets 019
      and 020 remain independently implementable.
- [ ] The exported payload contains no `warnings` key and no `durations_hours` key, both excluded on
      purpose by requirements 2 and 3.
- [ ] Every raw value that reaches the JSON was rounded to `output.decimals`, and no missing value
      was exported as a NaN.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
