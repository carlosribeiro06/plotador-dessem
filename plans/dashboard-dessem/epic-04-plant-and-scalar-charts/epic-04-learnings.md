# Epic 04 Learnings — Plant-Level and Scalar Charts

> Written at the epic-04 boundary, 2026-09-11. Implementation mode: Rigoroso.
> Audience: whoever refines and executes epic 5, and whoever maintains this dashboard afterwards.
> Sections 9 to 10 were written at the boundary, after ticket-032 and the boundary fan-out.

Epic 4 delivered six tickets (15 points) at **quality 1.00 uniformly**, adding 3,831 lines across
15 files. It also produced **seven spec defects and two cross-ticket collisions**, one of the
collisions authored by the orchestrator. The defects are the more useful output, because five of
the seven share one shape and that shape is now cheap to prevent.

---

## 1. The single most valuable finding: five defects, one shape, one cheap check

Spec defects **15, 18, 19, 20 and 21** are the same mistake in five costumes: **a claim about the
test suite, made without running the test suite.**

| # | Ticket | The claim | The reality |
| - | ------ | --------- | ----------- |
| 15 | 027 | "no existing assertion covers an all-`null` array" | One did. `_hand_built_data()` builds a one-stage axis and a test stored `values=[None]`, which is trivially all-`None`. |
| 18 | 030 | `tests/test_renderer_value_mode.py` already has a `_function_body` helper | Zero occurrences at `HEAD`. |
| 19 | 030 | "the thirteen members present after ticket-026" | Ticket-028 had already added a fourteenth. |
| 20 | 031 | `_settings_dict` "matching the repository's own values" | It hard-coded `time.stage_groups = {"PL": ["PL"]}` against a shipped `settings.json` carrying three groups. A test helper misdescribing itself. |
| 21 | 031 | the three `test_payload.py` assertions are "the only assertions in the repository that this ticket's requirements force to change" | A fourth, in `test_charts_costs.py`, was already there. |

Every one was catchable in **seconds** — one `grep`, or one `pytest -k`. Every one survived
refinement *and* independent readiness scoring *and*, in three cases, an orchestrator amendment,
because **all three of those verify by reading.** Two of them (15 and 21) were caught only when a
specialist ran the suite and watched it fail.

**The rule for epic 5 and for any future plan on this repository:** any ticket sentence asserting
what the test suite does or does not contain must be **measured before the ticket is scored**, not
read. Two of the five defects were load-bearing rather than cosmetic — defect 15 made two
requirements logically incompatible with a pinned assertion, and defect 20 was the reason a
mandated assertion value was unreachable.

### Defect 17 was not a defect. The orchestrator's ruling on it was the error.

> **Retracted 2026-09-11 at the epic-04 boundary review, and this retraction is the more useful
> lesson of the two.**

The original entry read: ticket-030 asserted "In the real data `FUTURO` is about 2.3e8 R$ while
`PRESENTE` is about 5.9e4 R$"; those figures "exist nowhere in the repository", the real data lives
under `exemplo/` which no agent may read, so the refinement could not have measured them; therefore
the precision was false and was removed.

**Every part of that is wrong.** `plans/dashboard-dessem/reference/parquet-schemas.txt` is
**tracked, committed and readable** — 84 KB, listed in `planning-context.md`'s own Sources table —
and lines 92-93 give `PRESENTE 5.866757e+04` and `FUTURO 2.284204e+08`. Ticket-030's figures were
correct and verifiable. The orchestrator searched for the *rendered figures* (`grep "2.3e8"`)
instead of asking whether the *underlying data* was accessible, then generalised from a failed
string search to a claim about what the plan can know.

Three things follow, in increasing order of importance.

1. **A ticket amendment deleted verified facts as fabrications.** Both ticket-030 and ticket-031
   were amended, and the checklist step lost its magnitudes.
2. **The generalisation was wrong for this plan.** Agents here cannot read `exemplo/`, but they can
   read a 60-file schema dump of it — including dtypes, unique-value sets, row counts and three
   sample rows per file. The correct rule is the opposite of the one recorded: **check
   `reference/parquet-schemas.txt` before declaring a data fact unknowable.**
