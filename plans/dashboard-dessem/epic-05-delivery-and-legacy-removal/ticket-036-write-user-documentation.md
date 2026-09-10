# ticket-036 Write the user documentation

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `open-source-documentation-writer`

## Objective

Replace the Epic 1 README skeleton with the complete documentation of the delivered tool, in
English per Rigoroso mode, following the section order of `rules/markdown.md`, so an operator who has
never seen the project can install it, configure it, run it and read the dashboard.

## Anticipated Scope

- **Files likely to be modified**: `README.md`, `CLAUDE.md`, `docs/dashboard-guide.md`.
- **Key decisions needed**:
  - whether a separate guide file is created for the dashboard interface itself, or whether
    everything stays in the README;
  - whether the expected input tree, the two view modes and the difference view are illustrated with
    a diagram or with plain text;
  - which configuration keys get an extended explanation beyond the table, expected to be
    `chaining.stages_per_deck`, `costs.total_parcels`, `time.stage_groups` and `charts.disabled`,
    since those are the ones an operator will actually change.
- **Open questions**:
  - Are screenshots wanted, and if so where are they stored, given that `.gitignore` ignores
    generated HTML but not images?
  - Does the documentation state how to add a new chart, which is the extensibility promise of the
    registry and would be the most valuable section for a future maintainer?
  - Does it document the two intentional divergences from the spec: `logo/` and `*.md` staying
    versioned, and the datetime axis replacing the categorical axis?

## Dependencies

- **Blocked By**: `ticket-035-run-legacy-parity-check.md`
- **Blocks**: `ticket-037-polish-cli-usability-and-errors.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
