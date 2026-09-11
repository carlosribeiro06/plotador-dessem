# Epic 04: Plant-Level and Scalar Charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **refined** — all six tickets were refined on 2026-09-11 with the learnings of
> Epics 1 to 3 and independently scored for readiness (mean 0.99, floor 0.85). No `[OUTLINE]`
> marker remains.

## Goal

Complete the chart catalogue: the eight hydro-plant charts and the thermal-plant chart with the
BI-style name and code filters of spec section 3, the `CUSTOS` and `TEMPO` grouped bar charts by
deck date, and the enforcement of the output size strategy.

## Scope

In scope: hydro and thermal plant chart rendering, the independent and combinable name and code
filters over the plant registry embedded in the HTML, the two scalar bar charts with their
configurable groupings, and the HTML size measurement, logging and warning.

Out of scope: the theme, payload, HTML shell, renderer core, view modes and difference toggle, which
are Epic 3; the pipeline wiring, the real-data run, the parity check, the documentation and the
legacy removal, which are Epic 5.

## Tickets

| Ticket | Title | Points | Detail |
| ------ | ----- | ------ | ------ |
| ticket-027 | Render the hydro plant charts | 3 | refined |
| ticket-028 | Implement the name and code filters | 3 | refined |
| ticket-029 | Verify the thermal plant chart end to end | 1 | refined |
| ticket-030 | Render the cost bar charts | 4 | refined |
| ticket-031 | Render the computational time bar charts | 2 | refined |
| ticket-032 | Enforce the output size strategy | 2 | refined |

Total: 15 points, revised from the outline estimate of 14 by the two rulings below.

> **Ticket-029 is a verification ticket, not a rendering one** — established by the refinement
> on 2026-09-11. The thermal level needs no source change at all: ticket-027 generalises the plant
> rendering path and ticket-028 adds the filters, and together they already cover `GTER_UTE`. Its
> requirement 7 therefore forbids touching any source file and requires stopping and reporting if a
> change turns out to be necessary. Points drop from 2 to 1 accordingly. **The filename still reads
> `ticket-029-render-thermal-plant-charts.md` deliberately**: three sibling tickets, the plan
> README and `.implementation-state.json` all reference it by that exact string, so renaming it
> would buy a cosmetic match at the cost of five cross-reference edits and a stale-reference risk.
> The title in the table above is the authoritative one — brief the deliverable from the ticket
> body, never from the filename.

> **Ticket-030 stays whole at 4 points and 7 files.** Readiness scoring put it at 0.96, clearing
> the 0.85 floor, with the only deduction on atomicity, where 7 files exceeds the 6-file ceiling.
> The ticket names its own seam — requirements 1 to 5 are Python aggregation, 6 to 9 are
> renderer changes — but splitting it would renumber every later ticket across five documents,
> and the numbering of this plan is load-bearing. Dispatch it whole; if the specialist stalls or
> the guardian finds the diff too wide, the seam is already identified and applying the split
> costs nothing at that point.

## Dependency Order

```text
ticket-027 -> ticket-028 -> ticket-029
ticket-030 -> ticket-031
ticket-029 ─┬─> ticket-032
ticket-031 ─┘
```

The graph above states the **data** dependencies. The **dispatch** order is stricter and strictly
sequential — 027, 028, 029, 030, 031, 032, one at a time — because every ticket from 027 to 031
writes `payload.py`, `builder.py` or `assets/dashboard.js`, so the `030 -> 031` branch cannot in
fact run beside `027 -> 028 -> 029` without a write collision. Ticket-030 records this in its own
Dependencies block as a dispatch-order constraint rather than a graph edge.

## Refinement Inputs Required

- `epic-03-learnings.md`: the payload key names, the renderer function boundaries, the decision on
  whether a group shows all charts at once or one at a time, and the browser testing approach.
  **Still pending** — Epic 3 is in execution.
- ~~Answers to master plan open questions 1 to 3.~~ **RESOLVED** — see E4-1 and E4-2 below.

## Resolved Epic Decisions

Settled 2026-09-11 by orchestrator ruling, under the developer's standing authorisation to take the
recommended option and record it for later audit. Binding on the refinement of tickets 027 to 032.

### E4-1 · Cost total: the sum of `costs.total_parcels`, never a hard-coded pair