3. **The mis-ruling disarmed the gate that would have caught a live 1000x error.** Replacing the
   cost magnitudes in checklist step 29 with "read and record the two magnitudes" removed the only
   order-of-magnitude expectation the cost chart had — and the boundary review then found that
   `FALLBACK_UNITS["CUSTOS"]` says `R$` for values that are in `10^3 R$`. An operator with the
   expected magnitudes in hand would have compared `2.28e8` on a `R$` axis against a future cost
   that `CFU_SIN` reports as `2.29e11 R$`. See section 10.2.

**The meta-lesson, which is the one worth carrying:** the "measure, do not assert" rule this plan
enforces can be applied to the wrong quantity. Measuring that a string is absent is not measuring
that a fact is unverifiable. When a claim looks unsupported, the question is not "can I find this
sentence" but "what would have to be true for this to be checkable, and is that available".

The one part of the original entry that survives: **step 30's "tens to a few hundred" minutes band
is genuinely unmeasured, and wrong.** `TEMPO.parquet` (dump lines 709-718) holds
`{48, 438, 469, 564, 714, 786, 1056, 1086, 6726}` seconds. Any single etapa is between **0.8 and
112.1 minutes**, and the `Leitura` group is one row in 438-1086 s, i.e. **7.3 to 18.1 minutes** —
below the stated band. An operator following step 30 literally would record a FAIL on a correct
chart, which is the epic-03 H1 class. Replace the band with the measurable relation
(`TOTAL == MILP + PL + Leitura`, and `TOTAL` ≈ Σ`tempo`/60 = 198.1 min on the reference deck) and
have the operator record values rather than judge them against an invented range.

## 2. Cross-ticket collisions 6 and 7: the same shape, one ticket apart

Both are: **a test written by ticket N encoding a precondition that ticket N+1 exists to destroy.**

- **Collision 6 — the orchestrator's own error.** Ticket-028's requirement 12, written *that day* to
  fix spec defect 16, had the specialist assert that the plant-filter checklist section "sits last
  in the file". Ticket-031 requirement 9 appends a section 9. The fix for defect 16 reproduced
  defect 16's own shape one level up. Resolved by scoping the assertion to section 8's own slice.
- **Collision 7.** Ticket-030's `test_payload_tempo_scalars_still_has_five_raw_etapa_keys_proving_the_pass_through_branch`
  asserted `TEMPO` was still un-aggregated. Ticket-031 requirement 1 routes it through
  `aggregate_times`. Measured as `assert 2 == 5`.

**The rule:** never assert *"nothing follows"* or *"X is unchanged"* when a later ticket is
scheduled to follow or change it. Before pinning a document's or a payload's **shape**, check
whether a later ticket changes that shape.

**The second rule, which is what made both resolutions good:** when you replace a colliding
assertion, make the replacement **stronger than what it replaced**, never merely green. Collision
7's original was a bare `len(tempo) == 5` naming no key — the vacuous-length shape this plan had
already recorded twice. Its replacement asserts the exact key set `{"PL", "TOTAL"}` under the
calling module's own narrow `stage_groups`, which carries three properties the length could not
distinguish: that `TEMPO` is no longer pass-through, that aggregating `CUSTOS` does not disturb it,
and that the time path honours the settings of the module calling it.

## 3. The verification technique this epic invented: build the wrong implementation and measure it

Confirming that a guard *has a test* is weak. Twice in this epic a guardian instead **built the
wrong implementation and measured what it produced**, and both times the number was the argument.

- **Ticket-030, E4-1's cost total.** Patching `scalars.py` to sum whichever parcels happen to be
  present at a cell yielded `TOTAL["caso_b"]["04/03/2024"] = 230.0` — the `FUTURO` value alone,
  silently reported as a total — against a raw mapping missing that cell from `PRESENTE`.
- **Ticket-031, the lenient/strict asymmetry.** Making `TOTAL` lenient yielded `15.0` where the
  correct answer is to omit the cell. Making a group strict yielded `None` where the correct value
  is `10.0`, needlessly dropping a bar.

