# Epic 03 — Dashboard Core: Learnings

> Started 2026-09-11, while tickets 023 to 026 were still executing. Sections 1 to 6 cover the four
> committed and guardian-verified tickets (019 to 022) and are stable. Sections 7 and 8 are completed
> at the epic boundary, once the four interactive tickets land.
>
> Written for the refinement of Epics 4 and 5. Everything here is measured or verified. The Epic 4
> overview names three refinement inputs it needs from this file: the payload key names (section 2),
> the renderer function boundaries (section 7, pending), the decision on whether a group shows all
> charts at once (section 7, pending) and the browser testing approach (section 1).

---

## 1. E3-1 in practice: what "no JavaScript is executed" actually costs and buys

The developer chose Python-only assertions plus a manual checklist, with `node` and `npm` absent from
this environment (measured, not assumed). Four tickets in, here is how that plays out.

**What is genuinely covered automatically.** The generated HTML and the exported JSON are text, and
text is fully assertable: placeholder sets, element order, chart counts, hidden state, entity option
lists, escaping, rounding, key sets, array lengths against their axis, absence of the `NaN` token,
and the size of the document. Ticket-021 has 18 such tests and ticket-020 has 19; none of them is
weaker for lacking a browser.

**What is not covered, and must never be pretended otherwise.** No test parses or runs
`dashboard.js`. There is therefore **no syntax gate on the JavaScript at all** — a stray brace ships
a 4.5 MB file that renders nothing. That is why the first item of `docs/checklist-manual-dashboard.md`
is opening the file and confirming the browser console reports no error, and why the checklist says
so explicitly rather than burying it.

**The pattern that made this work**: move every decidable thing into Python, then assert the
*artefact*. The renderer reads a precomputed `end` timestamp rather than computing it from
`durations_hours`; the scenario colours and the Plotly layout arrive fully built in the payload; the
entity lists arrive sorted. Each of those is a behaviour that would have needed a browser to test and
now needs only a dict comparison.

**Static contracts can substitute for execution, if they are adversarial.** See section 3.

---

## 2. The payload contract (`dashboard/payload.py`) — Epic 4 builds on this

Ten top-level keys, exactly: `schema_version` (integer `1`), `scenarios`, `reference`, `deck_dates`,
`chained_key`, `axes`, `charts`, `theme`, `formats`, `labels`. There is deliberately **no `warnings`
key** — ticket-021 renders warnings in Python, per E3-1.

```
axes[key]            -> {"starts": ["%Y-%m-%d %H:%M", ...], "end": "%Y-%m-%d %H:%M"}
charts[chart_key]    -> nine keys, uniform across BOTH chart kinds:
                        group, kind, selector, title, subtitle, unit, entities, series, scalars
entities             -> [{"id": ..., "label": ...}, ...]   already sorted by sort_key
labels               -> {"y_axis_difference_suffix": " (diferença)"}
theme                -> {"scenario_colors": {...}, "layout": {...}}
```

Four shape rules that are easy to get wrong:

- **`durations_hours` is not exported.** The precomputed `end` is the only thing the browser needs,
  and computing it in Python is what keeps the JavaScript thin.
- **Two date formats coexist and must not be confused.** Axis timestamps use the machine format
  `%Y-%m-%d %H:%M`. Deck labels and the keys of the `axes` map come from `TimeAxis.key`, already
  rendered `%d/%m/%Y`. **`settings.dashboard.date_format` is `"%d/%m/%Y %H:%M"`** and is the wrong
  source for a date-only label — it would render a deck as `03/03/2024 00:00`.
- **A missing key means missing data, at two levels.** A scenario lacking a deck has no entry for
  that axis key, and a scenario contributing no stored dates for an entity has no key at all. The
  renderer must skip, never substitute zero.
- The nine chart keys are present for both kinds: a `SERIES` chart carries an empty `scalars`, a
  `SCALAR_BY_DECK` chart carries empty `entities` and `series`.

`payload_json` uses `allow_nan=False` and escapes `<` as `<`. Both are load-bearing: the `NaN`
token is invalid JSON and would make `JSON.parse` throw, blanking every chart, and the escape stops
the payload terminating its own `<script>` block.

