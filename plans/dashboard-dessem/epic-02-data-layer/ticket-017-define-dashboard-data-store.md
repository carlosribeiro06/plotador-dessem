# ticket-017 Define the dashboard data store

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The dashboard is one HTML file holding one embedded JSON data store, and the master plan output size
strategy fixes its shape: columnar value arrays keyed by (chart, entity, scenario, deck), one shared
time axis per deck plus one chained axis, absolute values only, rounded to `output.decimals`. That
shape is what keeps two scenarios times two decks at about 3 MB of JSON instead of an order of
magnitude more. `DashboardData` is the Python mirror of that store: ticket-018 fills it, ticket-020
serialises it, and its invariants, in particular that every value array has exactly the length of
its deck axis, must be enforced at insertion time rather than discovered in the browser.

### Relation to Epic

This is the target data structure of the whole epic. It is deliberately built before ticket-018 so
that consolidation is written against an already-tested contract, and its accessor names become the
contract that ticket-020 serialises.

### Current State

`src/dessem_dashboard/models/` holds `__init__.py` and `entities.py` with `DeckRef`, `ScenarioRef`,
`Stage` and `DeckTimeline`. `src/dessem_dashboard/data/registries.py` exposes `Registries`.
`src/dessem_dashboard/charts/` exposes the 23 enabled `ChartSpec` entries. There is no store module.

## Specification

### Requirements

1. Create `src/dessem_dashboard/models/store.py` declaring:
   - `@dataclass(frozen=True, slots=True) class EntityRef` with fields `entity_id: str`,
     `label: str` and `sort_key: tuple[object, ...]`, where `entity_id` is the stable key used in the
     store and in the JSON, and `label` is the Portuguese display text;
   - `@dataclass(frozen=True, slots=True) class TimeAxis` with fields `key: str`,
     `starts: tuple[pandas.Timestamp, ...]` and `durations_hours: tuple[float, ...]`, and a property
     `length` returning `len(starts)`;
   - `class DashboardData` holding `scenarios: tuple[str, ...]`, `reference: str`,
     `deck_dates: tuple[datetime.date, ...]`, `registries: Registries`, and private mutable
     containers for axes, series, scalars, entities and warnings.
2. `DashboardData.__init__` takes `scenarios`, `reference`, `deck_dates` and `registries` as
   keyword arguments and raises `StoreError` when `scenarios` is empty, when it contains duplicates,
   or when `reference` is not in `scenarios`.
3. Provide `set_deck_axis(deck_date, axis)` and `set_chained_axis(axis)`, with
   `deck_axis(deck_date) -> TimeAxis` and `chained_axis() -> TimeAxis` raising `StoreError` when the
   axis was never set.
4. Provide `add_series(*, chart_key: str, entity_id: str, scenario: str, deck_date: datetime.date |
   None, values: Sequence[float | None]) -> None`. A `deck_date` of `None` means the chained axis.
   The method raises `StoreError` when the scenario is unknown, when the axis for that key was never
   set, when `len(values)` differs from the axis length, or when the same four-part key is added
   twice.
5. Provide `series(chart_key, entity_id, scenario, deck_date) -> tuple[float | None, ...]` returning
   the stored array and raising `StoreError` when the key is absent, plus
   `has_series(...) -> bool` for the non-raising query.
6. Provide `set_entities(chart_key, entities: Sequence[EntityRef]) -> None` and
   `entities(chart_key) -> tuple[EntityRef, ...]`, which returns an empty tuple for a chart with no
   registered entities, and which stores the entities sorted by `sort_key`.
7. Provide `add_scalar(*, chart_key, series_name: str, scenario: str, deck_date, value: float |
   None) -> None` and `scalars(chart_key) -> Mapping[tuple[str, str, datetime.date], float | None]`
   for the `CUSTOS` and `TEMPO` bar charts.
8. Provide `add_warning(message: str) -> None` and `warnings() -> tuple[str, ...]`, preserving
   insertion order and deduplicating identical messages.
9. Provide `value_count() -> int` returning the total number of stored series values plus scalars, so
   the size strategy and the run manifest can report the data volume.
10. Add `StoreError(DashboardError)` to `src/dessem_dashboard/errors.py`.

### Inputs

Values pushed by ticket-018. The store performs no I/O.

### Outputs and Behavior

An in-memory structure with enforced invariants and deterministic iteration order. It is mutable by
design during construction and never mutated after ticket-018 returns it; enforcing that freeze is
not required.

### Error Handling

`StoreError` for every violation in requirements 2, 4, 5 and 6, with a Portuguese message naming the
chart key, the entity, the scenario and the deck involved, and, for the length mismatch, both
lengths. No bare `except`.

## Dependencies

