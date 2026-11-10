---
filesToBeCreated: []
filesToBeModified:
  - src/dessem_dashboard/data/registries.py
  - src/dessem_dashboard/data/consolidate.py
  - tests/test_registries.py
  - tests/test_consolidate.py
  - tests/test_parity.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R27, R23, ADR-005]
---

# ticket-002: Pass settings.submarkets.fictitious_codes to load_registries

## Context

### Background (bug, R27)

`settings.submarkets.fictitious_codes` is meant to decide which submarkets are fictitious, and
therefore hidden when `include_fictitious` is false. It never reaches the registry loader, so the
hard-coded default `(11, 99)` always applies.

Measured on `main` during planning with the `scenario_tree` fixture (submarkets 1, 2, 11, 99):

- With `fictitious_codes=[99]`, `CMO_SBM` entities are `['1','2']`: code 11 is still hidden. The
  run also emits 24 spurious warnings: "... código(s) de submercado ... descartado(s): 11".
- With `[2, 11, 99]`, code `2` stays visible.

Expected after the fix, with `include_fictitious=False`:

- `[99]` shows `1`, `2` and `11`, with no submarket-code warning.
- `[2, 11, 99]` shows only `1`.

ADR-005 (answer A3) selects Option A: make the keyword required and pass the setting through.

### Current state

**`src/dessem_dashboard/data/registries.py:225`**

```python
def load_registries(sintese_dir: Path, *, fictitious_codes: Sequence[int] = (11, 99)) -> Registries:
```

It builds `fictitious_set = frozenset(fictitious_codes)`, which feeds `Submarket.fictitious`.
`visible_submarket_codes(registries, *, include_fictitious)` at line ~272 filters on it.

**`src/dessem_dashboard/data/consolidate.py`**

- `_load_registries(scenarios)` at line ~349 calls `load_registries(primary_deck.sintese_dir)` and,
  for the advisory name comparison, `load_registries(deck.sintese_dir)`. Neither call passes
  `fictitious_codes`.
- `build_dashboard_data` at line ~645 calls `_load_registries(scenarios)` at line ~665.
- `_load_series` already uses `settings.submarkets.fictitious_codes` (line ~430) for its
  dropped-code set. That mismatch is why the spurious warnings appear.

**Tests**

- `tests/test_registries.py` calls `load_registries(sintese_dir)` 27 times.
- In `tests/test_consolidate.py`, `_settings_dict(...)` hard-codes `"fictitious_codes": [11, 99]`.
  `_build_settings(tmp_path, *, stages_per_deck=4, include_fictitious=False, disabled=())` has no
  knob for it. The existing fictitious tests are at lines ~494-538.
- `tests/test_parity.py:594` calls `registries = load_registries(official_first_deck)`.

### Target state

**`registries.py`**

```python
def load_registries(sintese_dir: Path, *, fictitious_codes: Sequence[int]) -> Registries:
```

The default is removed, and the docstring names the parameter's source,
`settings.submarkets.fictitious_codes`.

**`consolidate.py`**

```python
def _load_registries(scenarios: Sequence[ScenarioRef], *, fictitious_codes: Sequence[int]) -> Registries:
```

Both inner calls pass `fictitious_codes=fictitious_codes`. `build_dashboard_data` calls
`_load_registries(scenarios, fictitious_codes=settings.submarkets.fictitious_codes)`. The docstring
mentions the parameter.

**`tests/test_registries.py`**

- A module constant `_FICTITIOUS_CODES: tuple[int, ...] = (11, 99)`, commented to say it mirrors
  the repository's `settings.json`. Every call passes `fictitious_codes=_FICTITIOUS_CODES`.
- A new unit test:
  `test_load_registries_fictitious_flag_follows_given_codes`. With `fictitious_codes=(99,)`,
  `Submarket` 11 has `fictitious is False` and 99 has `fictitious is True`. The visible set without
  fictitious codes is `(1, 2, 11)`.

**`tests/test_consolidate.py`**

- `_settings_dict` and `_build_settings` gain `fictitious_codes: Sequence[int] = (11, 99)` and
  write it into the dict.
