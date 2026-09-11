# ticket-029 Verify the thermal plant chart end to end

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-028.** Requirement 3 asserts the filter fragment
> ticket-028 renders and requirement 1 imports `tests/dashboard_document.py`, which ticket-027
> creates. This ticket writes **no source file at all**, so it can run in parallel with nothing —
> but it also blocks nothing except ticket-032, which needs the whole epic measured.

## Context

### Background

`GTER_UTE` Geração is the entire `UTE` level of master plan Appendix A.6: one chart, 89 thermal
plants in the real data, `MW`, with a thermal-plant selector. The outline anticipated "minimal new
code" from reusing the hydro machinery; the epic-03 learnings and the two preceding tickets make the
sharper statement true — **there is no new code at all.**

Everything the level needs is already shipped and generic over the aggregation level:
`charts/specs.py` declares `GTER_UTE` with `ChartGroup.UTE`, `AggregationLevel.UTE` and
`EntitySelector.THERMAL_PLANT`; `consolidate._entity_ref` labels a UTE entity with
`Registries.thermal_name(code)` and sorts by that name; `builder.GROUP_LABELS` maps `UTE` to
`Usinas termelétricas` and `SELECTOR_LABELS` maps `THERMAL_PLANT` to `Usina termelétrica`;
ticket-021 renders the section and its `<option>` list; ticket-023's `setGroup` reveals the level;
ticket-025's `buildLayout` labels the Y axis from the chart's own unit; ticket-026's `setEntity`
redraws it on a selector change; ticket-027's payload rules give it a plant list drawn from its own
file; ticket-028 renders its two filters from `PLANT_SELECTORS`, which holds both plant selector
values precisely so the thermal level needs no second implementation.

This ticket is therefore the **verification** ticket of the level: it proves, on the shipped
fixture, that the generic path really does cover `UTE` and did not quietly special-case `UHE`. That
is worth a ticket of its own rather than an appendix to ticket-027, because the two levels differ in
four ways that a `UHE`-only test suite cannot observe: a different group label, a different selector
label, a different registry accessor with a different name prefix (`TERMICA_` against `USINA_`), and
a chart whose curated title `Geração` **collides exactly** with `GHID_UHE`'s. If any assertion here
fails, the defect belongs to the ticket that owns the file, as an amendment there — not to a new
mechanism invented here.

The two original key decisions and the two open questions resolve as follows.

- **Nothing is generalised and nothing is duplicated**, because the machinery was already written
  level-agnostically. The one place that could have gone either way is ticket-028's filter fragment,
  and it is driven by a set of selector values rather than by a group name, so `UTE` is covered by
  construction.
- **No `limite_inferior` / `limite_superior` bands.** This is settled upstream, not decided here:
  ticket-018 stores only `valor`, so the payload carries no bounds at all, and ticket-025 already
  recorded the same refusal for the SIN charts. The outline is right that the thermal bounds are
  informative and finite in the real data, and that is exactly why adding them is a data-layer
  change — a new stored series per chart, roughly doubling the plant-level payload the epic is
  trying to keep small — and therefore a developer decision, not a test ticket's.
- **`CVU` stays excluded.** The master plan lists it under "never read" as a thermal cost *input*
  rather than a result, and enabling it would be a catalogue change (a new `ChartSpec`, a new source
  file, a new unit) that contradicts the plan's own scope statement.
- **The selector is not grouped by submarket.** `Registries.thermal` carries `submarket_code` for
  each of the 89 units, so `<optgroup>` grouping would be nearly free — which is the same argument
  E4-4 rejected for submarket filtering, and it is rejected here for the same reason: unrequested
  scope in an epic that already owns nine chart renderings, two filters and the size strategy.

### Relation to Epic

The closing ticket of the plant-level chain. It confirms that the UHE work of tickets 027 and 028
generalised rather than special-cased, and it is one of the two tickets ticket-032 waits for before
measuring the document, because the filter markup it asserts is part of what the measurement covers.

### Current State

On the `scenario_tree` fixture, whose generator default is `thermal_codes=(1, 2)` —
`build_scenario_tree` forwards **no** code set, overriding only `n_stages=50`,
`half_hour_stages=48`, `long_stage_hours=6.0` and `seed` — the document holds exactly one
`data-group="UTE"` section:

```text
<section class="chart" id="chart-GTER_UTE" data-chart="GTER_UTE" data-group="UTE"
         data-selector="THERMAL_PLANT" hidden>
  <h2>Geração</h2>
  <label class="entity-label">Usina termelétrica</label>
  <select class="entity-selector" id="entity-GTER_UTE">
    <option value="1">TERMICA_1</option><option value="2">TERMICA_2</option>
  </select>
  <div class="plant-filters">…ticket-028's two inputs and the empty-state paragraph…</div>
  <div class="plot" id="plot-GTER_UTE"></div>
</section>
```

`hidden` is present because `SIN` is the group of the first enabled spec. The payload entry carries
unit `MW`, curated title `Geração`, `subtitle` `None` on the unmodified fixture (its
`METADADOS_OPERACAO.parquet` writes `nome_longo_variavel` equal to the curated title for every key),
two entities `{"id": "1", "label": "TERMICA_1"}` and `{"id": "2", "label": "TERMICA_2"}` in
`sort_key` order, and series arrays of 50, 50 and 96 values for `03/03/2024`, `04/03/2024` and
`encadeado` in both `caso_a` and `caso_b`. The level-navigation bar holds six buttons, of which the
fifth reads `Usinas termelétricas`.

`Geração` is also the curated title of `GHID_UHE`, and in the real data it is additionally the
registry long name of several variables. `tests/test_payload.py` already deletes
`caso_b/deck_dois/sintese/GTER_UTE.parquet` in one test, which proves the missing-file degradation
at payload level but asserts nothing about the document.

## Specification

### Requirements

1. Create `tests/test_charts_thermal.py`, importing the document-slicing helpers from
   `tests/dashboard_document.py` (ticket-027) and following the settings-copy-in-`tmp_path` pattern
   of `tests/test_builder.py`. Every heading assertion must be scoped to the single
   `data-group="UTE"` section slice, because `Geração` is the exact curated title of `GHID_UHE` too
   and an unscoped substring assertion would be satisfied by the wrong section — the incidental-match
   failure mode recorded in Epic 2 learnings section 7.
2. Assert the document facts of the Current State: one `UTE` section, its opening-tag attributes, its
   `hidden` attribute, its single `<h2>` reading `Geração`, the absence of a
   `<p class="chart-subtitle">`, the `Usina termelétrica` entity label, the exact two-option list in
   `sort_key` order, and the `Usinas termelétricas` button in the level navigation.
3. Assert that the `UTE` section carries ticket-028's filter fragment — both `plant-filter` inputs
   with their `data-filter` roles and ids, and the hidden empty-state paragraph — so a fragment
   rendered for `HYDRO_PLANT` only would fail here rather than in a browser.
4. Assert the payload facts of the Current State: unit `MW`, the two entities, and the three axis
   lengths per scenario.
5. Prove the option list follows the file rather than the registry, by regenerating a tree through
   `make_sintese_dir` with `thermal_codes=(1, 2, 3)`: the selector then holds three options including
   `<option value="3">TERMICA_3</option>`. `build_scenario_tree` does not forward `thermal_codes`, so
   this assertion is unsatisfiable on the shared fixture and must build its own tree — the exact
   trap that cost ticket-018 a correction and ticket-026 an explicit requirement.
6. Prove the level is registry-driven, by building with `charts.disabled = ["GTER_UTE"]`: the
   document then contains no `id="chart-GTER_UTE"`, no `data-group="UTE"` section and no
   `Usinas termelétricas` button, while the `UHE` level is untouched.
7. Change **no** source file. Not `builder.py`, not `payload.py`, not `theme.py`, not any packaged
   asset, not any epic-02 module, and not any existing test module. The only file this ticket adds or
   modifies is `tests/test_charts_thermal.py`. If an assertion of requirements 2 to 6 cannot be made
   to pass, stop and report it: the fix is an amendment to ticket-027 or ticket-028, which own those
   files, and inventing a thermal-specific code path here would hide a defect in the generic one.

### Inputs

The `scenario_tree` fixture, one tree regenerated through `make_sintese_dir` with
`thermal_codes=(1, 2, 3)`, the repository `settings.json` copied into `tmp_path`, and one settings
variant with `charts.disabled = ["GTER_UTE"]`.

### Outputs and Behavior

No runtime behaviour changes. The suite gains a module that fails if the `UTE` level ever loses its
section, its label, its selector, its filters, its unit or its registry-driven navigation entry.
Nothing is written outside `tmp_path`.

### Error Handling

No error path of its own. The one degradation the level can show — `GTER_UTE.parquet` missing for a
(scenario, deck) — is already covered at payload level by
`test_build_payload_missing_series_file_omits_only_that_scenario_and_deck` and at document level by
the Avisos section ticket-021 renders; this module asserts neither again.

## Dependencies

