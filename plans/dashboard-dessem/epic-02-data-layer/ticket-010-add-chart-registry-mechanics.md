# ticket-010 Add the chart registry mechanics

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The spec requires that adding a new chart or a new synthesis file be cheap, and
`planning-context.md` decision 7 makes that concrete: the design must be registry-driven, so adding
a chart means adding one declarative entry. The legacy code did the opposite: each variable had its
own module with a copy of the reading logic and a copy of the Plotly layout, which is why only five
of the twenty-three required charts were ever implemented. This ticket builds the mechanics only:
the `ChartSpec` record, the enumerations it uses, and the register and query functions. The
catalogue itself is ticket-011, so the mechanics can be tested against toy specs without depending
on the real 23 entries.

### Relation to Epic

`ticket-011` fills the registry, `ticket-018` iterates over `enabled_specs` to decide which files to
read, and Epics 3 and 4 iterate over the same list to decide which charts to render and which UI
selector to attach. The field names chosen here are therefore a contract for the rest of the plan.

### Current State

`src/dessem_dashboard/data/schemas.py` exists with `AggregationLevel`, `ENTITY_KEYS`,
`SERIES_COLUMNS`, `FALLBACK_UNITS` and the validation helpers. `errors.py` exposes
`DashboardError`, `ConfigError`, `SchemaError` and `DataFileError`. There is no `charts/`
subpackage.

## Specification

### Requirements

1. Create the subpackage `src/dessem_dashboard/charts/` with an `__init__.py` containing only
   `from __future__ import annotations`.
2. Create `src/dessem_dashboard/charts/registry.py` declaring:
   - `class ChartKind(StrEnum)` with members `SERIES` and `SCALAR_BY_DECK`;
   - `class EntitySelector(StrEnum)` with members `NONE`, `SUBMARKET`, `SUBMARKET_PAIR`,
     `HYDRO_PLANT` and `THERMAL_PLANT`;
   - `class ChartGroup(StrEnum)` with members `SIN`, `SBM`, `SBP`, `UHE`, `UTE` and `EXECUCAO`;
   - `@dataclass(frozen=True, slots=True) class ChartSpec` with fields `key: str`,
     `source_file: str`, `level: AggregationLevel | None`, `group: ChartGroup`, `kind: ChartKind`,
     `selector: EntitySelector`, `title: str`, `unit: str`, `enabled: bool = True` and
     `notes: str = ""`.
3. Provide a `ChartRegistry` class holding an insertion-ordered mapping, with methods
   `register(spec) -> None`, `all_specs() -> tuple[ChartSpec, ...]`,
   `enabled_specs(*, disabled: Sequence[str] = ()) -> tuple[ChartSpec, ...]` and
   `spec(key) -> ChartSpec`, plus a module-level `REGISTRY = ChartRegistry()` singleton and
   module-level convenience functions delegating to it.
4. `register` raises `RegistryError` when the `key` is already registered, when `source_file` is
   empty, or when `kind` is `SERIES` and `level` is `None`.
5. `enabled_specs` returns, in registration order, the specs whose `enabled` is true and whose `key`
   is not in `disabled`. A `disabled` entry naming an unknown key raises `RegistryError`, so a typo
   in `settings.json` fails loudly instead of silently disabling nothing.
6. `spec(key)` raises `RegistryError` naming the key when it is not registered.
7. Add `RegistryError(DashboardError)` to `src/dessem_dashboard/errors.py`.

### Inputs

`ChartSpec` instances at registration time and a sequence of disabled keys at query time.

### Outputs and Behavior

Immutable spec records and deterministic, insertion-ordered query results. The module holds process
state in the `REGISTRY` singleton, so the tests must be able to build an independent
`ChartRegistry()` instance.

### Error Handling

`RegistryError` for every violation above, with Portuguese messages naming the key. No other
exception type is raised and no bare `except` is used.

## Dependencies

- **Blocked By**: `ticket-009-define-parquet-schema-contracts.md`
- **Blocks**: `ticket-011-declare-enabled-chart-specs.md`

## Acceptance Criteria

- [ ] Given a fresh `ChartRegistry()` and a spec with `key="X"`, when `register` is called twice with
      that spec, then the second call raises `RegistryError` whose message contains `X`.
