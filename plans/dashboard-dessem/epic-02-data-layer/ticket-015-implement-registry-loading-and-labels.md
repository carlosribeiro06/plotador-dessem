# ticket-015 Implement registry loading and labels

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The series files carry only numeric codes, so every label shown in the dashboard comes from a
registry: `UHE.parquet` supplies the 165 hydro plant names that the name filter of spec section 3
searches, `UTE.parquet` the 89 thermal plant names, `SBM.parquet` the submarket short and long names
used in chart titles and in the interchange pair labels, `REE.parquet` the equivalent reservoir
names, and `METADADOS_OPERACAO.parquet` the variable titles and units. Three real-data details make
this non-trivial: `SBM.codigo_submercado` is the nullable `Int64` dtype, code 99 has a **null**
`nome_submercado`, and `METADADOS_OPERACAO` has null `nome_*` values for `VAGUA_UHE` and
`VCALHA_UHE`. Codes 11 and 99 are fictitious submarkets that the default configuration hides from
submarket charts while keeping every interchange pair.

### Relation to Epic

Ticket-018 calls `load_registries` once per deck and stores the result in `DashboardData`, from
which Epic 3 builds the chart titles and Epic 4 builds the plant filter index. This ticket is
therefore the single source of every human-readable label in the dashboard.

### Current State

`src/dessem_dashboard/data/` holds `__init__.py`, `schemas.py`, `discovery.py` and `readers.py`.
`read_registry` returns validated frames and preserves the `Int64` dtype. `FALLBACK_UNITS` in
`schemas.py` covers all 42 chart keys. The ticket-012 fixtures write `SBM.parquet` with a null
`nome_submercado` for code 11 and write `METADADOS_OPERACAO.parquet` from `FALLBACK_UNITS`.

## Specification

### Requirements

1. Create `src/dessem_dashboard/data/registries.py` declaring the frozen slotted dataclasses
   `HydroPlant` (`code: int`, `name: str`, `ree_code: int`, `ree: str`, `submarket_code: int`,
   `submarket: str`), `ThermalPlant` (`code`, `name`, `submarket_code`, `submarket`),
   `Submarket` (`code: int`, `short_name: str`, `long_name: str`, `fictitious: bool`) and
   `VariableMeta` (`key: str`, `short_name: str`, `long_name: str`, `unit: str`).
2. Declare `@dataclass(frozen=True, slots=True) class Registries` with fields
   `hydro: Mapping[int, HydroPlant]`, `thermal: Mapping[int, ThermalPlant]`,
   `submarkets: Mapping[int, Submarket]`, `rees: Mapping[int, str]` and
   `variables: Mapping[str, VariableMeta]`, plus the methods
   `unit_for(chart_key) -> str`, `title_for(chart_key) -> str | None`,
   `hydro_name(code) -> str`, `thermal_name(code) -> str` and
   `submarket_label(code) -> str`.
3. Expose `load_registries(sintese_dir: Path, *, fictitious_codes: Sequence[int] = (11, 99)) ->
   Registries`, reading the five registry files through `readers.read_registry`.
4. `unit_for` returns the `METADADOS_OPERACAO` unit when present and non-null, otherwise
   `FALLBACK_UNITS[chart_key]`, and raises `RegistryError` when the key is in neither.
5. `title_for` returns the `nome_longo_variavel` when present and non-null, otherwise `None`, so the
   caller can fall back to the static `ChartSpec.title`.
6. A `Submarket` with a null `nome_submercado` takes its `short_name` as `long_name`. Its
   `fictitious` flag is true when its code is in `fictitious_codes`.
7. `hydro_name` and `thermal_name` return the registry name when known and the Portuguese fallback
   `f"Usina {code}"` when the code is absent from the registry, because a series file may reference
   a plant the registry omits.
8. `submarket_label(code)` returns `f"{short_name} ({long_name})"` for a known code and
   `f"Submercado {code}"` otherwise.
9. Expose `visible_submarket_codes(registries: Registries, *, include_fictitious: bool) ->
   tuple[int, ...]`, returning the sorted codes, excluding the fictitious ones when
   `include_fictitious` is false.
10. Log at INFO one line with the counts of hydro plants, thermal plants, submarkets, equivalent
    reservoirs and variables loaded.

### Inputs

A deck synthesis directory and the list of fictitious submarket codes from
`Settings.submarkets.fictitious_codes`.

### Outputs and Behavior

One immutable `Registries` per deck. The function performs five reads and no writes.

### Error Handling

`DataFileError` propagates from `read_registry` when a registry file is missing, because a deck
without `UHE.parquet` cannot label its plant charts and that is a hard failure rather than a
degradable warning. `RegistryError` for an unknown chart key in `unit_for`. No bare `except`.

## Dependencies