- **Blocked By**: `ticket-028-implement-name-and-code-filters.md`
- **Blocks**: `ticket-032-enforce-output-size-strategy.md`

## Acceptance Criteria

- [ ] Given the document built from the `scenario_tree` fixture with the repository `settings.json`,
      when the section slices are filtered to `data-group="UTE"`, then exactly one slice is returned;
      its opening tag carries `data-chart="GTER_UTE"`, `data-selector="THERMAL_PLANT"` and `hidden`;
      it holds exactly one `<h2>` whose text is `Geração`, no `<p class="chart-subtitle">`, a
      `<label class="entity-label">` reading `Usina termelétrica`, and
      `<select class="entity-selector" id="entity-GTER_UTE">` holding exactly
      `<option value="1">TERMICA_1</option>` then `<option value="2">TERMICA_2</option>`.
- [ ] Given that same slice, when the filter markup is inspected, then it contains exactly one
      `<div class="plant-filters">` with `id="filter-name-GTER_UTE"` carrying `data-filter="name"`
      and `id="filter-code-GTER_UTE"` carrying `data-filter="code"`, both with
      `class="plant-filter"`, and one `<p class="filter-empty" hidden>`; and the `<div class="plot"
      id="plot-GTER_UTE">` appears after that fragment inside the slice.
- [ ] Given the payload built from the same fixture, when the `GTER_UTE` entry is read, then its
      `unit` is `MW`, its `title` is `Geração`, its `subtitle` is `None`, its `entities` equal
      `[{"id": "1", "label": "TERMICA_1"}, {"id": "2", "label": "TERMICA_2"}]`, its `scalars` is
      empty, and its series arrays hold 50, 50 and 96 values for `03/03/2024`, `04/03/2024` and
      `encadeado` in both `caso_a` and `caso_b`.
- [ ] Given a tree built by calling `make_sintese_dir` directly for both decks of both scenarios with
      `thermal_codes=(1, 2, 3)`, when the document is built, then `entity-GTER_UTE` holds three
      options ending with `<option value="3">TERMICA_3</option>`; and given the shared fixture built
      with `charts.disabled = ["GTER_UTE"]`, then the document contains no `id="chart-GTER_UTE"`, no
      `data-group="UTE"` section and no `Usinas termelétricas` button, while the eight
      `data-group="UHE"` sections are still present.
