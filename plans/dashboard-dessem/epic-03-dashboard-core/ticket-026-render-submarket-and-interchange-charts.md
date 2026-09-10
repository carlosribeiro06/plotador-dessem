# ticket-026 Render the submarket and interchange charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Render the six submarket charts — `MER_SBM`, `GHID_SBM`, `GTER_SBM`, `GUNS_SBM`, `CMO_SBM` and
`VARMF_SBM` — with a submarket selector, and the `INT_SBP` interchange chart with a submarket-pair
selector, labelling both from the registries loaded in ticket-015.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/assets/dashboard.html`, `tests/test_builder.py`.
- **Key decisions needed**:
  - whether the submarket selector is a single choice, matching the legacy one-file-per-submarket
    output, or a multiple choice showing several submarkets at once;
  - whether the interchange pair selector lists ordered pairs such as `SE para S` and `S para SE`
    separately, which is what the data contains, or nets them into one signed series;
  - whether the fictitious submarkets 11 and 99 are visible in the pair selector labels, given that
    they are excluded from the submarket charts by default.
- **Open questions**:
  - Should the interchange chart offer a net-exchange derived view? The data supports it but the
    spec asks only for `Intercâmbios`.
  - Does the submarket selector remember its choice across charts within the submarket group?
  - How is code 99, whose long name is null in `SBM.parquet`, labelled in the pair selector, given
    that ticket-015 falls back to the short name `IV`?

## Dependencies

- **Blocked By**: `ticket-025-render-sin-level-charts.md`
- **Blocks**: `ticket-027-render-hydro-plant-charts.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
