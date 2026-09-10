# ticket-014 Implement the typed Parquet readers

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Every read of a synthesis file must be validated at the boundary, because the files come from an
external model whose output shape can change between versions. Appendix A of the master plan fixes
the contract and ticket-009 declared it; this ticket is the only place in the codebase that calls
`pandas.read_parquet`. Two properties matter beyond the column set. First, `pandas 3.x` reads text
columns as the `str` dtype and `SBM.codigo_submercado` as the nullable `Int64`, so a reader that
assumes `object` or `int64` breaks silently. Second, decision 15 asserts that each operation file
holds exactly one row per (entity keys, `estagio`); if a future file carried several `patamar` rows
per stage, a naive read would plot an arbitrary one of them, so the reader must detect the
duplication and refuse.

### Relation to Epic

Tickets 015, 016 and 018 all read through this module and never call `pandas.read_parquet`
themselves. It converts the declarative contract of ticket-009 into enforced behavior.

### Current State

`src/dessem_dashboard/data/` holds `__init__.py`, `schemas.py` and `discovery.py`. `errors.py`
exposes `DashboardError`, `ConfigError`, `SchemaError`, `DataFileError`, `RegistryError` and
`DiscoveryError`. The ticket-012 fixtures can generate any of the 30 files, including with an
`omit` list, so both success and missing-file paths are testable.

## Specification

### Requirements

1. Create `src/dessem_dashboard/data/readers.py` exposing four functions:
   - `read_series(path: Path, level: AggregationLevel) -> pandas.DataFrame`;
   - `read_registry(path: Path, name: str) -> pandas.DataFrame`;
   - `read_costs(path: Path) -> pandas.DataFrame`;
   - `read_times(path: Path) -> pandas.DataFrame`.
2. Every function raises `DataFileError` with a Portuguese message naming the path when the file does
   not exist, and chains `pyarrow` read failures into `DataFileError` with `raise ... from err`.
3. `read_series` validates the columns with `validate_series_columns`, casts the nine shared columns
   to `SERIES_DTYPES`, casts the entity key columns of the level to `int64`, and asserts that
   `(entity keys, estagio)` is unique.
4. A duplicated key raises `SchemaError` with a Portuguese message naming the file, the number of
   duplicated keys and the first offending key values.
5. `read_series` returns the frame sorted by the entity keys then `estagio`, with a reset index, so
   every downstream consumer sees a deterministic order.
6. `read_registry` validates against `REGISTRY_COLUMNS[name]`, preserving the declared dtypes,
   specifically **not** casting `SBM.codigo_submercado` away from `Int64`.
7. `read_costs` and `read_times` validate against `SCALAR_COLUMNS`, and `read_times` keeps the
   several `PL` rows intact rather than aggregating, since grouping is ticket-031 business.
8. Every function logs one DEBUG line with the file name and the row count, and `read_series`
   additionally logs the entity count.

### Inputs

A path to a Parquet file, plus the aggregation level or registry name that selects the contract.

### Outputs and Behavior

Validated, dtype-normalised, deterministically ordered `DataFrame` objects. The functions never
mutate their input files and never cache.

### Error Handling

`DataFileError` for a missing or unreadable file, `SchemaError` for a contract violation. Catch
`FileNotFoundError` and `pyarrow.lib.ArrowInvalid` explicitly; never a bare `except` and never
`except Exception`. A `ValueError` from `astype` is chained into `SchemaError` naming the column
whose cast failed.

## Dependencies

- **Blocked By**: `ticket-009-define-parquet-schema-contracts.md`,
  `ticket-012-add-synthetic-sintese-fixtures.md`
