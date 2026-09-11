# ticket-026 Render the submarket and interchange charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Seven charts of master plan Appendix A.6 need an entity selector at submarket level: the six `SBM`
charts `MER_SBM` Carga (Mercado de Energia), `GHID_SBM` Geração Hidráulica, `GTER_SBM` Geração
Térmica, `GUNS_SBM` Geração Não Simulada, `CMO_SBM` CMO and `VARMF_SBM` Volume Armazenado, plus the
single `SBP` chart `INT_SBP` Intercâmbios, whose entities are ordered submarket pairs. Everything
needed is already in place: ticket-018 built the per-chart entity lists and their Portuguese labels
from `Registries`, applying `submarkets.include_fictitious` to the `SBM` charts and keeping **every**
pair for `INT_SBP`; ticket-020 exported them; ticket-021 rendered one `<select class="entity-selector">`
per chart with the options already populated. What is missing is the one behaviour that makes them
live: a change on a selector must redraw that chart with the newly selected entity.

The three original key decisions and the three open questions resolve as follows.

- **The selector is single choice.** Multiple submarkets at once would mean one curve per
  (scenario, submarket) pair, and `planning-context.md` decision 5 fixes one curve per scenario. It
  also matches the legacy output, which wrote one file per submarket.
- **Interchange pairs are listed as ordered pairs, not netted.** `SE (SUDESTE) para S (SUL)` and
  `S (SUL) para SE (SUDESTE)` are separate entities because that is what `INT_SBP` contains; netting
  them into one signed series would be a derived view the spec does not request, and it would hide
  which direction the model actually scheduled.
- **The fictitious submarkets stay visible in the pair labels.** Ticket-018 requirement 7 keeps every
  `INT_SBP` pair while filtering the `SBM` charts to
  `visible_submarket_codes(..., include_fictitious=False)` by default. That asymmetry is deliberate:
  a fictitious submarket is noise on a load chart and load-bearing on an interchange chart.
- **Code 99 is labelled `IV (IV)`.** `SBM.parquet` gives it the short name `IV` and a null
  `nome_submercado`, ticket-015 falls the long name back to the short name, and `submarket_label`
  formats `f"{short} ({long})"`. The repetition is a known cosmetic wart of that fallback and is
  **settled upstream**: changing it would mean reopening ticket-015, whose behaviour is test-pinned.
  Code 11, whose long name `NOFICT1` is real, reads `FC (NOFICT1)`.
- **The selected entity is per chart, not shared across the group.** Entity coverage is per variable
  by master plan decision 16, so a group-wide selection could name an entity that one chart of the
  group does not have; and a group-wide "apply to all" control is unrequested scope. Each chart
  therefore keeps its own entry in `state.entities`, defaulting to the first entity of its own
  sorted list.
- **No net-exchange derived view.** The spec asks for `Intercâmbios`, the data gives directed pairs,
  and epic decision E3-1 keeps the JavaScript free of data shaping.

### Relation to Epic

The last ticket of the epic. It closes the interactive surface for every chart that has a selector,
and the mechanism it adds is exactly the one Epic 4 reuses: ticket-027 and ticket-029 render the
hydro and thermal charts through the same `setEntity`, and ticket-028 adds the name and code filters
that narrow the same `<option>` lists.

### Current State

`dashboard.js` exposes `payload`, `state`, `axisKey`, `buildTraces`, `buildLayout`, `renderChart`,
`renderActiveGroup`, `init`, `setMode`, `setDeck`, `setGroup` and `setValueMode`. `state.entities`
already maps every chart key with at least one entity to that chart first entity id, set by `init`
from the payload `entities` list, which arrives sorted by `EntityRef.sort_key` — the numeric code
tuple for submarkets and pairs. `buildTraces(chartKey)` already reads
`chart[KEYS.SERIES][state.entities[chartKey]][scenario][axisKey()]`, so **changing that one state
entry and re-rendering is the whole feature**. `renderChart(chartKey)` renders a single chart, and
`renderActiveGroup()` renders every unhidden one. The frozen `KEYS` object already declares
`entities` and `id`; this ticket needs no new key.

`builder.py` renders, per chart whose selector is not `NONE`, a `<label class="entity-label">` from
`SELECTOR_LABELS` (`SUBMARKET` maps to `Submercado`, `SUBMARKET_PAIR` to `Par de submercados`) and a
`<select class="entity-selector" id="entity-KEY">` holding one `<option value="ID">LABEL</option>`
per payload entity, in payload order. The six `SBM` sections and the one `SBP` section carry
`data-group="SBM"` and `data-group="SBP"` and are `hidden`, because `SIN` is the initially active
group; ticket-023 `setGroup` is what reveals them.

