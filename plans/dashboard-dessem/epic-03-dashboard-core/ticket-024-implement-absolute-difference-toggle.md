# ticket-024 Implement the absolute and difference toggle

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Add the Absoluto and Diferença toggle required by `planning-context.md` decision 8, computing the
difference in the browser as scenario minus reference from the embedded absolute series, so the
payload never carries precomputed differences.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/assets/dashboard.html`, `tests/test_payload.py`.
- **Key decisions needed**:
  - whether the reference curve is hidden in Diferença mode, since it would be a flat zero line, or
    kept as a visual baseline;
  - how a `null` on either side is handled: the difference should be `null` rather than treated as
    zero, so a missing deck does not read as a zero difference;
  - whether the Y axis label gains a suffix such as `(diferença)` and whether the axis is forced to
    include zero.
- **Open questions**:
  - Is a relative difference in percent also wanted, which the spec does not require but which is
    common in this kind of comparison?
  - Does the toggle state persist across level and deck changes?
  - Is the reference scenario shown in the UI so the reader knows what the difference is measured
    against, given that `--referencia` can override the default first scenario?

## Dependencies

- **Blocked By**: `ticket-022-implement-js-chart-renderer-core.md`
- **Blocks**: `ticket-025-render-sin-level-charts.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
