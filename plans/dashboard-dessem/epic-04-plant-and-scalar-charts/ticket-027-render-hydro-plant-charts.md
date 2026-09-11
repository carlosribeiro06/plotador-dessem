# ticket-027 Render the hydro plant charts from data-driven plant lists

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: first of the epic, strictly before ticket-028.** ticket-028 asserts inside
> `<section class="chart">` slices and this ticket creates the shared slicing helper module
> `tests/dashboard_document.py`. Running them in the other order would make ticket-028 write its own
> slicer and this ticket add a second one — duplication that passes every test, because each ticket
> tests only its own. It must also not run in parallel with ticket-030: both modify
> `dashboard/payload.py`.

## Context

### Background

The eight hydro-plant charts of master plan Appendix A.6 — `GHID_UHE` Geração, `QTUR_UHE`
Turbinamento, `QVER_UHE` Vertimento, `VARMF_UHE` Volume Armazenado (hm3), `VARPF_UHE` Volume
Armazenado (%), `QDEF_UHE` Defluência, `QAFL_UHE` Vazão Afluente and `QINC_UHE` Vazão Incremental —
are the widest part of the catalogue: 165 plants in the real data, against one entity at SIN level
and five at submarket level.

Almost all of the rendering they need already exists. ticket-018 derived each chart's entity list
**from its own file** (master plan decision 16) with the plant name as both label and `sort_key`;
ticket-020 exported those lists; ticket-021 rendered, for every chart whose selector is not `NONE`,
a `<label class="entity-label">` and a `<select class="entity-selector" id="entity-KEY">` with one
`<option value="CODE">NAME</option>` per entity; ticket-023 made `setGroup("UHE")` reveal and render
the group; ticket-025 gave `buildLayout` the per-chart Y-axis unit; ticket-026 made every
`.entity-selector` live through one delegated listener and `setEntity`. Opening the built file and
clicking `Usinas hidrelétricas` therefore already draws eight stacked hydro charts today.

What is missing is a payload rule and the verification that the whole path is right. The payload
rule is epic decision **E4-3**: the plant series stay fully embedded, because the deliverable is one
self-contained offline HTML and a lazy fetch would need a server or sibling files, so size is
*managed* rather than dodged — by rounding (already in ticket-020), by **omitting entities and
arrays that hold nothing but `null`**, and by ticket-032 measuring the document and warning past
`output.size_warning_mb`. Omitting the empty arrays is also what makes this ticket's own objective
true: a plant that a variable does not cover must not appear in that variable's selector.

Three facts from the epic-03 boundary review correct the outline's framing of that rule, and the
refinement records them rather than repeating them:

- **The omission is new code, not existing behaviour.** `_build_series` already omits a
  *never-stored* `(scenario, axis)` key, but a **stored all-`None` array is emitted in full** — the
  store deliberately distinguishes "nothing was ever added" from "an all-`None` array was added", and
  `consolidate` adds exactly the latter for an entity absent from a file that exists (decision 17).
  Nothing exercises the new filter today: the fixture payload holds 258 arrays and **zero** of them
  is entirely `None`.
- **E4-3's own justification for the rule is wrong, and the rule is still right.** E4-3 motivates it
  with `VCALHA_UHE` "covering 92 of 165 plants" shipping "73 arrays of pure `null`". That cannot
  happen: `VCALHA_UHE` is a **disabled** registry entry, so it is never read at all, and even
  enabled, decision 16 builds its entity list from its own file, so the 73 uncovered plants never
  enter the payload. The real and measurable case is different: `all_entity_ids` in
  `consolidate._load_series` is the **union over every scenario and deck**, so a plant present in one
  scenario and absent from another gets a full-length all-`None` array in the other — 68 nulls per
  deck per absent plant in the real data.
- **Omitting an all-`null` array does not contradict decision 17.** Decision 17 fills a missing
  `(entity, stage)` with `null` inside an array, and that stays. ticket-020 requirement 8 already
  traded away "uniform shape" at the key level by emitting no key at all for a scenario missing a
  deck, and the renderer already implements the matching rule: a missing key means missing data at
  two levels, and `buildTraces` skips that scenario instead of substituting zero.

The three original key decisions and the three open questions resolve as follows.

- **Each chart keeps its own plant selector and its own selection.** ticket-026 fixed this for the
  submarket level and the reason is stronger here: coverage is per variable by decision 16, so a
  union selector shared by the eight charts would offer a plant that `VARMF_UHE` does not have. The
  per-chart `state.entities` entry already exists and needs no change.
- **The plant label stays the plant name alone, without the code.** ticket-028's code filter matches
  the `<option value>`, which already *is* `str(codigo_usina)` (the fixed entity-id format of epic-02
  learnings section 1), so putting the code in the label would duplicate data the filter already
  reads. It would also mean editing `consolidate._entity_ref`, whose label and `sort_key` are pinned
  by `tests/test_consolidate.py` and `tests/test_registries.py` — an epic-02 contract, reopened for
  cosmetics. If the developer later wants `NAME (CODE)` in the dropdown, that is a one-line change in
  `_entity_ref` plus its epic-02 test updates, i.e. its own ticket.
- **Both members of both ambiguity pairs stay enabled**, with the curated titles ticket-011 shipped:
  `Volume Armazenado (hm3)` beside `Volume Armazenado (%)`, and `Vazão Afluente` beside
  `Vazão Incremental`. That is epic decision **E4-2**, which closed master plan open questions 2
  and 3 — nothing remains to decide and neither pair may be collapsed.
- **One plant at a time, never several overlaid.** `planning-context.md` decision 5 fixes one curve
  per scenario; overlaying plants as well would need a two-dimensional legend nobody asked for.
- **A plant present in `GHID_UHE` and absent from `VARMF_UHE` needs no empty state at all.** The
  question dissolves under decision 16: that plant is simply not in `VARMF_UHE`'s option list, and
  because the selection is per chart, nothing ever asks `VARMF_UHE` for it.
- **The size mitigation does not need to land before this view.** E4-3 settled it: rendering is
  already lazy — ticket-023 renders only the unhidden group — so the 165 plant traces are not built
  until the operator opens the level. This ticket carries the payload-side omission and ticket-032
  measures the bytes it saves.

### Relation to Epic

The first ticket of the epic and the one that opens the plant level. It hands ticket-028 the eight
populated plant selectors its filters narrow and the shared document-slicing helpers its assertions
need, hands ticket-029 the pattern its thermal verification mirrors, and hands ticket-032 both a
payload that no longer pays for plants a variable does not cover and the saving that ticket measures.

### Current State

`payload.py` exports ten top-level keys and gives each chart nine keys — `group`, `kind`, `selector`,
`title`, `subtitle`, `unit`, `entities`, `series`, `scalars` — uniform across both chart kinds.
`_build_series(data, chart_key, entity_id, *, decimals)` nests scenario then axis key, reads
`data.stored_deck_dates(...)` once per scenario, and emits **no key at all** for a scenario that
stored nothing — but emits a stored all-`None` array in full. `_build_chart_entry` derives
`entities` from `data.entities(chart_key)` and `series` from `_build_series` **independently of each
other**, which is the divergence hazard requirement 2 closes. `_round_value` normalises a rounded
`-0.0` to `0.0` and passes `None` through. `build_payload` never mutates `data`, never touches disk,
and returns equal payloads on repeated calls; its only Portuguese operator output is
`_warn_omitted_charts`'s `logger.warning`, because the payload deliberately has no `warnings` key
(ticket-021 renders the Avisos section in Python from `data.warnings()`).

`dashboard.js` exposes thirteen members after ticket-026 and reads every payload field through the
frozen `KEYS` object. Its contract tests were narrowed at the epic-03 boundary: each `KEYS` value's
quoted literal must occur exactly once **inside the `KEYS` declaration**, must never appear as a raw
index anywhere, and every `payload[` must be followed by `KEYS.`; comments and CSS-selector strings
are no longer counted, so this epic needs none of the workarounds tickets 025 and 026 required. One
further assertion is being added at that boundary and must be assumed in force: **dot access on a
payload-derived object is forbidden**, so a field of a chart entry is read as `chart[KEYS.UNIT]`,
never as `chart.unit`. `tests/test_charts_sin.py` additionally pins that `dashboard.js` contains none
of the quoted unit literals `"MW"`, `"MWh"`, `"hm3"` and `"m3/s"`, that `yaxis` is assigned in
exactly one function, and that `Plotly.react(` occurs exactly once.

