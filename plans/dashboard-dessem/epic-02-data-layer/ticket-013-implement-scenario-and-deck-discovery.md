# ticket-013 Implement scenario and deck discovery

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-02-data-layer` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

`planning-context.md` decision 4 fixes the input layout: each `--casos` argument is one comparison
series whose legend label is the directory basename, and its decks are the **immediate**
subdirectories that contain a `sintese/` subfolder. Deck folder names are free-form and must never
be parsed: the deck date comes from `EST.parquet` in ticket-016. A scenario directory with no deck is
a fatal error with a clear Portuguese message. The legacy `leitor_arquivos.py` did the opposite: it
searched recursively with `rglob("*")` for anything named `sintese`, assumed a date-first two-level
nesting, and built its result at import time, so a wrong tree produced an empty dictionary and a
later `KeyError`.

### Relation to Epic

Discovery is the entry point of the data layer. Ticket-016 attaches a timeline to each `DeckRef`
found here and ticket-018 iterates the discovered structure to read files. The dataclasses defined
here are the shared vocabulary of the rest of the plan.

### Current State

`src/dessem_dashboard/data/` holds `__init__.py` and `schemas.py`. There is no `models/` subpackage
and no discovery code. `cli.py` from ticket-006 validates only basename uniqueness and
`--referencia` membership, and explicitly defers existence and deck checks to this ticket. The
`scenario_tree` fixture from ticket-012 provides a two-scenario, two-deck tree whose deck directories
are deliberately named `deck_um` and `deck_dois` rather than dates.

## Specification

### Requirements

1. Create the subpackage `src/dessem_dashboard/models/` with an `__init__.py` containing only
   `from __future__ import annotations`.
2. Create `src/dessem_dashboard/models/entities.py` declaring
   `@dataclass(frozen=True, slots=True) class DeckRef` with fields `name: str`, `path: Path` and
   `sintese_dir: Path`, and `@dataclass(frozen=True, slots=True) class ScenarioRef` with fields
   `label: str`, `path: Path` and `decks: tuple[DeckRef, ...]`.
3. Create `src/dessem_dashboard/data/discovery.py` exposing
   `discover_scenarios(paths: Sequence[Path], *, sintese_dirname: str = "sintese") ->
   tuple[ScenarioRef, ...]`.
4. For each path: resolve it, require that it is an existing directory, then collect its immediate
   subdirectories that contain a child directory named `sintese_dirname`. Sort the resulting decks
   by `name` so the order is deterministic, and set `label` to `path.name`.
5. A path that does not exist or is not a directory raises `DiscoveryError` with a Portuguese
   message naming the path.
6. A scenario directory with zero decks raises `DiscoveryError` with a Portuguese message naming the
   scenario label and the expected `sintese_dirname`.
7. Two paths whose basenames collide raise `DiscoveryError` naming the duplicated label, because the
   basename is the legend and must be unique.
8. An empty `paths` sequence raises `DiscoveryError`.
9. Log at INFO one line per scenario with its label and deck count, and one summary line with the
   total scenario and deck counts, using the `log_step` helper from `logging_setup`.
10. Add `DiscoveryError(DashboardError)` to `src/dessem_dashboard/errors.py`.

### Inputs

A sequence of filesystem paths, normally the parsed `--casos` values, plus the configured synthesis
directory name from `Settings.discovery.sintese_dirname`.

### Outputs and Behavior

A tuple of `ScenarioRef` in the order the paths were given, each holding its decks sorted by name.
The function reads directory entries only; it opens no file.

### Error Handling

`DiscoveryError` for every case in requirements 5 to 8, always with a Portuguese message that names
the offending path or label. A `PermissionError` from `iterdir` propagates unchanged, since a
permission problem is an environment failure rather than a user input error. No bare `except`.

## Dependencies

- **Blocked By**: `ticket-012-add-synthetic-sintese-fixtures.md`
- **Blocks**: `ticket-016-implement-deck-timeline-and-chaining.md`,
  `ticket-018-implement-series-consolidation.md`

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture, when
      `discover_scenarios([tree["caso_a"], tree["caso_b"]])` is called, then it returns two
      `ScenarioRef` whose `label` values are `"caso_a"` and `"caso_b"` in that order, each with two
      decks, and each `DeckRef.sintese_dir` points at an existing directory named `sintese`.
- [ ] Given `tmp_path / "inexistente"`, when `discover_scenarios([that path])` is called, then it
      raises `DiscoveryError` whose message contains `inexistente`.
- [ ] Given a directory `tmp_path / "vazio"` holding one subdirectory without a `sintese` child,
      when `discover_scenarios([tmp_path / "vazio"])` is called, then it raises `DiscoveryError`
      whose message contains both `vazio` and `sintese`.
- [ ] Given `tmp_path / "a" / "caso_x"` and `tmp_path / "b" / "caso_x"`, both valid scenario trees,
      when `discover_scenarios` is called with both, then it raises `DiscoveryError` whose message
      contains `caso_x`.
- [ ] Given the `scenario_tree` fixture and `caplog` at INFO level, when `discover_scenarios` is
      called, then the captured records include one line containing `caso_a` and the deck count `2`,
      and `.venv/bin/pytest tests/test_discovery.py -q` exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Declare the two dataclasses in `models/entities.py` with no methods, so they stay plain records.
2. In `discovery.py`, write a private `_decks_of(scenario_path, sintese_dirname) ->
   tuple[DeckRef, ...]` that iterates `sorted(scenario_path.iterdir())`, keeps entries where
   `entry.is_dir() and (entry / sintese_dirname).is_dir()`, and builds one `DeckRef` per hit.
3. In `discover_scenarios`, validate the empty-sequence case first, then loop over the paths
   building the scenarios, then check label uniqueness with a `dict[str, Path]` accumulator so the
   error message can name both colliding paths.
4. Log with `logger = logging.getLogger(__name__)` and the `log_step` helper, passing
   `cenario=label` and `decks=count` as fields.
5. Write `tests/test_discovery.py` using the `scenario_tree` fixture and small hand-built trees in
   `tmp_path` for the error paths.

### Key Files to Create/Modify

- `src/dessem_dashboard/models/__init__.py` (create)
- `src/dessem_dashboard/models/entities.py` (create)
- `src/dessem_dashboard/data/discovery.py` (create)
- `tests/test_discovery.py` (create)

### Patterns to Follow

- `pathlib.Path` throughout, never `os.path`, per `rules/python.md`.
- Frozen slotted dataclasses, consistent with `config.py` and `ChartSpec`.
- Portuguese error and log messages; English identifiers, docstrings and test names.
- Resolve paths with `Path.resolve()` once, at the top, so every stored path is absolute.

### Pitfalls to Avoid

- Do not search recursively: `rglob` was the legacy bug. Only the **immediate** subdirectories of a
  scenario directory are decks, per decision 4.
- Do not treat the scenario directory itself as a deck even when it directly contains a `sintese/`
  child. That shape is the flat `exemplo/sintese` structure sample (master plan open question 5, resolved);
  it must raise the zero-deck error so the developer sees the real problem instead of a
  single-deck dashboard. State this explicitly in the module docstring.
- Do not parse or sort deck directory names as dates. Sorting by name here is only for
  determinism; the real ordering happens in ticket-016 from `EST.parquet`.
- Do not verify that the `sintese` directory contains any Parquet file: a deck whose files are
  missing produces per-file warnings in ticket-018, not a discovery failure.
- Do not compare labels case-insensitively; two directories differing only in case are distinct
  scenarios on Linux.

### Out of Scope

- Reading `EST.parquet` or any other file (tickets 014 and 016).
- Aligning deck dates across scenarios or warning about a deck present in only one scenario, which
  ticket-016 owns.
- Reading `sintese_dirname` from `settings.json`; the caller passes it, and ticket-018 is the caller.
- Changing the `cli.py` validation from ticket-006.

## Testing Requirements

### Unit Tests

`tests/test_discovery.py`:

- happy path on the `scenario_tree` fixture: labels, order, deck counts, `sintese_dir` existence;
- deck ordering is by name, verified with deck directories created in reverse alphabetical order;
- non-existent path raises;
- a file instead of a directory raises;
- zero-deck scenario raises naming the label and `sintese`;
- a scenario directory that directly contains `sintese/` raises the zero-deck error;
- duplicate basenames raise;
- empty `paths` raises;
- a custom `sintese_dirname="resultados"` is honoured;
- a deck subdirectory containing a **file** named `sintese` is not treated as a deck;
- `caplog` assertions on the per-scenario and summary INFO lines.

### Integration Tests

None. The real-tree walk is exercised by ticket-034.

## Definition of Done

- [ ] The four files exist and all five acceptance criteria pass.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0.
- [ ] The module docstring states that discovery is non-recursive and why.
- [ ] `errors.py` exposes `DiscoveryError` in addition to the five earlier classes.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
