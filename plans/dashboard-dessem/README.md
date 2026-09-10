# Plan: Dashboard HTML para Comparação de Resultados do DESSEM

Progressive implementation plan for the DESSEM comparison dashboard: 5 epics, 38 tickets, Epics 1
and 2 fully detailed and ready for dispatch, Epics 3 to 5 as outlines to be refined with the
learnings of the earlier epics.

## Navigation

| File | Purpose |
| ---- | ------- |
| [`00-master-plan.md`](00-master-plan.md) | Goals, architecture, 19 design decisions with rationale, epic breakdown, risk analysis, open questions, and the data-model appendix |
| [`planning-context.md`](planning-context.md) | **Binding** user decisions and verified data, environment and brand facts. Never contradict it. |
| [`reference/parquet-schemas.txt`](reference/parquet-schemas.txt) | Raw dtype, unique-value and sample-row dump of all 60 synthesis files. Only needed when Appendix A of the master plan is not enough. |
| [`epic-01-project-foundation/`](epic-01-project-foundation/) | Scaffold and repository hygiene, 8 detailed tickets |
| [`epic-02-data-layer/`](epic-02-data-layer/) | Discovery, readers, registries, timeline, chart registry, data store, 10 detailed tickets |
| [`epic-03-dashboard-core/`](epic-03-dashboard-core/) | Theme, payload, HTML shell, JS renderer, SIN and SBM charts, 8 outline tickets |
| [`epic-04-plant-and-scalar-charts/`](epic-04-plant-and-scalar-charts/) | Plant charts with filters, cost and time bars, size enforcement, 6 outline tickets |
| [`epic-05-delivery-and-legacy-removal/`](epic-05-delivery-and-legacy-removal/) | Pipeline wiring, validation, documentation, legacy removal, 6 outline tickets |
| `.implementation-state.json` | Machine-readable execution state, readiness scores and open questions |
| [`HANDOFF-PROMPT.md`](HANDOFF-PROMPT.md) | Prompt to paste into a new chat to start `/implement-plan` with every decision carried over |

**Required reading before implementing any ticket**, in order: `planning-context.md`, then
`00-master-plan.md` (especially Appendix A, the data model, and Appendix B, the `settings.json`
contract), then `~/.claude/rules/python.md` and `~/.claude/rules/markdown.md`.

## Decisions of Record

| Item | Value |
| ---- | ----- |
| Implementation mode | **Rigoroso** — English identifiers, comments, docstrings, README and tests; minimal comments |
| User-facing language | **Portuguese** — CLI flags, `--help`, log messages, error messages, dashboard UI |
| Rigor tier | **full** (`/plan` plus `/implement-plan`, guardian after every ticket, quality gate at every epic boundary) |
| Scaffolding | **Epic 1**, `/new-project` template applied in place; `scaffolded: false`, `scaffolding: "epic-1"` |
| Planning mode | **progressive** — Epics 1 and 2 detailed, Epics 3 to 5 outline |
| Target stack | Python `>=3.12` on WSL Ubuntu, `uv`-managed `.venv`, `pandas>=3.0`, `pyarrow`, `plotly>=6`, `rich`; dev `pytest`, `pytest-cov`, `ruff`, `mypy --strict` |
| Agent chain | `python-task-automation-developer` for code, `open-source-documentation-writer` for docs, `docker-linux-server-architect` for git and shell, `monorepo-test-developer` for the fixture and integration tickets, `type-lint-guardian` at epic gates |

Execution strategy: **Continuous** — chosen 2026-09-10 by the developer at the start of
`/implement-plan` and recorded in `.implementation-state.json` (`execution_strategy: "continuous"`).
See "Phases & Estimates" below.

## Epics

| Epic | Name | Tickets | Points | Detail | Phase |
| ---- | ---- | ------- | ------ | ------ | ----- |
| epic-01 | Project foundation and repo hygiene | 001-008 | 17 | detailed | executing |
| epic-02 | Data layer | 009-018 | 28 | detailed | executing |
| epic-03 | Dashboard core | 019-026 | 21 | outline | outline |
| epic-04 | Plant-level and scalar charts | 027-032 | 14 | outline | outline |
| epic-05 | Delivery, validation and legacy removal | 033-038 | 14 | outline | outline |

Total: 38 tickets, 94 points. Detailed tickets are sized at 30 minutes of agent time or less.

## Progress