`builder.SELECTOR_LABELS` already maps `HYDRO_PLANT` to `Usina hidrelétrica` and `THERMAL_PLANT` to
`Usina termelétrica`, and `GROUP_LABELS` maps `UHE` to `Usinas hidrelétricas`; the eight UHE sections
render today with `data-group="UHE"`, `data-selector="HYDRO_PLANT"` and the `hidden` attribute,
because `SIN` is the initially active group.

The document-slicing helpers written for ticket-025 and extended for ticket-026 are **private to
their test modules** (`_chart_section_slices`, `_sections_by_chart_key`, `_sections_by_group`,
`_section_heading`, `_entity_options`, `_entity_selector_id`, `_opening_tag` in
`tests/test_charts_submarket.py`). Four Epic 4 test modules need them.

Measured on the `scenario_tree` fixture, whose generator defaults are `hydro_codes=(1, 2, 3)` and
`reservoir_codes=(1, 2)` — `build_scenario_tree` overrides only `n_stages=50`,
`half_hour_stages=48`, `long_stage_hours=6.0` and `seed`, and forwards **neither** code set:

| Chart | Entities | Labels | Unit | Curated title |
| ----- | -------- | ------ | ---- | ------------- |
| `GHID_UHE` | 3 | `USINA_1`, `USINA_2`, `USINA_3` | `MW` | Geração |
| `QTUR_UHE` | 3 | idem | `m3/s` | Turbinamento |
| `QVER_UHE` | 3 | idem | `m3/s` | Vertimento |
| `VARMF_UHE` | 2 | `USINA_1`, `USINA_2` | `hm3` | Volume Armazenado (hm3) |
| `VARPF_UHE` | 2 | `USINA_1`, `USINA_2` | `%` | Volume Armazenado (%) |
| `QDEF_UHE` | 3 | `USINA_1`, `USINA_2`, `USINA_3` | `m3/s` | Defluência |
| `QAFL_UHE` | 3 | idem | `m3/s` | Vazão Afluente |
| `QINC_UHE` | 3 | idem | `m3/s` | Vazão Incremental |

Four distinct units across eight charts, which is why no unit literal may ever reach the asset — the
SIN level already carried three distinct units across five charts and cost ticket-025 the same rule.
Each series array holds 50, 50 and 96 values for `03/03/2024`, `04/03/2024` and `encadeado`. The
fixture's `METADADOS_OPERACAO.parquet` writes `nome_longo_variavel` equal to the curated title for
every key, so no section carries a `<p class="chart-subtitle">` on the unmodified tree — in the real
data `VARMF_UHE`'s long name is `Volume Armazenado Absoluto Final`, which is exactly why E3-2 keeps
the curated title as the heading and demotes the registry name to a subtitle.

## Specification

### Requirements

1. In `dashboard/payload.py`, `_build_series` must omit an axis entry whose values are **all** `None`,
   and then omit a scenario whose axis mapping became empty. Partial arrays keep their `null` holes
   untouched: decision 17 governs a missing `(entity, stage)` inside an array, while this rule
   governs an array that carries no information at all. The renderer already handles both levels of
   absence by skipping the trace.
2. `_build_chart_entry` must build `series` **first** and then derive `entities` from the entities
   that survived in it, so the two stay in lockstep by construction. An entity dropped from `series`
   but kept in `entities` would still be rendered as an `<option>`, and `init()` takes
   `chartEntities[0]` as that chart's default selection — if the dropped plant sorts first, opening
   the hydro level would show a blank chart with no message and nothing in the document explaining
   it. `entities` order stays `data.entities(...)` order, which is `sort_key` order, and every
   surviving entity keeps its `{"id", "label"}` shape.
3. Log exactly one Portuguese INFO line per chart that lost at least one entity, naming the chart key
   and the count, and no line for a chart that lost none. Use `logger.info`, never
   `data.add_warning`: `build_payload` must stay non-mutating, which `tests/test_payload.py` relies
   on, and the payload has no `warnings` key by design. The already-shipped `consolidate` warning
   `N entidade(s) do gráfico '…' ausente(s) no cenário '…'` remains the operator-facing message in
   the Avisos section; this line is the audit record of what the payload then dropped.