- **Blocked By**: `ticket-014-implement-typed-parquet-readers.md`
- **Blocks**: `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given a generated `sintese_dir`, when `load_registries(sintese_dir)` is called, then
      `registries.hydro[1].name` equals the name written by the fixture,
      `registries.submarkets[1].short_name` equals `"SE"` and `registries.rees[1]` is a non-empty
      string.
- [ ] Given a `sintese_dir` whose `SBM.parquet` holds `codigo_submercado=11` with a null
      `nome_submercado`, when the registries are loaded, then `registries.submarkets[11].long_name`
      equals `registries.submarkets[11].short_name` and
      `registries.submarkets[11].fictitious` is `True`.
- [ ] Given a `sintese_dir` whose `METADADOS_OPERACAO.parquet` has no row for `QTUR_UHE`, when the
      registries are loaded, then `registries.unit_for("QTUR_UHE")` equals `"m3/s"` from
      `FALLBACK_UNITS`, and `registries.unit_for("NAO_EXISTE")` raises `RegistryError`.
- [ ] Given the loaded registries, when
      `visible_submarket_codes(registries, include_fictitious=False)` is called, then it returns only
      the non-fictitious codes present in the fixture, in ascending order, and calling it with
      `include_fictitious=True` additionally returns `11`.
- [ ] Given the loaded registries, when `registries.hydro_name(9999)` is called, then it returns
      `"Usina 9999"`, and `.venv/bin/pytest tests/test_registries.py -q` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Declare the five dataclasses, then `Registries` with its lookup methods implemented as small
   `dict.get` calls with the documented fallbacks.
2. In `load_registries`, read the five files, then build each mapping with a vectorised
   `itertuples` pass; `itertuples` over a 165-row registry is acceptable and clearer than a
   `to_dict` gymnastics, and the row count is bounded by the number of plants.
3. Convert `SBM.codigo_submercado` from `Int64` to `int` with `int(value)` after dropping null codes
   with `dropna(subset=["codigo_submercado"])`, and treat a null `nome_submercado` with
   `pandas.isna`.
4. Build `variables` from `METADADOS_OPERACAO` keyed by `chave`, storing `unit` as the file value
   when non-null and otherwise the `FALLBACK_UNITS` value, so `unit_for` becomes a plain lookup with
   one final fallback for keys absent from the file altogether.
5. Wrap each mapping in `types.MappingProxyType` before constructing `Registries`, so the dataclass
   is genuinely immutable.
6. Write `tests/test_registries.py`, using the fixture generator and rewriting individual registry
   files to create the null and missing-row cases.

### Key Files to Create/Modify

- `src/dessem_dashboard/data/registries.py` (create)
- `tests/test_registries.py` (create)

### Patterns to Follow

- Frozen slotted dataclasses and `MappingProxyType`, consistent with `schemas.py`.
- Portuguese fallback labels (`"Usina 9999"`, `"Submercado 7"`) because they reach the dashboard UI.
- `Mapping` for the dataclass fields, concrete `tuple[int, ...]` for the
  `visible_submarket_codes` return.

### Pitfalls to Avoid

- `pandas.isna` is required for the null checks: a null in a `str`-dtype column is not the empty
  string, and `if value:` would treat the literal string `"nan"` as truthy.
- Do not cast `codigo_submercado` with `astype(int)` on a column containing nulls: it raises. Drop
  the nulls first, and log a warning naming the dropped rows.
- Do not filter the fictitious submarkets inside `load_registries`: the registry must stay complete
  because `INT_SBP` labels need codes 11 and 99. Filtering is the caller decision through
  `visible_submarket_codes`.
- Do not merge `UHE.parquet` with the series files here; entity lists come from the series files
  themselves, per decision 16.
- Do not assume `codigo_ree` is present for a plant: the real `VCALHA_UHE` covers 11 of the 12
  reservoirs, so `rees.get` must tolerate a miss.

### Out of Scope

- Building the plant filter index for the dashboard, which is ticket-028.
- Choosing between the metadata title and the static `ChartSpec.title`, which Epic 3 decides.
- Reading `submarkets.include_fictitious` from the settings, which ticket-018 does.
- Registries for the 19 disabled chart keys beyond what `METADADOS_OPERACAO` already contains.

## Testing Requirements

### Unit Tests

`tests/test_registries.py`:

- happy path: hydro, thermal, submarket, REE and variable counts and one spot check each;
- null `nome_submercado` falls back to the short name;
- `fictitious` flag for codes 11 and 99, and false for codes 1 to 4;
- a null `codigo_submercado` row is dropped with a warning, asserted through `caplog`;
- `unit_for` from metadata, from fallback, and raising on an unknown key;
- `title_for` returns the long name, and `None` when the metadata value is null;
- `hydro_name` and `thermal_name` fallbacks for unknown codes;
- `submarket_label` for a known and an unknown code;
- `visible_submarket_codes` with and without the fictitious codes;
- a missing `UHE.parquet` raises `DataFileError`;
- the returned mappings reject mutation, asserted with `pytest.raises(TypeError)`.

### Integration Tests

None. The 165-plant, 89-thermal real registries are exercised by ticket-034.

## Definition of Done

- [ ] Both files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `load_registries` reads only through `readers.read_registry`, verified with
      `grep -n "read_parquet" src/dessem_dashboard/data/registries.py` printing nothing.
- [ ] Every fallback label produced by this module is Portuguese.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes
