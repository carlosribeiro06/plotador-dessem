# Epic 03: Dashboard Core

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **outline** — every ticket in this epic carries the `[OUTLINE]` marker and must be
> refined with the learnings of Epics 1 and 2 before dispatch.

## Goal

Turn the `DashboardData` produced by Epic 2 into a single self-contained HTML file that opens
offline with the ONS visual identity and renders the SIN, submarket and interchange charts for every
scenario, with the view-mode toggle, the deck selector, the level navigation and the
Absoluto/Diferença toggle all working.

## Scope

In scope: the brand theme module, the compact JSON payload, the HTML shell with inlined
`plotly.min.js`, inlined CSS and JavaScript and the base64 logo, the JavaScript renderer core, the
view-mode and deck controls, the difference toggle, and the SIN, submarket and interchange chart
rendering.

Out of scope: plant-level charts and their name and code filters, the `CUSTOS` and `TEMPO` bar
charts, and the output size enforcement, which are Epic 4; pipeline wiring, the run against real
data, the parity check and the legacy removal, which are Epic 5.

## Tickets

| Ticket | Title | Points | Detail |
| ------ | ----- | ------ | ------ |
| ticket-019 | Build the brand theme module | 2 | outline |
| ticket-020 | Export the compact JSON payload | 3 | outline |
| ticket-021 | Assemble the single-file HTML shell | 3 | outline |
| ticket-022 | Implement the JavaScript chart renderer core | 3 | outline |
| ticket-023 | Implement the view mode and deck selector | 3 | outline |
| ticket-024 | Implement the absolute and difference toggle | 2 | outline |
| ticket-025 | Render the SIN level charts | 2 | outline |
| ticket-026 | Render the submarket and interchange charts | 3 | outline |

## Dependency Order

```text
ticket-019 ─┐
ticket-020 ─┴─> ticket-021 -> ticket-022 ─┬─> ticket-023 ─┬─> ticket-025 -> ticket-026
                                          └─> ticket-024 ─┘
```

## Refinement Inputs Required

Before these tickets can be refined into detailed tickets, the following must be available:

- `epic-01-learnings.md`: the `Settings` field names, the interpreter used, the error hierarchy.
- `epic-02-learnings.md`: the `DashboardData` accessor names, the `EntityRef` and `TimeAxis` shapes,
  the entity identifier format, the warning wording, the `ChartSpec` field names.
- A decision on whether chart titles come from `ChartSpec.title` or from `Registries.title_for`,
  which ticket-015 made available but did not settle.

## Open Questions for the Epic

- How the renderer is tested without a browser. The candidate approaches are asserting on the
  generated HTML and JSON from Python only, adding a Node-based smoke test, or a documented manual
  checklist. This must be settled during refinement, since it shapes the acceptance criteria of
  tickets 022 to 026.
- Whether the deck selector and the level navigation share one URL-hash state so a particular view
  can be linked, which the spec does not require.
