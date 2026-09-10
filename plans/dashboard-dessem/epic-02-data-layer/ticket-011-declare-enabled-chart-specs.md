# ticket-011 Declare the enabled chart specs

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Appendix A.6 of `plans/dashboard-dessem/00-master-plan.md` fixes the chart catalogue: 23 specs
enabled by default, covering every item of the spec minimum list plus `TEMPO`, and 19 further specs
shipped disabled to demonstrate and enable the extensibility that `planning-context.md` decision 7
demands. Two entries exist because the spec is ambiguous and the developer chose to ship both
candidates: UHE "Volume armazenado" ships as `VARMF_UHE` in hm3 and `VARPF_UHE` in percent, and UHE
"Vazão" ships as `QAFL_UHE` (afluente) and `QINC_UHE` (incremental). Either of each pair can be
switched off through `charts.disabled` without touching code.

### Relation to Epic

This ticket turns the registry mechanics of ticket-010 into the actual catalogue that ticket-018
iterates to decide which files to read, and that Epics 3 and 4 iterate to decide which charts and
selectors to render. It is the single place a future chart is added.

### Current State

`src/dessem_dashboard/charts/registry.py` exposes `ChartSpec`, `ChartKind`, `EntitySelector`,
`ChartGroup`, the `ChartRegistry` class, the `REGISTRY` singleton and the delegating functions.
`src/dessem_dashboard/data/schemas.py` exposes `AggregationLevel` and `FALLBACK_UNITS`. Nothing is
registered yet, so `all_specs()` returns an empty tuple.

## Specification

### Requirements

1. Create `src/dessem_dashboard/charts/specs.py` declaring a module-level tuple `SPECS` of
   `ChartSpec` instances and a function `register_default_specs(registry: ChartRegistry | None =
   None) -> None` that registers every entry of `SPECS` into the given registry, defaulting to the
   `REGISTRY` singleton.
2. `SPECS` contains the 23 enabled entries of Appendix A.6 in the table order, then the 19 disabled
   entries listed at the end of Appendix A.6, each with `enabled=False`.
3. Each entry sets `unit` to the value of `FALLBACK_UNITS[source_file]`, referencing the mapping
   rather than repeating the literal, so the two declarations cannot diverge.
4. Each entry sets `title` to a Portuguese chart title matching the "Spec item" column of
   Appendix A.6, for example `"Geração Hidrelétrica"` for `GHID_SIN` and
   `"Volume Armazenado (%)"` for `VARPF_UHE`.
5. `selector` follows the Appendix A.6 "Selector" column: `NONE` for SIN and for the two
   `SCALAR_BY_DECK` entries, `SUBMARKET` for the six SBM entries, `SUBMARKET_PAIR` for `INT_SBP`,
   `HYDRO_PLANT` for the eight UHE entries and `THERMAL_PLANT` for `GTER_UTE`.
6. `CUSTOS` and `TEMPO` use `kind=ChartKind.SCALAR_BY_DECK` and `level=None`; every other entry uses
   `kind=ChartKind.SERIES` with the `AggregationLevel` matching its group.
7. The two ambiguity pairs carry a `notes` value naming the master plan open question, so a reader
   of the code learns why both exist.
8. `register_default_specs` is called from `src/dessem_dashboard/charts/__init__.py` at import time
   into the singleton, so importing `dessem_dashboard.charts` yields a populated registry, and
   calling it twice on the singleton must not raise. Guard with a module-level boolean.

### Inputs

None: the catalogue is a literal declaration.

### Outputs and Behavior

After `import dessem_dashboard.charts`, `enabled_specs()` returns exactly the 23 enabled specs in
Appendix A.6 order and `all_specs()` returns 42 specs.

### Error Handling

Registration errors are the responsibility of `ChartRegistry.register` from ticket-010. This module
adds no error handling of its own beyond the double-registration guard.

## Dependencies

