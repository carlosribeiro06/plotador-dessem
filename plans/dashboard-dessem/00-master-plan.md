# Master Plan: Dashboard HTML para Comparação de Resultados do DESSEM

> **Required reading for every implementer**, in this order:
>
> 1. `plans/dashboard-dessem/planning-context.md` — binding user decisions and verified data /
>    environment / brand facts. Never contradict it.
> 2. This file — architecture, decisions with rationale, and the data-model appendix.
> 3. `plans/dashboard-dessem/reference/parquet-schemas.txt` — raw dtype/unique/sample dump of all 60
>    synthesis files. Only needed when Appendix A below is not enough.
> 4. `~/.claude/rules/python.md` and `~/.claude/rules/markdown.md`.
>
> **Implementation mode: Rigoroso** — English identifiers, comments, docstrings, README and tests;
> minimal comments. **Rigor tier: full.** User-facing strings (CLI flags, `--help`, log and error
> messages, dashboard UI) are **Portuguese**; everything else is English.

## Executive Summary

Replace the loose legacy plotting scripts with a modular, typed, `settings.json`-driven Python
application (`dessem-dashboard`) that reads the DESSEM synthesis Parquet files of two or more study
scenarios and emits a **single self-contained HTML dashboard** (`dashboard_dessem.html`) with
interactive comparative charts at SIN / submarket / hydro-plant / thermal-plant level, plus per-deck
cost and computational-time bar charts. The dashboard works offline, carries the ONS visual identity,
and its chart catalogue is registry-driven so new charts and new synthesis files are added by
declaring one entry.

## Goals

1. Compare **one or more** scenarios simultaneously; one curve per scenario, legend = scenario
   directory basename.
2. Process the synthesis Parquet files of **all decks** found under each scenario, automatically.
3. Produce every chart in the spec minimum list, at every aggregation level present, plus `TEMPO`.
4. BI-style **independent and combinable** filters by plant name and plant code at plant level.
5. **Real date and time** X axis (`%d/%m/%Y %H:%M`), never the stage number.
6. Single HTML file, **no server and no network** at build time or view time.
7. ONS visual identity (brand green and gray, Arial, provided logo, mandatory FEN footer).
8. Modular, typed, tested code that is cheap to extend.

## Non-Goals

- No web server, no Dash / Streamlit / Panel runtime, no npm or bundler toolchain.
- No re-derivation of DESSEM results: the synthesis files are read-only inputs.
- No reading of the original decks. The synthesis files already carry the timestamps, so the open
  question in spec section 4 is closed (see `planning-context.md` decision 10).
- No `ESTATISTICAS_OPERACAO_*` files: they duplicate the same variables with `cenario='mean'`.
- No charts beyond the spec minimum list plus `TEMPO` **enabled by default**; the remaining
  variables ship as disabled registry entries.
- No deletion of the developer data on the plan own initiative. Commits and pushes are allowed:
  one conventional commit per completed ticket, pushed to `origin main` (planning-context
  decision 17, revised).

## Architecture Overview

### Current State

The repository root holds only loose legacy scripts: `Leitura/leitor_arquivos.py` (module-level
loops with a hard-coded Windows path and mutable module-level `defaultdict` state),
`Plotadores/*.py` (seven near-identical files, each duplicating the same Plotly layout and writing
one HTML per chart with `include_plotlyjs="cdn"`), and five `main_*.py` drivers that use star imports
and depend on import-time side effects. There is no `pyproject.toml`, no `src/`, no `settings.json`,
no tests and no `.gitignore`. The `exemplo/**` Parquet files and `**/__pycache__/**` are tracked in
git.

### Target State

```text
plotador-dessem/
├── pyproject.toml            # project metadata, ruff, mypy --strict, pytest
├── settings.json             # single configuration anchor (paths + all tunables)
├── CLAUDE.md                 # project rules (mode, config, logging)
├── README.md                 # English documentation per rules/markdown.md
├── .gitignore
├── logs/  output/            # runtime artifacts (gitignored, .gitkeep tracked)
├── logo/                     # provided ONS signature (versioned, never recolored)
├── src/dessem_dashboard/
│   ├── errors.py             # DashboardError hierarchy
│   ├── config.py             # settings.json load and validation
│   ├── logging_setup.py      # rich console + rotating file
│   ├── manifest.py           # run_manifest.json
│   ├── cli.py                # argparse: --casos/--saida/--referencia/--settings/...
│   ├── pipeline.py           # orchestration: discover -> consolidate -> build
│   ├── models/
│   │   ├── entities.py       # ScenarioRef, DeckRef, DeckTimeline, EntityRef
│   │   └── store.py          # DashboardData (columnar, JSON-ready)
│   ├── data/
│   │   ├── schemas.py        # column and dtype contracts, entity keys per level
│   │   ├── discovery.py      # scenario and deck discovery
│   │   ├── readers.py        # typed parquet readers with schema validation
│   │   ├── registries.py     # UHE/UTE/SBM/REE/METADADOS_OPERACAO
│   │   ├── timeline.py       # EST timeline, chaining window, contiguity checks
│   │   └── consolidate.py    # per-deck and chained assembly into DashboardData
│   ├── charts/
│   │   ├── registry.py       # ChartSpec and registry mechanics
│   │   └── specs.py          # declared chart catalogue (23 enabled)
│   └── dashboard/
│       ├── theme.py          # brand colors, palette, fonts, Plotly layout
│       ├── payload.py        # DashboardData -> compact embedded JSON
│       ├── builder.py        # assembles the single HTML file
│       └── assets/           # dashboard.css, dashboard.js (package data)
└── tests/                    # pytest, synthetic parquet fixtures in tmp_path
```

### Data Flow

```text
--casos DIR ...                       (CLI, Portuguese flags)
  -> discovery.discover_scenarios      ScenarioRef[] / DeckRef[]
  -> timeline.load_deck_timeline        per-deck stage table from EST.parquet
  -> timeline.align_deck_dates          union of deck dates plus gap warnings
  -> registries.load_registries         plant/submarket/REE names and units
  -> readers.read_series                one validated frame per (deck, ChartSpec)
  -> consolidate.build_dashboard_data   DashboardData: columnar arrays keyed by
                                        (chart, entity, scenario, deck), one time
                                        axis per deck plus one chained axis
  -> payload.build_payload              rounded compact JSON
  -> builder.build_html                 HTML + inline plotly.min.js + inline CSS/JS
                                        + base64 logo -> dashboard_dessem.html
  -> manifest.write_run_manifest        run_manifest.json (audit trail)
```

The browser holds the **absolute** series only. The renderer computes differences, applies filters,
switches view mode, changes deck and rebuilds figures on demand from that single data store.

## Key Design Decisions

Decisions 1 to 13 are the binding user decisions recorded in `planning-context.md` under "User
decisions". Decisions 14 to 19 are planner decisions that `planning-context.md` explicitly delegates,
each with its rationale.

| #  | Decision | Rationale |
| -- | -------- | --------- |
| 1  | Rigor tier full, mode Rigoroso | Code enters an official ONS process; the verification cost is justified. |
| 2  | Portuguese UI, CLI and log strings; English code and documentation | Operators read Portuguese; the code is publishable and transferable. |
| 3  | Scaffolding is Epic 1, `/new-project` template applied in place | The repository already exists; never overwrite legacy files, logo, PDF or LICENSE. |
| 4  | `--casos <cenario_dir> ...`; decks are the immediate subdirectories containing `sintese/`; deck date comes from `EST.parquet` | Folder names are free-form and unreliable; `EST.parquet` is authoritative. |
| 5  | Two view modes: "Por deck" (full original horizon) and "Encadeado" (first N stages per deck, default 48) | Matches how the results are analysed; 48 half-hour stages equals the legacy chained view. |
| 6  | Plotly.js **inlined** from the installed `plotly` package; hand-written JS renderer over one embedded JSON store | Offline requirement; pre-rendering one figure per chart per entity would explode the file size. |
| 7  | Chart scope is the spec minimum plus `TEMPO`, registry-driven, with about 19 extra variables shipped disabled | Extensibility requirement without shipping noise. |
| 8  | Absoluto / Diferença toggle computed in the browser; reference is the first `--casos` argument, overridable with `--referencia` | Halves the embedded payload versus shipping precomputed differences. |
| 9  | Plant views expose two independent combinable text filters (name, code) | Spec section 3. |
| 10 | Timestamps displayed **without timezone conversion**, formatted `%d/%m/%Y %H:%M` | The stamps are wall clock labeled UTC; `00:00` is the start of the operating day. |
| 11 | `.gitignore` ignores `exemplo/`, `*.pdf`, caches, `logs/`, `output/` and generated `*.html`, and **keeps** `logo/` and `*.md` | The spec suggestion to ignore `logo/` and `*.md` was rejected: both must stay versioned. |
| 12 | Legacy scripts are deleted only in Epic 5, after a parity check | Protects against silent behavior regressions. |
| 13 | Mandatory exact footer `Gerência de Ferramentas Energéticas - FEN` | Spec requirement. |
| 14 | **True datetime X axis with step interpolation** (`line_shape: "hv"`), not a categorical axis | In "Por deck" mode the stage durations vary (0.5, 2, 6 and 8 hours). A categorical axis gives an 8-hour stage the same width as a 30-minute stage, visually falsifying the horizon; a datetime axis with `hv` renders each stage as a constant value over its real duration and the tick labels are real timestamps as spec section 4 demands. Legacy used `type='category'`, so this is a deliberate documented improvement to be recorded in the Epic 5 parity check. |
| 15 | Series are keyed by `(entity keys, estagio)`; `patamar` and `duracao_patamar` are attributes, not dimensions | Verified: every operation file has exactly one row per (entity, stage). Readers assert this uniqueness so a future multi-`patamar` file fails loudly instead of silently averaging. |
| 16 | Entity lists are derived **per chart from its own file**, not from the full `UHE.parquet` registry | Coverage differs per variable (`GHID_UHE` 165 plants, `VARMF_UHE` 118, `VCALHA_UHE` non-rectangular). The registry supplies names only. |
| 17 | Consolidation pivots to arrays aligned on the deck axis and fills missing (entity, stage) with `null` | Coverage is not guaranteed rectangular; `null` keeps the browser code and the JSON shape uniform. |
| 18 | A missing file or a missing deck degrades to a **warning plus a gap**, never a crash; a scenario with zero decks is a **fatal** Portuguese error | Decision 4; a partially comparable dashboard is more useful than none. |
| 19 | Single agent chain: `python-task-automation-developer` for all code including the CSS and JS package assets, `open-source-documentation-writer` for documentation, `docker-linux-server-architect` for the git and shell hygiene ticket, `type-lint-guardian` at epic gates | The feature is single-domain Python data engineering plus static front-end assets. No formulation, solver, MPI, I/O-format or build-deploy domain is involved, so no multi-domain specialist chain applies. |

## Technical Approach

### Tech Stack

- Python `>=3.12` on WSL Ubuntu, with a `uv`-managed `.venv`. Runtime dependencies: `pandas>=3.0`,
  `pyarrow`, `plotly>=6` (used **only** as the source of `plotly.min.js`), `rich`.
- Development dependencies: `pytest`, `pytest-cov`, `ruff`, `mypy --strict`.
- Front end: hand-written ES2020 JavaScript and CSS, no framework, no build step, inlined into the
  output HTML.

### Testing Strategy

- Unit tests for every module, in `tests/test_<module>.py` mirroring `src/`.
- **No test may depend on `exemplo/`**, which is gitignored. `tests/fixtures_sintese.py` builds
  synthetic but schema-faithful `sintese/` directories in `tmp_path` (all 23 enabled source files
  plus the 7 registries), parameterised by stage count and entity sets.
- One end-to-end integration test in Epic 5 runs against a real scenario tree located via the
  `DESSEM_DASHBOARD_EXEMPLO` environment variable, falling back to the repository's `exemplo/caso_oficial` and `exemplo/caso_gurobi`, and is **skipped**
  when no valid tree is found.
- Numerical assertions use tolerances (`pytest.approx`, `numpy.testing.assert_allclose`).
- Quality gate at every epic boundary: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest --cov` with total coverage at or above 80 percent, raised to 85 percent in Epic 5.

### Output Size Strategy

Verified volumes: a UHE-level file holds about 11 220 rows per deck (165 plants times 68 stages).
Two scenarios times two decks embed about 0.4 M values, roughly 3 MB of JSON once rounded; 30 decks
times 3 scenarios would reach about 8 M values. Mandatory mitigations: columnar arrays keyed by
(chart, entity, scenario, deck); one shared time axis per deck plus one chained axis instead of a
timestamp per point; values rounded to `output.decimals` (default 2); absolute series only, with
differences computed in the browser; the final HTML size logged, and a warning emitted above
`output.size_warning_mb` (default 50).

## Epics

Progressive planning is active: **Epics 1 and 2 carry fully detailed tickets; Epics 3 to 5 carry
`[OUTLINE]` tickets** to be refined with the learnings of the earlier epics.

| Epic | Name | Tickets | Detail | Outcome |
| ---- | ---- | ------- | ------ | ------- |
| epic-01 | Project foundation and repo hygiene | 001-008 | detailed | Installable, typed, logged, configured and tested scaffold; git hygiene done. |
| epic-02 | Data layer | 009-018 | detailed | Discovery, typed readers, registries, timeline and chaining, chart registry, `DashboardData`. |
| epic-03 | Dashboard core | 019-026 | refined | Theme, JSON payload, single-file HTML shell, JS renderer, view modes, abs/diff toggle, SIN and SBM and interchange charts. |
| epic-04 | Plant-level and scalar charts | 027-032 | outline | UHE and UTE charts with name and code filters, `CUSTOS` and `TEMPO` bars, size enforcement. |
| epic-05 | Delivery, validation and legacy removal | 033-038 | outline | Pipeline wiring, end-to-end run, legacy parity check, documentation, legacy deletion. |

### Milestones

- **M1, end of epic-01** — `dessem-dashboard --casos <dir>` runs, validates `settings.json`, writes
  an audit log and `run_manifest.json`; `ruff`, `mypy --strict` and `pytest` are green.
- **M2, end of epic-02** — a scenario tree becomes a validated in-memory `DashboardData`, with
  per-deck and chained axes and explicit warnings, entirely under unit test.
- **M3, end of epic-03** — a single offline HTML with brand identity renders SIN and submarket
  charts for every scenario, with mode toggle, deck selector and abs/diff toggle.
- **M4, end of epic-04** — plant-level charts with working name and code filters plus the cost and
  time bar charts; output size measured and bounded.
- **M5, end of epic-05** — end-to-end run on real data, parity checked against the legacy charts,
  documented, legacy scripts removed.

## Risk Analysis

| Risk | Impact | Mitigation |
| ---- | ------ | ---------- |
| Embedded JSON grows beyond a usable HTML size with many decks and scenarios | High | Decisions 6 and 8 plus the size strategy above; log the size, warn above the threshold; ticket-032 owns enforcement. |
| `pandas 3.x` dtype surprises (`str` versus `object`, nullable `Int64`) | Medium | `data/schemas.py` declares dtypes explicitly, readers cast and validate, and fixtures are written with the same dtypes. |
| No `plotly` wheel for the chosen interpreter in WSL | Medium | ticket-002 pins `requires-python = ">=3.12"` and creates the venv with `uv venv --python 3.12`, with a documented fallback to the system 3.14 interpreter. |
| Non-rectangular entity and stage coverage silently drops data | Medium | Decisions 16 and 17: per-chart entity lists, `null` filling, and a unit test on a plant present in one file and absent from another. |
| The hand-written JS renderer becomes the untested corner of the project | Medium | The renderer is split into small tickets with explicit browser-checkable acceptance criteria, and the payload contract is unit tested on the Python side. |
| Brand compliance judged by eye | Low | `theme.py` is the single source of colors and fonts consumed by both the CSS and the Plotly layout, with values fixed in `planning-context.md`. |

## Success Metrics

1. `dessem-dashboard --casos caso_a caso_b` produces one `dashboard_dessem.html` that opens with no
   network access and no server.
2. All 23 enabled chart specs render for every scenario and every deck present.
3. The name and code filters locate a plant independently and in combination.
4. Every time-series X axis shows `dd/mm/yyyy hh:mm`.
5. `ruff check`, `ruff format --check` and `mypy src` are clean; `pytest` coverage is at or above
   85 percent.
6. Legacy `Leitura/`, `Plotadores/` and `main_*.py` are deleted after the parity check passes.
7. `run_manifest.json` records git sha, parameters, data volumes and elapsed time for every run.

## Open Questions

None of these blocks any epic. Items 1 to 3 carry a stated default and only need confirmation.
Items 4 and 5 were discovered while planning and were **resolved by the developer on 2026-09-10**;
the resolutions are recorded below and in `planning-context.md` ("Post-planning decisions").

1. **Cost total definition.** Default `costs.total_parcels = ["PRESENTE", "FUTURO"]` for legacy
   parity. `VIOLACOES` and `PEQUENAS PENALIDADES` are available and configurable. Affects
   ticket-030.
2. **UHE "Volume armazenado" ambiguity.** The plan ships both `VARMF_UHE` (hm3) and `VARPF_UHE`
   (percent); either can be disabled via `charts.disabled`. Affects ticket-011 and ticket-027.
3. **UHE "Vazão" ambiguity.** The plan ships both `QAFL_UHE` (afluente) and `QINC_UHE`
   (incremental); either can be disabled via `charts.disabled`. Affects ticket-011 and ticket-027.
4. **Resolved 2026-09-10 — the 240 `exemplo` worktree deletions are intentional.** The developer
   flattened `exemplo/` on purpose (the old date-first tree was only a sample of the Parquet
   structure). ticket-001 therefore runs `git rm -r --cached exemplo`, which leaves the 240 removals
   **staged**; the same ticket commits them together with `.gitignore` and pushes. Nothing is
   restored or deleted from disk. ticket-038 must still verify a clean tree before removing the legacy scripts.
5. **Resolved 2026-09-10 — the example scenario tree was rebuilt from git history.** The four
   `sintese/` folders tracked at `HEAD` (`exemplo/<data>/<caso>/sintese`, 2 dates × 2 scenarios) were
   extracted with `git archive HEAD` into the decided scenario-first layout:
   `exemplo/caso_oficial/2024-03-03/sintese`, `exemplo/caso_oficial/2024-03-04/sintese`,
   `exemplo/caso_gurobi/2024-03-03/sintese` and `exemplo/caso_gurobi/2024-03-04/sintese` (60 files
   each; blob hashes verified against `HEAD`). `exemplo/sintese/` stays as a flat structure sample.
   Everything under `exemplo/` is gitignored from ticket-001 on, so the tree exists only on the
   developer's machine: ticket-034 defaults to `exemplo/caso_oficial` + `exemplo/caso_gurobi`, still
   honours `DESSEM_DASHBOARD_EXEMPLO` as an override, and skips when neither is present. The README
   example command is `--casos exemplo/caso_oficial exemplo/caso_gurobi`.

## Appendix A: Data Model of the Synthesis Files

Verified against `exemplo/2024-03-03/caso_oficial/sintese` (60 files) and
`exemplo/2024-03-04/caso_oficial/sintese`. This appendix is sufficient for implementation; the raw
dump lives in `reference/parquet-schemas.txt`.

### A.1 The long operation-series schema

Every operation time-series file, 40 of the 60, shares one long schema: **the entity key columns
first, then these nine columns, in this order**.

| Column | dtype | Meaning |
| ------ | ----- | ------- |
| `estagio` | `int64` | 1-based stage index inside the deck |
| `data_inicio` | `datetime64[ns, UTC]` | stage start; wall clock labeled UTC, **never convert** |
| `data_fim` | `datetime64[ns, UTC]` | stage end |
| `cenario` | `int64` | always `1` in the operation files |
| `patamar` | `int64` | load-level label (`0`, `1`, `2`); **not** an extra dimension |
| `duracao_patamar` | `float64` | stage duration in hours (`0.5`, `2.0`, `6.0`, `8.0`) |
| `valor` | `float64` | the quantity, unit per `METADADOS_OPERACAO` |
| `limite_inferior` | `float64` | lower bound, `-inf` when unbounded |
| `limite_superior` | `float64` | upper bound, `+inf` when unbounded |

There is exactly **one row per (entity keys, `estagio`)**, per decision 15. Readers assert it.

### A.2 Entity keys per aggregation level

| Level | Key columns | Example file | Rows per deck |
| ----- | ----------- | ------------ | ------------- |
| `SIN` | none | `GHID_SIN` | 68, one per stage |
| `SBM` | `codigo_submercado` | `CMO_SBM` | 340 = 5 x 68 |
| `SBP` | `codigo_submercado_de`, `codigo_submercado_para` | `INT_SBP` | 816 = 12 pairs x 68 |
| `UHE` | `codigo_usina`, `codigo_ree`, `codigo_submercado` | `GHID_UHE` | 11 220 = 165 x 68 |
| `UTE` | `codigo_usina`, `codigo_submercado` | `GTER_UTE` | 6 052 = 89 x 68 |

**Coverage is per variable, not per level**, per decision 16. `GHID_UHE`, `QTUR_UHE`, `QVER_UHE`,
`QDEF_UHE`, `QAFL_UHE` and `QINC_UHE` cover 165 plants; `VARMF_UHE` and `VARPF_UHE` cover 118, the
reservoir plants only; `VCALHA_UHE` has 7 616 rows over 92 plants, which is **not** a plant times
stage product. Consolidation must pivot by (entity, stage) and fill gaps with `null`, per
decision 17.

### A.3 Stages and the time axis

- Deck `2024-03-03` has **68** stages. Deck `2024-03-04` has **64** stages.
- Stages 1 to 48 are half-hourly and cover the first operating day, `00:00` to `23:30`; later stages
  last 2, 6 or 8 hours.
- Deck `2024-03-03` stage 48 ends at `2024-03-04 00:00`, which is the start of deck `2024-03-04`
  stage 1, so chaining the first 48 stages of consecutive decks yields a contiguous half-hourly
  timeline. This is the default of the "Encadeado" mode, `chaining.stages_per_deck = 48`.
- `EST.parquet` with columns `estagio`, `data_inicio` and `data_fim` is the authoritative timeline;
  the **deck date is `min(data_inicio).date()`**, never the folder name.
- `PAT.parquet` with columns `data_inicio`, `estagio`, `patamar` and `valor` restates the durations
  and is not required.

### A.4 Registries

| File | Rows | Columns | Notes |
| ---- | ---- | ------- | ----- |
| `UHE.parquet` | 165 | `codigo_usina:int64`, `codigo_ree:int64`, `codigo_submercado:int64`, `ree:str`, `submercado:str`, `usina:str` | plant names for the name filter |
| `UTE.parquet` | 89 | `codigo_usina:int64`, `usina:str`, `codigo_submercado:int64`, `submercado:str` | |
| `SBM.parquet` | 6 | `codigo_submercado:Int64` (nullable), `submercado:str`, `nome_submercado:str` | 1 SE/SUDESTE, 2 S/SUL, 3 NE/NORDESTE, 4 N/NORTE, 11 FC/NOFICT1, 99 IV with **NaN** long name |
| `REE.parquet` | 12 | `codigo_ree:int64`, `ree:str` | SUDESTE, SUL, NORDESTE and others |
| `EST.parquet` | 68 | `estagio:int64`, `data_inicio`, `data_fim` | deck timeline |
| `PAT.parquet` | 68 | `data_inicio`, `estagio:int64`, `patamar:int64`, `valor:float64` | durations |
| `METADADOS_OPERACAO.parquet` | 40 | `chave`, `nome_curto_variavel`, `nome_longo_variavel`, `nome_curto_agregacao`, `nome_longo_agregacao`, `unidade`, `calculado:bool`, `limitado:bool` | titles and units; `nome_*` is NaN for `VAGUA_UHE` and `VCALHA_UHE`, so use `FALLBACK_UNITS` |
| `METADADOS_SISTEMA.parquet` | 7 | `chave`, `nome_curto`, `nome_longo` | registry catalogue |
| `METADADOS_EXECUCAO.parquet` | 5 | `chave`, `nome_curto`, `nome_longo` | `CUSTOS`, `TEMPO`, `PROGRAMA`, `TITULO`, `VERSAO` |
| `TITULO`, `VERSAO`, `PROGRAMA` | 1 | single string column | study title, model version, `DESSEM` |

Units seen in `METADADOS_OPERACAO.unidade`: `MW`, `MWh`, `R$/MWh`, `hm3`, `m3/s`, `%`, `10^3 R$` and
`10^6 R$`.

**Fictitious submarkets 11 and 99** appear in `CMO_SBM`, `MER_SBM`, `MERL_SBM`, `EARMF_SBM` and in
`INT_SBP` pairs. The default `submarkets.include_fictitious = false` hides codes 11 and 99 from
submarket charts; interchange pairs keep every pair present, labeled with the `submercado` short
names.

### A.5 Scalar-per-deck files

| File | Shape | Columns | Handling |
| ---- | ----- | ------- | -------- |
| `CUSTOS.parquet` | (4, 3) | `parcela:str`, `valor_esperado:float64` in R$, `desvio_padrao:int64` | `parcela` is one of `PRESENTE`, `FUTURO`, `VIOLACOES`, `PEQUENAS PENALIDADES`; grouped bars by deck date; total is the sum of `costs.total_parcels`, default `PRESENTE` plus `FUTURO` |
| `TEMPO.parquet` | (9, 3) | `etapa:str`, `tempo:float64` in seconds, `execucao:int64` | `etapa` is one of `Leitura de Dados e Impressão`, `MILP`, `PL` (several rows), `PL.Int.Fix`, `PL.CalcCMO`; groups come from `time.stage_groups`, default `MILP`, `PL` as `PL` plus `PL.Int.Fix` plus `PL.CalcCMO`, and `Leitura`, plus a total; **divide by 60** to plot minutes |

### A.6 Chart catalogue: spec item to source file

23 specs are enabled by default. `group` drives dashboard navigation and `selector` drives the UI
control.

| # | Group | Spec item | Key and source file | Unit | Selector |
| - | ----- | --------- | ------------------- | ---- | -------- |
| 1 | SIN | Geração térmica | `GTER_SIN` | MW | none |
| 2 | SIN | Geração hidrelétrica | `GHID_SIN` | MW | none |
| 3 | SIN | Geração não simulada | `GUNS_SIN` | MW | none |
| 4 | SIN | EARMF | `EARMF_SIN` | MWh | none |
| 5 | SIN | Volume armazenado | `VARMF_SIN` | hm3 | none |
| 6 | SBM | Carga (Mercado de Energia) | `MER_SBM` | MW | submarket |
| 7 | SBM | Geração hidráulica | `GHID_SBM` | MW | submarket |
| 8 | SBM | Geração térmica | `GTER_SBM` | MW | submarket |
| 9 | SBM | Geração não simulada | `GUNS_SBM` | MW | submarket |
| 10 | SBM | CMO | `CMO_SBM` | R$/MWh | submarket |
| 11 | SBM | Volume armazenado | `VARMF_SBM` | hm3 | submarket |
| 12 | SBP | Intercâmbios | `INT_SBP` | MW | submarket pair |
| 13 | UHE | Geração | `GHID_UHE` | MW | hydro plant |
| 14 | UHE | Turbinamento | `QTUR_UHE` | m3/s | hydro plant |
| 15 | UHE | Vertimento | `QVER_UHE` | m3/s | hydro plant |
| 16 | UHE | Volume armazenado (hm3) | `VARMF_UHE` | hm3 | hydro plant |
| 17 | UHE | Volume armazenado (percent) | `VARPF_UHE` | % | hydro plant |
| 18 | UHE | Defluência | `QDEF_UHE` | m3/s | hydro plant |
| 19 | UHE | Vazão afluente | `QAFL_UHE` | m3/s | hydro plant |
| 20 | UHE | Vazão incremental | `QINC_UHE` | m3/s | hydro plant |
| 21 | UTE | Geração | `GTER_UTE` | MW | thermal plant |
| 22 | EXECUCAO | Custo presente, futuro e total | `CUSTOS` | R$ | none, bars by deck |
| 23 | EXECUCAO | Tempo computacional | `TEMPO` | min | none, bars by deck |

Shipped **disabled** as registry entries only, enabled by editing `charts.disabled` or the spec:
`MER_SIN`, `MERL_SBM`, `MERL_SIN`, `GUNSD_SIN`, `GUNSD_SBM`, `EARMF_SBM`, `VARMI_SIN`, `VARMI_SBM`,
`VARMI_UHE`, `VARPI_UHE`, `VAGUA_UHE`, `VCALHA_UHE`, `CFU_SIN`, `COP_SIN`, `CUNS_SIN`, `CUNS_SBM`,
`QDEF_SIN`, `QTUR_SIN`, `QVER_SIN`.

Never read: `ESTATISTICAS_OPERACAO_{SIN,SBM,SBP,UHE,UTE}`, which repeat the same variables with
`cenario='mean'`, and `CVU`, which is a thermal cost input rather than a result.

### A.7 Legacy behaviors to preserve, checked in Epic 5

- Line charts: `GHID_SIN` and `GTER_SIN`; `GHID_SBM`, `GTER_SBM` and `CMO_SBM` for submarkets 1
  to 4.
- Bars by deck date: `CUSTOS` with presente, futuro and total as presente plus futuro; `TEMPO` with
  MILP, the PL group, Leitura and total, **in minutes**.
- Look: white plot background, light-gray grid, Arial 12, `hovermode="x unified"`, and x tick format
  `%d/%m/%Y %H:%M`.
- Legacy chained the first 48 stages of each deck, which is exactly the default "Encadeado" mode.
- Known intentional divergence: a datetime axis instead of `type='category'`, per decision 14.

## Appendix B: `settings.json` contract

Single configuration anchor. Relative paths resolve against the directory of the settings file
itself.

| Key | Default | Meaning |
| --- | ------- | ------- |
| `project` | `"dessem-dashboard"` | project label used in logs and in the manifest |
| `paths.output_dir` | `"output"` | destination of the HTML and of `run_manifest.json` |
| `paths.log_dir` | `"logs"` | log directory |
| `paths.logo_file` | `"logo/MarcasONS_Secundarias_verticais_Verde.png"` | ONS signature embedded in the header |
| `logging.level` | `"INFO"` | root log level |
| `logging.file` | `"logs/dashboard.log"` | rotating log file |
| `logging.rotate_max_bytes` | `5242880` | rotation size in bytes |
| `logging.rotate_backups` | `5` | number of kept backups |
| `logging.use_rich` | `true` | rich console handler, with plain `Formatter` fallback |
| `discovery.sintese_dirname` | `"sintese"` | name of the synthesis subfolder that marks a deck |
| `chaining.stages_per_deck` | `48` | stages taken from each deck in "Encadeado" mode |
| `costs.total_parcels` | `["PRESENTE","FUTURO"]` | parcels summed into the total cost |
| `time.stage_groups` | `{"MILP":["MILP"],"PL":["PL","PL.Int.Fix","PL.CalcCMO"],"Leitura":["Leitura de Dados e Impressão"]}` | `TEMPO` groupings |
| `time.unit_divisor` | `60.0` | seconds to minutes |
| `submarkets.include_fictitious` | `false` | show codes 11 and 99 in submarket charts |
| `submarkets.fictitious_codes` | `[11, 99]` | codes considered fictitious |
| `dashboard.title` | `"Comparação de Resultados do DESSEM"` | HTML title and header |
| `dashboard.footer_text` | `"Gerência de Ferramentas Energéticas - FEN"` | mandatory footer, exact |
| `dashboard.date_format` | `"%d/%m/%Y %H:%M"` | X axis tick and hover format |
| `output.default_filename` | `"dashboard_dessem.html"` | output name when `--saida` is omitted |
| `output.decimals` | `2` | rounding of the embedded values |
| `output.size_warning_mb` | `50` | warn above this HTML size |
| `charts.disabled` | `[]` | chart keys excluded from this run |