Measured on the `scenario_tree` fixture, whose generator defaults are
`submarket_codes=(1, 2, 11, 99)` and `pair_codes=((1, 2), (2, 1))`, with the repository
`submarkets.include_fictitious = false`: every `SBM` chart has exactly the two entities `1` labelled
`SE (SUDESTE)` and `2` labelled `S (SUL)`; `INT_SBP` has exactly the two entities `1-2` labelled
`SE (SUDESTE) para S (SUL)` and `2-1` labelled `S (SUL) para SE (SUDESTE)`. **The default
`pair_codes` contains no fictitious pair at all**, so any assertion about a fictitious pair must
regenerate the fixture with an explicit `pair_codes` — this is the exact vacuous-test trap recorded
in Epic 2 learnings section 7, which cost ticket-018 a correction.

## Specification

### Requirements

1. In `assets/dashboard.js`, add `setEntity(chartKey, entityId)`: it assigns
   `state.entities[chartKey] = entityId` and calls `renderChart(chartKey)`. It re-renders **only that
   chart**, not the whole group, because no other chart in the group is affected and a group re-render
   would redraw up to six figures for one selector change.
2. Register one delegated `change` listener on `<main id="charts">`, not one listener per `<select>`.
   It returns immediately unless `event.target` matches `.entity-selector`, then resolves the chart
   key with `event.target.closest("section.chart").dataset.chart` and calls `setEntity` with the
   element `value`. Delegation on the container is what lets Epic 4 add 165-option selectors without
   registering a listener per chart.
3. `setEntity` performs no validation of `entityId`. The only source is the `<option>` list that
   `builder.py` generated from the same payload the renderer reads, so a value that is not a key of
   `chart[KEYS.SERIES]` cannot arrive; adding a guard would be dead code.
4. Expose `setEntity` on `window.DessemDashboard` in addition to the twelve members present after
   ticket-025. Add no entry to the frozen `KEYS` object, because `entities` and `id` are already
   declared, and keep the file pure ASCII: every label an operator reads was rendered into the
   `<option>` elements by `builder.py`.
5. Keep the per-chart entity state. Do not introduce a group-level or document-level selected entity,
   and do not synchronise two selectors of the same group.
6. Add no net-exchange series, no signed aggregation of a pair with its reverse, no multi-select and
   no "apply to all charts" control.
7. Create `tests/test_charts_submarket.py`, the end-to-end verification of the submarket and
   interchange views. It must assert inside the relevant `<section class="chart">` slice, never over
   the whole document: `Geração Térmica` is the curated title of both `GTER_SIN` and `GTER_SBM`,
   `Geração Hidráulica` of both `GHID_SBM` and, as a registry long name, of `GHID_SIN`, and
   `Volume Armazenado` of both `VARMF_SIN` and `VARMF_SBM`, so an unscoped substring assertion is
   satisfied by the wrong section.
8. The fictitious-pair test must **regenerate** the fixture with an explicit
   `pair_codes=((1, 2), (2, 1), (1, 99))` through `make_sintese_dir`, because `build_scenario_tree`
   does not forward that parameter and the generator default contains no fictitious pair. An
   assertion written against the default tree would pass while proving nothing.
9. Change no Python module. This ticket touches one asset and one new test file.

### Inputs

At run time, the `change` events of the generated `<select class="entity-selector">` elements and the
entity lists already in the payload. At test time, the asset text, the fixture tree, and two
regenerated variants: one with a fictitious pair, one with `submarkets.include_fictitious = true`.

### Outputs and Behavior

Choosing a submarket redraws that chart for the selected submarket in every scenario; choosing an
interchange pair does the same for that directed pair. The choice survives a mode change, a deck
change and a level change, because `state.entities` is untouched by the other setters, and each chart
keeps its own choice. Nothing is written to disk.

### Error Handling

No new error path. A `change` event from an element that is not an `.entity-selector` is ignored,
which is the normal outcome of any other control inside `<main id="charts">`. A missing series for
the selected entity and scenario is already handled by `buildTraces`, which skips that scenario
trace, and the Portuguese explanation is the Avisos section ticket-021 renders. No `try`/`catch` is
added.

## Dependencies

- **Blocked By**: `ticket-025-render-sin-level-charts.md`
- **Blocks**: `ticket-027-render-hydro-plant-charts.md`

