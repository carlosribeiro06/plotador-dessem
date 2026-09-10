# ticket-025 Render the SIN level charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Render the five SIN-level charts of Appendix A.6 — `GTER_SIN`, `GHID_SIN`, `GUNS_SIN`, `EARMF_SIN`
and `VARMF_SIN` — as the first working end-to-end view, with one curve per scenario, real date and
time on the X axis and the unit in the Y axis title.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/builder.py`, `tests/test_builder.py`.
- **Key decisions needed**:
  - the chart title text source, either `ChartSpec.title` or `Registries.title_for`;
  - the chart height and whether the width is fixed at the legacy 1400 by 450 pixels or responsive
    to the viewport, given that the legacy value was chosen for a specific screen;
  - the hover template, with `x unified` fixed by the legacy look.
- **Open questions**:
  - Does the SIN view show all five charts stacked, following the decision taken in ticket-023?
  - Is a Y axis with a forced zero baseline wanted for the generation charts, which would make the
    scenario differences visually smaller but the levels honest?
  - Does the chart show the `limite_inferior` and `limite_superior` bands available in the data,
    which the spec does not request but which the files carry?

## Dependencies

- **Blocked By**: `ticket-023-implement-view-mode-and-deck-selector.md`,
  `ticket-024-implement-absolute-difference-toggle.md`
- **Blocks**: `ticket-026-render-submarket-and-interchange-charts.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