Three read-only store accessors were added here from epic-02 finding M6: `chart_keys()`,
`scalar_chart_keys()` and `stored_deck_dates(chart_key, entity_id, scenario)`, with `None` sorting
last as the chained axis. Their point is not the ~320 000 avoided `has_series` probes but the silent
defect: deriving the chart list solely from `enabled_specs(disabled=...)` drops a stored chart from
the HTML with nothing reporting it if that `disabled` list ever diverges from consolidation's.
`stored_deck_dates` is a per-call O(n) scan with no index — **ticket-034 should measure it at
production scale** (165 plants × 30 decks × 3 scenarios) before anyone optimises it.

---

## 3. The `KEYS` contract, and the four ways it was evaded

`dashboard.js` declares one frozen `KEYS` object as the first statement of its IIFE, with one entry
per payload key the file reads and no others (14 entries today). Three static assertions stand in for
execution: every `KEYS` value appears in the recursive key set of a real payload; each quoted literal
occurs **exactly once** in the asset; and the asset matches neither `payload\.[A-Za-z_]` nor
`payload\[\s*"`.

**The ticket-022 verification was asked to break that contract, and did.** Four evasions passed all
three checks:

1. optional chaining, `payload?.charts` — breaks the literal `payload.` the first regex needs;
2. destructuring, `const { charts } = payload` — uses neither dot nor bracket syntax;
3. a single-quoted or template-literal key, `payload['charts']` — dodges the double quote;
4. a key built by concatenation into a variable, `payload[k]` — puts an identifier after the bracket.

None was present, but tickets 023, 024 and 026 all extend this same file, so the gap was closed
immediately rather than recorded as a risk (commit `d7e98eb`). The fix worth reusing: **requiring
every `payload[` to be followed by `KEYS.`** closes 3 and 4 together, because neither a quote of any
kind nor an arbitrary identifier satisfies it. The other two became their own patterns. Proven
non-vacuous by checking each evasion is caught and that legitimate `KEYS` access still passes.

**Generalisable lesson**: a static contract that replaces execution must be attacked, not merely
written. The regex triad detected the naive violation and missed every reworded one.

---

## 4. The DOM contract (`assets/dashboard.html` + `builder.py`) — fixed, and Epic 4 attaches to it

Ids, classes and `data-` attribute names are **English identifiers**; every text node an operator
reads is **Portuguese**. Fifteen `string.Template` placeholders, closed.

```
body[data-initial-mode]
header#header  > img#logo, h1#title
nav#level-nav  > button[type=button][data-group=G]        one per group with an enabled chart
div#controls   > div#mode-toggle > button[data-mode=M]
                 label[for=deck-selector] "Deck", select#deck-selector
                 div#value-toggle > button[data-value=V]
                 span#reference-label
section#warnings (absent entirely when there are no warnings)
main#charts    > section.chart#chart-KEY[data-chart=KEY][data-group=G] > div#plot-KEY
footer#footer
script#plotly-js, script#dashboard-payload[type=application/json], script#dashboard-js   (last, in order)
```

The script order is load-bearing: the renderer must find both Plotly and its data already present.

**The staged-state pattern is worth copying in Epic 4.** Ticket-021 deliberately emitted **no**
`aria-pressed` and **no** `disabled`, so that the acceptance criteria of tickets 023 and 024 could
not pass before those tickets existed. Each ticket withholds exactly the state the next one owns.
Verified by scoped greps — and the grep scoping is itself measured: `builder.py` legitimately
contains the word `disabled` because it calls `enabled_specs(disabled=...)`, and the generated
document contains both `aria-pressed` and `disabled` because the inlined plotly bundle has them 3 and
78 times respectively.

---

## 5. Assembling the single file: five things that must not change

1. **`string.Template`, one `substitute` call, never `safe_substitute` and never `str.format`.** Every
   `{` in the CSS and the 4.29 MB of minified JavaScript would need doubling under `format`, and one
   missed brace corrupts the whole document. `R$/MWh` and the JavaScript both contain `$`, which is
   why a single pass is safe and a second is not. `safe_substitute` would ship a dashboard containing
   the literal text `$payload_json`.
