# ticket-032 Enforce the output size strategy

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Measure and bound the size of the generated HTML: log the embedded value count and the final file
size, warn above `output.size_warning_mb`, and record both in the run manifest, so a run with many
decks and scenarios reports its own cost instead of silently producing an unusable file.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/builder.py`,
  `src/dessem_dashboard/pipeline.py`, `tests/test_builder.py`.
- **Key decisions needed**:
  - whether exceeding the threshold is a warning only, as the master plan currently states, or
    whether a hard limit and a Portuguese error is also offered as an opt-in setting;
  - which volumes go into the manifest `data_volumes`: value count, entity count, deck count, HTML
    bytes, and the Plotly bundle bytes as a separate figure so the payload share is visible;
  - whether the size is measured before or after writing, and whether the write is atomic through a
    temporary file and a rename.
- **Open questions**:
  - Do the projected volumes for 30 decks and 3 scenarios, about 8 M values, require a mitigation
    beyond rounding, such as omitting plant-level series in Encadeado mode or splitting the output
    into more than one file? Answering this may change the master plan single-file goal and must be
    escalated to the developer rather than decided here.
  - Is `output.decimals` per chart rather than global, since `CMO_SBM` values around 0.05 need more
    decimals than `EARMF_SIN` values around 190 000?

## Dependencies

- **Blocked By**: `ticket-029-render-thermal-plant-charts.md`,
  `ticket-031-render-computational-time-bar-charts.md`
- **Blocks**: `ticket-033-wire-end-to-end-pipeline.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