4. Change nothing else in the payload. The nine chart keys, the `SCALAR_BY_DECK` branch, the
   rounding, `_axis_entry`, `_warn_omitted_charts`, `payload_json`'s `allow_nan=False` and the `<`
   escape, and the two INFO lines `build_payload` already logs all stay exactly as ticket-020 built
   them.
5. Create `tests/dashboard_document.py` — a helper module, not a test module, following the
   precedent of `tests/fixtures_sintese.py` — exposing the document-slicing helpers under public
   names: `chart_section_slices`, `sections_by_chart_key`, `sections_by_group`, `opening_tag`,
   `section_heading`, `entity_label_text`, `entity_selector_id`, `entity_options` and `nav_slice`,
   with the behaviour the ticket-026 private versions already have. Leave
   `tests/test_charts_sin.py` and `tests/test_charts_submarket.py` untouched: de-duplicating two
   guardian-verified test modules is a wider change than this ticket owns, and the duplication is a
   recorded, accepted trade. If a shared helper module already exists when this ticket starts — a
   concurrent simplifier pass may have created one — extend that module instead of adding a second.
6. Create `tests/test_charts_hydro.py`, the end-to-end verification of the hydro view, asserting the
   facts of the Current State table and the two omission rules. Every heading assertion must be
   scoped to its own `<section class="chart">` slice: `Geração` is the curated title of both
   `GHID_UHE` and `GTER_UTE`, and `Volume Armazenado` is a substring of both UHE volume titles and
   the exact title of `VARMF_SIN` and `VARMF_SBM`.
7. Assert in that module that `dashboard.js` contains none of the quoted unit literals `"MW"`,
   `"MWh"`, `"hm3"`, `"m3/s"` **and `"%"`**. The first four are already pinned by
   `tests/test_charts_sin.py`; `"%"` is new with this level, because `VARPF_UHE` is the first
   percentage chart in the catalogue and a group-level default unit would mislabel it.
8. Change no other file. No JavaScript, no CSS, no HTML template, no `builder.py`, no `theme.py`, and
   no epic-02 module — in particular not `consolidate._entity_ref`, whose plant label and `sort_key`
   are test-pinned and whose format the Background settles.

### Inputs

At payload build time, a populated `DashboardData` and `Settings`. At test time, the `scenario_tree`
fixture, one tree regenerated through `make_sintese_dir` with per-scenario `hydro_codes`, one
hand-built `DashboardData`, the `dashboard.js` asset text and documents built from those trees.

### Outputs and Behavior

Each hydro chart's selector lists exactly the plants its own variable covers, and the payload carries
no array and no entity made only of `null`. Choosing a plant redraws that chart for every scenario in
its scenario colour; the choice is independent per chart and survives a mode, deck or level change.
`VARPF_UHE` labels its Y axis `%` while `VARMF_UHE` labels it `hm3`, from data, not from the asset.
Nothing is written to disk.

### Error Handling

No new error path and no new exception type. An entity or a scenario that disappears under
requirements 1 and 2 is normal degradation, already covered by decision 18's warning-plus-gap rule
and reported once by `consolidate`. A chart that loses **every** entity — its file missing from every
deck of every scenario — renders an empty `<select>` and an empty plot: `init` then stores no
`state.entities` entry, `buildTraces` finds `chart[KEYS.SERIES][undefined]` undefined and returns no
trace, and the Avisos section already carries one warning per missing file. That is the intended
degradation, not a crash, and it must not be special-cased in the asset.

## Dependencies

