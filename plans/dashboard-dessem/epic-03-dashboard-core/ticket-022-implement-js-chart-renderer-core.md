# ticket-022 Implement the JavaScript chart renderer core

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Write the hand-authored JavaScript core that reads the embedded payload and builds a Plotly figure
on demand for a given chart, entity, view mode and value mode, so that no figure is pre-rendered
and the file stays small. This is the engine that tickets 023 to 026 and all of Epic 4 drive.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `tests/test_renderer_contract.py`.
- **Key decisions needed**:
  - the module shape: one immediately invoked function expression, or ES modules, given that the
    file is inlined and must work from `file://`;
  - the function boundary between building a trace list and calling `Plotly.react`, and whether
    `Plotly.react` or `Plotly.newPlot` is used on a mode change;
  - how the step interpolation of decision 14 is expressed, expected to be `line_shape: "hv"` plus a
    final synthetic point at the last stage end so the last stage has visible width.
- **Open questions**:
  - How is this file tested? See the epic open question on browser testing. A Python-side contract
    test asserting that every payload key the JavaScript reads is actually produced by ticket-020 is
    the minimum.
  - Does the renderer cache built trace arrays per chart to keep interaction responsive at the
    verified plant-level volumes, or is rebuilding from the payload fast enough?
  - How are `null` gaps rendered: `connectgaps: false` leaves visible holes, which is the honest
    representation of a missing deck.

## Dependencies

- **Blocked By**: `ticket-021-assemble-single-file-html-shell.md`
- **Blocks**: `ticket-023-implement-view-mode-and-deck-selector.md`,
  `ticket-024-implement-absolute-difference-toggle.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
