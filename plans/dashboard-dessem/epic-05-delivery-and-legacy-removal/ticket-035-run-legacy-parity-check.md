# ticket-035 Run the legacy parity check

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`

## Objective

Prove that the new dashboard reproduces every chart the legacy scripts produced, before those
scripts are deleted, and document the one known intentional divergence: the datetime axis with step
interpolation instead of the legacy categorical axis, per master plan decision 14.

## Anticipated Scope

- **Files likely to be modified**: `plans/dashboard-dessem/epic-05-parity-report.md`,
  `tests/test_parity.py`.
- **Key decisions needed**:
  - the comparison method. Appendix A.7 lists the legacy behaviours to preserve: `GHID_SIN` and
    `GTER_SIN` line charts, `GHID_SBM`, `GTER_SBM` and `CMO_SBM` per submarket 1 to 4, `CUSTOS` bars
    with presente, futuro and total, and `TEMPO` bars with MILP, PL group, Leitura and total in
    minutes, all over the first 48 stages of each deck;
  - whether the check compares numbers extracted from the new payload against numbers recomputed
    directly from the Parquet files with a small independent script, which avoids running the legacy
    code at all, or whether the legacy scripts are actually executed;
  - the tolerance, which should be exact for values read straight from the files and
    `pytest.approx` only where a sum or a unit conversion is involved.
- **Open questions**:
  - The legacy scripts carry a hard-coded Windows path and rely on import-time side effects, so
    running them requires editing them, which conflicts with the plan not modifying legacy code.
    Refinement must choose between an independent recomputation, a throwaway copy of the legacy
    scripts outside the repository, or a documented visual comparison.
  - Is the divergence in the X axis type acceptable to the developer, or should a categorical-axis
    option be offered for continuity?

## Dependencies

- **Blocked By**: `ticket-034-add-example-data-integration-test.md`
- **Blocks**: `ticket-036-write-user-documentation.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