- **Blocked By**: `ticket-026-render-submarket-and-interchange-charts.md`
- **Blocks**: `ticket-028-implement-name-and-code-filters.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture and the repository `settings.json`, when the payload is built,
      then the eight `UHE` chart entries carry, in `enabled_specs` order, entity counts
      `3, 3, 3, 2, 2, 3, 3, 3` with labels drawn from `USINA_1`, `USINA_2`, `USINA_3`; their units are
      `MW`, `m3/s`, `m3/s`, `hm3`, `%`, `m3/s`, `m3/s`, `m3/s`, i.e. four distinct strings; and every
      series array holds 50, 50 and 96 values for `03/03/2024`, `04/03/2024` and `encadeado` in both
      `caso_a` and `caso_b`.
- [ ] Given a tree built by calling `make_sintese_dir` directly for both decks of both scenarios with
      `hydro_codes=(1, 2, 3)` for `caso_a` and `hydro_codes=(1, 2)` for `caso_b`, when the payload is
      built, then `charts["GHID_UHE"]["entities"]` still lists three plants, `series["3"]` has
      `caso_a` as its only key, `series["1"]` has both scenarios, and no array anywhere in
      `charts["GHID_UHE"]["series"]` consists only of `None`.
- [ ] Given a hand-built `DashboardData` holding two entities for one chart where every array of the
      second is all-`None` and the first has real values, when `build_payload` runs, then the second
      entity is absent from both `entities` and `series`, the first is present and unchanged, and
      exactly one INFO record of the `dessem_dashboard.dashboard.payload` logger names that chart key
      and the count `1`.
- [ ] Given the document built from the `scenario_tree` fixture, when the eight `data-group="UHE"`
      section slices are inspected, then each carries `data-selector="HYDRO_PLANT"`, the `hidden`
      attribute, a `<label class="entity-label">` reading `Usina hidrelétrica`, exactly one `<h2>`
      holding its curated title, and no `<p class="chart-subtitle">`; and
      `<select class="entity-selector" id="entity-VARMF_UHE">` holds exactly the two options
      `<option value="1">USINA_1</option>` and `<option value="2">USINA_2</option>` while
      `entity-GHID_UHE` holds those two plus `<option value="3">USINA_3</option>`, in that order.
- [ ] Given the `dashboard.js` asset text, when the quoted literals `"MW"`, `"MWh"`, `"hm3"`,
      `"m3/s"` and `"%"` are searched, then none of the five occurs; and
      `.venv/bin/pytest tests/test_charts_hydro.py tests/test_payload.py tests/test_charts_sin.py
      tests/test_charts_submarket.py tests/test_builder.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Start with `_build_series`: build `by_axis` as today, then drop the entries whose values are all
   `None` with `all(value is None for value in values)`, and `continue` before assigning
   `result[scenario]` when `by_axis` ends up empty. Keep `stored_dates` as the outer loop — the
   ticket-020 optimisation that avoids about 320 000 `has_series` probes is unrelated and must stay.
2. In `_build_chart_entry`'s `SERIES` branch, build the `series` mapping first, then build
   `entities_payload` by iterating `data.entities(spec.key)` and keeping only the entities whose id
   is a key of that mapping. Deriving the list from the mapping rather than filtering the two
   independently is what requirement 2 means by lockstep by construction.
3. Count the dropped entities in that branch and emit requirement 3's single `logger.info` only when
   the count is non-zero, in the style of `_warn_omitted_charts`: a `%s`/`%d` lazy format, chart key
   first.
4. Create `tests/dashboard_document.py` by lifting the ticket-026 helpers verbatim, renaming them
   without the leading underscore and adding module and function docstrings in English. Keep them
   pure functions over the document text, fully annotated, as `tests/fixtures_sintese.py` is.
5. Write `tests/test_charts_hydro.py` around that module. Build the fixture document with the
   settings-copy-in-`tmp_path` pattern of `tests/test_builder.py`, and slice before asserting. For
   the per-scenario coverage tree, call `make_sintese_dir` directly, once per (scenario, deck), with
   the same `n_stages=50, half_hour_stages=48, long_stage_hours=6.0` and distinct seeds
   `build_scenario_tree` uses — it forwards no code set, so passing `hydro_codes` through it is not
   an option and reusing the fixture would prove nothing.
6. Build the all-`null` entity case as a hand-built `DashboardData`, the way `tests/test_payload.py`
   builds its `NaN` and `<`-escaping cases: `set_entities` with two `EntityRef`s, `add_series` with
   an all-`None` tuple for the second on every axis, and `add_scalar` untouched. The fixture cannot
   produce this case — its 258 arrays contain no all-`None` one — because every entity in
   `all_entity_ids` got there from a file that had rows for it.
