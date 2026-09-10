# Epic 02: Data Layer

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **detailed** (tickets are ready for dispatch).

## Goal

Turn a directory tree of DESSEM synthesis Parquet files into one validated, typed, JSON-ready
in-memory structure, `DashboardData`, entirely under unit test and without any charting concern. At
the end of this epic a scenario tree becomes a `DashboardData` holding, for every enabled chart,
every entity, every scenario and every deck, a rounded value array aligned on a shared time axis,
plus a chained axis and an explicit list of Portuguese warnings.

## Scope

In scope:

- The declarative schema contract of the synthesis files: entity keys per aggregation level, the
  nine-column long series schema, the registry schemas, the fallback unit table.
- The chart registry mechanics and the declared catalogue of 23 enabled plus 19 disabled specs.
- Synthetic, schema-faithful Parquet fixtures so no test touches `exemplo/`.
- Scenario and deck discovery from the `--casos` directories.
- Typed readers with schema and uniqueness validation.
- Registry loading: plant, submarket and REE names, units with fallback, fictitious submarket
  filtering.
- Deck timeline from `EST.parquet`, deck ordering by date, the chaining window and its contiguity
  validation, deck-date alignment across scenarios.
- The `DashboardData` store and the consolidation that fills it.

Out of scope, and explicitly deferred:

- Any HTML, CSS, JavaScript, Plotly or theme concern (Epic 3).
- The compact JSON payload serialisation (ticket-020) and the output size enforcement
  (ticket-032). This epic keeps values in Python objects.
- `CUSTOS` and `TEMPO` aggregation into bar series (tickets 030 and 031); this epic only reads and
  validates those two files.
- Wiring the pipeline to the CLI (ticket-033) and any run against real data (ticket-034).
- Reading `ESTATISTICAS_OPERACAO_*` or `CVU`, which the master plan excludes.

## Reading Order for Implementers

1. `plans/dashboard-dessem/planning-context.md`, sections "Data facts" and "User decisions".
2. `plans/dashboard-dessem/00-master-plan.md`, Appendix A (the whole data model) and decisions 14
   to 18.
3. `plans/dashboard-dessem/reference/parquet-schemas.txt` only when a column or dtype is not in
   Appendix A.
4. `epic-01-learnings.md` for the `Settings` field names and the error hierarchy as implemented.

## Tickets

| Ticket | Title | Points | Agent time | Agent |
| ------ | ----- | ------ | ---------- | ----- |
| ticket-009 | Define the Parquet schema contracts | 3 | ~30 min | python-task-automation-developer |
| ticket-010 | Add the chart registry mechanics | 2 | ~25 min | python-task-automation-developer |
| ticket-011 | Declare the enabled chart specs | 3 | ~30 min | python-task-automation-developer |
| ticket-012 | Add the synthetic synthesis fixtures | 3 | ~30 min | monorepo-test-developer |
| ticket-013 | Implement scenario and deck discovery | 3 | ~30 min | python-task-automation-developer |
| ticket-014 | Implement the typed Parquet readers | 3 | ~30 min | python-task-automation-developer |
| ticket-015 | Implement registry loading and labels | 3 | ~30 min | python-task-automation-developer |
| ticket-016 | Implement the deck timeline and chaining | 3 | ~30 min | python-task-automation-developer |
| ticket-017 | Define the dashboard data store | 2 | ~25 min | python-task-automation-developer |
| ticket-018 | Implement series consolidation | 3 | ~30 min | python-task-automation-developer |

Total: 28 points, about 5 hours of agent time.

## Dependency Order

```text
ticket-009 ─┬─> ticket-010 -> ticket-011 ─────────────────┐
            ├─> ticket-012 ─┬─> ticket-013 ──────────────┤
            └───────────────┴─> ticket-014 ─┬─> ticket-015┼─> ticket-018
                                            └─> ticket-016┤
                            ticket-017 ──────────────────┘
```

## Definition of Done for the Epic

- [ ] `build_dashboard_data` turns the two-scenario, two-deck synthetic fixture into a
      `DashboardData` with the expected series lengths, entity lists and chained axis.
- [ ] A missing source file, a missing deck in one scenario, a chaining gap and a plant present in
      one variable and absent from another are each covered by a test and each produce a Portuguese
      warning rather than an exception.
- [ ] The 23 enabled chart keys of Appendix A.6 are exactly the keys returned by `enabled_specs`.
- [ ] No test reads from `exemplo/`, verified with
      `grep -rn "exemplo" tests/ | grep -v DESSEM_DASHBOARD_EXEMPLO` printing nothing.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` exit 0, and
      `pytest --cov=dessem_dashboard` total coverage is at or above 80 percent.

## Learnings to Capture for Later Epics

Record in `epic-02-learnings.md` at the epic boundary: the exact `ChartSpec` field names and the
`EntitySelector` values; the entity identifier string format used as a dictionary key; the
`DashboardData` public accessors; the deck-date key type; the shape of the per-deck and chained
axes; the warning message wording; the measured fixture build time; and any dtype surprise found in
`pandas 3.x`.
