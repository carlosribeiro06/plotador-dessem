# ticket-028 Implement the name and code filters

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-027 and strictly before ticket-029.** It asserts inside
> `<section class="chart">` slices through `tests/dashboard_document.py`, which ticket-027 creates,
> and ticket-029 asserts that the thermal section carries the filter fragment this ticket renders.
> It must also not run in parallel with ticket-032: both modify `dashboard/builder.py`.

## Context

### Background

Spec section 3, recorded as `planning-context.md` decision 9 and master plan decision 9, requires the
plant-level views to expose **two independent, combinable text filters** — one over the plant name
(`usina`) and one over the plant code (`codigo_usina`) — as a BI-style incremental search over the
plant registry embedded in the HTML. It is the last unimplemented item of the spec's interactive
surface and the one success metric of the master plan that no other ticket can satisfy: "the name and
code filters locate a plant independently and in combination".

Everything the filters operate on already exists. ticket-021 renders, for every chart whose selector
is not `NONE`, a `<select class="entity-selector" id="entity-KEY">` holding one
`<option value="CODE">NAME</option>` per payload entity; ticket-027 made those option lists carry
exactly the plants each variable covers. The code is therefore already in the document as
`option.value` — `str(codigo_usina)` is the fixed entity-id format of epic-02 — and the name is
already in `option.textContent`. **Both filters are pure DOM work over data the builder has already
rendered**, which is why this ticket reads no payload key and adds no `KEYS` entry.

Two constraints shape the design more than any preference would.

- **The asset must stay pure ASCII.** `tests/test_renderer_contract.py`,
  `tests/test_renderer_controls.py`, `tests/test_charts_sin.py` and
  `tests/test_charts_submarket.py` each assert `text.isascii() is True`, and the reason is the one
  ticket-025 recorded: operator-visible text belongs in Python, so that `payload.labels` and the HTML
  are the only places an accent can appear. `Filtrar por código` and `Nenhuma usina corresponde ao
  filtro` therefore ship from `builder.py` as rendered markup, and the JavaScript only toggles a
  `hidden` property on an element whose text it never reads.
- **Options are hidden, never removed.** `option.hidden = true` keeps the element, its `value` and
  the `<select>`'s current selection intact, so clearing the filter restores the list with one pass
  and no rebuild. Removing and recreating options would lose the selection, recreate 165 elements per
  keystroke, and break ticket-026's exact-option assertions if the markup changed.

The three original key decisions and the three open questions resolve as follows.

- **The name filter is case-insensitive and accent-insensitive substring matching.** The registry
  writes plant names unaccented and uppercase (`SAO SIMAO`, `S.SIMAO`), while an operator types
  whatever their keyboard gives them; prefix matching would fail `SIMAO` against `SAO SIMAO` and
  exact matching defeats incremental search outright. Both needle and haystack are normalised with
  `normalize("NFD")`, the combining-mark range stripped, and `toUpperCase()` applied, so `são`
  matches `SAO` and `sao` matches `SÃO` if a future registry carries accents.
- **The code filter is substring matching over `option.value`.** Typing `6` narrows to 6, 16 and 66,
  which is what incremental search means; exact matching would show nothing until the last digit and
  prefix matching would arbitrarily privilege the leading digits of a number that carries no
  hierarchy. It shares the same normalisation path, which costs nothing on digits.
- **Both fields combine with AND.** Two independent filters that intersect is the BI convention and
  the only reading of "independent and combinable" that adds information; OR would widen the list as
  the operator types more.
- **The filter narrows the option list and the selection follows it.** One rule covers the outline's
  "does it directly select when exactly one plant matches" question without a special case: whenever
  at least one option matches and the currently selected option is **not** among the matches, the
  `<select>` moves to the first match and `setEntity` redraws that chart. With one match that is the
  BI behaviour the outline asked about; with several it guarantees the visible selection is always a
  visible option; with the current selection still matching, nothing is touched and nothing is
  redrawn.
- **A no-match state shows a Portuguese message and leaves the chart alone.** Every option stays
  hidden, the selection and the drawn figure are untouched, and the pre-rendered
  `<p class="filter-empty">` becomes visible. Blanking a chart on a typo destroys the context the
  operator was reading, and re-showing all 165 options would silently contradict the filter they
  just typed.
