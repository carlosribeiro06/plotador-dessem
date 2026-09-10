# ticket-033 Wire the end-to-end pipeline

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`

## Objective

Replace the Epic 1 stub body of `pipeline.run` with the real orchestration: discover the scenarios,
build the `DashboardData`, serialise the payload, build the HTML, write it to the requested output
path, and return the volumes and warnings that the CLI records in the run manifest.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/pipeline.py`, `tests/test_pipeline.py`,
  `tests/test_cli.py`.
- **Key decisions needed**:
  - the exact order and logging of the pipeline phases, and which elapsed times are recorded
    separately, given that `CLAUDE.md` requires per-stage timing for time-bounded runs;
  - whether the output file is written atomically through a temporary file and a rename;
  - how the accumulated warnings are surfaced: log only, embedded in the HTML, recorded in the
    manifest, or all three.
- **Open questions**:
  - Does a run with zero usable charts, for example when every source file is missing, still write
    an HTML file with a Portuguese explanatory message, or does it fail?
  - Does the pipeline validate `--modo-inicial` against the modes actually available, since a deck
    shorter than `chaining.stages_per_deck` makes the Encadeado mode partially empty?
  - Is a dry-run flag wanted that reports the volumes without writing the HTML, which would be
    useful given the size concerns of ticket-032?

## Dependencies

- **Blocked By**: `ticket-032-enforce-output-size-strategy.md`
- **Blocks**: `ticket-034-add-example-data-integration-test.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