## Acceptance Criteria

- [ ] Given `assets/dashboard.js`, when its text is inspected, then `window.DessemDashboard`
      names `setEntity` in addition to the twelve members present after ticket-025; `setEntity`
      assigns `state.entities[chartKey]` and calls `renderChart(` while calling
      `renderActiveGroup(` nowhere inside itself; the asset contains `".entity-selector"` and
      `closest("section.chart")`; `text.isascii()` is `True`; and
      `.venv/bin/pytest tests/test_renderer_contract.py -q` still exits 0, proving no payload key
      literal was introduced outside the frozen `KEYS` object.
- [ ] Given the document built from the `scenario_tree` fixture with the repository `settings.json`,
      when the six `data-group="SBM"` section slices are inspected, then each carries
      `data-selector="SUBMARKET"`, a `<label class="entity-label">` whose text is `Submercado`, and a
      `<select class="entity-selector" id="entity-KEY">` holding exactly the two options
      `<option value="1">SE (SUDESTE)</option>` and `<option value="2">S (SUL)</option>`, with no
      option whose value is `11` or `99`.
- [ ] Given the same document, when the single `data-group="SBP"` section slice is inspected, then it
      carries `data-selector="SUBMARKET_PAIR"`, the heading `Intercâmbios`, a
      `<label class="entity-label">` whose text is `Par de submercados`, and
      `<select class="entity-selector" id="entity-INT_SBP">` holding exactly
      `<option value="1-2">SE (SUDESTE) para S (SUL)</option>` and
      `<option value="2-1">S (SUL) para SE (SUDESTE)</option>`, in that order.
- [ ] Given a tree regenerated with `make_sintese_dir(..., pair_codes=((1, 2), (2, 1), (1, 99)))`,
      when the document is built with `submarkets.include_fictitious = false`, then the
      `entity-INT_SBP` selector holds three options including
      `<option value="1-99">SE (SUDESTE) para IV (IV)</option>` while the `entity-CMO_SBM` selector
      still holds only the values `1` and `2`; and when the same tree is built with
      `submarkets.include_fictitious = true`, then `entity-CMO_SBM` holds four options including
      `<option value="11">FC (NOFICT1)</option>` and `<option value="99">IV (IV)</option>`.
- [ ] Given the fixture payload, when the `INT_SBP`, `CMO_SBM` and `MER_SBM` entries are read,
      then `payload["charts"]["INT_SBP"]["series"]` has one entry per pair
      entity, each with both scenarios and all three axis keys, and the `CMO_SBM` chart `unit` is
      `R$/MWh` while `MER_SBM` is `MW`; and
      `.venv/bin/pytest tests/test_charts_submarket.py tests/test_charts_sin.py
      tests/test_renderer_contract.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Add `setEntity` next to the other setters and the delegated `change` listener next to the
   ticket-023 and ticket-024 listeners. The JavaScript change is under ten lines.
2. Guard the listener with `if (!event.target.matches(".entity-selector")) return;` before touching
   `closest`, so an unrelated `change` inside `<main>` costs one comparison.
3. Write `tests/test_charts_submarket.py` around a small helper that splits the document into
   `<section class="chart" ...>` slices and returns them keyed by `data-chart`, then assert inside
   the slice. That helper is worth writing once here and reusing in Epic 4, which has 165-option
   selectors and the same collision risk.
4. Build the fictitious-pair variant by calling `make_sintese_dir` directly for two decks of two
   scenarios with `pair_codes=((1, 2), (2, 1), (1, 99))`, mirroring what `build_scenario_tree` does
   but passing the extra parameter.
5. Build the `include_fictitious = true` variant by writing a modified `settings.json` into
   `tmp_path`, not by mutating a loaded `Settings`: every settings dataclass is frozen.
6. Walk item 7 of `docs/checklist-manual-dashboard.md` by hand: switch to the Submercado level,
   change the submarket on two different charts and confirm each keeps its own choice, then switch to
   Intercâmbio and change the pair.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: `setEntity` plus one delegated
  listener)
- `tests/test_charts_submarket.py` (create)

### Patterns to Follow

- The delegated-listener pattern of tickets 023 and 024, now on `<main id="charts">`.
- The per-chart `state.entities` map `init` already established.
- The document-slicing assertion pattern introduced in `tests/test_charts_sin.py`.
- The `tmp_path/settings.json` copy pattern for a settings variant, since the dataclasses are frozen.

### Pitfalls to Avoid

- Do not assert a heading or a label over the whole document. `Geração Térmica`, `Geração Hidráulica`
  and `Volume Armazenado` each occur in more than one section, so an unscoped assertion is satisfied
  by the wrong chart — the exact incidental-match failure mode recorded in Epic 2 learnings
  section 7.
- Do not write the fictitious-pair test against the default fixture. `pair_codes` defaults to
  `((1, 2), (2, 1))`, which contains no fictitious code, so the assertion would pass vacuously.
- Do not filter fictitious submarkets out of `INT_SBP`, and do not add them to the `SBM` charts.
  Ticket-018 requirement 7 fixes both behaviours and `visible_submarket_codes` is the only switch.
- Do not rewrite the `IV (IV)` label. It is `submarket_label` documented fallback for the null
  `nome_submercado` of code 99, pinned by `tests/test_registries.py`; changing it here would
  contradict ticket-015 and break that test.
- Do not call `renderActiveGroup()` from `setEntity`. One selector change affects one chart, and a
  group re-render would redraw five charts that did not change.
- Do not register a listener per `<select>`. Epic 4 adds eight hydro selectors with 165 options each,
  and per-element listeners would scale with the catalogue instead of staying at one.
- Do not net the interchange pairs or add a multi-select. Both are unrequested, and netting would
  also need a sign convention nobody has specified.
- Do not synchronise the selectors of a group. Coverage is per variable by decision 16, so a shared
  submarket could name an entity a chart does not have.

### Out of Scope

- The hydro and thermal plant charts (tickets 027 and 029) and the plant name and code filters
  (ticket-028), even though they reuse `setEntity` unchanged.
- The `CUSTOS` and `TEMPO` bar charts (tickets 030 and 031).
- Any net-exchange, percentage or multi-entity view.
- Any change to `builder.py`, `payload.py`, `theme.py`, the HTML template or the CSS.
- Any change to `Registries.submarket_label` or to `visible_submarket_codes`.

## Testing Requirements

### Unit Tests

`tests/test_charts_submarket.py`:

- the five acceptance criteria;
- the set of `data-group="SBM"` chart keys in the document equals
  `{"MER_SBM", "GHID_SBM", "GTER_SBM", "GUNS_SBM", "CMO_SBM", "VARMF_SBM"}` and the
  `data-group="SBP"` set equals `{"INT_SBP"}`;
- all seven of those sections carry the `hidden` attribute on the default fixture, because `SIN` is
  the initially active group, so the level navigation is what reveals them;
- the option order inside each selector equals the payload `entities` order, which is
  `sort_key` order, so submarkets read 1 then 2 and pairs read `1-2` then `2-1`;
- `charts.disabled = ["INT_SBP"]`: the `SBP` group disappears from the level navigation and no
  `id="chart-INT_SBP"` section exists, proving the navigation is driven by the enabled catalogue;
- the payload series for one `SBM` chart and one `SBP` pair hold 50, 50 and 96 values per scenario;
- the asset assertions of the first acceptance criterion, each confirmed able to fail by temporarily
  breaking the asset before restoring it.

### Integration Tests

None automated, by epic decision E3-1. Item 7 of `docs/checklist-manual-dashboard.md` covers the
submarket and interchange-pair selectors in a browser, including that two charts of one group keep
independent choices; the run against real data, with its four real submarkets and twelve real pairs,
is ticket-034.

## Definition of Done

- [ ] Both files exist, one modified and one created, and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent, the Epic 3 gate.
- [ ] Exactly one delegated `change` listener serves every entity selector in the document.
- [ ] The fictitious-pair assertion runs against a regenerated fixture whose `pair_codes` includes a
      fictitious code, and the `SBM` charts still exclude codes 11 and 99 by default.
- [ ] Every heading and label assertion is scoped to a single chart section slice.
- [ ] `tests/test_builder.py`, `tests/test_renderer_contract.py`, `tests/test_renderer_controls.py`,
      `tests/test_renderer_value_mode.py` and `tests/test_charts_sin.py` all pass unchanged.

## Effort Estimate

**Points**: 2 · **Confidence**: Medium · **Agent time**: about 25 minutes. Re-estimated down from
the outline 3 points: the behaviour is one setter and one delegated listener, because ticket-018
already built the entity lists and their labels and ticket-021 already rendered the options. The
remaining weight is the two regenerated fixture variants, and confidence is Medium because the
selector interaction itself is verified by the manual checklist under epic decision E3-1.
