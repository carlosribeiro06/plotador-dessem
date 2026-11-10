# ticket-009: README facts for the hydro flow charts (R24) [OUTLINE]

**Confidence: Low.** This ticket is refined just-in-time, after epics 01 and 02.

## Objective

Make every feature-touched README statement match the code (ADR-008). Measure every number with
`enabled_specs()` / `all_specs()` from `dessem_dashboard.charts.registry` on the tree as it stands
after ticket-008:

- **Chart counts** count chart keys (`s.key`).
- **Per-chart warning counts** count distinct `s.source_file` values. `FALLBACK_UNITS` is keyed the
  same way, and the seven scalar charts share the `CUSTOS` and `TEMPO` files.
- **Group filters** use `s.group`, because scalar specs have `level=None`.

## Anticipated Scope

- `README.md`, the only file.
- **Catalogue counts:** 47 declared, 31 enabled and 16 disabled, all measured. These counts appear
  in three places:
  - the Charts configuration paragraph;
  - "Extending the chart catalogue";
  - the Structure comment on `specs.py`.
- **Chart catalogue:**
  - The SIN list gains Defluência, Turbinamento and Vertimento.
  - The UHE list takes the R13 order.
  - One sentence states the "no synthesized file, no chart" rule (ADR-003).
- **Hydro-flow semantics paragraph:** worded from the amended C-SEM (sources under Refinement
  requirements). It must say:
  - SIN flows are the synthesized per-stage sums over all plants. As an aggregate indicator they
    count cascade water at every plant it passes, for QDEF, QTUR and QVER.
  - QINC is the deck's inflow input (dadvaz).
  - For most plants QINC is the natural incremental inflow, and QAFL adds upstream outflows, lagged
    by travel time where it exists.
  - Where the deck gives a regularized inflow (Sobradinho, dadvaz `itp=3`), the upstream outflows
    are already included and QAFL equals QINC.

  It must never:
  - call QINC "natural" for every plant;
  - state "Defluência = Turbinamento + Vertimento" as a definition.
- **"Enabling an already-declared chart":** use a still-disabled key such as `MER_SIN` as the
  example instead of `QDEF_SIN`. Rewrite the recipe, because `charts.disabled` can only subtract.
- **Test-pin table:** list the files measured from tickets 003-005, plus the `_ENABLED_CHART_COUNT`
  grep. The checklist guard from ticket-008 pins literals, so it is not a catalogue pin site.
- **Logging and auditing:**
  - the per-chart warning counts, 26 and 104, from the ticket-005 measurement (per source file);
  - R27's effect on warning shape 7.

## Refinement requirements

- The refined ticket cites the amended C-SEM: the master plan's "Domain contracts" section,
  amended at sign-off 2026-11-09, whose source is the dessem-specialist notes (a)-(c) in the plan's
  design sign-off record. It does not cite the council brief's original C1.
- The refined ticket adds a dessem-specialist review of the hydro-flow semantics paragraph as a
  Definition-of-Done item. The review must approve the final wording before the ticket completes.
  CLAUDE.md routes DESSEM result interpretation to the dessem-specialist.

## Dependencies

- **Blocked By**: ticket-008-checklist-section-10-guard-test.md
- **Blocks**: ticket-010-readme-stale-content.md

## Notes

- Agent: open-source-documentation-writer, with a dessem-specialist review of the semantics
  paragraph.
- Implements R24 and ADR-008. It also states ADR-003 in user terms.
- Out of scope: R28 content (ticket-010) and the checklist (ticket-007).