**Use this wherever a requirement guards against a wrong *number* rather than a crash.** A crash
announces itself; a wrong cost or a wrong runtime does not, and "the test passes" cannot distinguish
a guard that works from a guard that is never exercised.

## 4. The scalar aggregation contract (`dashboard/scalars.py`)

Public API, all three functions:

```python
aggregate(chart_key: str, raw: ScalarsByName, *, settings: Settings) -> ScalarsByName
aggregate_costs(raw: ScalarsByName, *, parcels: Sequence[str], decimals: int) -> ScalarsByName
aggregate_times(raw, *, stage_groups, unit_divisor, decimals) -> ScalarsByName
```

`aggregate` dispatches `CUSTOS` to `aggregate_costs`, `TEMPO` to `aggregate_times`, and passes every
other key **through by identity**. `payload.py`'s `SCALAR_BY_DECK` branch is its only caller.

Four invariants that are easy to break and were each paid for:

1. **No parcel or group name is hard-coded anywhere in `src/`.** `grep -rn "PRESENTE" src/` and
   `grep -rn "FUTURO" src/` must return nothing — a ticket-030 DoD gate, and it caught two prose
   occurrences (a docstring and a JS comment) before they shipped. The total is the sum of exactly
   what `costs.total_parcels` names, so adding `VIOLACOES` is a settings edit.
2. **`TOTAL` in `costs.total_parcels`, or as a `time.stage_groups` key, is a `ConfigError`** — it
   would be a circular definition.
3. **A name configured but absent from the data is a Portuguese warning plus omission, never a
   crash** (decision E4-1, mirroring master-plan decision 18).
4. **The lenient/strict asymmetry of section 3.** A group's own sum omits a cell only when *every*
   present member lacks a value there; `TOTAL`'s sum over groups omits a cell unless *every* emitted
   group has a value. The reason is presentational: a group's member etapas are internal to one bar,
   so a partial sum costs that bar precision, while the groups are separately displayed bars, so a
   partial `TOTAL` reports a number that is simply wrong.

**The division by `time.unit_divisor` happens exactly once, in this module.**
`grep -rln "unit_divisor" src/` must name only `config.py` and `dashboard/scalars.py`. Everything
below `scalars.py` — `consolidate.py`, the readers, the schemas — keeps **seconds** on purpose
(ticket-018), so raw-second references in `test_consolidate.py`, `test_fixtures_sintese.py` and
`test_readers.py` are correct, not defects.

## 5. Why the `TEMPO` label defect survived eight guardians

Epic 3 shipped an axis labelled `min` carrying seconds, and the suite **positively asserted that no
division had happened**, checking the `PL` figure exceeded 60. It asserted both halves of a
contradiction.

No guardian caught it because **every guardian verifies a ticket against that ticket's own
requirements**, and each half was correctly specified in a different ticket: 018 to store raw
values, 020 to export them unrounded, 025 to write the unit from the registry. **No ticket owned the
correspondence between a label and the value it labels.**

It was found by the **refinement of a later epic reading the shipped code against its own plan**.
That is the transferable point, and it has a direct instruction attached: **epic 5's refinement
should re-read `payload.py`, `scalars.py`, `builder.py` and the asset before it writes anything**,
rather than refining against the plan alone. Where a label, unit, or heading asserts something about
data produced elsewhere, one of the two tickets must own the correspondence — or a test must.

Closed by ticket-031, measured: `PL` was `4492.11` raw seconds for the etapa alone; the `PL` group
sums its three distinct etapas to `8905.16` seconds; the payload now carries
`round(8905.16 / 60.0, 2) = 148.42` minutes.

## 6. Document and asset facts that bite

1. **`dashboard.js` is embedded verbatim in the HTML, so it is searchable text of the final
   document.** Two consequences, each of which cost a defect: a JS *comment* containing
   `<section class="chart">` created a spurious 24th chart section for
   `dashboard_document.py`'s slicing regex; and `data-filter="code"` occurs **ten** times in a built
   document — nine in markup plus once inside the embedded asset.
