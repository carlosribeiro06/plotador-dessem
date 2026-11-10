---
filesToBeCreated: []
filesToBeModified:
  - src/dessem_dashboard/data/schemas.py
  - tests/test_schemas.py
  - src/dessem_dashboard/cli.py
  - tests/test_cli.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R25, R24, R23, R22, ADR-004]
---

# ticket-005: Regroup FALLBACK_UNITS and remove stale count and Avisos text from source

## Context

### Background

After ticket-004, the catalogue has 47 specs: 31 enabled and 16 disabled. `FALLBACK_UNITS` is
keyed by `source_file`, not by chart key. The 31 enabled specs read 26 distinct source files: the
24 SERIES keys, whose `source_file` equals their key, plus `CUSTOS` and `TEMPO`, which back the
seven dedicated scalar charts `CUSTO_*` and `TEMPO_*`. Several source comments and one
log message still describe an older state:

- 23 keys enabled and 19 disabled.
- A UHE order that ticket-003 has replaced.
- A dashboard "Avisos" section that no longer exists. `cli.py` still tells the operator to read
  the full warning list in it.

R25 requires that no stale text be left behind.

### Current state (verified during planning, line numbers approximate)

**`src/dessem_dashboard/data/schemas.py`**

- Lines ~97-99 carry this comment above `FALLBACK_UNITS`:

  ```
  # ... Covers the 23 keys enabled by default (Appendix A.6) plus the 19 disabled registry
  # entries listed below that table; units verified against METADADOS_OPERACAO.parquet.
  ```

- The dict has an `# Enabled chart catalogue (Appendix A.6).` block in the old UHE order:
  GHID, QTUR, QVER, VARMF, VARPF, QDEF, QAFL, QINC.
- `"QDEF_SIN"`, `"QTUR_SIN"` and `"QVER_SIN": "m3/s"` sit under `# Disabled registry entries`.

**`tests/test_schemas.py`**

- Lines 25-74 hold `_ENABLED_CHART_KEYS`, under the comment "The 23 enabled chart-catalogue keys".
  It has 23 entries in the old UHE order, including `CUSTOS` and `TEMPO`.
- `_DISABLED_CHART_KEYS` sits under the comment "The 19 disabled". It has 19 entries and ends with
  `QDEF_SIN`, `QTUR_SIN`, `QVER_SIN`.
- `test_fallback_units_has_exactly_forty_two_keys` checks the dict size, which stays at 42.

**`src/dessem_dashboard/cli.py`**

- Lines 24-29 carry the comment "Measured cap (epic-05 refinement): 23 charts ... reach 92 ...
  run_manifest.json and the dashboard's Avisos section still carry every message", above
  `_MAX_LOGGED_WARNINGS = 20`.
- The `_log_warnings` docstring mentions "the dashboard's Avisos section".
- The truncation message reads `"%d aviso(s) adicional(is) omitido(s) no console e no arquivo de
  log; lista completa em run_manifest.json e na seção Avisos do dashboard."`

**`tests/test_cli.py`**

- Line ~589 asserts `assert "Avisos" in truncation_message`.

### Target state

**`src/dessem_dashboard/data/schemas.py`**

- The `FALLBACK_UNITS` comment says it covers the 26 source files enabled by default plus the 16
  disabled registry entries.
- Both numbers are measured, not copied, from the distinct `source_file` values (see the script in
  Technical Details):
  - enabled entries: `len(dict.fromkeys(s.source_file for s in enabled_specs()))`, after ticket-004;
  - disabled entries: `len(FALLBACK_UNITS) - enabled`.
- The enabled block lists keys in the first-occurrence order of `source_file` in `SPECS`. That means:
  - the three `Q*_SIN` keys come right after `VARMF_SIN`;
  - the UHE keys run GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER;
  - `CUSTOS` and `TEMPO` come last, after `GTER_UTE`.
- The disabled block no longer holds the three SIN flow keys. The dict values, the key set and the
  size of 42 are unchanged.
- Drop the "(Appendix A.6)" qualifiers if they no longer match. Keep the CUSTOS unit comment.

**`tests/test_schemas.py`**

- `_ENABLED_CHART_KEYS` holds the 26 enabled source files in the same first-occurrence order as
  `FALLBACK_UNITS`, ending with `CUSTOS` and `TEMPO`. Its comment says "The 26 enabled ...". It
  holds source files, not chart keys, so it never lists `CUSTO_*` or `TEMPO_*`.
- `_DISABLED_CHART_KEYS` has 16 entries under the comment "The 16 disabled ...".
- The test that pins 42 keys is unchanged.

**`src/dessem_dashboard/cli.py`**

- The comment states the measured figures: 26 per-chart warnings for one (scenario, deck), and 104
  for four combinations (two scenarios by two decks).
- It keeps the derivation sentence and drops "Avisos". It must say that `run_manifest.json` still
  carries every message, uncapped.
- The docstring drops the Avisos clause.
- The message becomes `"%d aviso(s) adicional(is) omitido(s) no console e no arquivo de log; lista
  completa em run_manifest.json."`
- `_MAX_LOGGED_WARNINGS` stays 20.

**`tests/test_cli.py`**

- The assertion becomes `assert "Avisos" not in truncation_message`.
- The `"run_manifest.json" in` assertion stays.

## Dependencies

- **Blocked By**: ticket-004-enable-sin-flow-charts.md
- **Blocks**: ticket-006-real-data-flow-contract-test.md

## Acceptance Criteria

1. **Given** `FALLBACK_UNITS`, **when** its keys are compared with
   `list(dict.fromkeys(s.source_file for s in enabled_specs()))` (26 entries), **then**:
   - the first 26 keys of the dict equal that list, in that order;
   - every one of those entries is a dict key;
   - the key set equals the set before the change, and the size is still 42.
2. **Given** `tests/test_schemas.py`, **when** it runs, **then** `_ENABLED_CHART_KEYS` has 26 entries
   and `_DISABLED_CHART_KEYS` has 16. The comments state 26 and 16, and every test in the file
   passes.
3. **Given** more than 20 warnings, **when** `cli.main` logs them, **then** the truncation record
   contains `run_manifest.json` and does not contain `Avisos`. `tests/test_cli.py` asserts both.
4. **Given** the repository, **when** you run
   `grep -rn "Avisos\|23 keys\|19 disabled\|23 charts" src/`, **then** it prints nothing.
5. **Given** the full gate, **when** it runs, **then** all four commands exit 0. Run pytest in two
   background chunks: `tests/test_[a-l]*.py`, then `tests/test_[m-z]*.py --cov-append`. Coverage
   must stay at or above 85%.

## Files

| File | Change |
| --- | --- |
| `src/dessem_dashboard/data/schemas.py` | Comment rewrite; dict entries regrouped into SPECS order (structure only) |
| `tests/test_schemas.py` | Partition tuples regrouped, comments now say 26 and 16 |
| `src/dessem_dashboard/cli.py` | Comment (26/104), docstring, Portuguese message without Avisos |
| `tests/test_cli.py` | `"Avisos" not in` assertion |

## Technical Details

### Measure the numbers (never copy them)

```bash
.venv/bin/python -c "from dessem_dashboard.charts.registry import enabled_specs; \
from dessem_dashboard.data.schemas import FALLBACK_UNITS as F; \
e=list(dict.fromkeys(s.source_file for s in enabled_specs())); assert set(e) <= set(F), set(e) - set(F); \
print(len(e), len(F)-len(e), e)"
```

Notes on the script:

- `enabled_specs` and `all_specs` live in `dessem_dashboard.charts.registry`. Importing them from
  `dessem_dashboard.charts.specs` raises ImportError.
- Importing `dessem_dashboard.charts.registry` loads the `dessem_dashboard.charts` package, whose
  `__init__` calls `register_default_specs()`, so the registry is populated.
- `FALLBACK_UNITS` is keyed by `source_file`, not by chart key. `specs.py::_scalar_series` takes
  each scalar chart's unit from `FALLBACK_UNITS[source_file]`, and its docstring says the scalar
  chart key is distinct from `source_file`.
- Measuring by `s.key` would therefore give 31 and 11 and include `CUSTO_PRESENTE`, which is not a
  dict key.

Measured on `main` during REVISION round 1 (before ticket-004), the script prints `23 19`. After
ticket-004 it should print `26 16`.

If the measurement differs from 26 and 16, use the measured values and report the difference,
because ticket-004 or a later change moved the catalogue. A measurement of 31 means the script was
changed to count chart keys; that is a defect in the script, not a catalogue change.

### Per-chart warning arithmetic for the cli.py comment

A missing synthesis folder raises one warning per enabled source file: the 24 SERIES files plus
the `CUSTOS` and `TEMPO` scalar files. That is the same 26 `source_file` count measured above. That gives 26 warnings for one (scenario, deck) and 4 x 26 = 104
for two scenarios by two decks.

Verify the "one warning per key" claim by reading `consolidate._load_series` and the scalar loaders
before you write it. If it does not hold, state the measured figure and say so in the report. The
numbers feed README ticket-009.

### Language rules

- The log message is Portuguese, as user-facing text.
- Comments and the docstring are English.

### Out of scope

- The README's Logging section and its 23/92 figures belong to ticket-009.
- No change to the `_MAX_LOGGED_WARNINGS` value.
- No change to any FALLBACK_UNITS value or key.
- No change to warning text other than the truncation message.

### Door, structure budget, debt

The decision is a two-way door. The ticket introduces no new structure and depends on no debt
ticket.

## Definition of Done

- [ ] All five acceptance criteria are met. The diff touches only the 4 listed files.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] Both background pytest chunks pass, and the combined coverage is at least 85%.
- [ ] No dead or stale comment remains in the touched regions.
- [ ] Commit message (Portuguese): `refactor: alinha FALLBACK_UNITS e textos de contagem ao catálogo`.