- **The filters serve the thermal level too**, because spec section 3 names usinas térmicas and
  hidrelétricas alike. The fragment is rendered for both plant selector values from one set, so the
  UTE level needs no second implementation — ticket-029 verifies it rather than building it.

### Relation to Epic

The middle ticket of the plant-level chain and the only one of the three that writes source code.
ticket-027 populated the option lists it narrows; ticket-029 verifies the same mechanism on the
thermal level and adds no code of its own. It also owns the `docs/checklist-manual-dashboard.md`
Epic 4 placeholder, which ticket-022 wrote and explicitly reserved for this ticket, because option
hiding inside a native `<select>` is the one behaviour in this epic that no Python assertion can
observe.

### Current State

`builder._chart_sections` emits, per enabled spec and in `enabled_specs` order:

```text
<section class="chart" id="chart-KEY" data-chart="KEY" data-group="G" data-selector="S"[ hidden]>
  <h2>TITLE</h2>[<p class="chart-subtitle">SUBTITLE</p>][LABEL + SELECT]
  <div class="plot" id="plot-KEY"></div>
</section>
```

`LABEL + SELECT` comes from `_entity_selector_fragment(spec, entities)` and is emitted only when
`spec.selector.value != EntitySelector.NONE.value`; `SELECTOR_LABELS` already maps `HYDRO_PLANT` to
`Usina hidrelétrica` and `THERMAL_PLANT` to `Usina termelétrica`. Nine sections carry a plant
selector on the default catalogue: the eight `UHE` charts and `GTER_UTE`.

`dashboard.js` exposes thirteen members after ticket-026 and holds exactly one delegated `change`
listener on `#charts`, which filters on `.entity-selector`, resolves the chart with
`closest("section.chart").dataset.chart` and calls `setEntity(chartKey, value)` — which re-renders
**only that chart**. `state.entities` is per chart and deliberately unsynchronised. `syncPressed` is
internal, generic over a container and a `data-` attribute, and reused by three toggles; it is the
precedent for any fourth control, though this ticket needs no pressed state.

Pinned asset invariants this ticket must not break: `text.count("Object.freeze({") == 1` — so no
second frozen object; `text.count("window.DessemDashboard") == 1`; `text.isascii() is True`; every
`payload[` followed by `KEYS.`; no `KEYS` value used as a raw index; none of `fetch(`,
`XMLHttpRequest`, `import(`, `eval(`, `document.write`, `http://`, `https://`, `location.hash`,
`pushState`, `popstate`, `annotations`, `rangemode`, `hovertemplate`, `newPlot`;
`text.count("Plotly.react(") == 1`.

One further assertion is being added at the epic-03 boundary and must be assumed in force when this
ticket is dispatched: **dot access on a payload-derived object is forbidden**, so a chart entry's
field is read as `chart[KEYS.UNIT]` and never as `chart.unit`. This ticket satisfies it trivially,
because it reads no payload field at all — the plant name and the plant code are already in the
document as an option's text and its `value`.

`dashboard.css` contains **no colour literal** — `tests/test_builder.py` asserts
`re.search(r"#[0-9A-Fa-f]{3,8}\b", css_text) is None` — and reaches every value through a
`var(--ons-*)` custom property. `theme.css_root_block()` emits exactly eight properties, in this
order: `--ons-green`, `--ons-gray`, `--ons-white`, `--ons-grid`, `--ons-font-family`,
`--ons-font-size`, `--ons-logo-width`, `--ons-logo-padding`. A `var()` naming a ninth property
renders unstyled and silently: the correspondence is documented in the epic-03 learnings but only
half of it is automated today.

`assets/dashboard.html` is a `string.Template` with exactly fifteen identifiers, asserted as a set by
`test_dashboard_html_asset_is_a_valid_template_with_the_fifteen_documented_identifiers`. The filter
markup therefore ships inside `$chart_sections`, never as a sixteenth placeholder.

`docs/checklist-manual-dashboard.md` holds nineteen numbered steps in seven sections, followed by a
section reading `## Epic 4 placeholder — plant name and code filters (ticket-028)` whose body says
`**Not yet written.**` and names this ticket as its owner.
`tests/test_renderer_contract.py` asserts the file has at least one numbered step, mentions
`console`, `file://` and the exact footer text.

## Specification

### Requirements

1. In `builder.py`, declare a module-level `PLANT_SELECTORS: Final[frozenset[str]]` holding the two
   plant `EntitySelector` values, and render a filter fragment for exactly the charts whose selector
   is in that set, immediately after the entity selector fragment and before the plot `<div>`. A
   future plant level joins by adding one member rather than by editing a condition.
2. The fragment is exactly this markup, with `KEY` the chart key:

   ```html
   <div class="plant-filters"><label class="filter-label" for="filter-name-KEY">Nome</label>
   <input type="text" class="plant-filter" data-filter="name" id="filter-name-KEY"
    placeholder="Filtrar por nome"><label class="filter-label" for="filter-code-KEY">Código</label>
   <input type="text" class="plant-filter" data-filter="code" id="filter-code-KEY"
    placeholder="Filtrar por código"><p class="filter-empty" hidden>Nenhuma usina corresponde ao
    filtro</p></div>
   ```

   emitted as one line with no added whitespace, following `_entity_selector_fragment`'s style. The
   two inputs share the class `plant-filter` so one delegated listener serves both, and differ by
   `data-filter`, so the handler reads them by role and not by document order. Every operator-visible
   string is here, in Portuguese, and none of them may appear in the JavaScript.
3. In `dashboard.js`, add `applyPlantFilter(chartKey)`. It resolves the section by chart key, reads
   the two inputs by their `data-filter` role, normalises each needle, and for every `<option>` of
   that section's `.entity-selector` sets `option.hidden` to the negation of
   `nameMatches && codeMatches`. An empty needle matches every option, so an empty pair reveals the
   whole list.
4. Normalisation is one helper applied identically to needle and haystack:
   `normalize("NFD")`, then `replace(/[\u0300-\u036f]/g, "")`, then `toUpperCase()`. Writing that
   range with literal combining characters instead of the two escapes would put non-ASCII bytes
   in the asset and break the four `text.isascii()` assertions requirement 7 preserves. The name
   is matched against the option's text, the code against the option's `value`, both with
   `indexOf(...) !== -1`.
5. After the pass, `applyPlantFilter` updates the state in this order: when at least one option
   matched and the `<select>`'s current value is not among the matches, assign the first match to the
   `<select>` value and call `setEntity(chartKey, value)` — the single re-render path, which redraws
   that chart only; when no option matched, change neither the value nor the figure. Then set the
   section's `<p class="filter-empty">` `hidden` property to whether at least one option matched.
   `setEntity` is called at most once per invocation.
6. Register exactly one delegated `input` listener on `<main id="charts">`, next to ticket-026's
   `change` listener. It returns immediately unless `event.target.matches(".plant-filter")`, then
   resolves the chart with `closest("section.chart").dataset.chart` and calls `applyPlantFilter`.
   One listener, not one per input: the nine plant charts hold eighteen inputs and the real data
   gives each of them a 165-option list.
7. Expose `applyPlantFilter` on `window.DessemDashboard` in addition to the thirteen members present
   after ticket-026. Add no `KEYS` entry — this ticket reads no payload field — add no second
   `Object.freeze({`, and keep `text.isascii()` true.
8. In `dashboard.css`, style `.plant-filters` as an inline-flex row with a gap, `.filter-label` with
   a right margin, `input.plant-filter` with the same border, radius and padding the existing
   controls use, and `.filter-empty` as italic text; add `option[hidden] { display: none; }` so a
   hidden option is also hidden where the attribute alone is not honoured, and
   `.filter-empty[hidden] { display: none; }` so the message obeys its own attribute. Every colour,
   font and size value must come from one of the eight properties `theme.css_root_block()` emits, and
   no hex literal and no `@import` may appear.
9. Replace the `## Epic 4 placeholder` section of `docs/checklist-manual-dashboard.md` with a real
   section titled for the plant filters, holding numbered steps continuing from 19 — navigate to
   `Usinas hidrelétricas`, type a partial name and confirm the list narrows and the chart follows,
   type a code and confirm the same, combine both, type a non-matching string and confirm the
   Portuguese message appears while the chart keeps its previous curve, clear both fields and confirm
   the full list returns, then filter two charts of the same level differently and confirm each keeps
   its own selection. State in the section that option hiding inside a native `<select>` is
   browser-dependent and is the reason these steps are manual.
10. Create `tests/test_charts_filters.py`, importing the slicing helpers from
    `tests/dashboard_document.py`. It must assert the fragment on the nine plant sections **and its
    absence** on every other section, the asset invariants, the CSS rules, the checklist replacement,
    and the non-vacuity of each text assertion.
