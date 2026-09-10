# ticket-031 Render the computational time bar charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Render the `TEMPO` charts as grouped bars by deck date, one bar per scenario, for the configurable
stage groups of `time.stage_groups` — by default MILP, the PL group summing `PL`, `PL.Int.Fix` and
`PL.CalcCMO`, and Leitura — plus a total, all converted from seconds to minutes through
`time.unit_divisor`.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/payload.py`, `tests/test_payload.py`.
- **Key decisions needed**:
  - whether the grouping is applied in Python at payload time, which keeps `time.stage_groups`
    authoritative, or in the browser, which would allow interactive regrouping;
  - whether the total is the sum of the configured groups or the sum of every `etapa` row, which
    differ if a future `TEMPO` file adds a stage not covered by any group;
  - whether an `etapa` value present in the file but absent from every group produces a warning, so
    a new DESSEM stage is not silently dropped from the total.
- **Open questions**:
  - Is a stacked bar per scenario preferable to four separate charts, since the groups sum to the
    total and stacking shows the composition at a glance? The legacy produced four separate charts.
  - Does the chart show minutes with one decimal, given that the real values range from 48 s to
    6 726 s?
  - Is the `execucao` column, always zero in the sample, ever non-zero and therefore a dimension?

## Dependencies

- **Blocked By**: `ticket-030-render-cost-bar-charts.md`
- **Blocks**: `ticket-032-enforce-output-size-strategy.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