7. Prove each asset and payload assertion can fail: insert `"%"` into a copy of the asset text and
   confirm the literal check raises; replace one `None` with a number in the all-`None` array and
   confirm the entity survives; add a third plant to `caso_b` and confirm the `series["3"]`
   single-key assertion fails. Inspection is not enough — one genuinely vacuous test shipped in
   Epic 1 and was caught only by mutation.
8. Open the built file once by hand and click `Usinas hidrelétricas`: confirm eight charts stacked,
   the console clean, and `VARPF_UHE`'s Y axis reading `%`. The numbered checklist steps for this
   level belong to ticket-028, which owns the `docs/checklist-manual-dashboard.md` Epic 4
   placeholder.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/payload.py` (modify: the two omission rules and one INFO line)
- `tests/dashboard_document.py` (create)
- `tests/test_charts_hydro.py` (create)

### Patterns to Follow

- ticket-020's `_build_series` shape: one scenario loop, one axis loop, keys omitted rather than
  filled, `_round_value` as the single rounding point.
- `_warn_omitted_charts`'s logging style for requirement 3: Portuguese text, lazy `%s` formatting,
  one line per affected chart, naming the chart key.
- The document-slicing assertion pattern of `tests/test_charts_sin.py` and
  `tests/test_charts_submarket.py`, now shared through `tests/dashboard_document.py`.
- The regenerate-the-fixture pattern ticket-026 used for its fictitious pair: when a parameter is not
  forwarded by `build_scenario_tree`, call `make_sintese_dir` directly.
- English identifiers, comments and test names; Portuguese only in operator-facing strings.

### Pitfalls to Avoid

- Do not filter `entities` and `series` independently. That is the divergence the epic-03 boundary
  review measured: the selector would offer a plant the payload no longer carries, and `init()`
  defaults to the first entity in sort order, so the level could open on a blank chart with nothing
  in the document explaining it.
- Do not assert a heading over the whole document. `Geração` is the curated title of `GHID_UHE`
  **and** `GTER_UTE`, and `Volume Armazenado` is a substring of both UHE volume titles as well as the
  exact title of `VARMF_SIN` and `VARMF_SBM`. Scope every heading assertion to its section slice.
- Do not hard-code a unit anywhere. The eight hydro charts carry four distinct units, and `VARPF_UHE`
  is `%` while its twin `VARMF_UHE` is `hm3` — a group-level default is wrong on the pair the
  catalogue exists to distinguish.
- Do not collapse either ambiguity pair, and do not "fix" the near-duplicate titles. E4-2 settled it:
  both members stay enabled with the distinguishing curated titles ticket-011 shipped.
- Do not put the plant code in the `EntityRef` label. The code already travels as `option.value`,
  which is exactly what ticket-028's code filter reads, and the label format is pinned by epic-02
  tests.
- Do not call `data.add_warning` from `payload.py`. It would mutate the store during payload building,
  break the repeated-call equality `tests/test_payload.py` asserts, and duplicate a warning
  `consolidate` already emits.
- Do not adjust `data.value_count()`. It is the store's audit figure and legitimately counts the
  `None` slots the payload then drops; `write_dashboard` logs it as `valores` and ticket-032 reports
  it. Two different numbers, two different questions.
- Do not remove the `null` holes inside a partially covered array. Decision 17 governs those, and
  `connectgaps: false` renders them as the visible gaps they are.
- Do not import a private helper from another test module. `from test_charts_submarket import
  _sections_by_group` would work today and break the moment a simplifier renames it; that is what
  `tests/dashboard_document.py` exists to prevent.
- Do not write the per-scenario coverage test against the default fixture. Both scenarios share the
  same `hydro_codes` there, so the assertion would pass while proving nothing — the exact vacuous
  shape recorded in Epic 2 learnings section 7 and hit again by ticket-018.
- Do not assert the absence of the subtitle as `"<p" not in section`, and do not assert a single
  `<label` per plant section. ticket-028 adds a `<p class="filter-empty">` and two
  `<label class="filter-label">` elements to every plant section three days later, so both
  shortcuts would turn a correct later ticket into a failing suite. Assert by class.
- Do not touch `dashboard.js`. Its `KEYS` contract, its single `Plotly.react(` call and its
  single-function `yaxis` assignment are all pinned, and this ticket needs none of them changed.

### Out of Scope

- The name and code filters (ticket-028) and the `docs/checklist-manual-dashboard.md` Epic 4
  placeholder they own.
- The thermal plant chart and its verification (ticket-029).
- The `CUSTOS` and `TEMPO` bar charts (tickets 030 and 031), whose `SCALAR_BY_DECK` branch in
  `_build_chart_entry` this ticket leaves exactly as it is, and the `data-kind` attribute and
  `KEYS.KIND` entry ticket-030 adds.
- Measuring or warning about the document size and measuring the saving these rules produce
  (ticket-032), and any lazy, split or fetched payload, which E4-3 rules out outright.
- Filtering by submarket or equivalent reservoir (E4-4), `<optgroup>` grouping, multi-plant overlay,
  natural-sort plant ordering, and `limite_inferior`/`limite_superior` bands, which the store does
  not carry.
- Any change to `consolidate.py`, `registries.py`, `store.py`, `builder.py`, `theme.py` or the three
  packaged assets.

## Testing Requirements

### Unit Tests

`tests/test_charts_hydro.py`:

- the five acceptance criteria;
- the set of `data-group="UHE"` chart keys in the document equals the eight expected keys, so a chart
  silently dropped from the group fails here;
- `charts.disabled = ["VARPF_UHE"]`: seven UHE sections, no `id="chart-VARPF_UHE"`, and the remaining
  seven headings and units unchanged — proving the level is registry-driven and that the `%` unit
  belongs to exactly one chart;
- the payload `VARMF_UHE` and `VARPF_UHE` entity lists are equal to each other and a strict subset of
  `GHID_UHE`'s, which is decision 16 made observable on the shipped fixture;
- every `GHID_UHE` value is either `None` or equal to itself rounded to two decimals;
- a scenario whose `GHID_UHE.parquet` is deleted for one deck keeps its other deck's key and its
  chained key, so requirement 1 did not swallow a partially covered array;
- the `entities`/`series` lockstep on the hand-built store: the surviving `entities` ids equal the
  keys of `series`, asserted for every chart of the fixture payload as well;
- the non-vacuity mutations of Suggested Approach step 7, each confirmed to fail before restoration.

`tests/test_payload.py` is not modified by this ticket: no existing assertion covers an all-`null`
array, and `test_build_payload_missing_series_file_omits_only_that_scenario_and_deck` stays green
because the chained array of the affected scenario still holds its other deck's real values.

### Integration Tests

None automated, by epic decision E3-1. The rendered hydro view is covered by the manual steps
ticket-028 adds to `docs/checklist-manual-dashboard.md`; the run against the real 165-plant data is
ticket-034.

## Definition of Done

- [ ] The three files exist — one modified, two created — and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] Every hydro selector lists exactly the plants its own file covers, with `VARMF_UHE` and
      `VARPF_UHE` at two and the other six at three on the fixture.
- [ ] No array and no entity made only of `null` reaches the payload; `entities` and `series` hold the
      same id set for every chart; and one INFO line records each chart's dropped count.
- [ ] `tests/test_charts_sin.py`, `tests/test_charts_submarket.py`, `tests/test_builder.py`,
      `tests/test_payload.py`, `tests/test_renderer_contract.py`, `tests/test_renderer_controls.py`
      and `tests/test_renderer_value_mode.py` all pass unchanged.
- [ ] `tests/dashboard_document.py` is importable by a sibling test module and is not collected as a
      test module by pytest.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 35 minutes. Re-estimated from the
outline's 3 points with a different balance: the rendering the outline anticipated is already
shipped by tickets 021 to 026, so the source change is about twenty lines across two functions of
one module, while the weight moved to the shared helper module and to a verification suite that must
prove both omission rules on inputs the default fixture cannot produce. Confidence is High rather
than the outline's Low because every fact it rests on is measured and every new behaviour is
decidable in Python — unlike ticket-025 and ticket-026, this ticket's new behaviour needs no browser
to verify.