2. **The "no external reference" assertion must excise the plotly block first.** Measured on plotly
   7.0.0: `get_plotlyjs()` is 4,293,280 chars containing 52 `https://`, 71 `http://`, one
   `cdn.plot.ly`, 9 `src=` and 17 `href=` inside its own string literals, so the same search over the
   whole document can never pass. It contains no `</script` and no `<!--`, which is what makes
   verbatim inlining safe — and there is a test asserting that, so a future plotly upgrade fails
   loudly here instead of silently corrupting output.
3. **Assets are read through `importlib.resources.files("dessem_dashboard.dashboard.assets")`**, never
   a path relative to `__file__`, which works in an editable install and breaks in a wheel. This is
   also why `assets/__init__.py` exists: `[tool.setuptools.packages.find]` only discovers directories
   containing one, so without it the `[tool.setuptools.package-data]` key resolves to nothing and a
   built wheel ships no CSS, JavaScript or HTML. That defect was latent in `pyproject.toml` and was
   found during refinement, not execution.
4. **No colour literal in `dashboard.css`.** Every colour resolves through a `var(--ons-*)` property
   that `theme.css_root_block()` emits, and **the correspondence was verified in both directions** —
   the CSS references exactly the eight properties the theme emits. A `var()` naming a property the
   theme does not emit renders an unstyled page silently, which no one-directional check would catch.
5. **The size assertion is a measured range, not a budget check.** `[4_300_000, 5_242_880]` against a
   measured 4,506,387; the floor components alone are 4,293,280 (plotly) + 72,648 (logo base64) =
   4,365,928. A literal "under 50 MB" would be a can-never-fail check. `output.size_warning_mb`
   enforcement belongs to ticket-032.

---

## 6. The theme module: the one-source-of-truth pattern, and its arithmetic

`theme.py` is the single source of every visual constant, consumed by the CSS (through
`css_root_block()`), the Plotly layout (`plotly_layout_template()`) and the scenario colours
(`scenario_colors()`).

- The **reference scenario always takes brand green `#486018`**, whatever its position in `--casos`,
  because it is the baseline for Diferença mode.
- Slots beyond the fourth use 60 % tints of the first four. Verified distinct up to nine scenarios;
  the ninth relies on `0.6² = 0.36`, which is outside the range the ticket tested.
- `tint("#486018", 0.6) == "#91A074"` and `tint("#606060", 0.2) == "#DFDFDF"`; `GRID_COLOR` is
  **derived** as `tint(BRAND_GRAY, 0.2)`, not written as a literal, so the grid colour has one place
  to change.
- Auxiliary yellow `#FBC90B` is **deliberately not declared**: the brand manual caps auxiliary
  colours at three and the plan spends them on blue, orange and red, so declaring it would be dead
  code. Exactly six hex literals exist in the file, and a DoD grep counts them.
- `plotly_layout_template()` carries **no top-level `title`**, because E3-2 makes the curated
  `ChartSpec.title` the heading rendered in HTML and a Plotly title would double it. It returns a
  fresh object per call.

---

## 7. Renderer function boundaries and the group-render decision

This is the declared refinement input for Epic 4. Tickets 027, 029, 030 and 031 extend this same
asset, so specify against these boundaries rather than inventing new ones.

**`window.DessemDashboard` exposes thirteen members** after ticket-026. Assert **presence, never a
count** — five tickets grew this object in sequence and a count assertion would have broken each
successor:

```
payload, state           getters over the live module bindings, not shorthand: the object literal is
                         evaluated before init() runs on DOMContentLoaded, so shorthand would pin
                         both at null forever and defeat the console handle
axisKey()                state.deck in "deck" mode, payload chained key otherwise, so the axis and
                         the series arrays are always read with one key
buildTraces(chartKey)    one trace per scenario in payload order, so legend order matches --casos.
                         Skips a scenario entirely when any level of the series lookup is absent
buildLayout(chartKey)    fresh deep copy of the theme layout, plus the Y-axis title. THE ONLY place
                         that assigns yaxis, asserted by a test that walks every function body
renderChart(chartKey)    Plotly.react only, never newPlot: one render path
renderActiveGroup()      iterates "#charts .chart:not([hidden])" and renders by dataset.chart
init()                   parses the embedded JSON, stops on a schema_version mismatch, builds state,
                         renders; bound on DOMContentLoaded
setMode, setDeck,        state setters; each re-renders the active GROUP
setGroup, setValueMode
setEntity(k, id)         re-renders ONLY that chart — no sibling chart is affected, and a group
                         re-render would redraw up to six figures for one selector change
```

