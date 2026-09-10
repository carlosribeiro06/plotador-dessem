# ticket-009 Define the Parquet schema contracts

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The 60 synthesis files follow a small number of fixed shapes, documented in Appendix A of
`plans/dashboard-dessem/00-master-plan.md`: 40 operation time-series files share one nine-column
long schema prefixed by the entity keys of their aggregation level, and the remaining files are
registries or per-deck scalars with their own fixed columns. The legacy code encoded none of this:
each plotter called `pd.read_parquet` and indexed columns by name, so a renamed or missing column
produced a `KeyError` deep inside a plotting function. Declaring the contract once, in data, lets
every reader validate up front and fail with a message that names the file and the offending column.

### Relation to Epic

This is the foundation ticket of the data layer: ticket-012 builds its fixtures from these
declarations, ticket-014 validates against them, and ticket-011 cross-checks its unit values against
the fallback table defined here.

### Current State

`src/dessem_dashboard/` holds the Epic 1 modules only: `errors.py` with `DashboardError` and
`ConfigError`, plus `config.py`, `logging_setup.py`, `manifest.py`, `pipeline.py` and `cli.py`.
There is no `data/` subpackage and no schema knowledge anywhere in the code. `pandas` and `pyarrow`
are installed but not yet imported by any module.

## Specification

### Requirements

1. Create the subpackage `src/dessem_dashboard/data/` with an `__init__.py` containing only
   `from __future__ import annotations`.
2. Create `src/dessem_dashboard/data/schemas.py` declaring:
   - `class AggregationLevel(StrEnum)` with members `SIN`, `SBM`, `SBP`, `UHE`, `UTE`;
   - `ENTITY_KEYS: Mapping[AggregationLevel, tuple[str, ...]]` exactly as in Appendix A.2, with
     `SIN` mapping to the empty tuple;
   - `SERIES_COLUMNS: tuple[str, ...]` holding the nine shared columns in the Appendix A.1 order;
   - `SERIES_DTYPES: Mapping[str, str]` mapping each of those nine columns to its pandas dtype
     string, with `datetime64[ns, UTC]` for the two timestamps;
   - `REGISTRY_COLUMNS: Mapping[str, tuple[str, ...]]` for `UHE`, `UTE`, `SBM`, `REE`, `EST`, `PAT`
     and `METADADOS_OPERACAO`, and `SCALAR_COLUMNS: Mapping[str, tuple[str, ...]]` for `CUSTOS` and
     `TEMPO`, all from Appendix A.4 and A.5;
   - `FALLBACK_UNITS: Mapping[str, str]` covering the 23 enabled keys of Appendix A.6 plus the 19
     disabled ones;
   - `series_columns(level) -> tuple[str, ...]` returning `ENTITY_KEYS[level] + SERIES_COLUMNS`.
3. Add `SchemaError(DashboardError)` and `DataFileError(DashboardError)` to
   `src/dessem_dashboard/errors.py`, with English docstrings.
4. Implement `validate_columns(frame: pandas.DataFrame, expected: Sequence[str], *, source: Path)
   -> None`, raising `SchemaError` with a Portuguese message that names the source file, the missing
   columns and the unexpected columns. Column order is **not** required to match; only the set.
5. Implement `validate_series_columns(frame, level, *, source) -> None` as a thin wrapper over
   `validate_columns` using `series_columns(level)`.

> **Two notes added during execution (2026-09-10), both approved by the developer.**
>
> 1. **`pandas-stubs` was added as a dev dependency.** This is the first ticket to import `pandas`
>    into `src/`, and `pandas 3.0.5` ships no `py.typed` marker, so `mypy --strict` failed with
>    `import-untyped` — breaking acceptance criterion 5. ticket-008 requirement 5 pre-authorised a
>    scoped `[[tool.mypy.overrides]]` for exactly this case, but that would make `DataFrame` resolve
>    to `Any` and erase type checking across the whole data layer. `pandas-stubs==3.0.5.260730` is
>    version-aligned with the installed pandas and was measured to leave `mypy src` completely clean
>    (9 files, zero findings), so the developer chose the stubs over the override. Declared as
>    `pandas-stubs>=3.0` in the `dev` extra, per ticket-002's no-exact-pins rule.
> 2. **The units of the 19 disabled chart keys came from the data, not from the plan.** Appendix A.6
>    lists the 23 enabled keys with units, but names the 19 disabled ones without any. Rather than
>    guess, the implementer validated the source first — 21 of the 23 enabled keys appear in the real
>    `METADADOS_OPERACAO.parquet` and their `unidade` values match Appendix A.6 exactly — and then
>    transcribed the 19 disabled keys' units from that same file, cross-checked across both example
>    scenarios and both decks. `FALLBACK_UNITS` therefore holds 42 keys, of which 19 are grounded in
>    data inspection rather than in the master plan. Those charts ship disabled, and ticket-011
>    re-checks units against `METADADOS_OPERACAO` at load time.

### Inputs

A pandas `DataFrame` and the expected column list; no file I/O in this module.

### Outputs and Behavior

Pure declarations plus two validation functions that return `None` or raise. This module must not
import `pyarrow` and must not read any file.

### Error Handling

