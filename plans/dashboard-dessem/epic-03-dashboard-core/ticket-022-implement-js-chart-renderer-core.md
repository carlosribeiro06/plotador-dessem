# ticket-022 Implement the JavaScript chart renderer core

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Master plan decision 6 forbids pre-rendering one Plotly figure per chart: with 165 hydro plants,
23 charts, several scenarios and up to 31 decks that would multiply the file size by orders of
magnitude. Instead the browser holds one JSON store and builds a figure on demand. This ticket writes
that engine — the one file every later ticket of Epics 3 and 4 extends — and, because epic decision
E3-1 rules out executing any JavaScript in the test suite, it also writes the two things that stand
in for a browser test: a Python-side **payload-key contract test**, and the **manual checklist** under
`docs/` that is walked once per release.

E3-1 is binding on how this file is written, not only on how it is tested. The JavaScript stays thin
and free of data shaping: everything computable in Python already happened in Python, which is why
the payload carries a precomputed axis `end` instead of `durations_hours`, a per-chart `unit` and
`subtitle` instead of registry lookups, pre-rounded values instead of raw ones, and a `labels` object
instead of Portuguese literals. The three computations this file is allowed to perform are naming a
trace, appending the terminal edge point, and reading a colour out of `theme.scenario_colors`;
ticket-024 adds exactly one more, the difference subtraction that master plan decision 8 places in
the browser.

The three original key decisions and the three open questions of this ticket resolve as follows.

- **Module shape: one IIFE assigned to a single global.** Not ES modules: an inline
  `<script type="module">` cannot import a sibling inline module, and the whole point of the artifact
  is that it is a single file opened from `file://`. One IIFE exposing `window.DessemDashboard` also
  gives the manual checklist a console handle.
- **`Plotly.react` only, never `Plotly.newPlot`.** `react` initialises an empty container as well as
  it updates a populated one, so there is exactly one render path and no first-render branch to get
  wrong — the thinnest option, which is what E3-1 asks for.
- **Step interpolation is `line.shape: "hv"` plus one terminal point.** Master plan decision 14 keeps
  a true date axis so a 6-hour stage is six times wider than a 30-minute one; without a final point
  at the last stage end the last stage would have no width at all. That terminal timestamp is
  `payload.axes[key].end`, computed in Python by ticket-020.
- **`null` gaps render as visible holes**, through `connectgaps: false`. A missing deck is a fact
  about the data and joining across it would draw a line that does not exist.
- **No trace caching.** In this epic the largest figure is 3 scenarios by 97 points, so rebuilding
  from the store costs microseconds and a cache would be unrequested state to keep coherent across
  four controls. If plant-level volumes prove otherwise, ticket-032 owns the measurement.
- **The contract test is the minimum E3-1 names**, made falsifiable: every payload key the file reads
  is declared once, in one frozen object, and the test proves each declared key exists in the payload
  ticket-020 actually produces.

### Relation to Epic

The engine tickets 023 to 026 and all of Epic 4 drive. Ticket-023 adds the mode, deck and level
setters; ticket-024 adds the value-mode setter and the difference arithmetic; ticket-025 adds the
per-chart layout; ticket-026 adds the entity-selector wiring. Because ticket-021 leaves the five
`data-group="SIN"` sections unhidden, the SIN charts already draw at the end of this ticket, with the
shared layout and no Y-axis unit title; ticket-025 completes them.

### Current State

`build_html` produces the full document and inlines
`src/dessem_dashboard/dashboard/assets/dashboard.js` through the `$dashboard_js` placeholder. That
asset currently holds **one comment line** naming this ticket as its implementer; replacing its
content is the main deliverable here. The DOM contract is fixed and must not be changed:
`<body data-initial-mode="...">`; `#header`, `#logo`, `#title`; `<nav id="level-nav">` with one
`<button data-group="...">` per group; `#controls` with `#mode-toggle` holding
`<button data-mode="deck">` and `<button data-mode="encadeado">`, `<select id="deck-selector">`,
`#value-toggle` holding `<button data-value="absoluto">` and `<button data-value="diferenca">`, and
`#reference-label`; `<main id="charts">` with one
`<section class="chart" id="chart-KEY" data-chart="KEY" data-group="..." data-selector="...">` per
enabled chart, `hidden` unless its group is the initially active one, each holding an `<h2>`, an
optional `<p class="chart-subtitle">`, an optional `<select class="entity-selector" id="entity-KEY">`
and a `<div class="plot" id="plot-KEY">`; `#footer`; and the three script elements
`#plotly-js`, `#dashboard-payload` (`type="application/json"`) and `#dashboard-js`, in that order.

