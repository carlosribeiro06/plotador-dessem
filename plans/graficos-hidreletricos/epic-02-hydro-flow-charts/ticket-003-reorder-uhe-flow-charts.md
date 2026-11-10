---
filesToBeCreated: []
filesToBeModified:
  - src/dessem_dashboard/charts/specs.py
  - tests/test_chart_specs.py
  - tests/test_charts_hydro.py
  - tests/test_charts_filters.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R3, R4, R13, R14, R7, R22, ADR-002, ADR-004]
---

# ticket-003: Reorder the Usinas hidrelétricas block into water-balance order

## Context

### Background

R13 fixes the UHE section order: GHID_UHE, VARMF_UHE, VARPF_UHE, QAFL_UHE, QINC_UHE, QDEF_UHE,
QTUR_UHE, QVER_UHE. The order goes generation, storage, inflow, release and its split. Section
order is the order of `SPECS` in `src/dessem_dashboard/charts/specs.py`, through
`builder._level_nav` and `_chart_sections`. Every SERIES chart flows through the pipeline with no
key-specific code, so moving tuple entries is the whole source change.

R14 forbids changing any key, title, unit, `notes` or `enabled` flag. ADR-002 forbids UI changes,
which means no sub-headings, CSS or JS.

### Current state (verified)

**`src/dessem_dashboard/charts/specs.py`**

The UHE block runs from `_series("GHID_UHE", ...)` to `_series("QINC_UHE", ...)`, just before
`GTER_UTE`, in this order:

GHID_UHE "Geração", QTUR_UHE "Turbinamento", QVER_UHE "Vertimento", VARMF_UHE "Volume Armazenado
(hm3)" (with `notes=_OPEN_QUESTION_2_NOTE`), VARPF_UHE "Volume Armazenado (%)" (same note),
QDEF_UHE "Defluência", QAFL_UHE "Vazão Afluente" (with `notes=_OPEN_QUESTION_3_NOTE`), QINC_UHE
"Vazão Incremental" (same note).

**Tests that pin this order**

In a scratch run of the full suite with only this reorder applied, one test failed:
`tests/test_chart_specs.py::test_enabled_specs_returns_exact_key_tuple_in_appendix_order`. It
compares against `_ENABLED_KEYS_IN_ORDER` (lines ~13-42).

Three other failures in that run came from the scratch setup, not from the reorder:
- the two `test_manifest.py` git-sha tests, because the scratch copy was not a git repository;
- the Group B failure in `test_parity.py` (`assert 2 == (2 * 2)`), which ticket-001 fixes before
  this ticket runs.

These tuples declare SPECS order in their comment but do not fail, because they are used as maps
or sets. They must still be reordered so the comments stay true (R25):

- `tests/test_charts_hydro.py:55-79`:
  - `_UHE_CHART_KEYS_IN_ORDER`;
  - `_UHE_TITLES_IN_ORDER`;
  - `_UHE_UNITS_IN_ORDER`, currently `("MW","m3/s","m3/s","hm3","%","m3/s","m3/s","m3/s")`;
  - `_UHE_ENTITY_COUNTS_IN_ORDER`, currently `(3, 3, 3, 2, 2, 3, 3, 3)`. The fixture's VARMF and
    VARPF have 2 entities.
- `tests/test_charts_filters.py:44-57`: `_PLANT_CHART_KEYS`, whose comment says "in enabled_specs
  order".

### Target state

**`specs.py`**

The UHE block is ordered GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER. Each `_series(...)`
call moves verbatim, with its arguments and `notes=` unchanged.

**Hydro test tuples, permuted together**

| Tuple | New value |
| --- | --- |
| keys | `GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER` (all `_UHE`) |
| titles | `Geração, Volume Armazenado (hm3), Volume Armazenado (%), Vazão Afluente, Vazão Incremental, Defluência, Turbinamento, Vertimento` |
| units | `("MW","hm3","%","m3/s","m3/s","m3/s","m3/s","m3/s")` |
| entity counts | `(3, 2, 2, 3, 3, 3, 3, 3)` |

**Other tuples**

- `_PLANT_CHART_KEYS` lists the same eight keys in the same order, followed by `GTER_UTE`.
- `_ENABLED_KEYS_IN_ORDER` in `test_chart_specs.py` puts the UHE slice in the new order. Nothing
  else in it changes; the SIN keys are ticket-004.