- **Blocks**: `ticket-015-implement-registry-loading-and-labels.md`,
  `ticket-016-implement-deck-timeline-and-chaining.md`,
  `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given a generated `sintese_dir`, when
      `read_series(sintese_dir / "GHID_SBM.parquet", AggregationLevel.SBM)` is called, then the
      returned frame has `codigo_submercado` dtype `int64`, `data_inicio` dtype
      `datetime64[ns, UTC]`, `len(frame)` equal to the submarket count times the stage count, and
      rows ordered by `codigo_submercado` then `estagio`.
- [ ] Given a Parquet file written without the `valor` column, when `read_series` is called on it,
      then it raises `SchemaError` whose message contains both `valor` and the file name.
- [ ] Given a Parquet file whose rows are duplicated so that `(codigo_submercado, estagio)` repeats,
      when `read_series` is called, then it raises `SchemaError` whose message contains the
      Portuguese word `duplicad` and the first offending key values.
- [ ] Given `tmp_path / "ausente.parquet"`, when `read_series` is called on it, then it raises
      `DataFileError` whose message contains `ausente.parquet`.
- [ ] Given a generated `sintese_dir`, when `read_registry(sintese_dir / "SBM.parquet", "SBM")` is
      called, then `codigo_submercado` keeps the `Int64` dtype, and
      `.venv/bin/pytest tests/test_readers.py -q` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write a private `_read_parquet(path) -> pandas.DataFrame` that checks `path.is_file()`, raises
   `DataFileError` when absent, and wraps `pandas.read_parquet(path, engine="pyarrow")` in a
   `try/except (OSError, pyarrow.lib.ArrowInvalid)` chaining into `DataFileError`.
2. Write a private `_cast(frame, dtypes, *, source) -> pandas.DataFrame` that applies `astype`
   column by column so a failing cast can name its column, chaining `ValueError` into `SchemaError`.
3. In `read_series`: read, validate columns, cast, then compute
   `keys = list(ENTITY_KEYS[level]) + ["estagio"]` and check
   `frame.duplicated(subset=keys).any()`; on a hit, take the first duplicated row to build the
   message. Finish with `frame.sort_values(keys).reset_index(drop=True)`.
4. Keep `read_registry` deliberately thin: validate and return, with no dtype coercion beyond what
   the file already carries, because the nullable `Int64` must survive.
5. Write `tests/test_readers.py`, building the malformed files by reading a generated file, dropping
   or duplicating rows or columns, and writing it back with `to_parquet`.

### Key Files to Create/Modify

- `src/dessem_dashboard/data/readers.py` (create)
- `tests/test_readers.py` (create)

### Patterns to Follow

- Vectorised pandas operations only; no row loops, per `rules/python.md`.
- Explicit dtypes on every cast, so memory and semantics are controlled.
- `logger = logging.getLogger(__name__)` at module level; DEBUG for per-file detail, so an
  operational run at INFO stays readable.

### Pitfalls to Avoid

- Do not cast `limite_inferior` or `limite_superior` to anything but `float64`: they carry `-inf`
  and `+inf`, which no integer dtype can hold.
- Do not use `frame.astype(SERIES_DTYPES)` in one call for the timestamp columns if the file was
  written timezone-naive: cast timestamps with `pandas.to_datetime(..., utc=True)` instead, and only
  then `astype` the rest. Timezone conversion is forbidden by decision 10, so the values must not
  shift; assert that in a test.
- Do not drop the `patamar` or `duracao_patamar` columns: `duracao_patamar` is what ticket-016 uses
  for the step axis width.
- Do not deduplicate silently. A duplicate is a contract violation and must raise, per decision 15.
- Do not sort registries: `UHE.parquet` order is meaningful to nobody, but re-sorting it would make
  ticket-015 tests depend on the sort rather than on the lookup.
- `pyarrow.lib.ArrowInvalid` must be imported from `pyarrow.lib`; importing `pyarrow` alone does not
  expose it in all versions, so import it explicitly and guard the import with a module-level
  `from pyarrow.lib import ArrowInvalid`.

### Out of Scope

- Interpreting the data: no unit conversion, no filtering of fictitious submarkets, no chaining
  window, no grouping of `TEMPO` stages.
- Building the entity name lookups, which is ticket-015.
- Caching or memoising reads, which ticket-018 handles by reading each file once.
- Reading `ESTATISTICAS_OPERACAO_*` or `CVU`.

## Testing Requirements

### Unit Tests

`tests/test_readers.py`:

- `read_series` on one file per level, `SIN`, `SBM`, `SBP`, `UHE` and `UTE`, asserting dtypes, row
  counts and ordering;
- timestamps are unchanged by the read, comparing against the value written by the fixture, proving
  no timezone shift;
- missing column raises `SchemaError`;
- extra column raises `SchemaError`;
- duplicated key raises `SchemaError` naming the key;
- missing file raises `DataFileError`;
- a truncated or non-Parquet file raises `DataFileError` chained from the arrow error;
- `read_registry` for `UHE`, `UTE`, `SBM`, `REE`, `EST` and `METADADOS_OPERACAO`, asserting the
  `Int64` dtype survives for `SBM`;
- `read_registry` with a wrong `name` raises `RegistryError` or `SchemaError`, whichever the
  implementation chooses, with the choice recorded in the completion report;
- `read_costs` returns four rows and `read_times` returns nine rows with three `PL` rows preserved;
- `caplog` at DEBUG shows one line per read with the row count.

### Integration Tests

None. Reading the real 60-file directory happens in ticket-034.

## Definition of Done

- [ ] Both files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] `grep -rn "read_parquet" src/` matches only `src/dessem_dashboard/data/readers.py`.
- [ ] No reader converts a timezone or aggregates rows.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes
