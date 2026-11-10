# Intake: hydro flow charts in the SIN and Usinas hidrelétricas sections

- **Mode:** INTAKE, revision 2 (requirements, classification, roster and questions only; no master
  plan, epics or decision records, which belong to SYNTHESIS).
- **Plan dir:** `/home/carlosribeiro/git/plotador-dessem/plans/graficos-hidreletricos`
- **Date:** 2026-11-09. Repository at `main` `dfae1ed` (clean).
- **Inputs:** the raw feature spec (below) and the operator's Phase 1 clarification answers of
  2026-11-09 (section "Clarification answers"). No `--council=` override.
- **Revision 2 changes:** scope reduced by the operator's rule *no synthesized file → no chart*;
  derivation requirements withdrawn; answered questions removed; counts re-measured.
- **Read for this intake:** `CLAUDE.md`, `README.md`, `settings.json`, every module under
  `src/dessem_dashboard/charts/`, `data/consolidate.py`, `data/readers.py`, `data/schemas.py`,
  `data/registries.py`, `models/store.py`, `dashboard/payload.py`, `dashboard/builder.py`,
  `dashboard/assets/dashboard.js` (trace builders), `tests/fixtures_sintese.py`,
  `tests/exemplo_tree.py`, the count pins across `tests/`, `docs/checklist-manual-dashboard.md`,
  and both example synthesis folders under `examples/`.

## Raw feature spec (verbatim, Portuguese)

> Quero adicionar todos os gráficos referentes às usinas hidrelétricas. Quero que na seção SIN
> tenha vertimento, turbinamento, defluência, vazão afluente, vazão incremental. Isso vale também
> para a seção submercado e para a seção hidrelétricas. Os gráficos devem ficar organizados de tal
> forma que faça sentido o ordenamento. Estude o repositório, é de extrema importância ter a noção
> do todo para que a implementação desejada não fique incorreta. Os dados para montar os gráficos
> seguem oriundos da pasta síntese. Dentro da pasta examples é possível encontrar duas pastas de
> síntese, uma para o caso nomeado de Oficial e outra para o caso nomeado de Modificado. Você pode
> usar os arquivos dentro dessas pastas para estudar e entender como serão incorporados os novos
> gráficos que mencionei. Vale destacar que os gráficos devem suportar a análise por caso, análise
> encadeada e também a funcionalidade de diferença.

## Clarification answers (operator, 2026-11-09)

| Question | Answer |
| --- | --- |
| Q3: Vazão Afluente / Incremental at SIN | "Se não existem a nível de SIN então não precisam de gráfico na seção SIN." Rule: **no synthesized file → no chart.** `QAFL`/`QINC` are out of the SIN section. |
| Submercado follow-up | The same rule applies. None of the five flows exists as an SBM file, so the Submercado section gets **no flow charts**. **No derived series anywhere in this plan.** |
| Q4: SIN source | Use the synthesized `QDEF_SIN`/`QTUR_SIN`/`QVER_SIN` files by enabling the existing declared specs. |
| Q2: ordering | Water-balance order. SIN: `GTER, GHID, GUNS, EARMF, VARMF, QDEF_SIN, QTUR_SIN, QVER_SIN`. UHE: Geração, Volume Armazenado (hm3), Volume Armazenado (%), then Vazão Afluente → Vazão Incremental → Defluência → Turbinamento → Vertimento. Submercado unchanged. |
| Q1: scope of "todos" | Only the five flows. No `VAGUA`/`VCALHA`/`VARMI`/`VARPI`/`EARMF_SBM`. |
| Q8: `fictitious_codes` defect | Fix it in its own small ticket inside this plan. |
| Q9: README | The feature-touched sections, plus the unrelated stale content (removed `Avisos` section, `Execução` vs `Custo`/`Tempo`, "two Execução charts" → seven, measured quality-gate table) as a separate doc ticket in this plan. |
| Q12: real-data validation | An automated real-data test that skips when the data is absent (run with `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`), plus a manual CLI run and checklist entries. |
| Q10: visual organisation | Reorder only. No sub-headings, no UI change. |
| Q11: count pins | Update each pin literal with the measured value. No centralisation ticket. |
| Q14: "análise por caso" | `Por deck` mode plus one trace per scenario in `Absoluto`. No new filter. |
| Q15: non-goals | Confirmed: REE level, limit bands, flow charts in other sections, new UI controls. |
| Block confirmation | Existing UHE charts are only repositioned (R14). No new `settings.json` key (R18). No new performance budget (R21). CLAUDE.md quality gate, invariants and stale-count cleanup (R22, R23, R25). Docs in scope (R24). |
| SYNTHESIS follow-up 1: `test_parity.py` Group B pre-existing failure on `examples/` | "Ticket próprio neste plano." A test-only fix in `tests/test_parity.py`: the expected CUSTOS/TEMPO scalar visit count is derived from the measured decks in `context.dirs_by_scenario` instead of `len(context.scenarios) * 2`; any other Group B assertion with the same premise is covered too. No product code changes. Group B must PASS on `examples/` and still pass on the documented two-deck pair by construction. Placement left to the planner (→ R29, ADR-009). |
| SYNTHESIS follow-up 2: debt record A4 register | "Só no plano mestre." No repository `DEBT.md`; the record stays in `00-master-plan.md` only, with no ticket. |

Q5, Q6, Q7 and Q13 lapsed, because each only concerned derived series, which are now out of scope.

## Repository facts that shape the requirements (verified 2026-11-09)

### What the synthesis ships per level, and what this plan does with it

| Flow (UI title) | UHE | SIN | SBM |
| --- | --- | --- | --- |
| Vazão Afluente | `QAFL_UHE` file; spec enabled → **reposition** | no file → **no chart** | no file → **no chart** |
| Vazão Incremental | `QINC_UHE` file; enabled → **reposition** | no file → **no chart** | no file → **no chart** |
| Defluência | `QDEF_UHE` file; enabled → **reposition** | `QDEF_SIN` file; declared `enabled=False` → **enable** | no file → **no chart** |
| Turbinamento | `QTUR_UHE` file; enabled → **reposition** | `QTUR_SIN` file; declared `enabled=False` → **enable** | no file → **no chart** |
| Vertimento | `QVER_UHE` file; enabled → **reposition** | `QVER_SIN` file; declared `enabled=False` → **enable** | no file → **no chart** |

- Both example folders (`examples/Oficial/2026-08-15/sintese`, `examples/Modificado/2026-08-15/sintese`)
  hold the same 65 Parquet files. Each scenario has one deck of 80 stages (48 half-hour stages, then
  stages of 2 h to 17 h), so `Encadeado` takes the first 48.
- `METADADOS_OPERACAO` (40 keys) has rows for `QDEF_SIN`, `QTUR_SIN` and `QVER_SIN`, with long names
  `Vazão Defluente`, `Vazão Turbinada` and `Vazão Vertida`, all in `m3/s`. These differ from the
  curated titles `Defluência`, `Turbinamento` and `Vertimento`, so on real data each enabled SIN
  flow chart shows that long name as its subtitle, the same as the UHE flow charts.
- The synthesized SIN flow files equal plain sums over all 169 plants: `QDEF_SIN`, `QTUR_SIN` and
  `QVER_SIN` match Σ `*_UHE` per stage within 3e-11 m3/s. `QDEF_UHE == QTUR_UHE + QVER_UHE` per plant
  and stage, within 2e-12. No file in the synthesis carries cascade topology.
- `QINC_UHE` is identical between Oficial and Modificado (0 of 13,520 rows differ), so `Diferença`
  on Vazão Incremental is identically zero for this pair. That is expected, since both scenarios
  share the same hydrology. `QAFL`, `QDEF`, `QTUR` and `QVER` differ in 2,615, 4,028, 3,662 and
  1,158 rows respectively.

### Architecture facts a correct implementation must respect

- `Por deck`, `Encadeado` and client-side `Diferença` work automatically for every SERIES chart
  stored through `data/consolidate.py::_load_series` → `DashboardData.add_series` (deck_date=None
  is the chained axis). The renderer (`dashboard.js::buildTraces/valuesForMode`) has no
  chart-key-specific code. Enabling the three SIN specs therefore needs no consolidation, payload
  or renderer change.
- Ordering is the order of entries in `SPECS`. `builder._level_nav` lists groups by first
  occurrence, and `_chart_sections` renders each group's sections in `enabled_specs()` order.
  - `QDEF_SIN`, `QTUR_SIN` and `QVER_SIN` currently sit at the very end of `SPECS`, after the
    disabled block.
  - Enabled in place, they already render after `VARMF_SIN` in the confirmed order. This was
    measured on a fresh registry.
  - Moving them into the enabled SIN block keeps the docstring's "enabled first, then disabled"
    layout true (agenda K5).
- The UHE section is reordered from `GHID, QTUR, QVER, VARMF, VARPF, QDEF, QAFL, QINC` to
  `GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER`. Keys, titles and units do not change.
- **`fictitious_codes` defect (fixed by R27).** `consolidate._load_registries` calls
  `load_registries(...)` without `fictitious_codes` (`consolidate.py:365` and `:373`). As a result,
  `Submarket.fictitious` always comes from the hard-coded default `(11, 99)` in the
  `registries.load_registries` signature (`registries.py:225`), and
  `settings.submarkets.fictitious_codes` only feeds the dropped-code warning set
  (`consolidate.py:430`). It never affects SBM visibility, which breaks the rule "never hard-code a
  tunable".
- **README stale content.**
  - Feature-touched parts (R24):
    - catalogue counts (42 declared / 23 enabled / 19 disabled, against today's 47/28/19);
    - `QDEF_SIN` used as the worked "disabled chart" example;
    - the twelve-file test-pin table (23/42/30);
    - the `## Structure` comment on `specs.py`;
    - the per-chart warning counts in `## Logging and auditing`.
  - Unrelated parts (R28):
    - the `Avisos` section that commit `1e95a72` removed from the dashboard but the README still
      documents (layout figure, "Avisos: the eight warning shapes", manifest and log paragraphs);
    - `Execução` where `builder.GROUP_LABELS` has `Custo`/`Tempo`;
    - "The two Execução charts", which are now seven dedicated bar charts;
    - the measured quality-gate table.
  - `docs/checklist-manual-dashboard.md` already reflects `Custo`/`Tempo` and the removed `Avisos`
    section (lines 47–51, 136–140, 192–203). Its only stale text is "five SIN charts" (lines 33
    and 56).
- **Count pins that move** (grep `tests/`):

  | Test file | Pin | Change |
  | --- | --- | --- |
  | `test_chart_specs.py` | `_ENABLED_KEYS_IN_ORDER` | 31 keys, UHE reordered |
  | `test_chart_specs.py` | disabled count in `test_all_specs_has_forty_seven_entries_with_nineteen_disabled` | 19 → 16 (47 unchanged) |
  | `test_builder.py` | `_ENABLED_CHART_COUNT`, `_SIN_CHART_COUNT` | 28 → 31; 5 → 8 |
  | `test_charts_costs.py` | literal | 28 → 31 |
  | `test_charts_sin.py` | `_ALL_ENABLED_CHART_KEYS` (also passed as `disabled`), `_SIN_CHART_KEYS`, `_SIN_TITLES_IN_ORDER`, `_SIN_UNITS_IN_ORDER` | add the three SIN flows; literal 28 → 31 |
  | `test_charts_hydro.py` | `_UHE_CHART_KEYS_IN_ORDER`, titles, units, entity counts | reordered; entity counts become (3, 2, 2, 3, 3, 3, 3, 3) |
  | `test_output_size.py`, `test_payload.py`, `test_pipeline.py`, `test_parity.py`, `test_integration_exemplo.py` | `_ENABLED_CHART_COUNT` | 28 → 31 |
  | `test_registries.py` | `_ENABLED_CHART_KEY_COUNT` | 28 → 31 |
  | `test_fixtures_sintese.py` | fixture file counts | 30/29/30 → 33/32/33 |
  | `test_schemas.py` | `_ENABLED_CHART_KEYS`/`_DISABLED_CHART_KEYS` partition and its "19 disabled" comment | the three SIN keys move to enabled; 42 total unchanged |
  | `test_renderer_controls.py` | `_ALL_SIN_CHART_KEYS` | add the three, or the "disable every SIN chart" test keeps SIN active |

  `test_charts_submarket.py` is unaffected. The controlled-share range in `test_output_size.py`
  (150k–400k bytes, 238k measured) absorbs three one-entity charts.
- **Real-data tests.** `exemplo/` does not exist; `examples/` holds `Oficial`/`Modificado`. With
  `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, `exemplo_tree.qualifying_scenarios` finds both
  scenarios. The `documented_pair` tests (`caso_oficial`/`caso_gurobi`) still skip.
- **Baseline run** (`dessem-dashboard --casos examples/Oficial examples/Modificado`, output in a
  scratch folder): 28 charts, 0 warnings, 6,623,433-byte HTML (Plotly 4,293,347), 348,178 values,
  1.7 s wall time, about 336 MB peak RSS.

### Projected counts (measured 2026-11-09 by enabling the three SIN specs on a fresh `ChartRegistry`)

| Quantity | Before | After |
| --- | --- | --- |
| `all_specs()` | 47 | 47 |
| `enabled_specs()` | 28 | **31** |
| disabled | 19 | **16** |
| SIN group | 5 | **8** |
| SBM group | 6 | 6 |
| UHE group | 8 | 8 (reordered) |
| SERIES charts | 21 | 24 |
| scalar source files | 2 | 2 |
| fixture files (`make_sintese_dir`) | 30 | **33** |
| fixture METADADOS rows | 28 | **31** |
| `FALLBACK_UNITS` | 42 | 42 |
| README per-chart warnings for one missing synthesis folder | 23 | **26** (24 series + 2 scalar files) |
| same, across 2 scenarios × 2 decks | 92 | **104** |

## (a) Source-tagged requirements

```yaml
requirements:
  - id: R1
    text: "The SIN section shows three hydro flow charts read from the synthesized files: Defluência (QDEF_SIN), Turbinamento (QTUR_SIN) and Vertimento (QVER_SIN); Vazão Afluente and Vazão Incremental are not shown at SIN because the synthesis ships no SIN file for them."
    kind: functional
    source: clarification
  - id: R2
    text: "Confirmed scope decision: the Submercado section gets no hydro flow chart. The raw spec asked for the five flows there, but none exists as an SBM synthesis file, and the operator applied the no-file-no-chart rule (R26); the Submercado section is unchanged."
    kind: constraint
    source: clarification
  - id: R3
    text: "The Usinas hidrelétricas section shows the five flow charts per plant (QAFL_UHE, QINC_UHE, QDEF_UHE, QTUR_UHE, QVER_UHE, already declared and enabled) and keeps them."
    kind: functional
    source: spec
  - id: R4
    text: "Within each section, charts follow a deliberate, domain-meaningful order; the concrete order is R13."
    kind: functional
    source: spec
  - id: R5
    text: "All chart data comes from each deck's sintese/ Parquet files (settings discovery.sintese_dirname); no other DESSEM output is read."
    kind: constraint
    source: spec
  - id: R6
    text: "Every chart of R1 and R3 supports Por deck (with the Deck selector), Encadeado, Absoluto and Diferença with the existing line-chart semantics; 'análise por caso' means Por deck mode plus one trace per scenario in Absoluto, and no new filter is added."
    kind: functional
    source: clarification
  - id: R7
    text: "The change is consistent with the repository as a whole (catalogue -> consolidation -> DashboardData -> payload -> renderer), not a local patch that is correct for one layer and wrong for another."
    kind: constraint
    source: spec
  - id: R9
    text: "SIN Defluência / Turbinamento / Vertimento are delivered by enabling the existing declared specs QDEF_SIN / QTUR_SIN / QVER_SIN; no derivation or aggregation code is added."
    kind: functional
    source: clarification
  - id: R13
    text: "Order (water balance): SIN = GTER_SIN, GHID_SIN, GUNS_SIN, EARMF_SIN, VARMF_SIN, QDEF_SIN, QTUR_SIN, QVER_SIN; UHE = GHID_UHE, VARMF_UHE, VARPF_UHE, QAFL_UHE, QINC_UHE, QDEF_UHE, QTUR_UHE, QVER_UHE; Submercado order unchanged (MER, GHID, GTER, GUNS, CMO, VARMF)."
    kind: functional
    source: clarification
  - id: R14
    text: "The existing UHE flow charts keep their key, title, unit and enabled state; only their position in SPECS changes."
    kind: constraint
    source: clarification
  - id: R18
    text: "No new settings.json key; the only operator-facing configuration effect is that charts.disabled can now hide the three newly enabled SIN keys."
    kind: constraint
    source: clarification
  - id: R20
    text: "Real-data validation on examples/Oficial + examples/Modificado: an automated test that skips when the data is absent (run with DESSEM_DASHBOARD_EXEMPLO=<repo>/examples), plus a manual CLI run and new manual-checklist entries covering the SIN flow charts and the UHE order in all four mode combinations."
    kind: nonfunctional
    source: clarification
  - id: R21
    text: "No new performance budget: the run stays well below output.size_warning_mb (baseline 6.6 MB HTML, 1.7 s on the example pair); growth is limited to three one-entity SIN charts."
    kind: nonfunctional
    source: clarification
  - id: R22
    text: "The CLAUDE.md quality gate passes (ruff check, ruff format --check, mypy src, pytest --cov) with coverage >= 85%; each moved count-pin literal is updated in place with the value measured through enabled_specs()/all_specs() (no centralisation)."
    kind: constraint
    source: clarification
  - id: R23
    text: "CLAUDE.md invariants hold: readers.py stays the only pandas.read_parquet caller; missing data degrades through DashboardData.add_warning; the output stays one offline HTML file; colors live only in theme.py; the CLI exit/stdout contract is unchanged; UI, log and error text is Portuguese, identifiers, comments, docs and tests are English."
    kind: constraint
    source: clarification
  - id: R24
    text: "Feature-touched documentation matches the code: README catalogue counts, chart catalogue text, a still-disabled chart replacing QDEF_SIN as the 'Enabling an already-declared chart' example, the test-pin table, the Structure comment on specs.py, the per-chart warning counts in Logging and auditing (23 -> 26, 92 -> 104); docs/checklist-manual-dashboard.md SIN count (five -> eight)."
    kind: constraint
    source: clarification
  - id: R25
    text: "No dead code or stale text is left: module docstrings and comments carrying counts or groupings (charts/specs.py '47 ... 28 ... 19', data/schemas.py FALLBACK_UNITS '23 keys ... 19 disabled' and its enabled/disabled grouping comments, test_schemas.py's '19 disabled' comment) are updated."
    kind: constraint
    source: clarification
  - id: R26
    text: "Governing rule: a chart exists at a level only when the synthesis ships a file for that variable at that level; this plan adds no derived or aggregated series at any level."
    kind: constraint
    source: clarification
  - id: R27
    text: "Own ticket: settings.submarkets.fictitious_codes reaches registries.load_registries from consolidation, so submarket visibility honours the configured codes instead of the hard-coded (11, 99) default."
    kind: functional
    source: clarification
  - id: R28
    text: "Own doc ticket: README content that is stale independently of this feature is corrected: the removed Avisos section (layout figure, 'Avisos: the eight warning shapes', manifest and log paragraphs), Execução vs Custo/Tempo (level list, layout figure), 'The two Execução charts' -> seven dedicated bar charts, and the measured quality-gate table."
    kind: constraint
    source: clarification
  - id: R29
    text: "Own ticket, test-only: the real-data Group B parity test (tests/test_parity.py::test_group_b_series_and_scalar_parity_matches_legacy_expressions) derives its expected CUSTOS/TEMPO scalar visit count from the measured decks in context.dirs_by_scenario instead of assuming two decks per scenario, so it PASSES on any qualifying tree (including examples/ with one deck per scenario) and still on the documented two-deck exemplo/ pair by construction; no product code changes."
    kind: constraint
    source: clarification
```

**Count by source:** spec 4 (R3, R4, R5, R7); clarification 17 (R1, R2, R6, R9, R13, R14, R18,
R20–R29); inferred 0. Total 21 active. R29 was added after SYNTHESIS from the operator's follow-up
answer (2026-11-09).

IDs are kept stable, so gaps mark withdrawn requirements. R26, R27 and R28 are new in this
revision.

## Withdrawn requirements (do not resurrect in SYNTHESIS)

All of these were withdrawn by the operator's rule "no synthesized file → no chart" (R26), which
removed every derived series from the plan.

| ID | Was | Why withdrawn |
| --- | --- | --- |
| R8 | Derive the five SBM charts and SIN Afluente/Incremental as plain sums of `*_UHE` | No derived series (R26). Those charts are out of scope (R1, R2). |
| R10 | Derived series enter the store path pre-pivot | Nothing is derived. |
| R11 | Derived SBM visibility and dropped-code warning; derived SIN sums every plant | Nothing is derived. The SBM visibility issue that does exist is R27. |
| R12 | SBM membership from each `*_UHE` row's `codigo_submercado` | Nothing is derived. |
| R15 | Derived keys `QAFL_SBM` … `QINC_SIN` | No new chart keys are declared. |
| R16 | Derived-chart subtitle and unit from the source file's METADADOS row | Nothing is derived. The enabled SIN specs have their own METADADOS rows. |
| R17 | Null semantics of the aggregate sum | Nothing is aggregated. |
| R19 | Fixture fidelity: one file per source file at its own level, no non-existent files, no METADADOS rows for derived keys | Every clause concerned derived keys. The pre-existing METADADOS fixture gap is not a requirement of this feature; it is on the council agenda (K2). |

## Requirements needing confirmation

**None.** Every requirement that was `inferred` in revision 1 has either been confirmed by the
operator (now `source: clarification`) or withdrawn. No `PENDING DECISION:` line is open.

If council item K2 or K5 produces a new requirement, SYNTHESIS must tag it `inferred` and surface
it as a `PENDING DECISION:` before any `accepted` decision cites it.

## (b) Domain classification

Step 1 of Domain Decomposition, mapped onto this Python repository, for the reduced scope:

| Domain | Touched? | What it covers here | Consultant |
| --- | --- | --- | --- |
| Formulation / domain semantics | **yes (narrowed)** | Interpreting the synthesized SIN flows (a plain sum over plants), physically meaningful real-data assertions (`QDEF = QTUR + QVER`, SIN = Σ UHE, `QINC` Diferença ≡ 0 on a shared hydrology), and the semantics wording in the README. CLAUDE.md routes DESSEM result interpretation to this seat. | `dessem-specialist` |
| Solver integration | no | — | — |
| Implementation (Python CLI) | **yes** | `SPECS` enable and reorder (`charts/specs.py`), the `fictitious_codes` plumbing (`data/consolidate.py`, `data/registries.py`), comment/docstring cleanup, pin updates, the real-data test | `python-task-automation-developer` |
| Distribution / MPI | no | — | — |
| I/O | touched read-only | Existing Parquet inputs, read through the unchanged `read_series` contract. No format is created or changed. | none |
| Build / deploy | no | `pyproject.toml` and packaging unchanged | — |
| Test strategy (cross-cutting) | **yes** | Pin updates in about 15 files, the real-data test design, a regression test for R27, renderer checks kept static (no Node.js) | `test-strategist` |
| Documentation | **yes (larger share)** | README feature sections (R24), the unrelated README cleanup (R28), new manual-checklist steps (R20) | `open-source-documentation-writer` |
| UI/UX | no | The operator chose reorder only (Q10); no DOM, CSS or JS change | — |

**Ordered specialist chain:**

```
dessem-specialist (semantics of the synthesized flows, real-data assertions, README semantics wording)
  -> python-task-automation-developer (SPECS enable/reorder, fictitious_codes fix, cleanup, pins, real-data test)
  -> open-source-documentation-writer (README feature sections, README stale-content ticket, checklist steps)
test-strategist: cross-cutting (pin plan, real-data test design, R27 regression test)
```

## (c) Consultant roster

| # | Consultant | Tier | Still earns its seat? |
| --- | --- | --- | --- |
| 1 | `dessem-specialist` | Design / formulation (Opus) | **Yes, with a narrow brief.** Derivation semantics are gone, but CLAUDE.md routes DESSEM result interpretation to this seat. It decides which real-data assertions are physically meaningful (R20) and how the README states what `QDEF_SIN` and the others mean (R24). It also confirms that no-file-no-chart (R26) leaves no hydro flow the synthesis ships unrepresented. |
| 2 | `python-task-automation-developer` | Implement (Sonnet; consult with per-call `model: "opus"`) | **Yes.** It owns the catalogue edit, the shape of the `_load_registries` fix (R27) and the pin updates. |
| 3 | `test-strategist` | Plan (Opus) | **Yes.** Rule 2 still holds: at least 2 epics are expected (feature, bugfix, docs/validation). It owns the real-data test design and the R27 regression test. |
| 4 | `open-source-documentation-writer` | Sonnet | **Yes, now the largest share**: R24, R28 and the checklist part of R20. |

- **Size:** 4 of the 6-consultant cap. No domain was dropped by the cap.
- **Considered and not selected:**
  - `data-model-format-specialist`: rule 3 is not triggered; no persisted or serialized format is
    created or changed.
  - `ui-ux-specialist`: Q10 was answered "reorder only".
  - All HPC, SDDP, solver and build seats: their domains are not touched.
- **Override:** no `--council=` was supplied. If one is, its list replaces this roster; the
  artifact's shape does not change.

## (d) Clarification questions for the operator

**None open.** Q1–Q4 and Q8–Q15 are answered (section "Clarification answers"). Q5, Q6, Q7 and Q13
lapsed with the withdrawal of derived series.

## Open design questions routed to the council (agenda only, not decisions)

- **K1. Where the real-data test lives and what it asserts (R20).**
  - Location: extend `tests/test_integration_exemplo.py`, or add a new module that uses
    `exemplo_tree.qualifying_scenarios` and skips when `DESSEM_DASHBOARD_EXEMPLO` / `exemplo/`
    yield fewer than two scenarios.
  - Dashboard-contract candidates:
    - zero warnings;
    - SIN has 8 sections in R13 order, and the UHE order matches R13;
    - each SIN flow chart has one entity and a `m3/s` unit;
    - each SIN flow chart's subtitle is the METADADOS long name;
    - payload SIN flow values equal the synthesized file values rounded to `output.decimals`, on
      the deck axis and on the chained window.
  - Synthesis-property candidates (dessem seat): `QDEF_SIN ≈ QTUR_SIN + QVER_SIN`, SIN ≈ Σ UHE.
    These check the synthesizer rather than the dashboard, so the council decides whether they
    belong here.
  - Constraints: avoid hard-coding example-specific numbers (169 plants, 80 stages) where a value
    measured from the files will do; keep the suite runnable in the chunked
    `tests/test_[a-l]*.py` / `tests/test_[m-z]*.py` invocation.
- **K2. Fixture METADADOS fidelity gap.** This is pre-existing, not required by this feature.
  `tests/fixtures_sintese.py::_metadados_operacao` writes `nome_longo_variavel = spec.title`, so
  the subtitle path is never exercised by fixture tests: on real data `QDEF_SIN` shows the subtitle
  `Vazão Defluente`, but in the fixture it shows none. It also writes rows for `CUSTO_*`/`TEMPO_*`
  keys that real METADADOS never has. The choice is to fix it as a structure-only ticket (which
  needs a new requirement and operator confirmation) or record it as debt.
- **K3. Manual checklist changes (R20, R24).**
  - Numbering scheme: renumber steps 1–N continuously, or insert sub-steps.
  - Placement of the SIN-flow and UHE-order steps (level navigation, modes, or Diferença section).
  - Whether the step-12 build command and the step-14 worked point keep the absent two-deck
    `exemplo/caso_oficial`/`caso_gurobi` pair or gain an `examples/Oficial`/`Modificado` variant.
    The `examples/` decks have one deck each, so the step-14 chained-axis arithmetic differs.
- **K4. Shape of the `_load_registries` fix (R27).**
  - Plumbing: thread `settings.submarkets.fictitious_codes` through `build_dashboard_data` →
    `_load_registries` → `load_registries`.
  - Default: drop the hard-coded `(11, 99)` signature default (a required keyword, which touches
    `test_registries.py` callers) or keep it. CLAUDE.md "never hard-code a tunable" argues for
    dropping it.
  - Regression test: a non-default fictitious set (for example only `99`) must change which SBM
    entities are visible, and the dropped-code warning set must stay consistent. This is a two-way
    door.
- **K5. `SPECS` and `FALLBACK_UNITS` layout symmetry (R13, R25).** Move `QDEF_SIN`/`QTUR_SIN`/
  `QVER_SIN` from the trailing disabled block into the enabled SIN block after `VARMF_SIN`, keeping
  the module docstring's "enabled first, then disabled" layout true (render order is identical
  either way, as measured). Regroup the three `FALLBACK_UNITS` entries under the enabled comment.
  Move the three keys between `test_schemas.py`'s `_ENABLED_CHART_KEYS` and `_DISABLED_CHART_KEYS`.
- **K6. Epic and ticket split.**
  - Expected epics: feature (enable + reorder + pins), bugfix (R27), docs/validation (R24, R28,
    R20).
  - Which ticket owns the R24 README edits, given that R28 touches the same file.
  - Ordering the two README tickets so they do not collide.

## Scope boundary

This artifact holds requirements, classification, roster and questions only. The master plan,
epics, decision records and `.implementation-state.json` belong to SYNTHESIS and the orchestrator.
No on-demand consult was issued during either intake revision, so `design/consults.md` was not
created.