2. **An unscoped literal mutation in this codebase is therefore almost always vacuous.** The
   ticket-029 guardian proved it by reproducing the trap: UHE sections precede the UTE section
   (byte offsets 80053 vs 87253), so a naive `replace(..., 1)` hits a UHE section and leaves the UTE
   occurrence intact, and the presence check still passes. **Scope every mutation to the specific
   section or function body it targets.**
3. **The same hazard applies to unscoped `text.index(...)` lookups.** Ticket-030 was told to place
   `buildBarTraces` immediately *before* `buildTraces`; doing so would make the new function's own
   `diferenca` branch the first occurrence and silently redirect an existing test's lookup to the
   wrong function. Placed after instead — measured: `buildTraces` at 3710, `buildBarTraces` at 6370,
   first quoted `"diferenca"` at 4380.
4. **`dashboard.js` must stay pure ASCII with no Portuguese string**, asserted in three modules. All
   user-facing text lives in `builder.py`. Writing a Unicode combining range literally produces real
   combining characters in the file; construct the escape rather than typing it.
5. **Member exposure is asserted by presence, never by count.** That convention is why adding
   `applyPlantFilter` (028) and `buildBarTraces` (030) broke nothing, and why defect 19's stale
   "thirteen members" was harmless. `window.DessemDashboard` now exposes 15: 13 non-getters plus the
   `payload` and `state` getters. **Keep the convention.**
6. **`KEYS` now holds 22 entries** and remains the only automated gate on payload access. Epic 4
   added `KIND` and `SCALARS`. The dot-access guard added at the epic-03 boundary
   (`_assert_no_dot_access_to_keys_values`) is scoped to seven payload-derived locals — extend that
   list when you introduce a new one.

## 7. When a requirement and a Suggested Approach disagree, the requirement wins

Established twice, and worth stating as precedence because both specialists reasoned it out
independently:

- Ticket-030: Suggested Approach step 6 gave a function placement that would break a test
  **requirement 10 explicitly asserts still holds**. The requirement is an obligation; the
  Suggested Approach is advice. Requirement won.
- Ticket-031: Suggested Approach hinted at extracting a shared helper, while requirement 1 said
  "change nothing else in the module". Requirement won; `aggregate_costs` stayed byte-identical.

## 8. Process facts

- **The refinement's falsifiable prediction held.** It concluded that the thermal level would need
  *no source change* — that ticket-027's plant path plus ticket-028's filters already covered
  `GTER_UTE` — and cut ticket-029 from 2 points to 1 on that basis. Requirement 7 was written to
  fail loudly if the prediction was wrong, forbidding any source edit and requiring a stop-and-
  report. **It never fired.** Ticket-029's whole diff is one test file. That is evidence the epic-027
  generalisation is real rather than a hydro-only path with a generic name.
- **Ticket-030 was dispatched whole at 7 files despite an atomicity deduction** (composite 0.96),
  because splitting would renumber later tickets across five documents. It delivered 5/5 at 1.00 and
  the specialist never asked for the pre-identified seam. The ruling was right, and the seam being
  *named in advance* is what made dispatching it whole safe.
- **Readiness scoring caught nothing that mattered here.** Mean 0.99 across six tickets, no defect
  shape flagged — and seven defects followed. Scoring reads; it does not run. That is the argument
  of section 1.
- **Specialists escalated four times across the epic and were right every time.** Two escalations
  came from the same ticket (031). Every escalation was preceded by a *measurement* — the failing
  test, the missing grep hit, the byte offsets — never by an opinion. That is the standard.
- **A specialist finding its own test wrong is the harder and better call.** The ticket-031
  specialist's first `-0.0` test was arithmetically impossible; rather than adjust the code it
  traced *why* — `TOTAL` sums already-normalised group values, and IEEE 754 addition of a value and
  its exact negation yields `+0.0`, so `-0.0` is reachable only at the group conversion step — and
  retargeted the test at the path that can produce it.
- **Sequential dispatch was mandatory and stayed so.** The graph shows `030 -> 031` as a branch
  independent of `027 -> 028 -> 029`, which is true of the *data* dependencies, but every ticket
  from 027 to 031 writes `payload.py`, `builder.py` or `dashboard.js`. Tickets 030 and 031 edit the
  **same test function** in `test_payload.py`. Parallelising any pair would have collided.

## 9. Ticket-032: measuring an artefact you are not allowed to shrink

Decision E4-3 forbids every lazy strategy, because the deliverable is **one self-contained HTML
file that opens offline** — fetching needs a server or sibling files and breaks the requirement
outright. So size is managed by measurement, not avoidance, and ticket-032 is where that becomes a
gate.

**The assertion is the interesting part, and it is a template worth reusing.** An "under 50 MB"
check on fixture data **cannot fail** — it would have been the fourth instance of the vacuous shape
this plan has recorded. The shipped test instead pins the **controlled share**,
`bytes_html - bytes_plotly`, measured at **238,059** bytes inside `[150_000, 400_000]`, with
*permanent* assertions that the doubled and halved values fall outside the bound. The guardian
confirmed the bound is load-bearing by widening the maximum to `999_999_999` and watching the
doubling assertion fail. The lesson generalises: **when a quantity is dominated by a constant you
do not control, assert the part you do control.** The 4.29 MB plotly bundle is 95 percent of the
document and would swamp any whole-document bound.

Three facts to carry forward:

- `plotly_bundle_bytes()` is `functools.cache`-memoised — safe, because the value is a property of
  the installed package and constant per process, and the cached object is an `int`, not the 4.3 MB
  string. Its test asserts `cache_info().hits == 1` and `.misses == 1` after a `cache_clear()`,
  which is order-independent and discriminates real memoisation.
- `output_volumes` cannot disagree with `build_html`: both derive `graficos` from the same
  `enabled_specs(disabled=...)` call, and `bytes_plotly` is exactly the inlined length because
  `build_html` embeds `get_plotlyjs()` verbatim through its single `Template.substitute`.
- **AC5 is the first test proving ticket-027's omission rule pays in bytes** rather than merely
  behaving: an all-`None` `GHID_UHE` entity is omitted and the document shrinks by 2,952 bytes.
  Filling the "omitted" store with real values makes it fail at `0 >= 1500`, so the saving is the
  rule and not an artifact of building two stores.

One judgment call was assessed rather than accepted. The specialist treated the ticket's four
non-vacuity mutations as **development-time discipline** — mutate, confirm failure, restore, with
`md5sum` checked both ways — rather than committed tests, because two of them require mutating
production comparison logic and cannot ship broken without a mutation-testing dependency. The
guardian agreed, for a reason worth recording: AC5 as shipped does not merely compare byte counts,
it structurally asserts the extra entity's `<option>` and `series` key are present in one document
and absent in the other, which is a stronger regression guard than a byte delta. **Permanent
structural assertions can substitute for uncommittable mutations; a bare numeric delta cannot.**

## 10. Two defects the boundary found that no per-ticket gate could

Both were found by the boundary `code-simplifier` and `code-reviewer`, not by any guardian, and
neither is visible to a green suite.

### 10.1 The generated HTML was not byte-for-byte reproducible

`scalars.py` built `pairs: set[tuple[str, str]]` and iterated it to insert the `{scenario:
{deck_key: value}}` keys of every aggregated scalar series. **Set iteration order depends on the
per-process randomised string hash**, so the same inputs produced byte-different HTML across runs.

Verified rather than assumed, and the first attempt nearly missed it: three hash seeds gave the
same output, which looked like a refutation. Confirming that `PYTHONHASHSEED` was actually
propagating (the `hash("abc")` values differed) and widening the sample showed seed 777 reversing
even the outer key order. On the real function the JSON bytes visibly diverge.

Nothing in the rendered dashboard is affected — dict equality ignores order and no chart reads by
position — and `build_payload`'s documented promise is only that two calls return *equal* payloads.
The damage is to audit: two archived official runs of the same deck compare as different, and
`rules/python.md` requires deterministic data ordering for formal studies. **No test could catch
it, because the only repeatability test compares two builds inside one process.** Fixed with
`sorted()` at three sites; the full suite then passed 601/601 under `PYTHONHASHSEED=777`, proving
nothing depended on the arbitrary order.

### 10.2 The `CUSTOS` axis was wrong by a factor of 1000 — see section 5's shape

`FALLBACK_UNITS["CUSTOS"]` declared `R$` for values that are in `10^3 R$`. `CUSTOS.parquet` has no
unit column and `METADADOS_EXECUCAO` has no `unidade` column, so that fallback is always what the
chart shows.

The arithmetic, from the committed `reference/parquet-schemas.txt` and verified twice:

| Anchor | Reported | `CUSTOS` read as `10^3 R$` | Ratio |
| ------ | -------- | -------------------------- | ----- |
| `COP_SIN` (`10^3 R$`), `406.6581 x duracao` summed over 144 h | 58,558.8 | `PRESENTE` = 58,667.6 | **1.0019** |
| `CFU_SIN` (`10^6 R$`) = 228,917.04 | 2.2892e11 R$ | `FUTURO` = 2.2842e11 R$ | **0.9978** |

Read as `R$`, `FUTURO` is ratio **0.000998** against `CFU_SIN` — exactly 1000x low. Physical sanity
agrees: 58,667 R$ of present operating cost for the whole SIN over 144 hours is absurd by four
orders of magnitude.

**This is section 5's defect shape exactly, on a chart shipped two epics later.** The value comes
from ticket-018, the fallback unit from ticket-010, the axis label from ticket-025, the chart from
ticket-030 — each correct against its own ticket, and **no ticket owned the correspondence.** There
was also no gate at all: unlike `TEMPO`, whose `"min"` is pinned by a test, nothing asserted
`CUSTOS`'s unit, and no checklist step read the cost axis.

**And the reason it had no gate was an orchestrator mis-ruling** — see the retraction under section
1. Removing the cost magnitudes from checklist step 29 removed the only order-of-magnitude
expectation the chart had. The fix therefore closes the seam rather than the instance: the unit,
plus a test pinning it with the arithmetic in a comment, plus a checklist step carrying reference
magnitudes.

### 10.3 A third finding, still open by design: a configurable divisor under a hard-coded label

`time.unit_divisor` is a documented tunable that `config.py` validates only as positive;
`FALLBACK_UNITS["TEMPO"]` is the constant `"min"`. Setting `"unit_divisor": 1.0` yields seconds
under an axis reading `min`, with every test green — **the defect ticket-031 just closed,
re-introducible by a one-line settings edit**, because the tests pin the two halves separately and
never together. The fix makes one side own the other and adds the test that asserts them *as a
pair*. The general rule: **where a label and a value are separately configurable, a test must
assert their correspondence, not each half.**

## 11. Open items handed to epic 5

1. **The manual browser walk is outstanding for the whole feature**, by design under E3-1 — the
   checklist now runs to 32 steps across 9 sections and no step of it has been walked in a browser.
   Epic 5's real-data run (ticket-034) is the natural moment.
2. **The cost-chart legacy-parity tension, owned by ticket-035.** `Plotadores/Custos.py` emits
   **three** separate cost figures with their own Y axes; the new dashboard ships **one** grouped bar
   chart, deliberately, and one series may be invisible on a shared linear axis. The parity check
   must not be read as passing merely because the totals agree — refine ticket-035 to compare
   *presentation* as well as values.
3. **Ticket-038 must not run before ticket-035.** It deletes `Plotadores/`, which is the parity
   check's reference implementation. The epic-05 order is strictly sequential, so this holds — do
   not reorder. Its open question about deleting outright versus moving to `legacy/` now has an
   argument on the record: the cost-presentation decision is unresolved and its only evidence is
   `Plotadores/Custos.py`.
4. **Ticket-038's `__pycache__` question is already answered** by measurement: nothing is tracked
   and `.gitignore` covers it. Drop the question.
5. **Three decisions the developer has not seen**, all non-blocking: the cost-scale caveat (now to
   be *measured* by checklist step 30 rather than asserted); plant labels carrying the name without
   the code; and `output.decimals` being global rather than per chart, which no ticket owns.
