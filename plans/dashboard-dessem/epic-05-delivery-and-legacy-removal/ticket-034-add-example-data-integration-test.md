# ticket-034 Add the example-data integration test

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `monorepo-test-developer`

## Objective

Add the one integration test that runs the whole pipeline against a real scenario tree, located
through the `DESSEM_DASHBOARD_EXEMPLO` environment variable with a fallback to the repository's `exemplo/caso_oficial` and `exemplo/caso_gurobi` scenario folders, and
skipped when no valid tree is found, so the real 60-file, 68-stage, 165-plant volumes are exercised
without making the suite depend on gitignored data.

## Anticipated Scope

- **Files likely to be modified**: `tests/test_integration_exemplo.py`, `README.md`.
- **Key decisions needed**:
  - what the test asserts beyond a successful run: the HTML size, the value count, the number of
    charts present in the payload, the absence of warnings, or a subset;
  - the skip predicate, which must recognise a directory holding at least one scenario with at least
    one deck in the decided `<cenario>/<deck>/sintese/` shape;
  - whether the test writes into `tmp_path` or into `output/`, and how long it is allowed to take.
- **Open questions**:
  - **Resolved (master plan open question 5, 2026-09-10)**: the scenario-first tree exists locally at
    `exemplo/caso_oficial/{2024-03-03,2024-03-04}/sintese` and
    `exemplo/caso_gurobi/{2024-03-03,2024-03-04}/sintese` (60 files each), rebuilt from git history
    and gitignored. The skip path only triggers on machines without that tree and without
    `DESSEM_DASHBOARD_EXEMPLO`.
  - Is a second integration test wanted that runs a single scenario, since the spec allows one
    `--casos` argument and the difference view then has nothing to compare against?
  - Should the test be marked so it can be selected explicitly, for example with a `slow` marker?

## Dependencies

- **Blocked By**: `ticket-033-wire-end-to-end-pipeline.md`
- **Blocks**: `ticket-035-run-legacy-parity-check.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