Master plan open question 1 is already answered by the `settings.json` contract, which ships
`costs.total_parcels = ["PRESENTE", "FUTURO"]`. Ticket-030 sums exactly the parcels that key names,
so including `VIOLACOES` or `PEQUENAS PENALIDADES` is a configuration edit rather than a code change,
which is the whole point of the key existing. Two consequences for refinement: the total must **not**
be computed as a literal `PRESENTE + FUTURO` anywhere, and a parcel named in settings but absent from
`CUSTOS.parquet` is a **Portuguese warning plus omission**, never a crash — the same degradation rule
as decision 18, because a study that omits a parcel is still worth comparing.

### E4-2 · Both members of each UHE ambiguity pair stay enabled — closed by existing work

Master plan open questions 2 and 3 were answered in Epic 2 rather than deferred: ticket-011's
catalogue ships `VARMF_UHE` (hm3) alongside `VARPF_UHE` (%), and `QAFL_UHE` (afluente) alongside
`QINC_UHE` (incremental), each carrying a distinguishing curated title and an explanatory `notes`
field. Decision E3-2 then made those curated titles the chart headings precisely so the
disambiguation survives. Nothing remains to decide; refinement must not collapse either pair.

### E4-3 · The plant payload stays fully embedded; size is measured, not avoided

The feature is **one self-contained HTML file that opens offline**. Any lazy strategy that fetches
data on demand needs a server or sibling files and breaks that requirement outright, so the trade is
not available. Size is therefore managed rather than dodged, by three means already in place or
specified:

- rounding to `output.decimals`, which ticket-020 already applies;
- **omitting entities whose arrays are entirely `null`**, so the non-rectangular coverage of decision
  17 costs nothing in bytes (justification corrected 2026-09-11 — see the note below);
- ticket-032 measuring the document, logging the size and warning past `output.size_warning_mb`.

> **Justification corrected 2026-09-11 during refinement.** The original wording motivated the
> omission rule with "`VCALHA_UHE` covering 92 of 165 plants should not ship 73 arrays of pure
> `null`". That example is impossible: `VCALHA_UHE` is a **disabled** spec and is never read, and
> under decision 16 its entity list would come from its own file anyway, so those 73 arrays cannot
> exist. The rule is still right, for a different reason the refinement established:
> `consolidate._load_series` builds `all_entity_ids` as the **union over scenarios and decks**, so a
> plant present in one scenario receives a full-length all-`None` array in the scenario that lacks
> it. That is the array the omission saves. Defect shape 1 of the catalogue — a requirement whose own
> justification does not describe what it prescribes — committed by the orchestrator in this very
> overview, and caught by the refinement reading the justification against the code.

Lazy **rendering** is a separate matter and already the design: ticket-023 renders only the active
group and leaves the other groups hidden, so 165 plant traces are never built until that group is
opened. Refine ticket-032 **together with** ticket-027, as this overview requires, and note the
measured figure that motivates it: the Epic 3 payload alone reaches roughly 56 MB at 30 decks times
3 scenarios, already past the 50 MB default warning, before any plant chart is added.

### E4-4 · Filtering by submarket and equivalent reservoir is out of scope

The spec asks for a name filter and a code filter. `Registries.hydro[code]` does carry
`submarket_code` and `ree_code`, so the capability is nearly free — which is exactly why it is
tempting and exactly why it stays out: it is unrequested scope in an epic that already owns nine
chart renderings, two filters and the size strategy. Consistent with the epic-03 ruling on URL-hash
state. Reopen only on an explicit request from the developer.

### Note for ticket-031 refinement

`time.stage_groups` maps `PL` to the three **distinct** etapas `PL`, `PL.Int.Fix` and
`PL.CalcCMO`, and `time.unit_divisor` is `60.0`. An epic-02 boundary defect is relevant here: the
store overwrote repeated rows of the *same* etapa, destroying 67.8 % of the PL time, and the fix sums
those repeated executions inside `consolidate`. Grouping distinct etapas remains entirely ticket-031's
job and now operates on correct inputs. Do not re-sum what consolidation already summed.

## Open Questions for the Epic

- ~~Whether the plant series stay fully embedded or need a lazy strategy.~~ **RESOLVED** — see E4-3.
- ~~Whether the plant filters also offer submarket and equivalent-reservoir filtering.~~
  **RESOLVED** — see E4-4.