11. Change no other file. No `payload.py`, no `theme.py`, no `consolidate.py`, no
    `assets/dashboard.html`, no existing test module, and no `<option>` markup: ticket-026 asserts
    the exact option string of `entity-CMO_SBM` and ticket-027 the exact options of `entity-VARMF_UHE`
    and `entity-GHID_UHE`.
12. Add no filter by submarket or equivalent reservoir, no `<optgroup>`, no multi-select, no
    "apply to all charts" control, no debounce timer and no URL-hash state. E4-4 rules the first two
    out explicitly; the rest are unrequested.

### Inputs

At run time, `input` events from the eighteen rendered text inputs, and the `<option>` elements
`builder.py` rendered from the payload entity lists. At test time, the `dashboard.js` and
`dashboard.css` asset text, `theme.css_root_block()`, the checklist file, and documents built from
the `scenario_tree` fixture.

### Outputs and Behavior

Typing in a plant chart's name or code field narrows that chart's dropdown as each character lands,
combining the two fields with AND; the drawn figure follows the filter whenever the current selection
stops matching, and stays put when it still matches or when nothing matches. A non-matching filter
shows `Nenhuma usina corresponde ao filtro` under the controls of that chart alone. Clearing both
fields restores the full list. Two charts of the same level filter and select independently, because
both the inputs and `state.entities` are per chart. Nothing is written to disk and no payload value
is read.

### Error Handling

No new error path and no `try`/`catch`. An `input` event from an element that is not a
`.plant-filter` — there is none today inside `<main id="charts">` — costs one `matches` call and
returns. A chart whose option list is empty, which ticket-027's degradation leaves possible when a
file is missing from every deck, matches nothing: the message shows, no `setEntity` call is made, and
the empty plot stays empty. An operator typing a regular-expression metacharacter is harmless,
because matching is `indexOf` over normalised strings and never a constructed pattern.

## Dependencies

- **Blocked By**: `ticket-027-render-hydro-plant-charts.md`
- **Blocks**: `ticket-029-render-thermal-plant-charts.md`

## Acceptance Criteria

- [ ] Given the document built from the `scenario_tree` fixture with the repository `settings.json`,
      when the section slices are inspected, then each of the nine slices whose `data-selector` is
      `HYDRO_PLANT` or `THERMAL_PLANT` contains exactly one `<div class="plant-filters">` holding
      `id="filter-name-KEY"` with `data-filter="name"` and `placeholder="Filtrar por nome"`,
      `id="filter-code-KEY"` with `data-filter="code"` and `placeholder="Filtrar por código"`, both
      carrying `class="plant-filter"`, and one `<p class="filter-empty" hidden>` reading
      `Nenhuma usina corresponde ao filtro`; and no slice whose `data-selector` is `NONE`,
      `SUBMARKET` or `SUBMARKET_PAIR` contains the string `plant-filter`.
- [ ] Given the `dashboard.js` asset text, when it is inspected, then `window.DessemDashboard` names
      `applyPlantFilter` in addition to the thirteen members present after ticket-026; the asset
      contains `".plant-filter"`, `addEventListener("input"`, `closest("section.chart")`,
      `normalize("NFD")`, `toUpperCase()` and the escaped combining-mark range
      `[\u0300-\u036f]`; `text.count("Object.freeze({")` is 1;
      `text.isascii()` is `True`.
- [ ] Given the same text, when `applyPlantFilter`'s body is isolated, then it assigns
      `option.hidden`, calls `setEntity(` exactly once, assigns the `hidden` property of the
      `filter-empty` element, and the whole asset contains none of `innerHTML`, `createElement`,
      `removeChild`, `new RegExp`, `setTimeout` or `Filtrar` or `Nenhuma`, proving options are hidden
      rather than rebuilt and that no operator-visible string leaked out of `builder.py`.
- [ ] Given `dashboard.css`, when it is inspected, then it contains the selectors `.plant-filters`,
      `.filter-label`, `input.plant-filter`, `.filter-empty` and `option[hidden]`, no match for
      `#[0-9A-Fa-f]{3,8}\b` and no `@import`; and the set of custom-property names it reads through
      `var(--...)` is a subset of the eight names `theme.css_root_block()` emits, so no rule can
      depend on a property the theme does not declare.
- [ ] Given `docs/checklist-manual-dashboard.md`, when it is read, then the string `Not yet written`
      is absent, one numbered step names `Filtrar por nome`, another names `Filtrar por código`,
      another names `Nenhuma usina corresponde ao filtro`, and another covers two charts of the same
      level filtered independently; and `.venv/bin/pytest tests/test_charts_filters.py
      tests/test_charts_hydro.py tests/test_builder.py tests/test_charts_submarket.py
      tests/test_renderer_contract.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Start in `builder.py`: add `PLANT_SELECTORS` next to `SELECTOR_LABELS`, write
   `_plant_filter_fragment(spec)` next to `_entity_selector_fragment`, and append its result inside
   `_chart_sections` between `selector_html` and the plot `<div>`. The fragment's text is constant,
   so `html.escape` is unnecessary — but keep the f-string shape of its sibling so the two read alike.
2. Write the JavaScript as one helper plus one function plus one listener, about thirty lines.
   Normalise once into a local before the option loop; do not normalise the needle inside the loop.
3. Read the two inputs with one `querySelector` each on the section, keyed by
   `[data-filter="name"]` and `[data-filter="code"]`. Do not index a `querySelectorAll` result by
   position: the handler must stay correct if the fragment's order ever changes.
4. Collect the matching options into an array in the same pass that sets `hidden`, so the
   first-match and the empty-state decisions both read one already-computed list instead of querying
   the DOM twice.
5. Add the CSS last, reusing the exact border, radius and padding values of the existing
   `#level-nav button` rule so the inputs sit beside the buttons without a visual seam.
6. Replace the checklist placeholder section wholesale — heading included — keeping the file's
   existing "**Expected result:**" convention at the end of the section, and continue the numbering
   from 19 without renumbering anything above it.
7. Prove each text assertion can fail before returning: insert `Filtrar` into a copy of the asset and
   confirm criterion 3 fails; remove `data-filter="code"` from a copy of the document and confirm
   criterion 1 fails; add `var(--ons-missing)` to a copy of the CSS and confirm criterion 4 fails;
   restore each. The regex triad of ticket-022 detected the naive violation and missed every reworded
   one, which is why these mutations are required rather than suggested.
