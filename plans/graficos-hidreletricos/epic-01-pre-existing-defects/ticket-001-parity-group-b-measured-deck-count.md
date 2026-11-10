---
filesToBeCreated: []
filesToBeModified:
  - tests/test_parity.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R29, R22, ADR-009]
---

# ticket-001: Group B parity measures the deck count instead of assuming two decks per scenario

## Context

### Background (pre-existing test defect, R29)

`tests/test_parity.py::test_group_b_series_and_scalar_parity_matches_legacy_expressions` is the
real-data parity test. It runs when `DESSEM_DASHBOARD_EXEMPLO` points at a tree with at least two
qualifying scenarios.

Its last two assertions hard-code the documented `exemplo/` pair's shape, two decks per scenario.
On any other qualifying tree they fail. `examples/Oficial` and `examples/Modificado` each have one
deck, so on `main` today the test fails:

```
>       assert _check_custos_scalars_match_legacy(context) == len(context.scenarios) * 2
E       AssertionError: assert 2 == (2 * 2)
tests/test_parity.py:608: AssertionError
```

This was measured on 2026-11-09, on `main`:

```bash
DESSEM_DASHBOARD_EXEMPLO=$PWD/examples .venv/bin/pytest tests/test_parity.py
```

The result was 1 failed, 10 passed and 4 skipped.

The defect is in the test, not in the product. The scalar checks themselves visit every (scenario,
deck) pair correctly; only the expected count is wrong.

This ticket runs first in the plan, so that later tickets (002 and 004) can require
`tests/test_parity.py` to pass fully on `examples/` instead of accepting a known failure (ADR-009).

### Current state (verified)

`tests/test_parity.py`, lines ~582-609:

```python
def test_group_b_series_and_scalar_parity_matches_legacy_expressions(tmp_path: Path) -> None:
    context = _build_group_b_context(tmp_path)

    for chart_key in _SIN_CHART_KEYS:
        visited = _check_chained_series_matches_legacy(context, chart_key, "", submarket_code=None)
        assert visited == len(context.scenarios)
    ...
    for chart_key in _SBM_FAMILY_CHART_KEYS:
        ...
        assert visited_total == len(codes) * len(context.scenarios)

    assert _check_custos_scalars_match_legacy(context) == len(context.scenarios) * 2
    assert _check_tempo_scalars_match_legacy(context) == len(context.scenarios) * 2
```

I audited the other Group B count assertions for the same two-decks-per-scenario premise. None has
it:

- `_check_chained_series_matches_legacy` returns the number of scenarios visited: one chained
  array per scenario, whatever the deck count. Its callers compare against `len(context.scenarios)`
  and `len(codes) * len(context.scenarios)`, which is correct for any deck count.
- `_check_custos_scalars_match_legacy` and `_check_tempo_scalars_match_legacy` (lines ~329 and ~418)
  loop over `context.dirs_by_scenario[scenario]`, one sintese directory per deck. They count
  visited (scenario, deck) pairs. Only their two call sites at lines 608-609 carry the premise.
- `_ParityContext.dirs_by_scenario` (line ~157) is a `Mapping[str, tuple[Path, ...]]`, built by
  `_build_group_b_context` from `_ordered_sintese_dirs(...)`. Its contents are the measured decks.
- The four `test_group_b_reference_deck_*` tests pin values of the documented pair. They skip by
  design when `documented_pair(root)` is None, as it is for `examples/`. They are not this defect.
- Group A's `visited == 1` checks run on a synthetic one-scenario tree and are correct.

### Target state

Lines 608-609 compare against the measured number of (scenario, deck) pairs, with a non-vacuity
guard:

```python
deck_pairs = sum(len(dirs) for dirs in context.dirs_by_scenario.values())
assert deck_pairs > 0, "Group B context holds no deck: the scalar checks would visit nothing"
assert _check_custos_scalars_match_legacy(context) == deck_pairs
assert _check_tempo_scalars_match_legacy(context) == deck_pairs
```

On the documented two-deck pair, `deck_pairs` is 4, the value the old expression produced. So the
test keeps its meaning there by construction, and no number is pinned.

I simulated this exact edit on a scratch copy of the repository on 2026-11-09. With
`DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, `tests/test_parity.py` gave 11 passed and 4 skipped,
and Group B passed. The 4 skips are the documented-pair pin tests.

## Dependencies

- **Blocked By**: None
- **Blocks**: ticket-002-pass-fictitious-codes-to-registries.md

## Acceptance Criteria

1. **Given** `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, **when** `tests/test_parity.py` runs with
   `-rs`, **then**:
   - `test_group_b_series_and_scalar_parity_matches_legacy_expressions` PASSED, not SKIPPED;
   - no test in the file fails;
   - the only skips are the four `test_group_b_reference_deck_*` documented-pair tests, each naming
     the documented pair in its skip reason.
2. **Given** the same run on `main` before the edit, **when** it is compared, **then** the report
   shows the pre-existing `assert 2 == (2 * 2)` failure as RED evidence.
3. **Given** the edited test, **when** you read lines ~606-612, **then**:
   - the expected scalar visit count is derived from `context.dirs_by_scenario`;
   - no literal deck count (`* 2`) remains in Group B;
   - a `deck_pairs > 0` non-vacuity assertion precedes the two checks.
4. **Given** `git diff --stat`, **when** it is inspected, **then** only `tests/test_parity.py`
   changed, so no product code is touched.
5. **Given** the full gate, **when** it runs, **then**:
   - ruff check, ruff format --check and mypy src exit 0;
   - both background pytest chunks pass (`tests/test_[a-l]*.py`, then
     `tests/test_[m-z]*.py --cov-append`), with Group B skipping because no `exemplo/` exists;
   - coverage is at least 85%.

## Files

| File | Change |
| --- | --- |
| `tests/test_parity.py` | Lines ~608-609: measured `deck_pairs` plus a non-vacuity guard |

## Technical Details

- Update the test's docstring if it implies two decks per scenario. Today it says "repeated over
  the two documented real scenarios". The scenario count of two is still true, because
  `_require_two_scenarios` enforces it, so keep that wording and add no deck premise.
- Keep the module docstring's Group B description as it is. It makes no deck-count claim.
- Do not touch `_check_*` helpers, `_build_group_b_context`, `exemplo_tree.py` or the reference-deck
  pin tests.
- `tests/test_parity.py` writes only under `tmp_path`. Run it from the repository root.

### Out of scope

- The `load_registries` call at line ~594 (ticket-002).
- The `_ENABLED_CHART_COUNT` pin (ticket-004).
- Making the documented-pair pin tests run on `examples/`. They pin values of a different study.
- Any `src/` change.

### Door, structure budget, debt

The decision is a two-way door. The ticket adds one local variable and depends on no debt ticket.

## Definition of Done

- [ ] All five acceptance criteria are met, with the RED (`main`) and GREEN `pytest -rs` summaries
      in the report.
- [ ] The gate is green and coverage is at least 85%.
- [ ] Commit message (Portuguese): `test: mede a quantidade de decks na paridade do grupo B`.