- [ ] Given a fresh `ChartRegistry()` holding three specs registered in the order `A`, `B`, `C` where
      `B` has `enabled=False`, when `enabled_specs()` is called, then it returns exactly the specs
      with keys `("A", "C")` in that order.
- [ ] Given the same registry, when `enabled_specs(disabled=("C",))` is called, then it returns
      exactly the spec with key `A`, and when `enabled_specs(disabled=("Z",))` is called, then it
      raises `RegistryError` whose message contains `Z`.
- [ ] Given a fresh `ChartRegistry()`, when `register` is called with `kind=ChartKind.SERIES` and
      `level=None`, then it raises `RegistryError` whose message contains the spec key.
- [ ] Given the repository root, when
      `.venv/bin/pytest tests/test_chart_registry.py -q && .venv/bin/mypy src` is run, then both
      commands exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Declare the three enumerations, then the frozen `ChartSpec` dataclass with `slots=True` so a
   typo in a field name at construction time fails immediately.
2. Implement `ChartRegistry` around a private `dict[str, ChartSpec]`; Python dictionaries preserve
   insertion order, so no separate ordering list is needed.
3. Put the three validation rules of requirement 4 in a private `_validate(spec)` method called at
   the top of `register`.
4. Implement the module-level delegating functions `register`, `all_specs`, `enabled_specs` and
   `spec` so callers never touch the singleton directly.
5. Write `tests/test_chart_registry.py` with a `_spec(key, **overrides)` factory helper building a
   valid `ChartSpec`, and always use a fresh `ChartRegistry()` instance so the tests never mutate
   the singleton.

### Key Files to Create/Modify

- `src/dessem_dashboard/charts/__init__.py` (create)
- `src/dessem_dashboard/charts/registry.py` (create)
- `src/dessem_dashboard/errors.py` (modify: add `RegistryError`)
- `tests/test_chart_registry.py` (create)

### Patterns to Follow

- `@dataclass(frozen=True, slots=True)` for the spec, matching the frozen-dataclass convention
  established by `config.py` in Epic 1.
- Concrete return types (`tuple[ChartSpec, ...]`), not `Sequence`, per `rules/python.md`.
- English identifiers and docstrings; Portuguese messages and Portuguese `title` values.

### Pitfalls to Avoid

- Do not make `enabled_specs` filter silently on an unknown disabled key: a typo in
  `charts.disabled` would then hide the mistake, which is exactly the silent-failure mode this plan
  avoids.
- Do not let tests register into the module singleton: a leaked registration would make ticket-011
  tests fail with a duplicate-key error. Always instantiate `ChartRegistry()` in tests.
- `EntitySelector.NONE` is a legitimate value, not a missing value; do not use `None` for it.
- `level` is `None` only for `SCALAR_BY_DECK` specs such as `CUSTOS` and `TEMPO`, which have no
  aggregation level; enforce that pairing in `_validate`.
- Do not import `pandas` here: the registry is pure metadata.

### Out of Scope

- The 23 enabled and 19 disabled catalogue entries (ticket-011).
- Reading `charts.disabled` from `settings.json`, which ticket-018 does at consolidation time.
- Any rendering, colour or layout attribute: the spec carries no visual property, since `theme.py`
  in Epic 3 owns those.
- Sorting or grouping helpers for the dashboard navigation, which Epic 3 adds if needed.

## Testing Requirements

### Unit Tests

`tests/test_chart_registry.py`:

- duplicate key raises `RegistryError`;
- registration order is preserved by `all_specs` and `enabled_specs`;
- `enabled=False` specs are excluded;
- `disabled` excludes an enabled spec;
- unknown `disabled` key raises;
- `spec` returns the registered instance and raises on an unknown key;
- `kind=SERIES` with `level=None` raises;
- `source_file=""` raises;
- `ChartSpec` is immutable, asserted with `pytest.raises(FrozenInstanceError)`;
- an unknown field name at construction raises `TypeError`, proving `slots=True` and the frozen
  dataclass catch typos.

### Integration Tests

None: this module is pure metadata with no I/O.

## Definition of Done

- [ ] The four files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] No test mutates the `REGISTRY` singleton, verified by `grep -n "REGISTRY" tests/` showing only
      import-free references or none at all.
- [ ] `errors.py` exposes exactly `DashboardError`, `ConfigError`, `SchemaError`, `DataFileError`
      and `RegistryError`.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 25 minutes
