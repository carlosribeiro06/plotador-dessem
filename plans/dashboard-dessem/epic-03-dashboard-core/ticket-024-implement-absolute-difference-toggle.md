# ticket-024 Implement the absolute and difference toggle

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Single-writer note:** this ticket and ticket-023 both modify `builder.py` and
> `assets/dashboard.js`. The dependency graph allows either order but **not** a parallel dispatch;
> run them sequentially, per Epic 2 learnings section 9.

## Context

### Background

`planning-context.md` decision 8 gives every chart an **Absoluto / Diferença** toggle, with the
difference defined as `cenário − referência` and computed **in the browser** from the embedded
absolute series. That choice halves the payload: shipping precomputed differences would mean one
extra array per scenario, per entity, per chart and per axis. The reference scenario is the first
`--casos` argument unless `--referencia` overrides it, and it already reached the browser as
`payload.reference` and the operator as the `#reference-label` text that ticket-021 renders.

This is the one computation epic decision E3-1 accepts as having **no automated test**, which is why
E3-1 also binds the shape of the solution: the arithmetic must be a subtraction, a null guard and a
rounding, nothing more, and the manual checklist ticket-022 wrote names the exact case to verify —
`GHID_SIN` in Encadeado mode at `04/03/2024 12:00` on the
`--casos exemplo/caso_oficial exemplo/caso_gurobi` tree, where the plotted `caso_gurobi` value must
equal `caso_gurobi − caso_oficial` and the `caso_oficial` trace must be a flat line at zero.

The three original key decisions and the three open questions resolve as follows.

- **The reference curve is kept in Diferença mode**, as a flat zero line in brand green. It is the
  visual baseline that makes the sign of every other curve readable, and hiding it would change the
  legend between modes, which reads as a bug. It also needs no special case: the same subtraction
  applied to the reference yields zero.
- **A `null` on either side produces `null`, never zero.** A missing deck must not read as "no
  difference". This follows master plan decision 17, which fills missing combinations with `null`
  precisely so a gap stays a gap.
- **The Y axis title gains the `payload.labels.y_axis_difference_suffix` text ` (diferença)`**, and
  the axis is **not** forced to include zero. `rangemode: "tozero"` would compress small differences
  against a large absolute range; the `zeroline` that ticket-019 already put in the layout template
  draws zero whenever it is inside the range, which is the honest middle. The suffix is **decided
  here and implemented by ticket-025**, which owns the per-chart layout and runs after this ticket;
  the label itself already exists in the payload from ticket-020 requirement 11.
- **No relative percentage difference.** The spec asks for a difference, E3-1 asks for thin
  JavaScript, and a percentage needs a division-by-zero policy that nobody has specified.
- **The toggle state persists across level and deck changes.** It lives in the same global `state`
  object as the mode and the deck, for the same reason ticket-023 gave: one comparison context.
- **The reference is already visible in the UI.** Ticket-021 renders
  `<span id="reference-label">Referência: caso_oficial</span>`, so this ticket adds nothing there;
  the open question is closed by existing work, not by new work.
- **A missing reference series renders an empty plot, with no annotation.** When the reference
  scenario itself lacks the selected deck there is nothing to subtract from. Adding an in-plot
  message would mean a second Portuguese label and a layout branch; instead the Avisos section that
  ticket-021 renders already tells the operator, in Portuguese and naming the scenario and the date,
  that the deck is missing.

### Relation to Epic

The second of the two control tickets, alongside ticket-023, and the last one before charts get their
final look. It owns the value control in the same three places ticket-023 owns the mode control: the
initial state in `builder.py`, the attribute in `dashboard.html`, and the setter, listener and
arithmetic in `dashboard.js`. Ticket-025 then consumes `state.valueMode` to title the Y axis.

### Current State

`dashboard.html` declares `<body data-initial-mode="$initial_mode">` and
`<div id="value-toggle">$value_toggle</div>`. `builder.py` generates `_value_toggle` from the
`VALUE_LABELS` mapping (`absoluto` maps to `Absoluto`, `diferenca` to `Diferença`) and **emits no
`aria-pressed`**, which ticket-021 requirement 2 withheld on purpose so this ticket owns it.
`_mode_toggle`, `_deck_selector` and `_level_nav` already carry their `aria-pressed` and `disabled`
state from ticket-023 and must not be touched here.

`dashboard.js` exposes `payload`, `state`, `axisKey`, `buildTraces`, `renderChart`,
`renderActiveGroup`, `init`, `setMode`, `setDeck` and `setGroup`. `state` is
`{mode, deck, valueMode, entities}` and `init()` currently sets `state.valueMode` from a file-level
`"absoluto"` constant, the line this ticket replaces. Ticket-023 left a private helper that syncs
`aria-pressed` across the buttons of a container, ready to be reused. `buildTraces(chartKey)` builds
one trace per scenario from `chart[KEYS.SERIES][entityId][scenario][axisKey()]`, skipping a scenario
whose entry is absent, appending the terminal `end` point to `x` and the last value to `y`, and
setting `connectgaps: false` and `line.shape: "hv"`. Every payload read goes through the frozen
`KEYS` object, and `tests/test_renderer_contract.py` asserts each declared key literal occurs exactly
once in the asset and that the asset is pure ASCII.

Available payload keys this ticket newly needs: `reference` (the reference scenario label), and
`formats.decimals` (the integer `2` by default). `labels.y_axis_difference_suffix` is
` (diferença)` and is read by ticket-025, not here. Measured on the `scenario_tree` fixture:
`payload["reference"]` is `caso_a`, both scenarios carry 96 chained values for `GHID_SIN`, and
`output.decimals` is `2`.

## Specification

### Requirements

1. In `assets/dashboard.html`, extend the body tag to
   `<body data-initial-mode="$initial_mode" data-initial-value="absoluto">`. This is a static
   attribute, not a placeholder: the placeholder set stays at the fifteen names ticket-021 fixed, so
   its fifth acceptance criterion keeps passing.
2. In `builder.py`, declare the module constant `INITIAL_VALUE_MODE = "absoluto"` and make
   `_value_toggle` mark the button whose `data-value` equals it with `aria-pressed="true"` and the
   other with `aria-pressed="false"`. Touch no other fragment helper.
3. In `dashboard.js`, replace the `state.valueMode` initialisation with a read of
   `document.body.dataset.initialValue`, so the document is the single source of both initial control
   states, exactly as `state.mode` reads `data-initial-mode`.
4. Add `setValueMode(valueMode)`: it assigns `state.valueMode`, syncs `aria-pressed` on both
   `#value-toggle` buttons through the helper ticket-023 introduced, and calls `renderActiveGroup()`.
5. Register one delegated `click` listener on `#value-toggle`, reading `event.target.dataset.value`
   and ignoring an event where that entry is absent, matching the delegation pattern of ticket-023.
6. Extend `buildTraces(chartKey)` for the `"diferenca"` value mode. Read the reference array once,
   from `chart[KEYS.SERIES][entityId][payload[KEYS.REFERENCE]][axisKey()]`. When that read is absent,
   **return an empty array** so the plot renders empty, per the ruling under Background. Otherwise
   build each scenario `y` element as `null` when either the scenario value or the reference value is
   `null`, and otherwise as `(value - reference)` rounded to `payload[KEYS.FORMATS][KEYS.DECIMALS]`
   decimals. The reference scenario passes through the same expression and therefore plots as a flat
   zero line, which requirement 6 keeps rather than special-cases.
7. Round the subtraction. Binary floating point turns a difference of two values that were already
   rounded to two decimals into figures such as `1.4000000000000057`, which would reach the hover
   text verbatim. Round with the `decimals` value from the payload — never with a literal `2` — so
   the browser and `output.decimals` cannot diverge.
8. Leave the `x` array, the terminal edge point, `connectgaps: false`, `line.shape: "hv"`, the trace
   order and the scenario colours exactly as ticket-022 built them. Diferença changes the `y` values
   and nothing else.
9. Expose `setValueMode` on `window.DessemDashboard` in addition to the ten members present after
   ticket-023. Add `reference`, `formats` and `decimals` to the frozen `KEYS` object, keep every
   payload read going through it, and keep the file pure ASCII: the only operator-visible string this
   feature needs is in the payload `labels` object and is consumed by ticket-025.
10. Add no relative or percentage difference, no Plotly `annotations`, no `rangemode` override and no
    second Y axis. Each is unrequested scope in the ticket E3-1 singles out as untestable.

### Inputs

At run time, `state.valueMode`, `payload.reference`, `payload.formats.decimals` and the absolute
series already in the payload. At build time, `INITIAL_VALUE_MODE`.

### Outputs and Behavior

