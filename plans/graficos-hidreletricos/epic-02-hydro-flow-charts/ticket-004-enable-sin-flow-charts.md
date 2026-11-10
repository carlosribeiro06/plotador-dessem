---
filesToBeCreated: []
filesToBeModified:
  - src/dessem_dashboard/charts/specs.py
  - tests/test_chart_specs.py
  - tests/test_builder.py
  - tests/test_charts_costs.py
  - tests/test_charts_sin.py
  - tests/test_fixtures_sintese.py
  - tests/test_integration_exemplo.py
  - tests/test_output_size.py
  - tests/test_parity.py
  - tests/test_payload.py
  - tests/test_pipeline.py
  - tests/test_registries.py
  - tests/test_renderer_controls.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R1, R9, R13, R6, R7, R18, R21, R22, R25, R26, ADR-001, ADR-002, ADR-003, ADR-004]
---

# ticket-004: Enable QDEF_SIN, QTUR_SIN and QVER_SIN, move them after VARMF_SIN, and update every count pin

## Context

### Background

R1 and R9 require SIN charts for Defluência, Turbinamento and Vertimento. They come from the
synthesized files `QDEF_SIN`, `QTUR_SIN` and `QVER_SIN`, which are already declared in `SPECS` with
`enabled=False`. ADR-001 enables them and moves them into the SIN block right after `VARMF_SIN`, as
R13 requires. Nothing is derived (R26, ADR-003).

The pipeline has no key-specific code, so Por deck, Encadeado, Absoluto and Diferença work
unchanged (R6). Keys, titles and units stay as they are (ADR-002).

The ticket touches many files but is one change. It must be a single commit, because enabling the
specs turns every count pin red at once (ADR-004).

### Current state (verified)

**`src/dessem_dashboard/charts/specs.py`**

- The three specs are the last entries of `SPECS`, after `CUNS_SBM`:

  ```python
  _series("QDEF_SIN", ChartGroup.SIN, AggregationLevel.SIN, EntitySelector.NONE, "Defluência", enabled=False)
  ```

  `QTUR_SIN` ("Turbinamento") and `QVER_SIN` ("Vertimento") are declared the same way. Each is
  formatted over multiple lines.
- `VARMF_SIN` is the last SIN entry, followed by `MER_SBM`.
- The module docstring says "47 ChartSpec entries ... the 28 charts enabled by default (the spec
  minimum list of 21 series plus the seven dedicated Custo/Tempo bar charts ...), followed by 19
  further specs shipped disabled".

**Measured in a scratch copy with this change applied after ticket-003**

- `len(enabled_specs())` is 31 and `len(all_specs())` is 47, so 16 specs are disabled.
- SIN order: GTER, GHID, GUNS, EARMF, VARMF, QDEF, QTUR, QVER. There are 24 SERIES charts.
- The fixture writes 33 files. The example-pair build gives 31 charts, 0 warnings and
  6,632,093 bytes, against a baseline of 6,623,439 (R21).

**Full suite on that scratch copy**

28 tests failed. Two are environmental (the `test_manifest.py` git-sha tests, because the copy was
not a git repository). One was the Group B deck-count defect in `test_parity.py`, which
ticket-001 fixes before this ticket runs. The other 25 fall in exactly these 12 files:

| File | Pins to update (measure each value; never copy) |
| --- | --- |
| `tests/test_chart_specs.py` | `_ENABLED_KEYS_IN_ORDER`: add the 3 keys after VARMF_SIN. Rename `test_all_specs_has_forty_seven_entries_with_nineteen_disabled` to `..._sixteen_disabled` and assert 16. Update the group-size test (SIN 5 -> 8) and the `disabled=` ambiguity test, re-reading what each asserts. |
| `tests/test_builder.py` | Lines ~33-38: `_ENABLED_CHART_COUNT` 28 -> 31, `_SIN_CHART_COUNT` 5 -> 8, plus their comment. The section, hidden-state and log-line tests read these pins and any volume literals. |
| `tests/test_charts_costs.py` | Line ~629: `len(sections) == 28` -> 31. |
| `tests/test_charts_sin.py` | `_SIN_CHART_KEYS` (5 -> 8 keys), `_ALL_ENABLED_CHART_KEYS` (28 -> 31, in the full new SPECS order including the ticket-003 UHE order), `_SIN_TITLES_IN_ORDER`, `_SIN_UNITS_IN_ORDER` (append three `"m3/s"`), and `_THREE_DISTINCT_SIN_UNITS` (now four units, including m3/s; rename the constant and the test `..._three_distinct_strings...` around line 362). Rename `..._the_five_default_enabled_charts` (line ~432) to `..._eight_...`. Fix `assert len(_ALL_ENABLED_CHART_KEYS) == 28` (line ~484). The EARMF-disabled test now expects 7 sections. The every-chart-disabled test must list the new keys. |
| `tests/test_fixtures_sintese.py` | Lines ~44, ~237, ~275: 30/29/30 -> 33/32/33. Rename `..._thirty_files` to `..._thirty_three_files`. |
| `tests/test_integration_exemplo.py` | `_ENABLED_CHART_COUNT = 28` -> 31 (line ~40) and its comment. |
| `tests/test_output_size.py` | `_ENABLED_CHART_COUNT` (lines ~41-44) and any `valores`/bytes literals in the two failing tests; measure them on `scenario_tree`. |
| `tests/test_parity.py` | `_ENABLED_CHART_COUNT = 28` (line ~141) -> 31; this is what fails Group C. `_SIN_CHART_KEYS` there are legacy-parity keys and stay unchanged. |
| `tests/test_payload.py` | `_ENABLED_CHART_COUNT` -> 31 and `_VALUE_COUNT = 16_892`, re-measured with `value_count()` on `scenario_tree`. Fix the comment that says "23 charts". |
| `tests/test_pipeline.py` | `_ENABLED_CHART_COUNT` (lines ~35-37), plus any volume literal in `test_pipeline_run_writes_document_and_returns_six_key_volumes`. |
| `tests/test_registries.py` | `_ENABLED_CHART_KEY_COUNT = 28` (line ~34) -> measured value, with the comment "21 series plus seven" changed to "24 series plus seven". |
| `tests/test_renderer_controls.py` | `_ALL_SIN_CHART_KEYS` (lines ~33-42) gains the 3 keys; the comment says "eight". |

