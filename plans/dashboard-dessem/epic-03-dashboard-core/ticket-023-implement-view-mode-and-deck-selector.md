# ticket-023 Implement the view mode and deck selector

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Add the two navigation controls that `planning-context.md` decision 5 requires: a Por deck and
Encadeado mode toggle, and, in Por deck mode, a deck selector by date, together with the
aggregation-level navigation that switches between the SIN, submarket, hydro plant, thermal plant
and execution groups.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/assets/dashboard.css`,
  `src/dessem_dashboard/dashboard/assets/dashboard.html`, `tests/test_builder.py`.
- **Key decisions needed**:
  - whether the deck selector is hidden or merely disabled in Encadeado mode;
  - whether the level navigation is a tab bar or a sidebar, given that there are six chart groups
    and up to eight charts in the hydro group;
  - which mode is preselected, defaulting to the CLI `--modo-inicial` value of `encadeado`.
- **Open questions**:
  - Are all charts of a group rendered at once, one below the other as the legacy scripts produced
    one file per chart, or is one chart shown at a time with a chart selector? This affects
    perceived performance at plant-level volumes and must be decided before ticket-025.
  - Does the selected deck persist when the user switches level, and does it reset when switching to
    Encadeado and back?
  - How are the deck dates labelled: `%d/%m/%Y` matching the operator convention.

## Dependencies

- **Blocked By**: `ticket-022-implement-js-chart-renderer-core.md`
- **Blocks**: `ticket-025-render-sin-level-charts.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
