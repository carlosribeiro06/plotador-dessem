# ticket-016 Implement the deck timeline and chaining

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

Spec section 4 forbids the stage number as the X axis and requires real date and time.
`planning-context.md` decision 4 adds that the deck date must come from `EST.parquet` and never from
the folder name, and decision 5 defines the two view modes: "Por deck" shows a deck full original
horizon at its native granularity, while "Encadeado" takes only the first `chaining.stages_per_deck`
stages of each deck, default 48, and concatenates them in deck-date order with no overlap. The
verified data makes that work exactly: deck `2024-03-03` stage 48 ends at `2024-03-04 00:00`, which
is where deck `2024-03-04` stage 1 starts. Because that contiguity is a property of the data rather
than a guarantee, it must be validated and reported instead of assumed, and a deck present in one
scenario but absent from another must produce a gap and a warning rather than a misaligned curve.

### Relation to Epic

Ticket-018 calls this module once per deck to obtain the axis its series arrays align to, and once
per scenario set to obtain the ordered deck list, the chained axis and the alignment warnings. Every
timestamp the dashboard displays originates here.

### Current State

`src/dessem_dashboard/data/` holds `__init__.py`, `schemas.py`, `discovery.py`, `readers.py` and
`registries.py`. `read_registry(path, "EST")` returns the validated stage table with
`datetime64[ns, UTC]` timestamps. `DeckRef` and `ScenarioRef` exist in
`src/dessem_dashboard/models/entities.py`. The `scenario_tree` fixture builds two decks whose
chaining windows meet exactly.

## Specification

### Requirements

1. Add to `src/dessem_dashboard/models/entities.py` the frozen slotted dataclasses
   `Stage` (`index: int`, `start: pandas.Timestamp`, `end: pandas.Timestamp`,
   `duration_hours: float`) and `DeckTimeline` (`deck: DeckRef`, `deck_date: datetime.date`,
   `stages: tuple[Stage, ...]`).
2. Create `src/dessem_dashboard/data/timeline.py` exposing:
   - `load_deck_timeline(deck: DeckRef) -> DeckTimeline`;
   - `chaining_window(timeline: DeckTimeline, *, stages_per_deck: int) -> tuple[Stage, ...]`;
   - `order_timelines(timelines: Iterable[DeckTimeline]) -> tuple[DeckTimeline, ...]`;
   - `validate_chaining(ordered: Sequence[DeckTimeline], *, stages_per_deck: int) -> list[str]`;
   - `align_deck_dates(scenario_timelines: Mapping[str, Sequence[DeckTimeline]]) ->
     tuple[tuple[datetime.date, ...], list[str]]`.
3. `load_deck_timeline` reads `EST.parquet` from `deck.sintese_dir`, derives
   `duration_hours` as `(end - start).total_seconds() / 3600`, requires `estagio` to start at 1 and
   be contiguous, and sets `deck_date` to `min(start).date()`.
4. A non-contiguous or non-1-based `estagio` sequence raises `SchemaError` naming the deck and the
   first offending index. Stages whose `end` is not greater than their `start` raise `SchemaError`.
5. `chaining_window` returns the first `stages_per_deck` stages, or every stage when the deck has
   fewer, in which case it also emits nothing itself; the shortfall is reported by
   `validate_chaining`.
6. `order_timelines` sorts by `deck_date`, then by `deck.name` as a deterministic tie-break, and
   raises `SchemaError` when two decks of the same scenario share a `deck_date`.
7. `validate_chaining` returns a list of Portuguese warnings, one per problem, covering: a deck with
   fewer stages than `stages_per_deck`; a gap where the window end of deck k is earlier than the
   window start of deck k+1; an overlap where it is later. It returns an empty list when the
   sequence is contiguous.
8. `align_deck_dates` returns the sorted union of deck dates across scenarios and one Portuguese
   warning per (scenario, missing date) pair.
9. Log at INFO one line per deck with its date and stage count, and one line with the chained axis
   length.

### Inputs

`DeckRef` objects from discovery, the configured `chaining.stages_per_deck`, and the per-scenario
timeline lists.

### Outputs and Behavior

