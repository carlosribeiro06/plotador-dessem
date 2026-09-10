# ticket-029 Render the thermal plant charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Render the thermal-plant generation chart `GTER_UTE` for the 89 thermal plants, reusing the plant
selector and the name and code filters built for the hydro view, so the UTE level is complete with
minimal new code.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `tests/test_builder.py`.
- **Key decisions needed**:
  - how much of the hydro view machinery is generalised versus duplicated, given that the UTE level
    has one chart while the UHE level has eight;
  - whether the thermal view shows the `limite_inferior` and `limite_superior` bands, which are
    genuinely informative for thermal units because they encode the committed operating range and
    are non-infinite in the real data.
- **Open questions**:
  - Is `CVU` per plant wanted alongside the generation, which would answer the natural question of
    why a unit dispatched? The master plan currently excludes `CVU` as an input rather than a
    result, so enabling it would be a scope change.
  - Do the thermal plants group by submarket in the selector, given that the registry carries the
    submarket for each of the 89 units?

## Dependencies

- **Blocked By**: `ticket-028-implement-name-and-code-filters.md`
- **Blocks**: `ticket-032-enforce-output-size-strategy.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
