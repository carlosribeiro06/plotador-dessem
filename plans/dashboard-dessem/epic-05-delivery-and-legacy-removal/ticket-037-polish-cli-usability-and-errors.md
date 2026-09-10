# ticket-037 Polish the CLI usability and error messages

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`

## Objective

Review every Portuguese message the operator can see — CLI help, argument errors, configuration
errors, discovery errors, schema errors and the accumulated warnings — for consistency, accuracy and
actionability, and make the console output of a normal run readable at a glance.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/cli.py`,
  `src/dessem_dashboard/errors.py`, `src/dessem_dashboard/logging_setup.py`,
  `tests/test_cli.py`.
- **Key decisions needed**:
  - a single message style: whether errors name the offending value first or the expected value
    first, and whether they suggest a corrective action;
  - whether the run ends with a short Portuguese summary on the console listing scenarios, decks,
    charts, warnings, output path and elapsed time;
  - whether the warning count is echoed as a non-zero exit code, which would let a batch caller
    detect a degraded run.
- **Open questions**:
  - Does the tool print the output path to stdout so it can be piped, which `rules/python.md` allows
    for a short CLI final result while everything else goes through logging?
  - Is a `--quiet` or `--verbose` pair wanted in addition to `--nivel-log`?
  - Are the warnings grouped by cause in the summary, since a missing deck can generate one warning
    per chart and flood the console at 23 charts?

## Dependencies

- **Blocked By**: `ticket-036-write-user-documentation.md`
- **Blocks**: `ticket-038-remove-legacy-scripts.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