| Ticket | Title | Epic | Status | Detail Level | Readiness | Quality | Badge |
| ------ | ----- | ---- | ------ | ------------ | --------- | ------- | ----- |
| ticket-001 | Configure `.gitignore` and untrack the input data | epic-01 | completed | Detailed | 0.94 | 1.00 | EXCELLENT |
| ticket-002 | Create `pyproject.toml` and the package skeleton | epic-01 | completed | Detailed | 0.94 | 0.90 | EXCELLENT |
| ticket-003 | Add `settings.json` and the validating config loader | epic-01 | completed | Detailed | 0.94 | 1.00 | EXCELLENT |
| ticket-004 | Add the audit logging setup module | epic-01 | completed | Detailed | 0.96 | 1.00 | EXCELLENT |
| ticket-005 | Add the run manifest module | epic-01 | completed | Detailed | 0.96 | 1.00 | EXCELLENT |
| ticket-006 | Add the CLI entry point and the pipeline stub | epic-01 | completed | Detailed | 0.94 | 1.00 | EXCELLENT |
| ticket-007 | Add the project `CLAUDE.md` and the README skeleton | epic-01 | completed | Detailed | 0.94 | 1.00 | EXCELLENT |
| ticket-008 | Verify the toolchain quality gates | epic-01 | completed | Detailed | 0.96 | 1.00 | EXCELLENT |
| ticket-009 | Define the Parquet schema contracts | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-010 | Add the chart registry mechanics | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-011 | Declare the enabled chart specs | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-012 | Add the synthetic synthesis fixtures | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-013 | Implement scenario and deck discovery | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-014 | Implement the typed Parquet readers | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-015 | Implement registry loading and labels | epic-02 | pending | Detailed | 0.94 | -- | -- |
| ticket-016 | Implement the deck timeline and chaining | epic-02 | pending | Detailed | 0.94 | -- | -- |
| ticket-017 | Define the dashboard data store | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-018 | Implement series consolidation | epic-02 | pending | Detailed | 0.96 | -- | -- |
| ticket-019 | Build the brand theme module | epic-03 | pending | Outline | -- | -- | -- |
| ticket-020 | Export the compact JSON payload | epic-03 | pending | Outline | -- | -- | -- |
| ticket-021 | Assemble the single-file HTML shell | epic-03 | pending | Outline | -- | -- | -- |
| ticket-022 | Implement the JavaScript chart renderer core | epic-03 | pending | Outline | -- | -- | -- |
| ticket-023 | Implement the view mode and deck selector | epic-03 | pending | Outline | -- | -- | -- |
| ticket-024 | Implement the absolute and difference toggle | epic-03 | pending | Outline | -- | -- | -- |
| ticket-025 | Render the SIN level charts | epic-03 | pending | Outline | -- | -- | -- |
| ticket-026 | Render the submarket and interchange charts | epic-03 | pending | Outline | -- | -- | -- |
| ticket-027 | Render the hydro plant charts | epic-04 | pending | Outline | -- | -- | -- |
| ticket-028 | Implement the name and code filters | epic-04 | pending | Outline | -- | -- | -- |
| ticket-029 | Render the thermal plant charts | epic-04 | pending | Outline | -- | -- | -- |
| ticket-030 | Render the cost bar charts | epic-04 | pending | Outline | -- | -- | -- |
| ticket-031 | Render the computational time bar charts | epic-04 | pending | Outline | -- | -- | -- |
| ticket-032 | Enforce the output size strategy | epic-04 | pending | Outline | -- | -- | -- |
| ticket-033 | Wire the end-to-end pipeline | epic-05 | pending | Outline | -- | -- | -- |
| ticket-034 | Add the example-data integration test | epic-05 | pending | Outline | -- | -- | -- |
| ticket-035 | Run the legacy parity check | epic-05 | pending | Outline | -- | -- | -- |
| ticket-036 | Write the user documentation | epic-05 | pending | Outline | -- | -- | -- |
| ticket-037 | Polish the CLI usability and error messages | epic-05 | pending | Outline | -- | -- | -- |
| ticket-038 | Remove the legacy scripts | epic-05 | pending | Outline | -- | -- | -- |

Readiness is the composite of the five-dimension rubric, computed during planning. Outline tickets
are scored after refinement. `Quality` and `Badge` are filled by `/implement-plan` after each ticket
is implemented and scored.

## Dependency Graph

Directed acyclic graph over all 38 tickets. Every arrow reads "must complete before".

```text
epic-01
  001 -> 002 -> 003 -> 006 -> 007 -> 008
                004 ------> 006
                005 ------> 006
         002 -> 004
         002 -> 005

epic-02
  008 -> 009 -> 010 -> 011 -> 018
         009 -> 012 -> 013 -> 018
         009 -> 014 -> 015 -> 018
                011 -> 012
                012 -> 014
                014 -> 016 -> 018
  008 -> 017 -----------------> 018

epic-03
  018 -> 019 -> 021
  018 -> 020 -> 021 -> 022 -> 023 -> 025 -> 026
                       022 -> 024 -> 025

epic-04
  026 -> 027 -> 028 -> 029 -> 032
  026 -> 030 -> 031 -> 032

epic-05
  032 -> 033 -> 034 -> 035 -> 036 -> 037 -> 038
```