- **Blocked By**: `ticket-008-verify-toolchain-quality-gates.md`
- **Blocks**: `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given a `DashboardData` built with `scenarios=("caso_a","caso_b")`, `reference="caso_a"` and a
      deck axis of length 4 registered for `date(2024,3,3)`, when
      `add_series(chart_key="GHID_SIN", entity_id="", scenario="caso_a",
      deck_date=date(2024,3,3), values=[1.0, 2.0, None, 4.0])` is called, then
      `series("GHID_SIN", "", "caso_a", date(2024,3,3))` returns `(1.0, 2.0, None, 4.0)` and
      `value_count()` returns `4`.
- [ ] Given the same store, when `add_series` is called twice with that identical four-part key,
      then the second call raises `StoreError` whose message contains `GHID_SIN` and `caso_a`.
- [ ] Given the same store, when `add_series` is called with three values against the length-4 axis,
      then it raises `StoreError` whose message contains both `3` and `4`.
- [ ] Given `scenarios=("caso_a","caso_b")`, when a `DashboardData` is constructed with
      `reference="caso_z"`, then it raises `StoreError` whose message contains `caso_z`, and
      constructing with `scenarios=("caso_a","caso_a")` raises `StoreError` containing `caso_a`.
- [ ] Given a store with three `EntityRef` objects registered for `GHID_UHE` with `sort_key` values
      out of order, when `entities("GHID_UHE")` is called, then they are returned in `sort_key`
      order, and `.venv/bin/pytest tests/test_store.py -q` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Declare `EntityRef` and `TimeAxis` as frozen slotted dataclasses.
2. Implement `DashboardData` as a plain class rather than a dataclass, since it owns mutable state
   with invariants; keep the four public attributes read-only by convention and annotate them as
   `Final`.
3. Store series in a `dict[tuple[str, str, str, datetime.date | None], tuple[float | None, ...]]`,
   which gives O(1) lookup and a natural duplicate check, and keeps the JSON grouping decisions for
   ticket-020.
4. Store axes in `dict[datetime.date | None, TimeAxis]` with `None` as the chained key, so
   `add_series` can validate lengths with one lookup for both modes.
5. Convert `values` to a `tuple` at insertion, which both freezes it and makes the length check
   trivial.
6. Implement `value_count` by summing `len(v) for v in series_values` plus the scalar count, and
   memoise nothing, since it is called once per run.
7. Write `tests/test_store.py` with a `_store()` helper building a two-scenario store with a
   length-4 deck axis and a length-8 chained axis.

### Key Files to Create/Modify

- `src/dessem_dashboard/models/store.py` (create)
- `src/dessem_dashboard/errors.py` (modify: add `StoreError`)
- `tests/test_store.py` (create)

### Patterns to Follow

- Keyword-only arguments for `add_series` and `add_scalar`, since both take four or five values of
  similar type and positional calls would be error-prone.
- Concrete return types (`tuple[...]`), never `Sequence`, per `rules/python.md`.
- Portuguese error messages, English identifiers, docstrings and test names.

### Pitfalls to Avoid

- Do not store the values as a `list`: an accidental mutation after insertion would silently corrupt
  the payload. Freeze to a `tuple`.
- Do not use `float('nan')` for a missing value: `json.dumps` emits the invalid JSON token `NaN`.
  Use `None`, which serialises to `null`, and state that in the docstring.
- Do not key the store by `EntityRef`: the identifier string is the JSON key and must be the
  dictionary key too, so the two cannot diverge.
- Do not let `entities` return the insertion order; the dashboard shows the plant list in sorted
  order and the sort must be decided once, here.
- `datetime.date` is hashable and JSON-unfriendly; keep it as the Python key here and let ticket-020
  format it, rather than storing pre-formatted strings.
- Do not add rounding here: `output.decimals` rounding is a serialisation concern that ticket-020
  owns, and rounding twice would lose the ability to change the precision without re-reading.

### Out of Scope

- Any JSON serialisation, key naming or rounding (ticket-020).
- Computing differences between scenarios, which happens in the browser per decision 8.
- Reading any file or knowing about `ChartSpec`; the store takes plain chart key strings.
- Enforcing immutability after construction.

## Testing Requirements

### Unit Tests

`tests/test_store.py`:

- construction validation: empty scenarios, duplicate scenarios, reference not in scenarios;
- deck axis and chained axis round-trip, and `StoreError` when an unset axis is requested;
- `add_series` happy path for a deck axis and for the chained axis with `deck_date=None`;
- duplicate key raises;
- length mismatch raises naming both lengths;
- unknown scenario raises;
- `None` values survive the round-trip and are counted by `value_count`;
- `has_series` returns false without raising for an absent key;
- `set_entities` sorts by `sort_key` and `entities` returns an empty tuple for an unknown chart;
- `add_scalar` and `scalars` round-trip for `CUSTOS` with two series names and two deck dates;
- `add_warning` deduplicates identical messages and preserves order;
- `value_count` equals the sum of series lengths plus the scalar count;
- the stored value tuples reject mutation, asserted with `pytest.raises(TypeError)`.

### Integration Tests

None: the store has no I/O. Ticket-018 provides the first end-to-end population test.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] No missing value is represented as `float('nan')` anywhere in the module.
- [ ] `errors.py` exposes `StoreError` in addition to the six earlier classes.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 25 minutes