`syncPressed(containerId, datasetKey, value)` is **internal, not exposed**. It is generic over the
container and the `data-` attribute, and is reused by the mode toggle, the level nav and the value
toggle. Epic 4 should reuse it for any new toggle rather than writing a fourth variant.

**The group-render decision, taken in ticket-023 and cited by 025 and 026:** all charts of the
active group render **stacked**, only the active group renders at all, and switching level is a
re-render rather than a page rebuild. Charts of inactive groups carry `hidden` and are skipped. That
is what keeps 165 plant traces from being built until the operator opens that level, and it is why
Epic 4 needs no lazy-loading strategy for rendering — see epic-04 decision E4-3, which keeps the
**payload** fully embedded for offline self-containment while rendering stays lazy by this mechanism.

**One delegated listener per control, on the container, never one per element.** `#charts` carries a
single delegated `change` listener that filters on `.entity-selector` and resolves the chart through
`closest("section.chart").dataset.chart`. This is load-bearing rather than a micro-optimisation:
Epic 4 adds 165-option plant selectors to this same mechanism, and a listener per chart would not
scale. Follow the same pattern for the plant name and code filter inputs of ticket-028.

**One deferred refactor, with its trigger.** The three toggle listeners (`#level-nav`, `#mode-toggle`,
`#value-toggle`) carry byte-identical 7-line bodies that a `bindToggle(containerId, datasetKey, apply)`
helper would collapse. The epic-03 simplifier verified by reading that the helper satisfies every
static assertion in the suite, and the orchestrator still **declined** it: the gain is about seven
lines, while decision E3-1 leaves this file with **no syntax gate at all**, so a stray brace ships a
4.5 MB document that renders nothing with every test green — and the verification cost is a human
browser walk of three controls. **Trigger to revisit:** if Epic 4 adds a fourth toggle, the helper
starts paying for itself, and ticket-028 already has to extend the manual checklist, so the browser
walk happens anyway. Do it then, as the only JavaScript change in its commit.

**Beware how much of this file is pinned at character level**, beyond the `KEYS` contract. Tests
pin the *indentation* of an early return inside `buildTraces`, the exact lines
`const layout = buildLayout(chartKey);` and `const traces = buildTraces(chartKey);`, the exact
member lines `buildLayout: buildLayout,` and `setEntity: setEntity,`, and the whole delegated-listener
expression as one contiguous string. Reindenting a function breaks a test even with behaviour
unchanged. That is the price of static-text verification under E3-1; know it before restructuring.

**`state` shape**: `{mode, deck, valueMode, entities}`. `deck` and `valueMode` are **global** and
survive a level switch and a mode round trip; `entities` is **per chart** and deliberately not
synchronised between two charts of one group. A deck that reset on level change, or two selectors
that moved together, would each be a silent usability defect that no test would catch — the manual
checklist covers both (steps 10 and 17).

---

## 7a. One live defect shipped by this epic, knowingly recorded — CLOSED 2026-09-11 by ticket-031

**The `TEMPO` Y axis has been labelled `min` while carrying seconds since ticket-025.** Found by the
Epic 4 refinement, not by any guardian, because each half is individually correct:
`FALLBACK_UNITS["TEMPO"]` is `"min"`, `buildLayout` writes `chart[KEYS.UNIT]` to the axis title, and
`payload.py` exports the raw value — while `tests/test_payload.py` positively asserts that **no
division has happened**, checking the `PL` figure is greater than 60. So the axis makes a claim the
data does not support, and the suite asserts both halves.

It is not a defect in any single ticket: ticket-018 was told to store raw values, ticket-020 to
export them unrounded, and ticket-025 to write the unit from the data. The division by
`time.unit_divisor` belongs to **ticket-031**, which is what makes the label true, and that
`test_payload.py` assertion must change with it. Recorded here rather than fixed at this boundary
because fixing it early would put the aggregation in the wrong module and pre-empt the ticket that
owns it.