- **Blocked By**: `ticket-010-add-chart-registry-mechanics.md`
- **Blocks**: `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given a fresh `ChartRegistry()` passed to `register_default_specs`, when `enabled_specs()` is
      called on it, then the tuple of keys equals exactly
      `("GTER_SIN","GHID_SIN","GUNS_SIN","EARMF_SIN","VARMF_SIN","MER_SBM","GHID_SBM","GTER_SBM","GUNS_SBM","CMO_SBM","VARMF_SBM","INT_SBP","GHID_UHE","QTUR_UHE","QVER_UHE","VARMF_UHE","VARPF_UHE","QDEF_UHE","QAFL_UHE","QINC_UHE","GTER_UTE","CUSTOS","TEMPO")`.
- [ ] Given the same registry, when `all_specs()` is called, then its length is `42` and exactly
      `19` of the returned specs have `enabled` false.
- [ ] Given each spec in `SPECS`, when its `unit` is compared with `FALLBACK_UNITS[spec.source_file]`,
      then the two are equal for all 42 specs.
- [ ] Given the enabled specs grouped by `group`, when the group sizes are counted, then they equal
      `{SIN: 5, SBM: 6, SBP: 1, UHE: 8, UTE: 1, EXECUCAO: 2}`, and the two `EXECUCAO` specs are the
      only ones with `kind == ChartKind.SCALAR_BY_DECK` and `level is None`.
- [ ] Given the repository root, when
      `.venv/bin/pytest tests/test_chart_specs.py -q && .venv/bin/mypy src` is run, then both
      commands exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write a small private helper `_series(key, group, level, selector, title, *, enabled=True,
   notes="")` that fills `source_file=key`, `kind=ChartKind.SERIES` and
   `unit=FALLBACK_UNITS[key]`, so each catalogue line stays one readable call. Every enabled series
   key equals its source file stem, which makes `source_file=key` correct.
2. Write a matching `_scalar(key, title, *, notes="")` helper for `CUSTOS` and `TEMPO`.
3. Declare `SPECS` as a tuple built from those helpers, in Appendix A.6 order, with a blank line
   between groups and no per-line comments.
4. Implement `register_default_specs` with a module-level `_registered_singleton = False` guard that
   applies only when the target registry is the singleton.
5. Call `register_default_specs()` from `charts/__init__.py` after importing the module.
6. Write `tests/test_chart_specs.py` using a fresh `ChartRegistry()` for the catalogue assertions and
   one test importing `dessem_dashboard.charts` twice to prove the guard works.

### Key Files to Create/Modify

- `src/dessem_dashboard/charts/specs.py` (create)
- `src/dessem_dashboard/charts/__init__.py` (modify: import and call `register_default_specs`)
- `tests/test_chart_specs.py` (create)

### Patterns to Follow

- Titles are Portuguese and use sentence-style capitalisation of the domain terms as in
  Appendix A.6; the brand manual forbids long runs of capitals.
- Reference `FALLBACK_UNITS` instead of repeating unit literals, so a unit correction has one home.
- Keep the file declarative: no conditionals, no loops other than inside `register_default_specs`.

### Pitfalls to Avoid

- `MER_SBM` is the "Carga" chart: the spec calls it Carga while the file is the Mercado de Energia
  variable. Use the title `"Carga (Mercado de Energia)"` so the operator recognises both names, and
  keep `MERL_SBM` disabled.
- `GUNS_SBM` and `GUNS_SIN` are the "Geração não simulada" charts; `GUNSD_*` is a different variable
  and stays disabled.
- `EARMF_SIN` is in MWh while `VARMF_SIN` is in hm3: both appear in the SIN group and must not be
  merged.
- Do not register the two `EXECUCAO` specs with an `AggregationLevel`; `register` in ticket-010
  rejects `SERIES` with a null level, and passing a level to a `SCALAR_BY_DECK` spec would mislead
  ticket-018 into treating them as time series.
- Do not let the import-time registration run twice and raise: the guard is required because
  `charts/__init__.py` is imported by several modules.

### Out of Scope

- Reading `charts.disabled` from the settings (ticket-018).
- Any per-chart visual attribute such as colour, height or axis type, which `theme.py` owns in
  Epic 3.
- Enabling any of the 19 disabled entries, which is a developer decision recorded as master plan
  open questions 2 and 3.
- Deriving titles from `METADADOS_OPERACAO` at runtime; ticket-015 supplies the metadata lookup and
  Epic 3 decides whether to prefer it over these static titles.

## Testing Requirements

### Unit Tests

`tests/test_chart_specs.py`:

- the exact enabled key tuple, in order;
- total spec count 42 and disabled count 19;
- unit consistency with `FALLBACK_UNITS` for all 42 specs;
- group size counts and the level and kind pairing of the two `EXECUCAO` specs;
- selector value per group, asserting that every UHE spec uses `HYDRO_PLANT` and `GTER_UTE` uses
  `THERMAL_PLANT`;
- every `source_file` of an enabled series spec equals its `key`;
- the four ambiguity-pair specs carry a non-empty `notes`;
- `enabled_specs(disabled=("VARPF_UHE","QINC_UHE"))` returns 21 specs, proving the two ambiguities
  can be switched off;
- importing `dessem_dashboard.charts` twice leaves `all_specs()` at 42 entries.

### Integration Tests

None: the catalogue is metadata only. Ticket-012 will assert that the fixture builder produces one
file per enabled `source_file`, which is the real cross-check.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] The 23 enabled keys match Appendix A.6 exactly, with no additions and no omissions.
- [ ] The 19 disabled keys match the disabled list at the end of Appendix A.6 exactly.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