The payload has the ten top-level keys `schema_version`, `scenarios`, `reference`, `deck_dates`,
`chained_key`, `axes`, `charts`, `theme`, `formats` and `labels`; each `axes` entry has `starts` and
`end`; each `charts` entry has `group`, `kind`, `selector`, `title`, `subtitle`, `unit`, `entities`,
`series` and `scalars`; `series` nests entity id, then scenario, then axis key, and an entry is
**absent** when the store has no series for that combination. There is no `docs/` directory yet.
`node` and `npm` are not installed, which is the measured basis of E3-1.

## Specification

### Requirements

1. Replace the content of `src/dessem_dashboard/dashboard/assets/dashboard.js` with one IIFE that
   assigns exactly one global, `window.DessemDashboard`, exposing these seven members: `payload`,
   `state`, `axisKey`, `buildTraces`, `renderChart`, `renderActiveGroup` and `init`. Tickets 023,
   024 and 026 add three, one and one further members, so assert presence rather than an exact
   member count, or their additions would break the test of this ticket.
2. Declare, as the first statement inside the IIFE, one frozen object literal
   `const KEYS = Object.freeze({ ... })` holding **one entry per payload key this file reads and no
   others**. Every payload access in the file goes through it: no `payload.someKey` dotted access and
   no `payload["someKey"]` string literal anywhere else in the file. This object is the contract the
   test in requirement 9 checks, and later tickets extend it by adding entries.
3. `init()` reads `document.getElementById("dashboard-payload").textContent`, parses it with
   `JSON.parse`, stores it as `payload`, and stops after a `console.error` when
   `payload[KEYS.SCHEMA_VERSION]` is not `1`. Console messages are developer-facing and therefore
   **English**; no operator-visible string may be written into this file.
4. `init()` then builds `state` as `{mode, deck, valueMode, entities}`: `mode` from
   `document.body.dataset.initialMode`; `deck` from the first entry of `payload[KEYS.DECK_DATES]`,
   because ticket-018 orders the deck dates chronologically; `valueMode` from the file-level constant
   `"absoluto"` (ticket-024 replaces this line with a read of the initial value attribute it adds);
   and `entities` mapping every chart key that has at least one entity to that first entity id, since
   `entities` arrives sorted by `sort_key`. Finally `init()` calls `renderActiveGroup()`, and is
   itself bound on `DOMContentLoaded`.
5. `axisKey()` returns `state.deck` when `state.mode` is `"deck"` and `payload[KEYS.CHAINED_KEY]`
   otherwise, so the axis and the series arrays are always read with the same key.
6. `buildTraces(chartKey)` returns an array with one trace per scenario of `payload[KEYS.SCENARIOS]`,
   in that order so the legend order matches the `--casos` order. For each scenario, read
   `chart[KEYS.SERIES][state.entities[chartKey]][scenario][axisKey()]` defensively and **skip the
   scenario entirely when any level is absent**, because ticket-020 omits the key for a scenario that
   lacks that deck. Each trace is
   `{type: "scatter", mode: "lines", name: scenario, connectgaps: false, x, y, line: {shape: "hv",
   color: payload[KEYS.THEME][KEYS.SCENARIO_COLORS][scenario], width: 2}}`, where `x` is
   `axis[KEYS.STARTS]` with `axis[KEYS.END]` appended and `y` is the values array with its own last
   element appended, so the final stage gets the width its duration entitles it to. When the last
   value is `null` the appended element is `null` too, which is honest rather than special-cased.
7. `renderChart(chartKey)` calls
   `Plotly.react(container, buildTraces(chartKey), layout, config)` on
   `document.getElementById("plot-" + chartKey)`, where `layout` is a **fresh deep copy** of
   `payload[KEYS.THEME][KEYS.LAYOUT]` obtained with `JSON.parse(JSON.stringify(...))`, and `config`
   is `{responsive: true, displaylogo: false, modeBarButtonsToRemove: ["sendDataToCloud"]}`. The
   copy is mandatory: `Plotly.react` writes computed properties into the layout it receives, and
   sharing one object across 23 charts would leak one chart axis range into another.
   `displaylogo: false` keeps a third-party logo away from the ONS identity, and removing
   `sendDataToCloud` removes the only modebar button that would open a network connection from a
   file that must work offline.
8. `renderActiveGroup()` iterates `document.querySelectorAll("#charts .chart:not([hidden])")` and
   calls `renderChart` with each element `dataset.chart`, so only the visible level is drawn and
   switching level is a re-render rather than a page rebuild.
9. Create `tests/test_renderer_contract.py`, reading the asset through
   `importlib.resources.files("dessem_dashboard.dashboard.assets")`, and assert the three static
   contracts: every string value declared in `KEYS` appears in the recursive key set of a payload
   built from the `scenario_tree` fixture; each of those double-quoted literals occurs **exactly
   once** in the asset, proving no payload key is accessed outside `KEYS`; and the asset matches
   neither `payload\.[A-Za-z_]` nor `payload\[\s*"`.
10. Create `docs/checklist-manual-dashboard.md`, the release checklist E3-1 requires, covering the
    whole of Epic 3 so it is written once by one author: opening the built file from `file://` with
    the network disabled and confirming the browser console reports **no error** — which is also the
    only gate on JavaScript syntax, since no test parses this file; the ONS identity, including the
    exact footer text; the level navigation over the six groups; the Por deck and Encadeado modes,
    including that the deck selector is disabled in Encadeado and that the 6-hour stages of a deck
    render six times wider than the half-hour stages; the Absoluto and Diferença toggle, with the
    exact case named in requirement 11; the submarket and interchange-pair selectors; and the Avisos
    section on a tree where one scenario lacks a deck. End the file with a clearly marked
    placeholder section for the Epic 4 plant name and code filters, which ticket-028 fills in.
11. The Absoluto and Diferença item must name a concrete, reproducible case, because master plan
    decision 8 puts that arithmetic in the browser and E3-1 accepts that it has no automated test.
    Name the build command of the README example,
    `--casos exemplo/caso_oficial exemplo/caso_gurobi`, whose reference is therefore
    `caso_oficial`; then: select the chart `GHID_SIN`, switch to Encadeado mode, hover the timestamp
    `04/03/2024 12:00` and write down the `caso_oficial` and `caso_gurobi` values; switch to
    Diferença and confirm that the plotted `caso_gurobi` value equals
    `caso_gurobi − caso_oficial` to the two decimals of `output.decimals`, and that the
    `caso_oficial` trace is a flat line at zero. That timestamp is on the chained axis by
    construction: chaining takes the first 48 half-hour stages of each deck, so the chained axis
    runs 03/03 00:00 to 23:30 followed by 04/03 00:00 to 23:30.
12. The checklist prose is **English** (Rigoroso mode, `rules/markdown.md`) and quotes the
    Portuguese interface strings verbatim where the reader has to match them on screen.

### Inputs

At run time, the embedded JSON payload and the DOM built by ticket-021. At test time, the asset text
and a payload built from the `scenario_tree` fixture.

### Outputs and Behavior

`dashboard.js` mutates only the DOM and its own `state`; it performs no I/O, opens no connection,
and writes nothing to `window` beyond the single `DessemDashboard` global. At the end of this ticket,
opening the built file draws the five SIN charts in Absoluto mode on the initial axis, with the
shared layout and no Y-axis unit title yet.

### Error Handling

A payload whose `schema_version` is not `1` stops `init()` after an English `console.error`, leaving
the shell visible with empty plot areas rather than a half-rendered dashboard. A missing series level
is a normal outcome and skips that scenario trace silently, because ticket-021 already renders the
Portuguese warning that explains the gap. Do not add a `try`/`catch` around `Plotly.react`: a Plotly
failure is a defect and must reach the console, which the checklist inspects. The Python test module
raises normally; it catches nothing.

## Dependencies

- **Blocked By**: `ticket-021-assemble-single-file-html-shell.md`
- **Blocks**: `ticket-023-implement-view-mode-and-deck-selector.md`,
  `ticket-024-implement-absolute-difference-toggle.md`

## Acceptance Criteria

- [ ] Given `assets/dashboard.js` read as text, when it is inspected, then it contains exactly one
      occurrence of `window.DessemDashboard`, that assignment names each of the seven documented
      members, the text contains `Object.freeze({` exactly once, and `text.isascii()` is `True`, so no
      accented operator-visible string can be hard-coded in the renderer.
- [ ] Given the same text, when it is searched for network and dynamic-evaluation constructs, then it
      contains none of `fetch(`, `XMLHttpRequest`, `import(`, `eval(`, `document.write`, `http://` or
      `https://`, and it does contain `displaylogo` set to `false` and `"sendDataToCloud"` inside
      `modeBarButtonsToRemove`, so opening the file opens no connection.
- [ ] Given the `KEYS` object literal extracted from the asset by regular expression, when its string
      values are compared with a payload built from the `scenario_tree` fixture, then every value
      appears in the recursive key set of that payload, and each of those values, written with its
      surrounding double quotes, occurs exactly once in the asset.
- [ ] Given the same text, when the render path is checked, then `Plotly.react(` occurs exactly once
      and `Plotly.newPlot(` does not occur, the text contains `shape: "hv"` and `connectgaps` set to
      `false`, it matches neither `payload\.[A-Za-z_]` nor `payload\[\s*"`, and the document returned
      by `build_html` contains the asset text verbatim between `<script id="dashboard-js">` and the
      following `</script>`.
- [ ] Given `docs/checklist-manual-dashboard.md`, when it is read, then it contains the literal
      timestamp `04/03/2024 12:00`, the chart key `GHID_SIN`, both `caso_oficial` and `caso_gurobi`,
      the words `Absoluto` and `Diferença`, a console-error check item, and a section naming
      ticket-028 as the owner of the plant-filter items; and
      `.venv/bin/pytest tests/test_renderer_contract.py -q && .venv/bin/ruff check src tests` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `KEYS` first, from the payload contract in Current State, then write the file so that every
   read goes through it. Adding a key later is a one-line change; a stray literal is a contract
   break.
2. Write `init`, `axisKey`, `buildTraces`, `renderChart`, `renderActiveGroup` in that order, and end
   the IIFE with the single `window.DessemDashboard = {...}` assignment followed by the
   `DOMContentLoaded` binding.
3. Guard the series read with three short-circuit checks rather than optional chaining if the target
   browser set is uncertain; either form is acceptable, but the skip must be silent and must not
   push an empty trace, or the legend would list a scenario with no data.
4. Build `x` once per `renderChart` call and share the array across the scenario traces: Plotly reads
   it and does not mutate it, and one array instead of three is measurably smaller in memory at
   plant volumes.
5. Write the checklist as numbered steps with an explicit expected result per step, so a reader can
   record pass or fail without interpretation. Put the offline-and-console step first: it is the only
   syntax gate this file has.
6. Write `tests/test_renderer_contract.py` last, and confirm each assertion can fail by temporarily
   breaking the asset — a renamed `KEYS` value, an added `payload.charts` dotted access — before
   restoring it.

### Key Files to Create/Modify

- `src/dessem_dashboard/dashboard/assets/dashboard.js` (modify: replaces the one-line stub)
- `docs/checklist-manual-dashboard.md` (create)
- `tests/test_renderer_contract.py` (create)

### Patterns to Follow

- English identifiers and English comments in the JavaScript, matching the Rigoroso rule that
  identifiers and code comments are English in both modes; keep comments minimal.
- Portuguese only in the interface strings quoted by the checklist, never in the asset.
- `importlib.resources` for reading package data in the test, as `builder.py` does.
- `tests/test_builder.py` settings-copy-in-`tmp_path` pattern if the test needs a built document.

### Pitfalls to Avoid

- Do not pass `payload.theme.layout` straight into `Plotly.react`. Plotly mutates the layout object,
  so 23 charts sharing one object will leak axis ranges between charts; requirement 7 mandates a
  fresh deep copy per call.
- Do not reintroduce `durations_hours`, a registry lookup, a unit table, a date formatter or a
  Portuguese literal into this file. Each of those exists on the Python side already, and E3-1 makes
  the thinness of this file the mitigation for its lack of automated tests.
- Do not use `Plotly.newPlot` for a first render. Two render paths mean the mode switch and the first
  paint can diverge, and only one of them is ever exercised by the checklist.
- Do not treat a missing series as zeros. Ticket-020 omits the key precisely so the trace disappears
  instead of drawing a line at zero, which an analyst would read as a real value.
- Do not append the terminal point to `x` without appending to `y`: Plotly silently truncates to the
  shorter array and the last stage vanishes instead of gaining width.
- Do not read the payload from a JavaScript variable assignment. It lives in a
  `<script type="application/json">` element and must be parsed from `textContent`; reading
  `innerHTML` instead would re-enter HTML entity decoding.
- Do not register listeners in this ticket. Tickets 023, 024 and 026 own the controls, and a listener
  added here would be re-added there.
- Do not write the checklist in Portuguese prose. Rigoroso puts documentation in English; only the
  quoted interface strings are Portuguese.

### Out of Scope

- Every control listener and every setter: mode, deck and level (ticket-023), value mode
  (ticket-024), entity selector (ticket-026).
- The per-chart layout, including the Y-axis unit title and the Diferença suffix (ticket-025).
- The difference arithmetic itself (ticket-024).
- Any change to `builder.py`, `payload.py`, `theme.py` or the HTML and CSS assets.
- The plant name and code filters, and the checklist items covering them (ticket-028).
- Any Plotly locale work: the modebar tooltips stay English, because `plotly.offline.get_plotlyjs()`
  exposes no locale bundle and adding one would mean a second asset from outside the installed
  package.

## Testing Requirements

### Unit Tests

`tests/test_renderer_contract.py`:

- the five acceptance criteria;
- the `KEYS` extraction itself: the regular expression finds a non-empty set, so a renamed or deleted
  `KEYS` object fails loudly instead of vacuously passing on an empty set;
- the asset is non-empty and longer than the one-line stub it replaced, so an accidental empty write
  fails;
- the asset appears exactly once in the built document, so it is neither omitted nor duplicated;
- `docs/checklist-manual-dashboard.md` contains a numbered step list and every one of the seven
  topics requirement 10 enumerates, asserted by one substring per topic.

### Integration Tests

None automated, by epic decision E3-1. The behavioural gate is
`docs/checklist-manual-dashboard.md`, walked once per release; the run against real data is
ticket-034.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `dashboard.js` is pure ASCII and contains no operator-visible string; every Portuguese word an
      operator reads comes from the HTML that ticket-021 generated or from `payload.labels`.
- [ ] `dashboard.js` performs no data shaping beyond naming a trace, appending the terminal edge
      point and reading a scenario colour.
- [ ] The checklist names the `GHID_SIN` at `04/03/2024 12:00` Absoluto-versus-Diferença case on
      the `exemplo/caso_oficial` and `exemplo/caso_gurobi` tree, which is the computation E3-1
      accepts as untested.
- [ ] No file outside the three listed above is modified, verified with `git status --porcelain`.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes. Confidence is Medium
rather than High because E3-1 limits the automated evidence to static assertions; the specification
is unambiguous, but a behavioural defect can only be caught by the checklist.
