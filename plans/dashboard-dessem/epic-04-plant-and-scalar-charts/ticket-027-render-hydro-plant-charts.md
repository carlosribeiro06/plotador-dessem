# ticket-027 Render the hydro plant charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Render the eight hydro-plant charts of Appendix A.6 — `GHID_UHE`, `QTUR_UHE`, `QVER_UHE`,
`VARMF_UHE`, `VARPF_UHE`, `QDEF_UHE`, `QAFL_UHE` and `QINC_UHE` — with a plant selector whose
entity list comes from each chart own file, so a plant absent from a variable does not appear in
that chart selector.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/builder.py`, `tests/test_builder.py`.
- **Key decisions needed**:
  - whether the eight charts share one plant selector, which forces the union of entity lists and a
    graceful empty state for a plant absent from `VARMF_UHE`, or whether each chart carries its own;
  - whether the plant label shows the code as well, for example `CAMARGOS (1)`, which helps the code
    filter of ticket-028;
  - whether the two ambiguity pairs remain enabled, which is master plan open questions 2 and 3.
- **Open questions**:
  - Is the plant view one plant at a time, or several plants overlaid? Overlaying plants and
    scenarios at once would need a two-dimensional legend and was not requested.
  - How does the view behave for a plant present in `GHID_UHE` but absent from `VARMF_UHE`: an empty
    chart with an explanatory Portuguese message, or the chart hidden?
  - Does this view need the size mitigation of ticket-032 in place first? See the epic open
    question.

## Dependencies

- **Blocked By**: `ticket-026-render-submarket-and-interchange-charts.md`
- **Blocks**: `ticket-028-implement-name-and-code-filters.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