### Target state

**`specs.py`**

The three `_series` calls move, verbatim, to directly after `VARMF_SIN`, with `enabled=False`
removed. The docstring says 47 entries, 31 enabled (24 series plus the seven dedicated Custo/Tempo
bar charts) and 16 disabled.

**Tests**

Each pin above holds the measured value. Every adjacent comment and test name that states a number
states the new one.

## Dependencies

- **Blocked By**: ticket-003-reorder-uhe-flow-charts.md
- **Blocks**: ticket-005-remove-stale-count-text.md

## Acceptance Criteria

1. **Given** the default registry, **when** you list
   `[s.key for s in enabled_specs() if s.group is ChartGroup.SIN]`, **then** it equals
   `["GTER_SIN","GHID_SIN","GUNS_SIN","EARMF_SIN","VARMF_SIN","QDEF_SIN","QTUR_SIN","QVER_SIN"]`.
   The Submercado and UHE slices are unchanged from ticket-003, and `len(all_specs())` is still 47.
2. **Given** the three new specs, **when** you compare their key, title, unit, kind, group, level
   and selector with `main`, **then** they are identical apart from `enabled`. `grep -n
   "enabled=False" src/dessem_dashboard/charts/specs.py | wc -l` equals the measured disabled
   count (16).
3. **Given** the full suite, **when** it runs in the two background chunks, **then** every test
   passes, except Group B of `test_parity.py`, which skips without `exemplo/`. No test is deleted
   or weakened; only pins, comments and names change.
4. **Given** `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, **when** `tests/test_integration_exemplo.py`
   and `tests/test_parity.py` run, **then** no test fails, and `pytest -rs` shows Group B's
   `test_group_b_series_and_scalar_parity_matches_legacy_expressions` PASSED. The only skips are
   the four `test_group_b_reference_deck_*` documented-pair tests.
5. **Given** a grep for stale numbers in the touched files
   (`grep -rn "28 charts\|nineteen\|thirty_files\|the_five_default\|21 series" tests/ src/dessem_dashboard/charts/`),
   **then** it prints nothing.

## Files

| File | Change |
| --- | --- |
| `src/dessem_dashboard/charts/specs.py` | Move and enable the 3 specs; update the docstring counts |
| 12 test files listed in Current state | Measured pins, adjacent comments and test names |

## Technical Details

### Measuring

Registry access: import `enabled_specs`, `all_specs` and `ChartGroup` from
`dessem_dashboard.charts.registry`. Importing it loads the `dessem_dashboard.charts` package, whose
`__init__` registers the default catalogue. `dessem_dashboard.charts.specs` exports `SPECS` but
not these functions. Filter specs by `s.group`, never by `s.level.value`: the seven scalar specs
have `level=None`, so `s.level.value` raises AttributeError.

```bash
.venv/bin/python -c "from dessem_dashboard.charts.registry import enabled_specs, all_specs; \
e=enabled_specs(); print(len(e), len(all_specs()), [s.key for s in e])"
```

To measure the fixture volumes (`value_count`, output sizes), write a short scratch script outside
the repository that builds `scenario_tree` the way `tests/conftest.py` does, or run the failing
test once and read the measured value from its assertion message. Then confirm it on a second run.

Keep the pin-update convention: grep `tests/` for `_ENABLED_CHART_COUNT`, then grep for
`_SIN_CHART`, `== 28`, `30` and `29` near `make_sintese_dir`. The table in Current state is the
measured failing set. If a test outside it fails, fix the pin the same way and report the extra
file, because that is a scope deviation.

### Subtitles on the fixture

The fixture METADADOS writes `nome_longo_variavel = spec.title`, so fixture documents show no
subtitle (debt A4). The "no subtitle on unmodified fixture" assertions stay true for the new keys.

### Out of scope

- FALLBACK_UNITS grouping, `test_schemas.py` and the `cli.py` text (ticket-005).
- The real-data contract test (ticket-006).
- README and checklist changes.
- Any derived series.
- Any change to a title, unit or key.

### Door, structure budget, debt

This is a one-way door for key identity: the keys become default-enabled and operators may name
them in `charts.disabled`. The ticket introduces no new structure and depends on no debt ticket.

## Definition of Done

- [ ] All five acceptance criteria are met. The diff touches only the 13 listed files, unless an
      extra file is reported.
- [ ] `ruff check`, `ruff format --check` and `mypy src` exit 0. Both background pytest chunks
      pass, and coverage is at least 85%.
- [ ] No test writes to the repository's `output/` or `logs/`.
- [ ] Commit message (Portuguese): `feat: habilita os gráficos de vazão do SIN`.