Verification: the graph has no cycle. Ticket indices only ever point forward, and within Epic 2 the
only non-consecutive edges are `009 -> 012`, `009 -> 014`, `011 -> 012`, `012 -> 014`, `014 -> 016`
and `008 -> 017`, all forward.

## Execution Order

A valid topological order that also respects the epic boundaries and the quality gates:

```text
Epic 1: 001, 002, 003, 004, 005, 006, 007, 008          gate: ruff + mypy + pytest, coverage >= 80 %
Epic 2: 009, 010, 011, 012, 013, 014, 015, 016, 017, 018 gate: same, plus DashboardData end-to-end test
        [refine epic-03 outlines with epic-01 and epic-02 learnings]
Epic 3: 019, 020, 021, 022, 023, 024, 025, 026           gate: single offline HTML renders SIN and SBM
        [refine epic-04 outlines with epic-03 learnings]
Epic 4: 027, 028, 029, 030, 031, 032                     gate: full catalogue renders, size measured
        [refine epic-05 outlines with epic-04 learnings]
Epic 5: 033, 034, 035, 036, 037, 038                     gate: parity check passed, coverage >= 85 %
```

Tickets 004 and 005 are independent of each other and of 003, so they may run in parallel after 002.
Tickets 009, 012 and 017 open three partly independent chains inside Epic 2. Everything else is
strictly sequential.

## Phases & Estimates

One phase per epic. Estimates are approximate **agent working time** for the tickets alone, not
wall-clock, and exclude the Full-tier overhead (guardian verification after every ticket, the
simplify + review fan-out at every epic boundary, clarification pauses). Outline epics carry
Low-confidence `≈` estimates derived from story points at the ~10.5 min/point ratio observed in
Epics 1 and 2; they are re-estimated when refined.

| Phase | Epic | Tickets | Points | Est. agent time | Confidence |
| ----- | ---- | ------- | ------ | --------------- | ---------- |
| 1 | epic-01-project-foundation | 8 | 17 | ~2.5–3.5 h | High |
| 2 | epic-02-data-layer | 10 | 28 | ~4–5.5 h | High |
| 3 | epic-03-dashboard-core | 8 | 21 | ≈3–5 h | Low (outline) |
| 4 | epic-04-plant-and-scalar-charts | 6 | 14 | ≈2–3.5 h | Low (outline) |
| 5 | epic-05-delivery-and-legacy-removal | 6 | 14 | ≈2–3.5 h | Low (outline) |

Total: ≈ 13.5–21 h of agent time (approximate).

**Execution strategy: Continuous** (chosen 2026-09-10, `.implementation-state.json` →
`execution_strategy: "continuous"`). The 38 tickets run straight through with no approval stop at
the phase boundaries. The Full-tier quality machinery is unaffected and still runs: `spec-scorer`
readiness gate and `implementation-guardian` verification on every ticket, and the epic quality gate
plus the `code-simplifier` + `code-reviewer` fan-out at every epic boundary. Execution still stops
for a readiness or quality gate failure, a guardian FAIL, a specialist `CLARIFICATION REQUIRED`, or
any ambiguity not settled by `planning-context.md`.

The phase table above therefore describes the epic boundaries and their estimates, not approval
stops.

## Open Questions

Questions 4 and 5 were discovered during planning and **resolved by the developer on 2026-09-10**;
nothing blocks any epic. Full text in `00-master-plan.md`, section "Open Questions".

| # | Blocking | Summary | Affects |
| - | -------- | ------- | ------- |
| 1 | no | Cost total defaults to `PRESENTE + FUTURO`; the other two parcels are configurable | ticket-030 |
| 2 | no | UHE "Volume armazenado" ships both `VARMF_UHE` (hm3) and `VARPF_UHE` (percent) | ticket-011, ticket-027 |
| 3 | no | UHE "Vazão" ships both `QAFL_UHE` (afluente) and `QINC_UHE` (incremental) | ticket-011, ticket-027 |
| 4 | no (resolved) | The 240 `exemplo` worktree deletions are intentional. ticket-001 stages them via `git rm -r --cached`, commits them with `.gitignore` and pushes | ticket-001, ticket-038 |
| 5 | no (resolved) | Example tree rebuilt from git history into `exemplo/caso_oficial/` and `exemplo/caso_gurobi/` (2 decks each, gitignored). ticket-034 defaults to it, `DESSEM_DASHBOARD_EXEMPLO` overrides, skip when absent | ticket-034, ticket-035 |

Every detailed ticket is dispatchable today.