`SchemaError` only, with a Portuguese message of the form
`Arquivo <nome>: colunas ausentes [...]; colunas inesperadas [...]`. Both lists are sorted so the
message is deterministic. When both lists are empty the function returns `None`.

## Dependencies

- **Blocked By**: `ticket-008-verify-toolchain-quality-gates.md`
- **Blocks**: `ticket-010-add-chart-registry-mechanics.md`,
  `ticket-012-add-synthetic-sintese-fixtures.md`,
  `ticket-014-implement-typed-parquet-readers.md`

## Acceptance Criteria

- [ ] Given the module, when `ENTITY_KEYS[AggregationLevel.UHE]` is read, then it equals
      `("codigo_usina", "codigo_ree", "codigo_submercado")`, and `ENTITY_KEYS[AggregationLevel.SIN]`
      equals `()`.
- [ ] Given a `DataFrame` holding the nine `SERIES_COLUMNS` minus `duracao_patamar`, when
      `validate_series_columns(frame, AggregationLevel.SIN, source=Path("GHID_SIN.parquet"))` is
      called, then it raises `SchemaError` whose message contains both `duracao_patamar` and
      `GHID_SIN.parquet`.
- [ ] Given a `DataFrame` holding the nine `SERIES_COLUMNS` plus a column named `extra`, when
      `validate_series_columns(frame, AggregationLevel.SIN, source=Path("GHID_SIN.parquet"))` is
      called, then it raises `SchemaError` whose message contains `extra`.
- [ ] Given the module, when `FALLBACK_UNITS` is read, then `FALLBACK_UNITS["CMO_SBM"]` equals
      `"R$/MWh"`, `FALLBACK_UNITS["QTUR_UHE"]` equals `"m3/s"`, `FALLBACK_UNITS["VARPF_UHE"]` equals
      `"%"` and `FALLBACK_UNITS["EARMF_SIN"]` equals `"MWh"`.
- [ ] Given the repository root, when
      `.venv/bin/pytest tests/test_schemas.py -q && .venv/bin/mypy src` is run, then both commands
      exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Transcribe Appendix A.1, A.2, A.4, A.5 and A.6 of the master plan into module-level constants.
   Use `types.MappingProxyType` around each dictionary literal so the declarations cannot be mutated
   at runtime, and annotate them as `Mapping[...]`.
2. Use `enum.StrEnum` for `AggregationLevel` so the members can be used directly as dictionary keys
   and interpolated into messages.
3. Implement `validate_columns` with two `sorted(set(...) - set(...))` computations, then build the
   message only when at least one list is non-empty.
4. Write `tests/test_schemas.py` constructing small `DataFrame` objects with
   `pandas.DataFrame(columns=[...])`, which needs no data rows.

### Key Files to Create/Modify

- `src/dessem_dashboard/data/__init__.py` (create)
- `src/dessem_dashboard/data/schemas.py` (create)
- `src/dessem_dashboard/errors.py` (modify: add `SchemaError` and `DataFileError`)
- `tests/test_schemas.py` (create)

### Patterns to Follow

- `from __future__ import annotations` first; `Mapping` and `Sequence` from `collections.abc`.
- Keep every constant name in English and every message in Portuguese, per decision 2.
- Sort the message lists so the tests can assert on exact strings.

### Pitfalls to Avoid

- Do not encode the column **order** as a requirement: the files are stable but ordering assertions
  would break on a harmless producer change, and Appendix A.1 order is documentation, not a contract.
- `SBM.codigo_submercado` is the nullable `Int64` dtype, not `int64`; keep that distinction in
  `REGISTRY_COLUMNS` documentation comments and do not normalise it here.
- `pandas 3.x` reads text columns as the `str` dtype rather than `object`; if a dtype mapping is
  declared for registries, use `str`, not `object`.
- Do not add a `patamar`-keyed dimension: `patamar` is an attribute, per decision 15.
- Do not import `pyarrow` in this module; only `pandas` for the `DataFrame` type annotation.

### Out of Scope

- Reading any Parquet file (ticket-014).
- Validating dtypes or row uniqueness (ticket-014 owns both).
- The chart catalogue itself (tickets 010 and 011).
- Titles and long names from `METADADOS_OPERACAO` (ticket-015).

## Testing Requirements

### Unit Tests

`tests/test_schemas.py`:

- `ENTITY_KEYS` values for all five levels;
- `series_columns` for `SIN`, `SBM`, `SBP`, `UHE` and `UTE`, asserting length 9, 10, 11, 12 and 11
  respectively;
- `validate_columns` returns `None` for an exact match and for a permuted column order;
- missing column raises `SchemaError` naming the column and the source;
- unexpected column raises `SchemaError` naming the column;
- both missing and unexpected in one message;
- `FALLBACK_UNITS` covers every key of Appendix A.6, asserted against a literal list of the 23
  enabled keys held in the test;
- the declaration mappings reject mutation, asserted with `pytest.raises(TypeError)`.

### Integration Tests

None: this module performs no I/O.

## Definition of Done

- [ ] The four files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] Every constant in `schemas.py` matches Appendix A of the master plan.
- [ ] `errors.py` exposes `DashboardError`, `ConfigError`, `SchemaError` and `DataFileError` and
      nothing else.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