8. Walk the new checklist steps by hand in a browser, with the console open. This is the only
   verification of the filtering behaviour itself under epic decision E3-1, and the first step of the
   checklist — console clean on load — is what catches a stray brace that would otherwise ship a
   4.5 MB file rendering nothing.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/builder.py` (modify: `PLANT_SELECTORS`, the fragment, one call)
- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: one helper, `applyPlantFilter`, one
  delegated listener, one exposed member)
- `src/dessem_dashboard/dashboard/assets/dashboard.css` (modify: five rules)
- `docs/checklist-manual-dashboard.md` (modify: replace the Epic 4 placeholder section)
- `tests/test_charts_filters.py` (create)

### Patterns to Follow

- `_entity_selector_fragment`'s shape for `_plant_filter_fragment`: one function, one f-string, no
  branching, called from `_chart_sections`.
- ticket-026's delegated-listener pattern on `<main id="charts">`, with the cheap `matches` guard
  before any `closest` call.
- ticket-025's rule that every operator-visible string enters the browser from Python, which here is
  what keeps the asset ASCII.
- `setMode`'s property-not-attribute idiom (`element.disabled = ...`) for every `hidden` toggle:
  `option.hidden = ...` and `paragraph.hidden = ...`, never `setAttribute`/`removeAttribute`.
- The document-slicing assertion pattern, through `tests/dashboard_document.py`.

### Pitfalls to Avoid

- Do not write a Portuguese string into `dashboard.js`. `Código` alone breaks four `isascii`
  assertions, and the unaccented ones would still put operator text in the wrong layer.
- Do not add a second `Object.freeze({`. `tests/test_renderer_contract.py` counts it at exactly one,
  so a frozen filter-role map is not available; use plain string comparisons.
- Do not add a sixteenth `string.Template` placeholder to `dashboard.html`. The identifier set is
  asserted exactly, and the fragment belongs inside `$chart_sections`.
- Do not change the `<option>` markup. ticket-026 asserts the exact option string of
  `entity-CMO_SBM`, ticket-027 those of `entity-VARMF_UHE` and `entity-GHID_UHE`, and a
  server-side `hidden` attribute would break both while also freezing the filter into the artefact.
- Do not remove or recreate options. A rebuild per keystroke loses the selection, and with 165 real
  options it also makes the filter feel broken.
- Do not call `renderActiveGroup()`. One filter narrows one chart; ticket-026 already recorded why
  the group re-render is the wrong granularity, and here it would redraw up to eight 165-plant
  figures per keystroke.
- Do not add a debounce timer. `setTimeout` is measurable in the asset, the work is one pass over at
  most 165 options, and a delay would make an incremental search feel laggy for no gain.
- Do not construct a regular expression from operator input. `new RegExp(needle)` turns a typed `(`
  into a syntax error; `indexOf` over normalised strings cannot fail.
- Do not build the filters once in `#controls`. They would then apply to whichever chart the operator
  last touched, contradicting the per-chart `state.entities` design ticket-026 fixed for exactly this
  reason.
- Do not filter by submarket or REE even though `Registries.hydro` carries both. E4-4 rules it out
  precisely because it is nearly free and therefore tempting.
- Do not reveal every option when nothing matches. The list would silently contradict the filter, and
  the operator would read it as a bug in the data.

### Out of Scope

- The hydro payload rules and the shared slicing helpers (ticket-027).
- The thermal-level verification of these same filters (ticket-029), which adds no code.
- The `CUSTOS` and `TEMPO` bar charts (tickets 030 and 031); their sections carry no selector and
  must carry no filter fragment.
- The document size measurement and its warning (ticket-032).
- Submarket and equivalent-reservoir filtering, `<optgroup>` grouping, multi-select, a shared
  "apply to all" control, fuzzy or regex matching, debouncing, and URL-hash state.
- Any change to the payload, the theme, the HTML template, the option markup or any existing test
  module.

## Testing Requirements

### Unit Tests

`tests/test_charts_filters.py`:

- the five acceptance criteria;
- the nine plant chart keys carrying a filter fragment equal the eight `UHE` keys plus `GTER_UTE`,
  so a fragment rendered for the wrong selector fails here;
- the fragment appears exactly once per plant section and the document holds exactly eighteen
  occurrences of `class="plant-filter"`, so a duplicated fragment fails;
- `charts.disabled = ["GTER_UTE"]`: sixteen occurrences remain and no `filter-name-GTER_UTE` exists,
  proving the fragment follows the enabled catalogue;
- the filter inputs appear **after** the entity `<select>` and **before** the plot `<div>` inside each
  plant section, asserted by index within the slice;
- `applyPlantFilter` appears in the asset exactly once as a declaration and once in the
  `window.DessemDashboard` assignment;
- the non-vacuity mutations of Suggested Approach step 7, each confirmed to fail before restoration.

### Integration Tests

None automated, by epic decision E3-1: no test parses or runs `dashboard.js`, so there is no syntax
gate on the JavaScript at all. The new checklist steps are the verification of the filtering
behaviour, and the run against the real 165-plant and 89-plant registries is ticket-034.

## Definition of Done

- [ ] The five files exist — four modified, one created — and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] Exactly one delegated `input` listener serves all eighteen filter inputs, and exactly one
      delegated `change` listener still serves the entity selectors.
- [ ] `dashboard.js` is pure ASCII, holds one `Object.freeze({`, reads no payload key outside `KEYS`,
      and contains no Portuguese string.
- [ ] `dashboard.css` has no colour literal and reads only properties the theme emits.
- [ ] The `docs/checklist-manual-dashboard.md` Epic 4 placeholder is gone, replaced by numbered steps
      that were walked by hand in a browser with the console open.
- [ ] `tests/test_builder.py`, `tests/test_charts_sin.py`, `tests/test_charts_submarket.py`,
      `tests/test_charts_hydro.py`, `tests/test_renderer_contract.py`,
      `tests/test_renderer_controls.py` and `tests/test_renderer_value_mode.py` all pass unchanged.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 40 minutes. The outline's 3 points
hold: the JavaScript is about thirty lines and the builder fragment about ten, but the ticket spans
five files across three layers — Python markup, asset behaviour, stylesheet and the manual checklist
— and its test module must prove nine positive and fourteen negative section cases plus four
mutations. Confidence is Medium rather than High for the reason E3-1 fixes for every interactive
ticket in this plan: the filtering itself is verified by hand, because no JavaScript is executed in
the suite.