`build_html` returns a document whose Absoluto button is pressed and whose body carries
`data-initial-value="absoluto"`. In the browser, clicking Diferença redraws every visible chart with
`cenário − referência`, the reference flat at zero, gaps preserved as gaps, and the toggle state
surviving a level, deck or mode change. Clicking Absoluto restores the stored values unchanged: the
payload is never mutated, so the round trip is lossless.

### Error Handling

No new error path in Python. In the browser, an absent reference array yields an empty trace list and
an empty plot, which is a normal outcome explained by the Avisos section, not an error; a click on
the container padding is ignored. No `try`/`catch` is added, so any real failure reaches the console
that the manual checklist inspects.

## Dependencies

- **Blocked By**: `ticket-022-implement-js-chart-renderer-core.md`
- **Blocks**: `ticket-025-render-sin-level-charts.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture and the repository `settings.json`, when
      `build_html(data, settings=settings)` is called, then the document contains
      `data-initial-value="absoluto"` on the `<body>` element, the `data-value="absoluto"` button
      carries `aria-pressed="true"`, the `data-value="diferenca"` button carries
      `aria-pressed="false"`, and the `#reference-label` text is still `Referência: caso_a`.
- [ ] Given `assets/dashboard.js`, when its text is inspected, then `window.DessemDashboard`
      names `setValueMode` in addition to the ten members present after ticket-023, the text
      contains `"value-toggle"` and `dataset.initialValue`, it contains no `"absoluto"` literal at
      all and exactly one `"diferenca"` literal — the value mode now arrives from the document and
      only the Diferença branch needs a comparison — and `text.isascii()` is `True`.
- [ ] Given the same text, when the difference branch is inspected, then it reads the reference
      series through `KEYS.REFERENCE` exactly once, the rounding factor is the exact substring
      `Math.pow(10, payload[KEYS.FORMATS][KEYS.DECIMALS])`, the asset contains neither
      `Math.pow(10, 2)` nor `* 100`, and it contains none of
      `annotations`, `rangemode`, `newPlot` or a percentage-difference expression; and the
      `KEYS` object now declares `"reference"`, `"formats"` and `"decimals"`, each of which appears
      exactly once in the asset.
- [ ] Given a `scenario_tree` variant in which the reference scenario `caso_a` lacks the deck of
      04/03/2024, when the payload is built, then
      `payload["charts"]["GHID_SIN"]["series"][""]["caso_a"]` has no `"04/03/2024"` key while
      `payload["charts"]["GHID_SIN"]["series"][""]["caso_b"]["04/03/2024"]` has 50 values; and the
      difference branch of `dashboard.js` returns an empty array when that reference read is absent,
      so the chart renders empty instead of plotting `caso_b` against zero.
- [ ] Given the whole epic asset set, when the regression suite is run, then
      `tests/test_builder.py`, `tests/test_renderer_contract.py` and
      `tests/test_renderer_controls.py` all still pass unchanged, and
      `.venv/bin/pytest tests/test_renderer_value_mode.py tests/test_renderer_contract.py
      tests/test_builder.py tests/test_renderer_controls.py -q && .venv/bin/mypy src` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Add the `data-initial-value` attribute and the `_value_toggle` `aria-pressed` state first, then
   run `tests/test_builder.py` and `tests/test_renderer_controls.py` to confirm the placeholder set,
   the section count and the mode and level state are untouched.
2. In `dashboard.js`, add the three `KEYS` entries, then change the `state.valueMode` initialisation,
   then add `setValueMode` and its listener next to the ticket-023 setters, reusing the
   `aria-pressed` sync helper.
3. Refactor `buildTraces` by computing the `y` array through one small private function
   `valuesForMode(values, referenceValues, decimals)` that returns `values` unchanged in Absoluto
   mode and the rounded difference array in Diferença mode. One function with one branch keeps the
   untested surface as small as E3-1 asks.
4. Round with `Math.round(delta * factor) / factor` where `factor` is `Math.pow(10, decimals)`,
   computed once per call rather than per point.
5. Write `tests/test_renderer_value_mode.py` with the builder assertions, the static asset
   assertions, and the payload-shape assertion of the fourth acceptance criterion, building the
   variant tree with `build_scenario_tree` and removing the reference deck directory before
   discovery.
6. Walk item 6 of `docs/checklist-manual-dashboard.md` by hand before declaring the ticket done: it
   is the only verification this arithmetic has.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/assets/dashboard.html` (modify: one static body attribute)
- `src/dessem_dashboard/dashboard/builder.py` (modify: `INITIAL_VALUE_MODE` and `_value_toggle`)
- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: one setter, one listener, the
  difference branch)
- `tests/test_renderer_value_mode.py` (create)

### Patterns to Follow

- The delegated-listener and `aria-pressed`-sync patterns ticket-023 established, reused rather than
  re-invented.
- The frozen `KEYS` discipline: three new entries, no literal payload key elsewhere.
- English identifiers and comments in the JavaScript; the single Portuguese string this feature needs
  lives in `payload.labels`.
- `tests/test_builder.py` settings-copy-in-`tmp_path` pattern, so nothing is written into the
  repository `output/`.

### Pitfalls to Avoid

- Do not treat a `null` as zero on either side of the subtraction. A missing deck would then plot as
  a zero difference, which is the most expensive possible misreading of a comparison dashboard.
- Do not hide the reference trace in Diferença mode. It is the baseline, and its disappearance would
  change the legend between modes.
- Do not skip the rounding, and do not hard-code `2`. `output.decimals` is configurable and the
  browser must follow it.
- Do not mutate the payload arrays in place while building the difference. The Absoluto round trip
  must return the original values, and `Array.prototype.map` returning a new array is the cheapest
  guarantee.
- Do not add a Plotly annotation, a `rangemode: "tozero"` or a percentage view. All three are
  unrequested, and the first two would also make the layout branch on value mode in two places.
- Do not touch `_mode_toggle`, `_deck_selector` or `_level_nav`: ticket-023 owns their state and a
  second writer would collide.
- Do not implement the Y-axis `(diferença)` suffix here. Ticket-025 owns `buildLayout`, runs after
  this ticket, and implementing it here would put the layout in two places.
- Do not read the reference series inside the per-scenario loop. One read before the loop is both
  cheaper and the only way the absent-reference early return stays a single branch.

### Out of Scope

- The Y-axis title and its Diferença suffix (ticket-025 requirement, decided here).
- Any percentage or relative difference view.
- The mode, deck and level controls and their initial state (ticket-023).
- The entity selector behaviour (ticket-026) and the plant filters (ticket-028).
- Any change to `payload.py`, `theme.py`, `dashboard.css` or
  `docs/checklist-manual-dashboard.md`, whose Absoluto and Diferença item ticket-022 already wrote.
- Precomputing differences in Python: master plan decision 8 places them in the browser.

## Testing Requirements

### Unit Tests

`tests/test_renderer_value_mode.py`:

- the five acceptance criteria;
- the two documents built with `initial_mode="deck"` and `initial_mode="encadeado"` both carrying
  `data-initial-value="absoluto"`, so the value mode is independent of the view mode;
- `INITIAL_VALUE_MODE` being one of the two `VALUE_LABELS` keys, asserted as a membership rather than
  a literal, so a typo in either mapping fails;
- the payload of the unmodified fixture: `payload["reference"]` equals `caso_a`, and for `GHID_SIN`
  both scenarios carry 96 chained values, which is the precondition that makes the checklist case
  computable pointwise;
- the variant tree of the fourth acceptance criterion, including that `data.warnings()` then contains
  a message naming `caso_a` and `04/03/2024`, which is the operator explanation for the empty
  Diferença plot — asserted as a filtered count over the matching messages, never as
  `len(data.warnings()) == 1`;
- the static asset assertions, each confirmed to be able to fail by temporarily breaking the asset
  before restoring it.

### Integration Tests

None automated, by epic decision E3-1. Item 6 of `docs/checklist-manual-dashboard.md` is the only
verification of the difference arithmetic and must be walked before this ticket is closed.

## Definition of Done

- [ ] The four files exist, with three modified and one created, and all five acceptance criteria
      pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.
- [ ] A `null` on either side of the subtraction yields `null`, and the reference trace is kept as a
      flat zero line.
- [ ] The difference is rounded with a factor computed from `payload.formats.decimals`, and
      `dashboard.js` hard-codes no decimal count, verified by the absence of `Math.pow(10, 2)`.
- [ ] Item 6 of `docs/checklist-manual-dashboard.md` was walked by hand against
      `--casos exemplo/caso_oficial exemplo/caso_gurobi`, and the result is reported with the ticket.
- [ ] `tests/test_builder.py`, `tests/test_renderer_contract.py` and
      `tests/test_renderer_controls.py` pass unchanged.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes. Confidence is Medium and
not High because the arithmetic itself is verified only by the manual checklist, which is the
accepted trade-off recorded in epic decision E3-1.