- [ ] Given the repository working tree after this ticket, when the added and modified files are
      listed, then `tests/test_charts_thermal.py` is the only one; and
      `.venv/bin/pytest tests/test_charts_thermal.py tests/test_charts_hydro.py
      tests/test_charts_filters.py tests/test_builder.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Copy the module skeleton of `tests/test_charts_hydro.py`: the same imports, the same
   `_build_settings` / `_build_data` helpers, the same `tests/dashboard_document.py` import. Do not
   re-derive the slicing helpers.
2. Write the four document criteria first, always through `sections_by_group(document, "UTE")` and
   then indexing the single slice, so a second `UTE` section would fail on the length rather than be
   silently ignored by a `next(...)`.
3. Build the three-plant tree the way ticket-026 built its fictitious-pair tree: call
   `make_sintese_dir` four times — two scenarios times two decks — with the same `n_stages=50`,
   `half_hour_stages=48`, `long_stage_hours=6.0` and distinct seeds `build_scenario_tree` uses, plus
   `thermal_codes=(1, 2, 3)`.
4. Build the disabled variant by writing a modified `settings.json` into `tmp_path`, never by
   mutating a loaded `Settings`: every settings dataclass is frozen.
5. Prove the scoping is load-bearing rather than stylistic: assert that the unscoped document
   contains `<h2>Geração</h2>` **twice** — once for `GHID_UHE` and once for `GTER_UTE` — so the
   reason the other assertions are scoped is itself pinned. If that count ever becomes one, either a
   chart disappeared or a title changed, and both are worth failing on.
6. Prove each document assertion can fail by mutating a copy of the document text: remove
   `data-filter="code"`, change `Usina termelétrica` to `Usina hidrelétrica`, drop the third option
   from the regenerated tree's expectation. Restore each. Specialist-initiated break-testing is the
   norm in this plan since Epic 1 shipped a genuinely vacuous test.
7. Walk the ticket-028 checklist steps once on the `Usinas termelétricas` level rather than the
   hydro one, confirming the console is clean and that the thermal filters behave as the hydro ones
   do. Add no checklist step: ticket-028's section is written to cover the plant level as a whole.

### Key Files to Create/Modify

- `tests/test_charts_thermal.py` (create)

### Patterns to Follow

- The module structure and helpers of `tests/test_charts_hydro.py`, through
  `tests/dashboard_document.py`.
- ticket-026's regenerate-the-fixture pattern for a parameter `build_scenario_tree` does not forward.
- The `tmp_path/settings.json` copy pattern for a settings variant, since the dataclasses are frozen.
- English test names and comments; the Portuguese strings appear only as asserted literals.

### Pitfalls to Avoid

- Do not assert `Geração` over the whole document. It is the curated title of `GHID_UHE` as well, so
  an unscoped assertion passes even if the thermal heading is missing entirely — and the thermal
  section is the one this module exists to check.
- Do not write the three-plant assertion against the shared fixture. `thermal_codes` defaults to
  `(1, 2)` and `build_scenario_tree` does not forward it, so the assertion would pass while proving
  nothing about where the option list comes from.
- Do not conflate the generator defaults with the `scenario_tree` overrides. The defaults are
  `n_stages=6, half_hour_stages=4, hydro_codes=(1,2,3), thermal_codes=(1,2)`; the fixture overrides
  the stage parameters only. Conflating the two produced a spec defect in Epic 2.
- Do not add a source file, a helper module or a fixture. The moment this ticket writes to `src/`, it
  has stopped verifying the generic path and started special-casing the thermal one.
- Do not add `limite_inferior` / `limite_superior` bands, `CVU`, or an `<optgroup>` selector. The
  first needs the data layer reopened, the second a catalogue entry the plan excludes, the third is
  the unrequested scope E4-4 rejected.
- Do not assert a member count on `window.DessemDashboard` or a chart count on the document. Presence
  assertions only: five tickets grew that object in sequence and a count assertion would have broken
  each successor.
- Do not re-assert the missing-file degradation. `tests/test_payload.py` already owns it, and a
  second copy would have to be updated twice.

### Out of Scope

- Any source change whatsoever, in particular to `builder.py`, `payload.py` or the packaged assets.
- The hydro payload rules and the shared slicing helpers (ticket-027) and the filter implementation
  (ticket-028), both of which this ticket only reads.
- The `CUSTOS` and `TEMPO` bar charts (tickets 030 and 031).
- The document size measurement and its warning (ticket-032).
- Confidence bands, `CVU`, submarket grouping or filtering, and any new checklist step.

## Testing Requirements

### Unit Tests

`tests/test_charts_thermal.py`:

- the five acceptance criteria;
- the unscoped document contains `<h2>Geração</h2>` exactly twice, pinning the collision that makes
  the scoping necessary;
- the `UTE` section's inner order is heading, entity label, entity select, filter fragment, plot div,
  asserted by index within the slice;
- `data-selector="THERMAL_PLANT"` appears on exactly one section of the whole document, and
  `data-selector="HYDRO_PLANT"` on exactly eight, so a selector wired to the wrong level — or a
  thermal chart silently rendered with the hydro label — fails here rather than in a browser;
- every `GTER_UTE` value is either `None` or equal to itself rounded to two decimals;
- the non-vacuity mutations of Suggested Approach step 6, each confirmed to fail before restoration.

### Integration Tests

None automated, by epic decision E3-1. The rendered thermal view and its filters are covered by
walking ticket-028's checklist steps on the `Usinas termelétricas` level; the run against the real
89-plant registry is ticket-034.

## Definition of Done

- [ ] `tests/test_charts_thermal.py` exists, is the only added or modified file, and all five
      acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] Every heading assertion in the module is scoped to the `data-group="UTE"` slice, and the
      `Geração` collision is pinned by its own count assertion.
- [ ] The three-plant assertion runs against a tree regenerated with `thermal_codes=(1, 2, 3)`.
- [ ] No file under `src/` and no existing test module was touched; if an assertion could not pass,
      the blocking defect was reported against ticket-027 or ticket-028 instead of worked around.
- [ ] The whole suite passes: every Epic 1 to Epic 3 module plus `tests/test_charts_hydro.py` and
      `tests/test_charts_filters.py`.

## Effort Estimate

**Points**: 1 · **Confidence**: High · **Agent time**: about 20 minutes. Re-estimated down from the
outline's 2 points, and the reason is the finding rather than optimism: the outline expected to
"reuse the plant selector and the filters" and found, once the epic-03 learnings landed, that every
mechanism the `UTE` level needs is level-agnostic and already shipped, so the deliverable is one test
module of about twelve tests and no source change. Confidence is High because every asserted fact is
measured on the fixture and nothing here depends on a browser.
