---
filesToBeCreated: []
filesToBeModified:
  - tests/test_integration_exemplo.py
filesToBeDeleted: []
agent: python-task-automation-developer
tier: standard
implements: [R20, R6, R13, R22, R23, ADR-006, ADR-003]
---

# ticket-006: Real-data contract test for the hydro flow charts

## Context

### Background

R20 requires an automated real-data check on `examples/Oficial` and `examples/Modificado`. The
check must skip when the data is absent, and it runs with
`DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`.

Answers A1 and A2 limit what it may assert, so that the dashboard suite never depends on the
synthesizer. It asserts the dashboard contract only:

- zero warnings, taken literally;
- SIN and UHE order;
- the shape of the three SIN flow charts;
- value fidelity against the files.

It must never assert `QDEF == QTUR + QVER` or that the QINC Diferença is zero.

### Current state

`tests/test_integration_exemplo.py` (426 lines) provides these helpers:

- `_build_settings(tmp_path)`: reads the repository's `settings.json` and redirects output and logs
  under `tmp_path`.
- `_extract_payload(document) -> dict`.
- `_require_scenarios(minimum)`.
- The fixture `exemplo_two_scenario_paths`, which returns the first two qualifying scenarios sorted
  by name. For `examples/` that is `Modificado`, then `Oficial`.
- `_WARNING_SHAPES` and `_ENABLED_CHART_COUNT`. After ticket-004, `_ENABLED_CHART_COUNT` is 31.
- The existing tests call `pipeline.run(scenario_dirs=[a, b], output_file=..., reference=a.name,
  settings=settings)`.

The module docstring says the module "never opens, lists, copies or transcribes anything under it
itself". The new test reads Parquet files with pandas to build its expected values, so the
docstring must be narrowed.

`tests/test_parity.py` (Group B) already shows the pattern:

```python
pd.read_parquet(sintese_dir / f"{chart_key}.parquet", engine="pyarrow")
```

It then reads the columns `estagio` and `valor`, and rounds with
`round(v, decimals)`, normalising -0.0 to 0.0 (`_round_like_payload`).

`tests/dashboard_document.py` provides `sections_by_group(document, group)` and
`sections_by_chart_key(document)`.

### Payload facts (from `dashboard/payload.py`)

- Each chart entry carries `subtitle`, `unit`, `entities` and `series`.
- `series[entity_id][scenario][axis_key]` is a list of floats. The SIN entity id is `""`.
- `subtitle` is the registry long name when that name is neither None nor equal to `spec.title`,
  and None otherwise (`payload.py:159`).
- The long name comes from the primary deck's `METADADOS_OPERACAO`. The primary deck is
  `discover_scenarios(...)[0].decks[0]`, with decks sorted by name.
- Deck axis keys use the `"%d/%m/%Y"` date of `min(EST.data_inicio)`. The chained axis key is
  `"encadeado"`.

### Values measured during planning (for orientation only; never hard-code them)

- 0 warnings and 31 charts.
- Subtitles: "Vazão Defluente", "Vazão Turbinada" and "Vazão Vertida". Unit m3/s, one entity `""`.
- The deck axis "15/08/2026" has 80 stages. The chained axis has 48 points, which is
  `chaining.stages_per_deck`.

## Dependencies

- **Blocked By**: ticket-005-remove-stale-count-text.md
- **Blocks**: ticket-007-checklist-flow-section.md

## Acceptance Criteria

1. **Given** `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, **when** the new test runs, **then** it
   passes. `pytest -rs` shows it PASSED, not SKIPPED. Without the variable, and without `exemplo/`,
   it is SKIPPED.
2. **Given** that run, **when** warnings are collected, **then** `result.warnings` is empty, or the
   equivalent run-result attribute is empty (A1). The assertion message lists every warning found,
   so a failure on another tree is self-explaining (test-strategist sign-off note (a)).
3. **Given** the document, **when** sections are listed by group, **then** the SIN chart keys equal
   `[s.key for s in enabled_specs() if s.group is ChartGroup.SIN]`, and that list equals the R13
   tuple written in the test. The same holds for UHE.
4. **Given** each of `QDEF_SIN`, `QTUR_SIN` and `QVER_SIN`, **when** its payload entry is checked,
   **then**:
   - it has exactly one entity, `""`;
   - its unit is `m3/s`;
   - its subtitle equals the primary deck's METADADOS long name when that name differs from the
     spec title, and is None otherwise.
5. **Given** each of those three charts, each scenario and each deck, **when** the payload series
   are compared, **then**:
   - the deck-axis array equals the file's `valor`, ordered by `estagio`, after
     `round(v, settings.output.decimals)` with -0.0 normalised to 0.0;
   - the first `min(stages_per_deck, n)` points of that deck's segment in the chained array equal
     the same values.

   The test never compares QDEF with QTUR + QVER and never checks QINC.

## Files

| File | Change |
| --- | --- |
| `tests/test_integration_exemplo.py` | New test `test_exemplo_sin_flow_charts_follow_dashboard_contract`, optional private helpers, docstring narrowed |

## Technical Details

### Test outline

```python
_SIN_ORDER = ("GTER_SIN", "GHID_SIN", "GUNS_SIN", "EARMF_SIN", "VARMF_SIN",
              "QDEF_SIN", "QTUR_SIN", "QVER_SIN")
_UHE_ORDER = ("GHID_UHE", "VARMF_UHE", "VARPF_UHE", "QAFL_UHE", "QINC_UHE",
              "QDEF_UHE", "QTUR_UHE", "QVER_UHE")
_SIN_FLOW_KEYS = ("QDEF_SIN", "QTUR_SIN", "QVER_SIN")

def test_exemplo_sin_flow_charts_follow_dashboard_contract(
    exemplo_two_scenario_paths: tuple[Path, Path], tmp_path: Path
) -> None:
    scenario_a, scenario_b = exemplo_two_scenario_paths
    settings = _build_settings(tmp_path)
    result = pipeline.run(scenario_dirs=[scenario_a, scenario_b], output_file=tmp_path / "out" / "d.html",
                          reference=scenario_a.name, settings=settings)
    warnings = list(result.warnings)       # use the real attribute name; read pipeline.RunResult
    assert warnings == [], "unexpected warnings:\n" + "\n".join(warnings)
    ...
```

Steps:

1. Read `pipeline.py` and `dashboard_document.py` for the exact result attribute and helper
   signatures before you write the test.
2. Build the expected values per deck. List the deck folders with the same rule `discovery` uses:
   call `dessem_dashboard.data.discovery.discover_scenarios` with the settings. Do not list
   directories by hand.
3. Read `EST.parquet` to get the date key, and `<KEY>.parquet` to get `estagio` and `valor`.
4. Read the long name from the primary deck's `METADADOS_OPERACAO.parquet`, using the key column
   that `readers.read_registry` validates. Read `readers.py` and `registries.py` to find the
   column names.
5. Use `round` plus the -0.0 normalisation for comparisons. Both sides are then exact, so no
   tolerance is needed.

### Docstring narrowing

Amend the "never opens ..." sentence:

- The module may read the tree's Parquet files with pandas to build expected values for
  assertions.
- It still never copies, writes or transcribes values into the source, and never hard-codes a
  measured value.

### Constraints

Registry access: import `enabled_specs`, `all_specs` and `ChartGroup` from
`dessem_dashboard.charts.registry`. Importing it loads the `dessem_dashboard.charts` package, whose
`__init__` registers the default catalogue. `dessem_dashboard.charts.specs` exports `SPECS` but
not these functions. Filter specs by `s.group`, never by `s.level.value`: the seven scalar specs
have `level=None`, so `s.level.value` raises AttributeError.

- `pandas.read_parquet` in tests is allowed. The "only caller" rule applies to `src/` (R23).
- All output goes under `tmp_path`.
- Leave `_WARNING_SHAPES` and the other tests unchanged.

### Out of scope

- Synthesis properties: QDEF = QTUR + QVER, the QINC Diferença and any balance identity (A1, A2).
- Submercado assertions (R2).
- Changes to `exemplo_tree.py` or `test_parity.py`.

### Door, structure budget, debt

The decision is a two-way door. The only structure allowed is private helpers inside this module.
The ticket depends on no debt ticket.

## Definition of Done

- [ ] The new test PASSED under the variable and was SKIPPED without it. Paste both `pytest -rs`
      summaries into the report.
- [ ] `ruff check`, `ruff format --check` and `mypy src` exit 0.
- [ ] Both background pytest chunks pass, and coverage is at least 85%.
- [ ] Nothing is written to the repository's `output/` or `logs/`.
- [ ] Commit message (Portuguese): `test: valida os gráficos de vazão do SIN com dados reais`.