Immutable timelines, a deterministic deck order, and warning lists that the caller accumulates into
`DashboardData.warnings`. The module reads only `EST.parquet` and never writes.

### Error Handling

`SchemaError` for a structurally invalid stage table, which is a data contract violation.
Everything a partially comparable dashboard can survive, namely short decks, gaps, overlaps and
missing decks, is a **warning string**, never an exception, per decision 18. `DataFileError`
propagates from the reader when `EST.parquet` is missing, because a deck without a timeline has no
usable axis.

## Dependencies

- **Blocked By**: `ticket-013-implement-scenario-and-deck-discovery.md`,
  `ticket-014-implement-typed-parquet-readers.md`
- **Blocks**: `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given a generated deck whose `EST.parquet` starts at `2024-03-03 00:00` UTC with
      `n_stages=6` and `half_hour_stages=4`, when `load_deck_timeline(deck)` is called, then
      `timeline.deck_date` equals `date(2024, 3, 3)`, `len(timeline.stages)` equals `6`,
      `timeline.stages[0].duration_hours` equals `0.5` and `timeline.stages[5].duration_hours`
      equals `2.0`.
- [ ] Given the two timelines of `caso_a` from the `scenario_tree` fixture, when
      `validate_chaining(order_timelines(timelines), stages_per_deck=48)` is called, then it returns
      an empty list.

> **Amended 2026-09-10 during execution: the criterion above said `stages_per_deck=4`, which made it
> unsatisfiable.** The `scenario_tree` fixture builds each deck with 48 half-hour stages followed by
> 6-hour stages (50 in total), so the chaining windows meet exactly only at 48: measured, deck 1's
> 48-stage window ends at `2024-03-04 00:00+00:00`, precisely where deck 2's first stage begins, for
> a gap of 0 h. At `stages_per_deck=4` the window ends at `2024-03-03 02:00+00:00`, leaving a
> **22-hour gap**, so `validate_chaining` must return a `lacuna` warning and could never return an
> empty list. 48 is also `chaining.stages_per_deck`'s binding default (`planning-context.md`
> decision 5) and the value Appendix A.3 documents as producing exact contiguity.
>
> Root cause, for the record: `make_sintese_dir`'s own generator defaults are `half_hour_stages=4,
> n_stages=6` — the values the criterion above and acceptance criterion 1 were written against —
> while ticket-012's `scenario_tree` deliberately overrides them to 48/50 to mirror the real 24-hour
> chaining window. Acceptance criterion 1 remains correct because it generates its own single deck at
> the generator defaults; only this criterion, which consumes `scenario_tree`, needed the value
> corrected. The following criterion ("the same `stages_per_deck`") therefore also means 48, and it
> builds its own pair with a deliberate 30-minute gap, so it needs no change.
- [ ] Given two timelines whose second deck starts 30 minutes after the first window ends, when
      `validate_chaining` is called with the same `stages_per_deck`, then it returns exactly one
      message containing the Portuguese word `lacuna` and both deck dates.
- [ ] Given `{"caso_a": [2024-03-03, 2024-03-04], "caso_b": [2024-03-03]}`, when
      `align_deck_dates` is called, then the returned dates equal
      `(date(2024, 3, 3), date(2024, 3, 4))` and the warning list holds exactly one message
      containing `caso_b` and the date rendered as `04/03/2024`.

> **Amended 2026-09-10 during execution.** The criterion above originally asked for the date as the
> ISO literal `2024-03-04`, which contradicts this ticket's own "Patterns to Follow" rule that every
> Portuguese message formats dates with `%d/%m/%Y` — the operator-facing format fixed by
> `dashboard.date_format` in Appendix B. A message cannot carry both renderings, and an
> operator-facing warning must use the Portuguese one. The date is still named; only its rendering
> follows the project-wide rule. The returned date TUPLE is unaffected and is still asserted by
> `date(...)` equality.
- [ ] Given an `EST.parquet` whose `estagio` values are `[1, 2, 4]`, when `load_deck_timeline` is
      called, then it raises `SchemaError` naming the deck and the index `3`, and
      `.venv/bin/pytest tests/test_timeline.py -q` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Add `Stage` and `DeckTimeline` to `entities.py`, keeping them record-only.
2. In `load_deck_timeline`, read `EST.parquet`, sort by `estagio`, validate contiguity by comparing
   the sorted `estagio` array with `numpy.arange(1, len(frame) + 1)`, then build the `Stage` tuple in
   one comprehension.
3. Implement `validate_chaining` as a loop over consecutive pairs, comparing
   `window[-1].end` of deck k with `window[0].start` of deck k+1 and branching on the three cases.
   Format the deck dates as `%d/%m/%Y` in the messages, matching the operator convention.
4. Implement `align_deck_dates` by building the sorted union with a `set` and then diffing each
   scenario list against it.
5. Write `tests/test_timeline.py`, building the gap and overlap cases by regenerating one deck with
   a shifted `first_stage_start`.

### Key Files to Create/Modify

- `src/dessem_dashboard/models/entities.py` (modify: add `Stage` and `DeckTimeline`)
- `src/dessem_dashboard/data/timeline.py` (create)
- `tests/test_timeline.py` (create)

### Patterns to Follow

- Warnings are returned, not logged and discarded, so `DashboardData` can embed them in the
  dashboard and the manifest can record them.
- Portuguese message text with dates formatted `%d/%m/%Y`; English identifiers and docstrings.
- `Iterable` and `Mapping` from `collections.abc` for parameters, concrete `tuple` and `list` for
  returns.

### Pitfalls to Avoid

- Do not convert timezones anywhere: decision 10 requires the stamps to be displayed as written.
  Keep them as `datetime64[ns, UTC]` and let the formatting layer in Epic 3 render them without
  conversion. Assert the absence of a shift in a test.
- Do not derive `duration_hours` from `duracao_patamar` in the series files: `EST.parquet` is the
  authoritative timeline and the two must agree, so compute from the timestamps and treat a
  disagreement as out of scope for this ticket.
- `deck_date` must come from `min(data_inicio)`, not from `stages[0]` before sorting, and never from
  `deck.name`.
- Comparing `pandas.Timestamp` values with `==` is exact and correct here because both come from
  the same nanosecond-resolution source; do not introduce a tolerance, which would hide real gaps.
- A deck with fewer stages than `stages_per_deck` is a warning, not an error: a deck at the end of a
  study legitimately has a shorter horizon.
- Do not sort the deck order by folder name as the primary key; the folder names in the fixture are
  deliberately not dates so a wrong implementation fails.

### Out of Scope

- Building the axis label strings, which ticket-020 formats for the payload.
- Slicing the series data to the chaining window, which ticket-018 does using
  `chaining_window`.
- Reading `chaining.stages_per_deck` from the settings, which ticket-018 does.
- Reconciling `EST.parquet` with `PAT.parquet`, which nothing in this plan needs.

## Testing Requirements

### Unit Tests

`tests/test_timeline.py`:

- `load_deck_timeline` happy path: deck date, stage count, first and last durations, and that the
  timestamps equal those written by the fixture;
- non-contiguous `estagio` raises naming the missing index;
- `estagio` not starting at 1 raises;
- a stage whose `end` equals its `start` raises;
- missing `EST.parquet` raises `DataFileError`;
- `chaining_window` returns `stages_per_deck` stages, and every stage when the deck is shorter;
- `order_timelines` sorts by date regardless of folder name, and raises on duplicate deck dates;
- `validate_chaining` returns an empty list for the contiguous fixture;
- gap case returns one message containing `lacuna`;
- overlap case returns one message containing `sobreposição`;
- short deck returns one message naming the deck date and both stage counts;
- `align_deck_dates` union and one warning per missing (scenario, date) pair, including the case
  where every scenario has every date and the warning list is empty;
- `caplog` assertions on the per-deck INFO line.

### Integration Tests

None. The 68-stage and 64-stage real decks are exercised by ticket-034.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] Every warning returned by this module is a Portuguese string naming the deck or scenario
      involved.
- [ ] No function in this module raises for a gap, an overlap, a short deck or a missing deck.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 30 minutes
