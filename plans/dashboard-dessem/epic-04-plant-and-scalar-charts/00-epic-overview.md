# Epic 04: Plant-Level and Scalar Charts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **outline** — every ticket in this epic carries the `[OUTLINE]` marker and must be
> refined with the learnings of Epics 1 to 3 before dispatch.

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
| ticket-027 | Render the hydro plant charts | 3 | outline |
| ticket-028 | Implement the name and code filters | 3 | outline |
| ticket-029 | Render the thermal plant charts | 2 | outline |
| ticket-030 | Render the cost bar charts | 2 | outline |
| ticket-031 | Render the computational time bar charts | 2 | outline |
| ticket-032 | Enforce the output size strategy | 2 | outline |

## Dependency Order

```text
ticket-027 -> ticket-028 -> ticket-029
ticket-030 -> ticket-031
ticket-029 ─┬─> ticket-032
ticket-031 ─┘
```

## Refinement Inputs Required

- `epic-03-learnings.md`: the payload key names, the renderer function boundaries, the decision on
  whether a group shows all charts at once or one at a time, and the browser testing approach.
- Answers to master plan open questions 1 to 3: the cost total parcels, and whether both members of
  each UHE ambiguity pair stay enabled.

## Open Questions for the Epic

- The plant-level payload is the size driver: 165 plants times 68 stages times 8 charts times the
  number of scenarios and decks. Refinement must decide whether the plant series stay fully embedded
  or whether a lazy strategy is needed, and ticket-032 must be refined together with ticket-027
  rather than after it.
- Whether the plant filters also offer filtering by submarket and by equivalent reservoir, which
  the registry supports and which the spec does not request.
