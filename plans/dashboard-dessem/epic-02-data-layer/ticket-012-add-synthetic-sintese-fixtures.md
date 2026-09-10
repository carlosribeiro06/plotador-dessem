# ticket-012 Add the synthetic synthesis fixtures

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `monorepo-test-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

`planning-context.md` states that the tests must not depend on `exemplo/`, because that folder is
gitignored from ticket-001 onwards and exists only on the developer's machine (the scenario tree
under `exemplo/caso_oficial/` and `exemplo/caso_gurobi/` was rebuilt locally from git history). Every data-layer test therefore needs synthetic Parquet files that are
faithful to the real schemas: the same column names, the same dtypes including the nullable `Int64`
of `SBM.codigo_submercado` and the `datetime64[ns, UTC]` timestamps, the same half-hour-then-longer
stage pattern, and the same non-rectangular entity coverage that makes `VARMF_UHE` cover fewer
plants than `GHID_UHE`. Building that generator once, parameterised, is what makes the following
five tickets testable in minutes instead of hours.

### Relation to Epic

This ticket is the test substrate of the whole epic: tickets 013 to 018 all consume its fixtures,
and it is also the practical cross-check that ticket-011 catalogue and ticket-009 schema
declarations agree, because the generator drives both from those declarations.

### Current State

`tests/` holds `test_config.py`, `test_logging_setup.py`, `test_manifest.py`, `test_cli.py`,
`test_schemas.py`, `test_chart_registry.py` and `test_chart_specs.py`. There is no `conftest.py` and
no fixture helper module. `src/dessem_dashboard/data/schemas.py` and
`src/dessem_dashboard/charts/specs.py` are available for the generator to read its column lists and
its file list from.

## Specification

### Requirements

1. Create `tests/fixtures_sintese.py` exposing
   `make_sintese_dir(target: Path, *, first_stage_start: datetime, n_stages: int = 6,
   half_hour_stages: int = 4, long_stage_hours: float = 2.0, hydro_codes: Sequence[int] = (1, 2, 3),
   reservoir_codes: Sequence[int] = (1, 2), thermal_codes: Sequence[int] = (1, 2),
   submarket_codes: Sequence[int] = (1, 2, 11), pair_codes: Sequence[tuple[int, int]] = ((1, 2), (2, 1)),
   omit: Sequence[str] = (), seed: int = 42) -> Path`.
2. The function creates `target` and writes one Parquet file per enabled `source_file` of the chart
   catalogue, driven by `enabled_specs()`, plus `EST.parquet`, `PAT.parquet`, `UHE.parquet`,
   `UTE.parquet`, `SBM.parquet`, `REE.parquet` and `METADADOS_OPERACAO.parquet`. Names listed in
   `omit` are skipped, which is how ticket-018 tests the missing-file warning.
3. Stage timestamps: the first `half_hour_stages` stages last 30 minutes, the remaining stages last
   `long_stage_hours` hours, starting at `first_stage_start` interpreted as UTC and contiguous
   throughout. `EST.parquet` and every series file share the same stage table.
4. Series files carry the entity keys of their level from `ENTITY_KEYS`, then the nine
   `SERIES_COLUMNS` with the dtypes of `SERIES_DTYPES`. `cenario` is `1`, `patamar` is `2`,
   `duracao_patamar` is the stage duration in hours, `limite_inferior` is `-inf` and
   `limite_superior` is `+inf`. `valor` is deterministic from `numpy.random.default_rng(seed)`.
5. UHE-level files use `hydro_codes`, except `VARMF_UHE` and `VARPF_UHE`, which use
   `reservoir_codes`, reproducing the real non-rectangular coverage. `VARPF_UHE` values stay within
   0 to 100.
6. Submarket-level files use `submarket_codes`, which by default include **both** fictitious codes,
   11 and 99, so the filtering of ticket-015 can be tested against each of them. `INT_SBP` uses
   `pair_codes`.
7. `SBM.parquet` uses the nullable `Int64` dtype for `codigo_submercado`, and reproduces the real
   long names: `1` SE/SUDESTE, `2` S/SUL, `11` FC/**NOFICT1**, `99` IV/**None**.

> **Amended 2026-09-10 during execution, approved by the developer — requirements 6 and 7 as
> originally written were factually wrong.** They set `submarket_codes = (1, 2, 11)` and put the null
> `nome_submercado` on code **11**, justifying it as "reproducing the real NaN long name". Both
> binding documents disagree and agree with each other: `planning-context.md` ("Data facts") and
> Appendix A.4 of the master plan both record **11 = FC/NOFICT1**, which has a real long name, and
> **99 = IV/NaN**, which is the code that actually carries the null. The ticket's own justification
> clause shows the intent was fidelity, so this is a defect in the attribution rather than a
> deliberate fixture-only simplification.
>
> The correction also improves coverage: `settings.json` defaults `submarkets.fictitious_codes` to
> `[11, 99]`, so including both codes exercises ticket-015's `include_fictitious` filter against each
> of them, while the null long name now sits on the code that really has it. Note the consequence for
> downstream tickets: every submarket-level fixture file now carries **four** codes rather than three,
> so row counts differ from the original ticket text.
8. `CUSTOS.parquet` holds the four `parcela` rows and `TEMPO.parquet` holds the five `etapa` values
   with three separate `PL` rows, matching Appendix A.5.
9. Create `tests/conftest.py` exposing two fixtures: `sintese_dir(tmp_path)` returning a single
   generated directory, and `scenario_tree(tmp_path)` returning a `dict[str, Path]` for a tree with
   two scenarios `caso_a` and `caso_b`, each holding two decks whose first stage starts on
   consecutive days, so the chaining window of the first deck ends exactly where the second begins.

### Inputs

The parameters above. No external data and no network.

### Outputs and Behavior

Parquet files on disk under `tmp_path`. Generating the default `scenario_tree` must take under five
seconds so the suite stays fast.

### Error Handling

An `omit` entry naming a file the generator does not produce raises `ValueError` naming the entry,
so a typo in a test does not silently produce a complete directory.

## Dependencies

- **Blocked By**: `ticket-009-define-parquet-schema-contracts.md`,
  `ticket-011-declare-enabled-chart-specs.md`
- **Blocks**: `ticket-013-implement-scenario-and-deck-discovery.md`,
  `ticket-014-implement-typed-parquet-readers.md`

## Acceptance Criteria

- [ ] Given `make_sintese_dir(tmp_path / "s", first_stage_start=datetime(2024, 3, 3, tzinfo=UTC))`,
      when the returned directory is listed, then it holds exactly 30 files: one per enabled
      `source_file` from `enabled_specs()` plus `EST.parquet`, `PAT.parquet`, `UHE.parquet`,
      `UTE.parquet`, `SBM.parquet`, `REE.parquet` and `METADADOS_OPERACAO.parquet`.
- [ ] Given the generated `GHID_UHE.parquet`, when it is read with `pandas.read_parquet`, then
      `set(frame.columns)` equals `set(series_columns(AggregationLevel.UHE))`, the
      `data_inicio` dtype is `datetime64[ns, UTC]` and `len(frame)` equals
      `len(hydro_codes) * n_stages`.
- [ ] Given the generated `EST.parquet` with `n_stages=6` and `half_hour_stages=4`, when it is read,
      then `data_fim` of stage 4 equals `data_inicio` of stage 5, the first four stages span 30
      minutes each and the last two span two hours each.
- [ ] Given the `scenario_tree` fixture, when the returned mapping is inspected, then
      `caso_a` and `caso_b` each contain two deck directories holding a `sintese` subdirectory, and
      the `data_fim` of the last chaining-window stage of the first deck equals the `data_inicio` of
      the first stage of the second deck.
- [ ] Given the generated `VARMF_UHE.parquet` and `SBM.parquet`, when both are read, then
      `VARMF_UHE` contains only `reservoir_codes` in `codigo_usina`, and `SBM.codigo_submercado` has
      dtype `Int64` with `nome_submercado` equal to `NOFICT1` for code 11 and null for code 99
      (amended 2026-09-10 — see the note under requirement 7).

## Implementation Guide (Technical Details)

### Suggested Approach

1. Build the stage table once as a `DataFrame` with `estagio`, `data_inicio`, `data_fim` and
   `duracao_patamar`, using `pandas.Timestamp(first_stage_start)` and `pandas.Timedelta`.
2. Write a private `_series_frame(level, entity_rows, stages, rng)` helper that takes the cartesian
   product of the entity rows and the stage table with `pandas.merge(how="cross")`, then adds the
   constant columns and the random `valor`, and finally reorders to `series_columns(level)` and casts
   with `astype(SERIES_DTYPES)`.
3. Derive the entity rows per level from the registries: UHE rows carry `codigo_usina`,
   `codigo_ree` and `codigo_submercado`; UTE rows carry `codigo_usina` and `codigo_submercado`.
4. Loop over `enabled_specs()`; dispatch on `spec.kind` and `spec.level`, with a small mapping from
   UHE key to the entity code list so `VARMF_UHE` and `VARPF_UHE` get `reservoir_codes`.
5. Write the registries and `METADADOS_OPERACAO` from the `REGISTRY_COLUMNS` declarations, filling
   `unidade` from `FALLBACK_UNITS` for every enabled key so ticket-015 can test both the metadata
   path and the fallback path by omitting one row.
6. Write `conftest.py` with the two fixtures; `scenario_tree` calls `make_sintese_dir` four times
   with `first_stage_start` on consecutive days and deck directory names that are deliberately not
   dates, such as `deck_um` and `deck_dois`, to prove that discovery does not parse folder names.
7. Add `tests/test_fixtures_sintese.py` holding the acceptance-criteria assertions.

### Key Files to Create/Modify

- `tests/fixtures_sintese.py` (create)
- `tests/conftest.py` (create)
- `tests/test_fixtures_sintese.py` (create)

### Patterns to Follow

- Deterministic data through `numpy.random.default_rng(seed)`, never the legacy global
  `numpy.random`, per `rules/python.md`.
- Drive the file list from `enabled_specs()` and the column lists from `schemas.py`, so the fixtures
  cannot drift from the contract.
- Full type hints on the generator and the fixtures, since `mypy` runs on `src` only but `ruff`
  covers `tests` and the code must still be readable.

### Pitfalls to Avoid

- `pandas.merge(how="cross")` on large inputs is expensive; keep the default entity counts tiny
  (three hydro plants, two thermal plants, three submarkets) so the whole suite stays fast. The real
  volumes are only exercised by the Epic 5 integration test.
- Writing `float("inf")` into a Parquet float column is valid, but writing it into an `int64` column
  is not; only the two limit columns carry infinities.
- `SBM.codigo_submercado` must be built with `pandas.array([...], dtype="Int64")`, not with a plain
  Python list, otherwise the dtype becomes `int64` and ticket-015 never exercises the nullable path.
- Naming deck directories with dates would let a wrong implementation pass by parsing the folder
  name; use non-date names on purpose.
- Do not write `ESTATISTICAS_OPERACAO_*` or `CVU` files: the plan never reads them, and generating
  them would slow the fixture down for nothing.
- Keep the generator out of `src/`: it is test-only code and must not ship in the package.

### Out of Scope

- Any assertion about reader behavior, which belongs to ticket-014.
- Fixtures for the HTML or payload layers, which Epic 3 adds when it needs them.
- A fixture reading real data from `exemplo/`, which is ticket-034 and is skip-guarded.
- Generating the 19 disabled source files.

## Testing Requirements

### Unit Tests

`tests/test_fixtures_sintese.py`:

- file count and exact file name set;
- column set and dtypes of one file per aggregation level, `SIN`, `SBM`, `SBP`, `UHE` and `UTE`;
- row counts equal entity count times stage count for each of those levels;
- stage contiguity and durations in `EST.parquet`;
- `VARMF_UHE` and `VARPF_UHE` restricted to `reservoir_codes`, and `VARPF_UHE` values within 0 to
  100;
- `SBM.parquet` dtype and the null long name for code 11;
- `CUSTOS.parquet` holds four rows with the four expected `parcela` values, and `TEMPO.parquet`
  holds nine rows with three `PL` rows;
- `omit=("GTER_UTE.parquet",)` produces 29 files, and `omit=("INEXISTENTE.parquet",)` raises
  `ValueError`;
- the same `seed` produces byte-identical `valor` arrays across two calls;
- the `scenario_tree` fixture layout and the chaining contiguity between its two decks;
- a timing assertion that generating `scenario_tree` completes in under five seconds.

### Integration Tests

None. The generator is itself the test infrastructure.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests` and `ruff format --check src tests` exit 0.
- [ ] `.venv/bin/pytest tests/test_fixtures_sintese.py -q` passes in under 30 seconds.
- [ ] `grep -rn "exemplo" tests/` prints nothing.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes
