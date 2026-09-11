# Epic 02 — Data Layer: Learnings

> Extracted 2026-09-10 at the epic boundary, after all ten tickets (009–018) passed their guardian.
> Written for the refinement of Epics 3, 4 and 5. Everything here is measured or verified, not
> assumed. Where a fact contradicts a ticket or the master plan, the contradiction is named.

Epic result: **10/10 tickets, 28 points, quality avg 0.971 (min 0.88), readiness avg 0.956**,
3 772 lines added across 15 files, **288 tests, 99 % total coverage**, every Epic 2 module at 100 %.
Milestone M2 reached at commit `ada0053`.

---

## 1. The public API Epic 3 consumes

These names are the contract. They are pinned by tests, so treat them as fixed and do not restate
them differently in a refined ticket.

### `models.store`

```python
@dataclass(frozen=True, slots=True)
class EntityRef:      entity_id: str; label: str; sort_key: tuple[object, ...]

@dataclass(frozen=True, slots=True)
class TimeAxis:       key: str; starts: tuple[pd.Timestamp, ...]; durations_hours: tuple[float, ...]
                      # plus the property `length` -> len(starts)

class DashboardData:  # plain class, mutable during construction by design
    __init__(*, scenarios, reference, deck_dates, registries)
    set_deck_axis(deck_date, axis) / deck_axis(deck_date) -> TimeAxis
    set_chained_axis(axis)         / chained_axis()       -> TimeAxis
    add_series(*, chart_key, entity_id, scenario, deck_date: date | None, values)
    series(chart_key, entity_id, scenario, deck_date) -> tuple[float | None, ...]
    has_series(...) -> bool                      # non-raising query
    set_entities(chart_key, entities) / entities(chart_key) -> tuple[EntityRef, ...]
    add_scalar(*, chart_key, series_name, scenario, deck_date: date, value)
    scalars(chart_key) -> Mapping[tuple[str, str, date], float | None]
    add_warning(message) / warnings() -> tuple[str, ...]
    value_count() -> int
```

Three shape rules that are easy to get wrong:

- `add_series`'s `deck_date=None` means **the chained axis**; `add_scalar`'s `deck_date` is a plain
  non-optional `date`, because a bar chart has one bar per deck and no chained variant.
- `value_count()` = sum of series array lengths **plus** the number of scalar entries. `None`
  entries count: they occupy a slot in the payload.
- `entities()` returns **sorted by `sort_key`**, and an empty tuple for an unregistered chart.
  Keep each chart's `sort_key` element types homogeneous — mixing them raises `TypeError` at sort
  time, and `mypy` cannot catch it because `tuple[object, ...]` satisfies the comparison protocol
  structurally (measured).

### `data.registries`

```python
Registries(hydro, thermal, submarkets, rees, variables)   # all MappingProxyType
  .unit_for(chart_key) -> str            # metadata unit if present AND non-null, else FALLBACK_UNITS, else RegistryError
  .title_for(chart_key) -> str | None    # None, never "", so the caller falls back to ChartSpec.title
  .hydro_name(code) / .thermal_name(code) -> str          # fallback f"Usina {code}"
  .submarket_label(code) -> str                            # f"{short} ({long})" or f"Submercado {code}"
visible_submarket_codes(registries, *, include_fictitious) -> tuple[int, ...]   # module-level, sorted
load_registries(sintese_dir, *, fictitious_codes=(11, 99)) -> Registries

HydroPlant(code, name, ree_code, ree, submarket_code, submarket)
ThermalPlant(code, name, submarket_code, submarket)
Submarket(code, short_name, long_name, fictitious)
VariableMeta(key, short_name, long_name, unit)
```

### `models.entities`, `data.discovery`, `data.timeline`, `data.readers`, `data.consolidate`

```python
DeckRef(name, path, sintese_dir)          ScenarioRef(label, path, decks)
Stage(index, start, end, duration_hours)  DeckTimeline(deck, deck_date, stages)

discover_scenarios(...) -> tuple[ScenarioRef, ...]
read_series / read_registry / read_costs / read_times          # the ONLY read_parquet call sites
load_deck_timeline(deck) -> DeckTimeline
chaining_window(timeline, stages_per_deck) -> tuple[Stage, ...]   # neither warns nor raises
order_timelines(...)      # sorts by deck_date then deck.name; RAISES on a duplicate date per scenario
validate_chaining(...) -> list[str]        # warnings only, never raises
align_deck_dates(...) -> (dates, warnings)
build_dashboard_data(scenarios, *, settings, reference) -> DashboardData
```

### `charts`

`ChartSpec(key, source_file, level, group, kind, selector, title, unit, enabled, notes)`;
`enabled_specs()` returns **23** specs of the 42 declared. `ChartSpec.unit` is always
`FALLBACK_UNITS[key]`, never a literal — one source of truth for units.

### Entity identifier format — fixed, and the JSON key

`""` for SIN · `str(codigo_submercado)` for SBM · `f"{de}-{para}"` for SBP ·
`str(codigo_usina)` for UHE and UTE. Labels come from `Registries`; a submarket pair reads
`f"{submarket_label(de)} para {submarket_label(para)}"`. `sort_key` is the numeric code tuple for
submarkets and pairs and the **plant name** for plant charts, so the dashboard list is alphabetical
(verified: `USINA_1 < USINA_10 < USINA_2`, i.e. plain string order, not natural sort — if natural
sort is wanted in the UI, that is a new decision, not a bug fix).

---

## 2. Portuguese operator-facing wording already established

Reuse this vocabulary rather than inventing synonyms; the operator should meet one dialect.

| Situation | Wording actually shipped |
| --------- | ------------------------ |
| Chaining gap | contains `lacuna`, both deck dates in `%d/%m/%Y` |
| Chaining overlap | contains `sobreposição` |
| Deck missing from a scenario | `Cenário 'caso_b' não possui deck para a data 04/03/2024, presente em outro(s) cenário(s)` |
| Entities absent from an existing file | `2 entidade(s) do gráfico 'GHID_UHE' ausente(s) no cenário '…', deck de 04/03/2024: valor(es) preenchido(s) com null` |
| Series length mismatch (`StoreError`) | `… tem 7 valor(es) … tem 9 posição(ões)` |
| Unknown plant label | `Usina {code}` · unknown submarket: `Submercado {code}` |

**Dates in operator-facing text are `%d/%m/%Y`**, from `dashboard.date_format` — never ISO. This
was the subject of a ticket-016 amendment: an acceptance criterion demanded the ISO literal while
the same ticket's own patterns mandated `%d/%m/%Y`, and a message cannot carry both.

---

## 3. Which binding decision governs which behaviour

Refinement must cite the decision, not re-derive the behaviour.

- **Decision 4** — a deck's date comes from `min(data_inicio)` of `EST.parquet`, **never** the folder
  name. The fixtures are deliberately named `deck_um`/`deck_dois` so a folder-name shortcut fails
  visibly.
- **Decision 10** — timestamps are wall clock *labelled* UTC and are never converted. A timezone
  conversion would shift every point of every chart by hours without failing a single test.
- **Decision 15** — a duplicate `(entity, stage)` key fails loudly rather than being averaged.
- **Decision 16** — a chart's entity list comes from **its own file**, not from `UHE.parquet`
  (`GHID_UHE` 165 plants, `VARMF_UHE` 118). The registry supplies names only.
- **Decision 17** — missing `(entity, stage)` combinations are filled with `null`. This governs an
  entity absent from a file that exists.
- **Decision 18** — a missing **file** or a missing **deck** degrades to a warning plus a gap, never
  a crash; a scenario with zero decks is fatal.

The three-case degradation split in `consolidate.py` follows directly and must not be collapsed:
missing file warns per chart and stores nothing; missing deck is reported **once** by the structural
`align_deck_dates` warning, stores nothing, but pads the chained arrays; an absent entity stores an
all-`None` array and warns once with a **count**. Two different decisions, three different
behaviours, code that looks similar.

**Raise versus warn** is the single most error-prone axis in this layer. `SchemaError` for a
malformed stage sequence or a non-positive stage window; `StoreError` for a store invariant; a
Portuguese **warning** for every coverage gap. A crash where decision 18 demands a warning lets one
bad deck kill an entire multi-scenario run.

---

## 4. Data facts confirmed or corrected

- Fictitious submarkets: **11 = FC / `NOFICT1`** (a real long name) and **99 = IV / null**. Both are
  fictitious; only 99 is unnamed. `fictitious` and "unnamed" are **independent properties** — this
  was mis-stated in two tickets and corrected both times.
- `SBM.codigo_submercado` is nullable `Int64`; do not `astype(int)` a column containing nulls.
- `METADADOS_OPERACAO` has **null units** for `VAGUA_UHE` and `VCALHA_UHE`, so "present" and
  "non-null" are different questions.
