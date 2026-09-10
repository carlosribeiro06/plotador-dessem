# ticket-030 Render the cost bar charts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Render the `CUSTOS` charts as grouped bars by deck date, one bar per scenario, for custo presente,
custo futuro and custo total, where the total is the sum of `costs.total_parcels`, defaulting to
`PRESENTE` plus `FUTURO` for legacy parity.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/payload.py`, `tests/test_payload.py`.
- **Key decisions needed**:
  - whether the total is computed in Python at payload time or in the browser from the parcels,
    which matters because `costs.total_parcels` is configuration and recomputing in the browser
    would let a reader change it interactively;
  - whether `VIOLACOES` and `PEQUENAS PENALIDADES` are shown as their own bars, given that the real
    data has them at zero and about 40 R$ respectively;
  - the value scale, since `FUTURO` is about 2.3e8 R$ while `PRESENTE` is about 5.9e4 R$, so a
    shared linear axis makes the present cost invisible.
- **Open questions**:
  - Master plan open question 1: is the default total definition confirmed?
  - Are the three charts separate, as in the legacy output, or one chart with a parcel selector?
  - Does the difference toggle of ticket-024 apply to bar charts as well, and if so is the
    difference shown as bars or as a percentage label?

## Dependencies

- **Blocked By**: `ticket-026-render-submarket-and-interchange-charts.md`
- **Blocks**: `ticket-031-render-computational-time-bar-charts.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