## Dependencies

- **Blocked By**: ticket-002-pass-fictitious-codes-to-registries.md
- **Blocks**: ticket-004-enable-sin-flow-charts.md

## Acceptance Criteria

1. **Given** the default registry, **when** you list
   `[s.key for s in enabled_specs() if s.group is ChartGroup.UHE]`, **then** it equals
   `["GHID_UHE","VARMF_UHE","VARPF_UHE","QAFL_UHE","QINC_UHE","QDEF_UHE","QTUR_UHE","QVER_UHE"]`.
2. **Given** each of the 8 UHE specs, **when** you compare
   `(key, title, unit, notes, enabled, kind, group, level, selector)` before and after the change,
   **then** they are identical. Only the positions differ (R14). The enabled count is unchanged,
   at 28, measured with `len(enabled_specs())`.
3. **Given** `tests/test_charts_hydro.py` and `tests/test_charts_filters.py`, **when** you read
   their order tuples, **then** they equal the new SPECS order, and the units and entity counts are
   permuted the same way. Both files pass.
4. **Given** `tests/test_chart_specs.py`, **when** it runs, **then**
   `test_enabled_specs_returns_exact_key_tuple_in_appendix_order` passes with the new UHE slice.
5. **Given** the full gate, **when** it runs, **then** ruff check, ruff format --check and mypy src
   exit 0. Pytest runs in two background chunks, `tests/test_[a-l]*.py` then
   `tests/test_[m-z]*.py --cov-append`, and both pass, with coverage at least 85%.

## Files

| File | Change |
| --- | --- |
| `src/dessem_dashboard/charts/specs.py` | Reorder 8 `_series` entries in the UHE block |
| `tests/test_chart_specs.py` | UHE slice of `_ENABLED_KEYS_IN_ORDER` |
| `tests/test_charts_hydro.py` | Four `_UHE_*_IN_ORDER` tuples, permuted together |
| `tests/test_charts_filters.py` | `_PLANT_CHART_KEYS` order |

## Technical Details

### Before and after checks

Registry access: import `enabled_specs`, `all_specs` and `ChartGroup` from
`dessem_dashboard.charts.registry`. Importing it loads the `dessem_dashboard.charts` package, whose
`__init__` registers the default catalogue. `dessem_dashboard.charts.specs` exports `SPECS` but
not these functions. Filter specs by `s.group`, never by `s.level.value`: the seven scalar specs
have `level=None`, so `s.level.value` raises AttributeError.

To prove R14, snapshot the attributes before and after the edit and diff the two files:

```bash
.venv/bin/python -c "from dessem_dashboard.charts.registry import ChartGroup; \
from dessem_dashboard.charts.specs import SPECS; \
[print(s) for s in SPECS if s.group is ChartGroup.UHE]" > <scratchpad>/before.txt
```

Use the scratchpad, not the repository.

The specs.py module docstring has no UHE order text, so leave it alone. Ticket-004 rewrites its
counts.

### Pytest in the background

The single-run `--cov` was OOM-killed on this machine, so run the two chunks:

```bash
.venv/bin/pytest tests/test_[a-l]*.py --cov=dessem_dashboard -q
.venv/bin/pytest tests/test_[m-z]*.py --cov=dessem_dashboard --cov-append --cov-report=term-missing -q
```

`test_manifest.py`'s git-sha tests need the real repository checkout. Run from the repository root.

### Out of scope

- Enabling or moving `QDEF_SIN`, `QTUR_SIN` or `QVER_SIN`, and every count change (ticket-004).
- The FALLBACK_UNITS ordering (ticket-005).
- Any change to a title, unit or key.
- Any UI, CSS or JS change.
- The Submercado order.

### Door, structure budget, debt

The decision is a two-way door, a tuple edit. The ticket introduces no new structure and depends on
no debt ticket. It is a structure-only commit, separate from the behaviour change in ticket-004.

## Definition of Done

- [ ] All five acceptance criteria are met. The diff touches only the 4 listed files.
- [ ] The gate is green and coverage is at least 85%.
- [ ] No stale "in order" comment remains in the touched tuples.
- [ ] Commit message (Portuguese): `refactor: ordena os gráficos de usinas hidrelétricas pelo balanço hídrico`.