- A new parametrized regression test,
  `test_build_dashboard_data_hides_exactly_the_configured_fictitious_codes`, takes:
  - `([99], {"1","2","11"})`
  - `([2, 11, 99], {"1"})`

  For each case, with `include_fictitious=False`, it asserts the `CMO_SBM` entity-id set equals the
  expected set. It also asserts that no warning containing `"código(s) de submercado"` exists.
- Show the test RED on `main`: write and run it before the source fix, and record the failure in
  the report. Then show it GREEN.

**`tests/test_parity.py:594`**

```python
load_registries(official_first_deck, fictitious_codes=context.settings.submarkets.fictitious_codes)
```

Check the attribute path on `_ParityContext`.

## Dependencies

- **Blocked By**: ticket-001-parity-group-b-measured-deck-count.md
- **Blocks**: ticket-003-reorder-uhe-flow-charts.md

Ticket-001 must land first. It also edits `tests/test_parity.py`, and once it is in, Group B passes
on `examples/`, so criterion 4 below can require a full pass. This ticket in turn precedes epic 02,
because ticket-004 later edits `tests/test_registries.py` (`_ENABLED_CHART_KEY_COUNT`) and
`tests/test_parity.py` (`_ENABLED_CHART_COUNT`). Its R27 measurements, taken on `main`, remain valid
because no earlier ticket touches product code.

## Acceptance Criteria

1. **Given** the new parametrized regression test, **when** it is run against the unfixed source,
   **then** it fails. After the fix it passes, in both cases. The report shows both runs.
2. **Given** `load_registries` called without `fictitious_codes`, **when** mypy checks `src`,
   **then** no caller in `src/` omits it. `grep -rn "load_registries(" src tests` shows every call
   passing the keyword, and `grep -rn "(11, 99)" src/` prints nothing.
3. **Given** `tests/test_registries.py`, **when** it runs, **then** all existing tests and
   `test_load_registries_fictitious_flag_follows_given_codes` pass.
4. **Given** `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, **when** `tests/test_parity.py` runs,
   **then** no test fails, including
   `test_group_b_series_and_scalar_parity_matches_legacy_expressions`, which PASSED under `-rs`
   (not SKIPPED). The only skips are the four `test_group_b_reference_deck_*` documented-pair
   tests. This criterion depends on ticket-001's fix.
5. **Given** the full gate, **when** it runs, **then** all four commands exit 0 and coverage is at
   least 85%. Group B skips in the default run, because no `exemplo/` directory exists.

## Files

| File | Change |
| --- | --- |
| `src/dessem_dashboard/data/registries.py` | Required `fictitious_codes` keyword, default removed |
| `src/dessem_dashboard/data/consolidate.py` | `_load_registries` gains the keyword; both calls and the caller pass it |
| `tests/test_registries.py` | `_FICTITIOUS_CODES` at 27 call sites, plus a unit test |
| `tests/test_consolidate.py` | `fictitious_codes` knob, plus the parametrized regression test |
| `tests/test_parity.py` | Line ~594 passes the settings' codes |

## Technical Details

- Use `Sequence[int]` from `collections.abc`, as the existing import does.
- mypy does not check `tests/`, so a missed call in tests only fails at runtime. Find every call
  with `grep -rn "load_registries(" tests`.
- In the regression test, read warnings through the `DashboardData` warnings accessor. Read
  `dashboard_data.py` for the real name.
- There are five files, so the readiness rubric's atomicity file score is 0.5. The change is still
  one behaviour: the edits in `test_registries.py` are mechanical keyword additions, and the
  `test_parity.py` edit is a single line forced by the signature change.

### Out of scope

- Option B: moving the policy into `visible_submarket_codes` or removing `Submarket.fictitious`.
- Changing `INT_SBP` pair handling.
- Group B's deck-count assertions (ticket-001).
- README wording on warning shape 7 (ticket-009).

### Door, structure budget, debt

The decision is a two-way door. The structure allowed is one parameter, one test constant and one
test knob. The ticket depends on no debt ticket.

## Definition of Done

- [ ] All five acceptance criteria are met, with RED and GREEN evidence in the report.
- [ ] The gate is green and coverage is at least 85%.
- [ ] No hard-coded `(11, 99)` remains in `src/`.
- [ ] Commit message (Portuguese): `fix: respeita submarkets.fictitious_codes ao carregar os registros`.