- Real `nome_longo_variavel` values differ from the curated titles, sometimes better, sometimes
  worse — the basis of epic-03 decision E3-2. Measured: `CMO_SBM` → `Custo Marginal de Operação`,
  `EARMF_SIN` → `Energia Armazenada Absoluta Final`, but `VARMF_UHE` → `Volume Armazenado Absoluto
  Final`, which loses the hm3-versus-% distinction the catalogue adds.
- `CUSTOS` has four `parcela` rows; `TEMPO` has nine `etapa` rows, three of them `PL`.
- Column **order is not a contract**: `validate_columns` compares sets, and `registries.py` selects
  columns by name before `itertuples`. Never use positional access on these frames.

---

## 5. Fixture generator contract (`tests/fixtures_sintese.py`, `tests/conftest.py`)

```python
make_sintese_dir(target, *, first_stage_start, n_stages=6, half_hour_stages=4,
                 long_stage_hours=2.0, hydro_codes=(1,2,3), reservoir_codes=(1,2),
                 thermal_codes=(1,2), submarket_codes=(1,2,11,99),
                 pair_codes=((1,2),(2,1)), omit=(), seed=42)
```

Writes one file per `enabled_specs()` entry plus seven registry files, and raises `ValueError` if
`omit` names a file it never writes. `VARMF_UHE`/`VARPF_UHE` use `reservoir_codes` while every other
UHE-level file uses `hydro_codes` — that is the deliberate non-rectangular coverage.

`scenario_tree` builds `caso_a` and `caso_b`, each with `deck_um` (2024-03-03) and `deck_dois`
(2024-03-04), overriding `n_stages=50, half_hour_stages=48, long_stage_hours=6.0`. **The generator
defaults and the `scenario_tree` overrides are different**, and conflating them produced a spec
defect: an acceptance criterion asserted an empty chaining result at `stages_per_deck=4`, which is
unsatisfiable on this fixture (window ends 02:00, leaving a 22-hour gap); the contiguous case is
`stages_per_deck=48`. `build_scenario_tree(root)` is a plain function for tests needing a custom
tree.

**No test may read `exemplo/`** — verified by `grep -rn "exemplo" tests/` returning nothing.

---

## 6. The ticket-spec defect pattern — ten instances, one tell

Ten specs in this plan contained a defect, and **every one had the same tell: a requirement, or a
summary sentence, contradicted its own justification clause or the rest of its own ticket.** Epic 2
alone produced six. Read every requirement against its own rationale before implementing it.

The instances, as a checklist of shapes to look for:

1. A requirement prescribing X while its justification describes Y (submarket 11 vs 99, twice).
2. An acceptance criterion that is **arithmetically unsatisfiable** against the shipped fixture
   (`stages_per_deck=4`).
3. An acceptance criterion demanding a format the same ticket's patterns forbid (ISO vs `%d/%m/%Y`).
4. A **summary paragraph** whose requirement list is off by one, naming a requirement with no error
   condition and omitting one that has a tested error condition (ticket-017 Error Handling).
5. A requirement bundling cases governed by **different binding decisions** under one treatment
   (ticket-018 requirement 9).
6. A **Definition of Done bullet left stale** by an amendment to the requirement it summarises —
   caught by the guardian, not by me, and the reason a plan-wide sweep after every amendment is now
   standard.
7. A verification command that can never fail (`grep -c` for a pattern that is always present).
8. A gitignore rule whose directory pattern makes a mandated negation unreachable.

Two process rules earned by this: **amend the ticket, never quietly satisfy the defect**, so the
paper trail survives; and after every amendment, **sweep the whole plan for downstream text that
repeated the wrong fact** — this caught stale text twice and missed it once.

---

## 7. Vacuous tests are the failure mode this epic actually had

A test can pass for the wrong reason, and three near-misses appeared here:

- An assertion that a message "contains `3` and `4`" is satisfiable by the date `03/03/2024` alone.
  Proven non-vacuous only by probing lengths 7-vs-9, digits absent from every date in the message.
- "`INT_SBP` keeps pairs involving code 11" passes trivially on the default `pair_codes`, which
  contains no code-11 pair. The test must regenerate the fixture with `pair_codes` including 11.
- "Warnings contains exactly one message naming X" is a **filtered count**, not
  `len(warnings()) == 1`; other warnings legitimately coexist in the store.

Rule for later epics: when an assertion could be satisfied by incidental content, prove it by
changing the inputs so the incidental match disappears, or by mutation. Inspection is not enough —
one genuinely vacuous test shipped in Epic 1 and was only caught by mutating the code under it.

---

## 8. Typing and toolchain facts

- `pandas` ships no `py.typed`, so `mypy --strict` cannot see through `import pandas`.
  **`pandas-stubs>=3.0` is a dev dependency**; version `3.0.5.260730` is exactly aligned with the
  installed pandas and leaves `mypy src` clean. The alternative — an `ignore_missing_imports`
  override — was rejected because it collapses `DataFrame` to `Any` across the whole data layer.
- **`pyarrow-stubs` was rejected** on the same evidence standard: 20.0.0 against pyarrow 25.0.1 is
  five majors behind. `from pyarrow.lib import ArrowInvalid  # type: ignore[import-untyped]` is the
  narrow, deliberate exception.
- Iterate frames with `frame[columns].itertuples(index=False, name=None)` — selecting **by name**
  first. The `name=None` overload is typed `Iterator[tuple[Any, ...]]`, so the `Any` comes from
  pandas' own stubs rather than a hand-written annotation, and the by-name selection is what makes
  the code independent of column order.
- `numpy>=2.0` is declared in the dev extra because the fixtures import it directly, even though it
  arrives transitively with pandas.
- `ruff` uses an explicit 20-family `select`; `TRY003`, `PLC0415`, `T201` and `PLR2004` are
  deliberately excluded because they contradict binding decisions. Never run `ruff format .` — it
  reaches outside the source tree; use `ruff format src tests`.
- `frozen=True, slots=True` raises `TypeError`, not `AttributeError`, when a **new** attribute is
  assigned (CPython issue 91126). It affects every dataclass in this codebase, so a test asserting
  `AttributeError` on such an assignment would be wrong.
- `order_timelines`' `deck.name` tie-break is **unreachable by construction**: any same-date pair
  raises before an ordering is returned. Harmless, but do not write a test that pretends to exercise
  it.

---

## 9. Process facts for Epics 3–5

- **Parallel dispatch works** when file sets are disjoint and single-writer discipline holds on
  shared files. Tickets 013 ∥ 014 and 015 ∥ 016 ran in parallel with zero cross-contamination; each
  agent was told explicitly which files were *not* its own, and the orchestrator ran the repo-wide
  gate afterwards rather than asking each agent to run it.
- **`errors.py` is the one genuinely shared file.** It grew across six tickets and every edit was
  verified additions-only with `git diff --numstat` showing `N 0`. It now holds exactly seven
  classes: `DashboardError`, `ConfigError`, `SchemaError`, `DataFileError`, `RegistryError`,
  `DiscoveryError`, `StoreError`. A ticket that adds an eighth must append and prove it.
- **Never dispatch a ticket that writes a file another agent is verifying.** Ticket-017 was held
  until the ticket-016 guardian finished, because 017 modifies `errors.py` while that guardian was
  asserting `errors.py` was unmodified — a false scope violation would have cost a full
  re-verification.
- Agents must be told **only read-only git commands are permitted**. One specialist ran
  `git stash`/`git stash pop` despite an enumerated prohibition; stating the principle rather than a
  list fixed it.
- The `bash -lc '...'` wrapper is terminated by **apostrophes as well as quotes** — "the entity's
  array" broke a patch script. Use `bash <<"EOF"` heredocs with double quotes only, or the
  Read/Edit/Write tools.
- Measure before ruling. A suspected `mypy --strict` blocker on sorting `tuple[object, ...]` turned
  out not to exist; probing it first avoided sending a specialist after a phantom.
- One commit per ticket, staged **by explicit path** (never `git add -A`), with the state file and
  README update inside the ticket's own commit.

## What Epic 3 must not re-litigate

Settled, with the evidence recorded in the epic-03 overview:

- **E3-1** — the renderer is tested with Python-only assertions on the generated HTML and JSON plus
  a manual checklist under `docs/`. No Node, no JS engine (`node`/`npm` are absent from this WSL
  environment). Accepted cost: the browser-side difference computation has no automated test, so the
  JavaScript stays thin and the checklist names the case.
- **E3-2** — the chart heading is always the curated `ChartSpec.title`; `Registries.title_for`
  supplies an additive subtitle or hover text.
- **Open question 8** — URL-hash state for linkable views is out of scope.