**The generalisable point**: a unit label and the value it labels were specified in two different
tickets, and nothing checked them against each other. Where a label asserts something about data
produced elsewhere, one of the two tickets has to own the correspondence — or a test does.

**Closed 2026-09-11 by ticket-031, with the measurement.** `aggregate_times` in
`dashboard/scalars.py` now divides by `time.unit_divisor` exactly once — `grep -rln "unit_divisor"
src/` names only `config.py` and `dashboard/scalars.py` — and the renamed
`test_build_payload_custos_and_tempo_scalars_shape` no longer asserts the raw-second form. On
`caso_a`/`03/03/2024`, reproduced independently by the ticket-031 guardian from the fixture and the
shipped `settings.json`: the `PL` etapa alone was **4492.11 s**, the `PL` group sums its three
distinct etapas to **8905.16 s**, and the payload now carries `round(8905.16 / 60.0, 2) =` **148.42
min**. The axis label and the value it labels finally agree.

The raw-second references that remain in `tests/test_consolidate.py`,
`tests/test_fixtures_sintese.py` and `tests/test_readers.py` are **correct and deliberate**: they
sit below `scalars.py`, where ticket-018 keeps seconds on purpose. Only the payload and document
layers were ever wrong.

**What the closure adds to the generalisable point.** The defect survived eight guardians because
every one of them verified a ticket against its own requirements, and no ticket owned the
correspondence. It was found by the *refinement of a later epic* reading the shipped code against
its own plan — which is an argument for refining late epics against the built artefact rather than
against the plan alone, and the reason epic 5's refinement should re-read `payload.py`,
`scalars.py` and the asset before it writes anything.

## 8. Process facts

**Epic 3 result: 8/8 tickets, 24 points, quality 1.00 on every ticket and every dimension**, 475
tests, 99 % coverage, readiness avg 0.9875. Compare Epic 2: quality avg 0.971, min 0.88. The
difference is not luck — Epic 3 was the first epic refined *with* the defect catalogue in hand, and
the refinement screened its own output against the eight known shapes before returning, catching
three unsatisfiable criteria and three can-never-fail commands in its own drafts.

**The defect count moved the right way.** Of the plan's fourteen spec defects, **six came from Epic 2
and only two from Epic 3** — and both Epic 3 defects were found by the agents implementing them
rather than by rework afterwards. Both were internal-consistency errors that no up-front screen
catches without reading the whole document against itself: a Definition-of-Done item requiring a test
to pass unchanged that the ticket's own requirements forced to change (023), and a cross-reference
naming section 6 of a document whose section 6 is about something else (024).

**A new failure class appeared, distinct from the spec defects: cross-ticket constraint collisions.**
Twice, in consecutive tickets, a legitimate assertion from an earlier ticket blocked a legitimate
requirement of a later one. Neither document was wrong on its own; the incompatibility only emerged
from the interaction. Ticket-025 needed an unquoted object key because the mode literal was pinned
to one occurrence; ticket-026 could not use `getElementById` because the container's DOM id happens
to equal a payload key. **Both were symptoms of one over-broad assertion**, which counted quoted
literals over the raw file text and so conflated "a payload object is indexed with this literal"
with "a string equal to a payload key appears anywhere, comments included". Narrowed at the boundary
to scan only the `KEYS` declaration plus actual index syntax, with proof it still catches
`payload["charts"]`, `chart["series"]` and `chart[ "unit" ]` while allowing
`getElementById("charts")`, `"#charts"` selectors and prose. **Lesson: when a contract test forces a
workaround twice, fix the test, not the code** — and record the workaround in the ticket so the
third author does not invent a third one.

**Specialist-initiated break-testing became the norm.** Tickets 024, 025 and 026 each mutated their
own assertions unprompted to prove they can fail — 024 removed an attribute and injected a duplicate
literal, 025 shipped a 16-case parametrized non-vacuity test over in-memory copies of the asset, 026
did seven. This started as an orchestrator demand after Epic 1 shipped a genuinely vacuous test and
is now self-sustaining. Guardians were asked to spot-check the claims rather than accept them, and
every spot-check held: a break-test claimed but not performed would be worse than none.

**The staged-state pattern worked and is worth copying.** Ticket-021 deliberately emitted no
`aria-pressed` and no `disabled`, so tickets 023 and 024 owned the initial state of the controls they
define, and their acceptance criteria could not pass before they existed. Each ticket withholds
exactly what the next one owns. Verified by greps whose scoping is itself measured — `builder.py`
legitimately contains the word `disabled` because it calls `enabled_specs(disabled=...)`, and the
generated document contains both words because the inlined plotly bundle has `aria-pressed` 3 times
and `disabled` 78.

**Specialist self-reported test counts are unreliable.** Three in a row were wrong: 31 against an
actual 29 (ticket-017), then 13 and 33 against an actual 10 and 19 (ticket-020), which the
orchestrator propagated into a dispatch without recounting. Since then every dispatch demands the
count from `pytest --collect-only -q` and every guardian recounts. No count has been wrong since.
Never cite a count you did not measure.

**Not every module is at 100 % coverage**, contrary to what several dispatches asserted: `config.py`
is at 94 %, `charts/registry.py` at 99 % and `logging_setup.py` at 95 %, all pre-existing and all
accepted by their own tickets' guardians. The project floor is 80 % and the total is 99 %. Stating
the stronger claim invites a specialist to "fix" something outside its scope, and one did flag it.

**A declared dispatch order can be wrong.** The refinement said tickets 023 and 024 could run "in
either order", but ticket-024 syncs `aria-pressed` through a helper ticket-023 introduces, so the
order is forced. Had 024 run first it would have invented its own helper and 023 would have added a
second — duplication that passes every test, because each ticket tests only its own. Only reading the
two texts against each other catches it. **Check the dependency claim against the ticket bodies, not
just the graph.**

**Parallel dispatch keeps working** where file sets are disjoint: 019 ∥ 020 ran with zero
contamination after the orchestrator pre-created the two `dashboard/` package markers that both
tickets were entitled to create. Removing a shared-file collision before dispatch costs a minute; a
false scope violation inside a guardian costs a full re-verification. Everything from 021 onward was
strictly sequential, because each ticket extends the asset the previous one wrote.

**The `bash -lc` wrapper is broken by apostrophes, single quotes and backticks alike.** It bit three
times in this epic, once leaving three empty files in the repository root from an ambiguous
redirect. The rule already recorded in the Epic 2 learnings stands and should simply be followed:
for any text containing quotes, use the Read/Edit/Write tools rather than a heredoc.

*Provisional entries from before the boundary, retained:*

- **Specialist self-reported test counts are unreliable.** Three in a row were wrong: 31 against an
  actual 29 (ticket-017), then 13 and 33 against an actual 10 and 19 (ticket-020), which the
  orchestrator propagated into a dispatch without recounting. Since then every dispatch demands the
  count from `pytest --collect-only -q`, and every guardian is told to recount. Never cite a count
  you did not measure.
- **Not every module is at 100 % coverage**, contrary to what several dispatches asserted:
  `config.py` is at 94 %, `charts/registry.py` at 99 % and `logging_setup.py` at 95 %, all
  pre-existing, all accepted by their own tickets' guardians. The project floor is 80 % and the
  actual total is 99 %. Stating the stronger claim in a dispatch invites a specialist to "fix"
  something outside its scope.
- **A declared dispatch order can be wrong.** The refinement said tickets 023 and 024 could run "in
  either order"; ticket-024's own requirement 4 syncs `aria-pressed` through a helper ticket-023
  introduces, so the order is forced. Had 024 run first it would have invented its own helper and 023
  would have added a second — duplication that passes every test, because each ticket tests only its
  own. Only reading the two texts against each other catches it.
- **Parallel dispatch keeps working** where file sets are disjoint: 019 ∥ 020 ran with zero
  contamination, after the orchestrator pre-created the two `dashboard/` package markers that both
  tickets were entitled to create. Removing a shared-file collision before dispatch costs one minute;
  a false scope violation in a guardian costs a full re-verification.
