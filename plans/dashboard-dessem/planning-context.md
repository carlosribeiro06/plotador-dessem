# Planning Context — DESSEM Comparison Dashboard

Binding input for the implementation planner and for every implementer. Everything here was either
decided by the developer during the `/plan` clarification gates (2026-09-10) or verified directly
against the repository and the example data. Do not re-ask any item in "User decisions"; when a
ticket needs something that is not covered here, list it as an open question in the plan.

## Sources

| Item                  | Path                                                                                                   |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| Feature spec          | `plano_dashboard_dessem.md` (repo root)                                                                |
| Parquet schema dump   | `plans/dashboard-dessem/reference/parquet-schemas.txt` (all 60 files: dtypes, uniques, sample rows)   |
| Example data          | `exemplo/caso_{oficial,gurobi}/{2024-03-03,2024-03-04}/sintese/*.parquet` (rebuilt 2026-09-10, gitignored); `exemplo/sintese/` is a flat structure sample, not a scenario |
| Brand manual          | `UsoCorreto da Marca_VR_dezembro2018.pdf` (23 pages; facts extracted below)                            |
| Logo                  | `logo/MarcasONS_Secundarias_verticais_Verde.png` (786×622 RGBA, secondary vertical signature, green)  |
| Legacy code           | `Leitura/leitor_arquivos.py`, `Plotadores/*.py`, `main_*.py`                                            |
| Global rules          | `~/.claude/CLAUDE.md`, `~/.claude/rules/python.md`, `~/.claude/rules/markdown.md`                      |
| Scaffold template     | `~/.claude/skills/new-project/SKILL.md` (Epic 1 follows it; summary below)                             |

Repo root: `/home/carlosribeiro/git/plotador-dessem` (WSL Ubuntu). From the Windows-side Claude
session the same tree is `\\wsl.localhost\Ubuntu\home\carlosribeiro\git\plotador-dessem`; shell
commands that must run inside WSL go through `wsl.exe -e bash -lc '<cmd>'`.

## User decisions (binding)

1. **Rigor tier: Full** (`/plan` + `/implement-plan`). **Implementation mode: Rigoroso** — English
   identifiers, comments, docstrings, README, tests; minimal comments.
2. **Language of user-facing text: Portuguese** for CLI flags and `--help` (the spec fixes `--casos`),
   log messages, error messages shown to the operator, and every dashboard UI string. English for
   code, comments, documentation and test names.
3. **Scaffolding is Epic 1**, following the `/new-project` template (summary below) applied *in place*
   in the existing repo root (`--here` semantics): project name `dessem-dashboard`, package
   `dessem_dashboard`, `src/` layout, `settings.json` with validation, audit logging (rich console +
   rotating file), run manifest, `pyproject.toml`, `tests/`, project `CLAUDE.md`, project
   `.claude/settings.json`. Never overwrite the existing files (legacy scripts, `exemplo/`, `logo/`,
   PDF, `LICENSE`, the spec).
4. **Input layout.** `--casos <scenario_dir> [<scenario_dir> ...]`. Each argument is one comparison
   series ("cenário"); its legend label is the directory basename. The **immediate subdirectories** of
   a scenario dir that contain a `sintese/` subfolder are its decks. Deck folder names are free-form;
   deck date and ordering come from `EST.parquet` (minimum `data_inicio`), never from the folder name.
   A deck present in one scenario and absent in another → warn and leave a gap; a scenario dir with no
   deck → fail fast with a clear Portuguese error.

   ```text
   caso_oficial/                 <- legend: caso_oficial
   ├── 2024-03-03/  (or deck_20240303, any name)
   │   └── sintese/*.parquet
   └── 2024-03-04/
       └── sintese/*.parquet
   caso_gurobi/                  <- legend: caso_gurobi
   └── 2024-03-03/
       └── sintese/*.parquet
   ```

5. **Two view modes** in the dashboard, selectable by the user:
   - **Por deck** — a deck selector (by date); charts show that deck's full original horizon (all
     stages, original granularity: half-hour stages on day 1, 2–8 h stages afterwards).
   - **Encadeado** — from each deck only the first *N* stages (settings key
     `chaining.stages_per_deck`, default **48** = first day at half-hour resolution), concatenated in
     deck-date order with no date overlap. Validate contiguity (end of deck *k* window == start of deck
     *k+1*) and warn on gaps/overlaps.
   One curve per scenario in both modes. Scalar-per-deck tables (`CUSTOS`, `TEMPO`) become grouped bar
   charts by deck date, one bar per scenario, independent of the mode.
6. **Chart library: Plotly.js embedded inline**, taken from the installed Python `plotly` package via
   `plotly.offline.get_plotlyjs()` — no network access at build time or view time. Data is embedded as
   JSON inside the single HTML file; a hand-written JavaScript renderer builds each chart on demand
   from that data store (mode toggle, deck selector, level navigation, filters). Do not pre-render one
   Plotly figure per chart.
7. **Chart scope: the spec's minimum list + TEMPO** (computational time, as the legacy scripts plot).
   The design must be **registry-driven** (adding a chart or a new synthesis file = adding one registry
   entry), but only the minimum list + TEMPO are enabled by default. Spec → file mapping:

   | Level | Spec item                | Parquet            | Notes                                                     |
   | ----- | ------------------------ | ------------------ | --------------------------------------------------------- |
   | SIN   | Geração térmica          | `GTER_SIN`         |                                                           |
   | SIN   | Geração hidrelétrica     | `GHID_SIN`         |                                                           |
   | SIN   | Geração não simulada     | `GUNS_SIN`         |                                                           |
   | SIN   | Custo total/presente/futuro | `CUSTOS`        | bars per deck; total = sum of `costs.total_parcels` (default `["PRESENTE","FUTURO"]`, legacy parity) |
   | SIN   | EARMF                    | `EARMF_SIN`        | MWh                                                       |
   | SIN   | Volume armazenado        | `VARMF_SIN`        | hm3                                                       |
   | SBM   | Carga                    | `MER_SBM`          | "Mercado de Energia"; `MERL_SBM` is a disabled registry entry |
   | SBM   | Geração hidráulica       | `GHID_SBM`         |                                                           |
   | SBM   | Geração térmica          | `GTER_SBM`         |                                                           |
   | SBM   | Geração não simulada     | `GUNS_SBM`         |                                                           |
   | SBM   | CMO                      | `CMO_SBM`          | R$/MWh                                                    |
   | SBM   | Intercâmbios             | `INT_SBP`          | pairs `codigo_submercado_de → codigo_submercado_para`; pair selector |
   | SBM   | Volume armazenado        | `VARMF_SBM`        |                                                           |
   | UHE   | Geração                  | `GHID_UHE`         |                                                           |
   | UHE   | Turbinamento             | `QTUR_UHE`         | m3/s                                                      |
   | UHE   | Vertimento               | `QVER_UHE`         | m3/s                                                      |
   | UHE   | Volume armazenado        | `VARMF_UHE` (hm3) **and** `VARPF_UHE` (%) | spec is ambiguous; ship both, flag in plan |
   | UHE   | Defluência               | `QDEF_UHE`         | m3/s                                                      |
   | UHE   | Vazão                    | `QAFL_UHE` (afluente) **and** `QINC_UHE` (incremental) | spec is ambiguous; ship both, flag in plan |
   | UTE   | Geração                  | `GTER_UTE`         |                                                           |
   | —     | TEMPO                    | `TEMPO`            | bars per deck: MILP, PL group (`PL`+`PL.Int.Fix`+`PL.CalcCMO`), Leitura, total; minutes; grouping configurable |

8. **Difference view.** Every chart gets a toggle **Absoluto / Diferença**; difference =
   scenario − reference, computed in the browser from the embedded absolute series. Reference scenario
   = first `--casos` argument by default, overridable with `--referencia <nome>`.
9. **Filters (spec §3).** Plant-level views (UHE, UTE) expose two independent, combinable text filters:
   by name (`usina`) and by code (`codigo_usina`), BI-style incremental search over the registry
   embedded in the HTML. Submarket and interchange-pair views use selectors.
10. **Time axis (spec §4).** X axis shows date + time from `data_inicio`, formatted `%d/%m/%Y %H:%M`.
    The parquet timestamps are wall-clock stamps labeled UTC (00:00 is the start of the operating
    day) — display them **without timezone conversion**. The synthesis files already carry the
    timestamps; no data from the original decks is needed (spec §4's open question is closed).
11. **`.gitignore`.** Ignore `exemplo/`, `*.pdf`, `__pycache__/`, `*.py[cod]`, `.venv/`, tool caches,
    `*.egg-info/`, `logs/`, `output/`, and generated dashboard `*.html`. **Keep `logo/` and `*.md`
    versioned** (the spec's `logo/` / `*.md` suggestion was rejected). Untrack the already-committed
    `exemplo/**` parquet files and `**/__pycache__/**` with `git rm -r --cached` (files stay on disk).
    Commits and pushes follow decision 17 (post-planning, revised).
12. **Legacy removal** happens in the last epic, only after a parity check (see "Legacy behaviors").
13. **Visual identity** — see the dedicated section below. Footer text is mandatory and exact:
    `Gerência de Ferramentas Energéticas - FEN`.

## Data facts (verified on `exemplo/2024-03-03` and `exemplo/2024-03-04`)

- 60 parquet files per `sintese/`. Every **operation time series** file shares one long schema:
  `[entity keys] + estagio:int64, data_inicio:datetime64[ns, UTC], data_fim:datetime64[ns, UTC],
  cenario:int64 (=1), patamar:int64, duracao_patamar:float64 (hours), valor:float64,
  limite_inferior:float64, limite_superior:float64` (±inf when unbounded).
- Entity keys by aggregation level: **SIN** none; **SBM** `codigo_submercado`; **SBP**
  `codigo_submercado_de`, `codigo_submercado_para`; **UHE** `codigo_usina`, `codigo_ree`,
  `codigo_submercado`; **UTE** `codigo_usina`, `codigo_submercado`.
- Stages: deck 2024-03-03 has **68** stages, deck 2024-03-04 has **64**. Day 1 is 48 half-hour stages
  (00:00–23:30); later stages last 2, 6 or 8 h (`duracao_patamar`). Deck 03-03 stage 48 ends at
  2024-03-04 00:00 = deck 03-04 stage 1 start, so chaining the first 48 stages yields a contiguous
  half-hourly timeline.
- Registries: `UHE.parquet` (165 rows: `codigo_usina, codigo_ree, codigo_submercado, ree, submercado,
  usina`), `UTE.parquet` (89 rows: `codigo_usina, usina, codigo_submercado, submercado`),
  `SBM.parquet` (`codigo_submercado` **Int64**, `submercado`, `nome_submercado`; codes 1 SE/SUDESTE,
  2 S/SUL, 3 NE/NORDESTE, 4 N/NORTE, 11 FC/NOFICT1, 99 IV/NaN), `REE.parquet` (12 rows),
  `EST.parquet` (`estagio, data_inicio, data_fim`), `PAT.parquet`.
- Fictitious submarkets 11 and 99 appear in `CMO_SBM`, `MER_SBM`, `MERL_SBM`, `EARMF_SBM` and in
  `INT_SBP` pairs. Default: SBM-level charts show codes 1–4 (settings
  `submarkets.include_fictitious`, default false); interchange pairs keep every pair present, labelled
  with `submercado` short names.
- `METADADOS_OPERACAO.parquet` (40 rows): `chave, nome_curto_variavel, nome_longo_variavel,
  nome_curto_agregacao, nome_longo_agregacao, unidade, calculado, limitado`. Units seen: `MW, MWh,
  R$/MWh, hm3, m3/s, %, 10^3 R$, 10^6 R$`. `nome_*` is NaN for `VAGUA_UHE` and `VCALHA_UHE`. Use it
  for chart titles/units with a static fallback table.
- `CUSTOS.parquet`: `parcela ∈ {PRESENTE, FUTURO, VIOLACOES, PEQUENAS PENALIDADES}`, `valor_esperado`
  (R$), `desvio_padrao`. Legacy total = PRESENTE + FUTURO.
- `TEMPO.parquet`: `etapa ∈ {Leitura de Dados e Impressão, MILP, PL (several rows), PL.Int.Fix,
  PL.CalcCMO}`, `tempo` (seconds), `execucao`. Legacy divides by 60 and plots MILP, PL group, Leitura,
  total.
- `ESTATISTICAS_OPERACAO_*` files duplicate the same variables with `cenario='mean'` — ignore them.
- pandas 3.x reads text columns as the `str` dtype (not `object`); `SBM.codigo_submercado` is nullable
  `Int64`. Readers must be explicit about dtypes.
- **Volume estimate**: UHE-level files ≈ 11,220 rows per deck (165 plants × 68 stages). For 2
  scenarios × 2 decks the embedded plant-level data is ~0.4 M values (~3 MB JSON when rounded); 30
  decks × 3 scenarios would reach ~8 M values. The plan needs an explicit size strategy: round values
  (settings `output.decimals`, default 2), columnar arrays keyed by (chart, entity, scenario, deck),
  one shared time axis per deck, log the final HTML size and warn above a configurable threshold.

## Environment facts

- WSL Ubuntu: `/usr/bin/python3` = **Python 3.14.4**; `uv` at `/snap/bin/uv`; system Python has
  `rich` but **no pandas/pyarrow/plotly**. Use `uv` to create and manage `.venv` (`uv venv`,
  `uv pip install -e ".[dev]"`, or `uv sync` with a lock file).
- Windows Python 3.14.6 has pandas 3.0.5 / pyarrow 25.0.1 / plotly 6.9.0 (the legacy scripts ran
  there) — not the target runtime.
- Target: `requires-python = ">=3.12"`; runtime deps `pandas>=3.0`, `pyarrow`, `plotly>=6` (source of
  `plotly.min.js`), `rich`; dev deps `pytest`, `pytest-cov`, `ruff`, `mypy` (strict).
- Tests must not depend on `exemplo/` (gitignored): build synthetic parquet fixtures in `tmp_path`
  mirroring the schemas above; add an integration test that runs on `exemplo/` and is skipped when
  the folder is absent.
- git: branch `main`, clean tree, no `.gitignore`, no `pyproject.toml`; `exemplo/**` and
  `**/__pycache__/**` are tracked. Conventional-commit messages (`feat:`, `fix:`, ...).

## Visual identity facts (from the brand manual and the provided logo)

- Brand colors: only green and gray. Sampled from the provided logo: **green `#486018`** (symbol and
  "ONS"), **gray `#606060`** (descriptor). The manual's institutional-color page is image-only, so
  these sampled values are the authoritative substitutes. Never recolor the logo; use the file as-is.
- Auxiliary palette (manual p. 11): yellow `#FBC90B` (Pantone 123), orange `#F76C00` (Pantone 1585),
  red `#D10429` (Pantone 186), blue `#4F8AD8` (Pantone 279). Tints of 80/60/40/20 % are allowed. Use
  at most three auxiliary colors combined with the brand colors.
- Typography: brand fonts (Neutra) are not available; the manual mandates **Arial** for web/open
  documents. Left-aligned text, clear hierarchy, generous whitespace, sentence case (never more than
  five words in caps), italics only for foreign words.
- Logo usage: keep a protection area ≥ 0.5 cm equivalent around the logo (generous CSS padding); do
  not reduce below 50 %; the provided file is the secondary (vertical) signature — use it as given.
- Series palette proposal (planner may refine, but it must live in one theme module consumed by both
  CSS and the Plotly layout): reference scenario = brand green `#486018`; then blue `#4F8AD8`, orange
  `#F76C00`, red `#D10429`; a 5th+ scenario uses 60 % tints. Chart background white, light-gray grid,
  hovermode `x unified` (legacy look).
- Mandatory footer: `Gerência de Ferramentas Energéticas - FEN`.

## `/new-project` template summary (baseline for Epic 1)

Tree: `src/<pkg>/{__init__,config,logging_setup,manifest,cli}.py`, `tests/test_config.py`,
`settings.json`, `pyproject.toml`, `README.md`, `CLAUDE.md`, `.claude/settings.json`, `.gitignore`,
`logs/` and `output/` with `.gitkeep`. Behaviors: `config.py` loads and validates `settings.json`
(fail fast with a clear message, `ConfigError`), resolving relative paths against the settings file
location; `logging_setup.py` configures root logging once at the entry point with a `RichHandler`
console (plain `Formatter` fallback) plus a `RotatingFileHandler`; `manifest.py` writes
`run_manifest.json` (timestamp UTC, git sha, python/platform, params, data volumes, elapsed);
`pyproject.toml` with `[project.scripts]`, ruff line-length 100, mypy strict on `src`, pytest with
coverage. Adapt the settings schema to this project (e.g. `paths.output_dir`, `paths.log_dir`,
`paths.logo_file`, `logging.*`, `chaining.stages_per_deck`, `costs.total_parcels`,
`time.stage_groups`, `submarkets.include_fictitious`, `dashboard.title`, `dashboard.footer_text`,
`output.decimals`, `output.size_warning_mb`, `output.default_filename = "dashboard_dessem.html"`).
Rigoroso mode: strip template comments to the minimum and write them in English.

## Legacy behaviors to preserve (parity check before deletion)

- Line charts: `GHID_SIN`, `GTER_SIN`; `GHID_SBM`, `GTER_SBM`, `CMO_SBM` per submarket 1–4.
- Bars by deck date: `CUSTOS` (presente, futuro, total = presente + futuro); `TEMPO` (MILP, PL group,
  Leitura, total) in minutes.
- Look: white plot background, light-gray grid, Arial 12, `hovermode="x unified"`, x labels
  `%d/%m/%Y %H:%M`.
- Legacy chained the first 48 stages of each deck — exactly the default of the "Encadeado" mode.

## Suggested epic decomposition (planner may adjust; keep tickets ≤ ~30 min)

1. **Project foundation & repo hygiene** — scaffold (pyproject/uv, settings + validation, logging,
   manifest, tests skeleton), `.gitignore` + untracking, project `CLAUDE.md`, README skeleton.
2. **Data layer** — scenario/deck discovery, typed parquet readers with schema validation,
   registries (UHE/UTE/SBM/METADADOS), deck timeline (EST), per-deck and chained consolidation,
   in-memory data model and compact JSON export.
3. **Dashboard core** — theme module (brand colors, palette, fonts), HTML template with embedded
   Plotly.js and logo, JS renderer (mode toggle, deck selector, level navigation, abs/diff toggle),
   SIN and SBM charts including interchange pairs.
4. **Plant-level views & scalar charts** — UHE/UTE charts with name/code filters, CUSTOS and TEMPO
   bar charts, size strategy and warnings.
5. **CLI, end-to-end validation, docs, legacy removal** — `--casos/--saida/--referencia/--settings`,
   run on `exemplo/`, README per `rules/markdown.md`, parity check, delete legacy scripts.

## Open questions to carry into the plan (non-blocking; defaults stated)

- Cost total definition: default `PRESENTE + FUTURO` (legacy parity); `VIOLACOES` and
  `PEQUENAS PENALIDADES` configurable via `costs.total_parcels`.
- "Volume armazenado" and "Vazão" at UHE level ship both candidate variables (hm3 + %, afluente +
  incremental); the developer may disable one via the registry.
- X-axis type in "Por deck" mode: true datetime axis with step lines (`hv`) is recommended so 6–8 h
  stages render with their real duration; legacy used a categorical axis. Planner decides and records
  the rationale.

## Post-planning decisions (2026-09-10)

Taken by the developer after the planner delivered the plan; they close master plan open questions 4
and 5 and settle how the plan is handed over.

14. **The 240 `exemplo` worktree deletions are intentional.** The developer flattened `exemplo/` on
    purpose. ticket-001 stages the removals through `git rm -r --cached exemplo` (index only) and
    commits them together with `.gitignore`, then pushes. Nothing is restored or deleted from disk.
15. **Example scenario tree rebuilt from git history.** `git archive HEAD` extracted the four tracked
    `sintese/` folders into the decided scenario-first layout: `exemplo/caso_oficial/{2024-03-03,
    2024-03-04}/sintese` and `exemplo/caso_gurobi/{2024-03-03,2024-03-04}/sintese` (60 files each,
    blob hashes verified). `exemplo/sintese/` remains as a flat structure sample and is not a valid
    scenario. All of `exemplo/` is gitignored, so the tree is local; ticket-034 defaults to it,
    `DESSEM_DASHBOARD_EXEMPLO` overrides, and the test skips when neither exists. README example:
    `--casos exemplo/caso_oficial exemplo/caso_gurobi`.
16. **Execution strategy deferred.** The developer starts `/implement-plan` in a new chat with the
    prompt in `HANDOFF-PROMPT.md`; that session asks Phased (recommended) vs Continuous and records
    the answer in `.implementation-state.json` and `README.md`.
17. **Git discipline during execution (revised 2026-09-10).** The implementing session may commit
    and push: one conventional commit per completed ticket (after the guardian passes), message in
    Portuguese focused on the why, ending with
    `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` (amended 2026-09-10 at the
    start of `/implement-plan`: the executing session's attribution directive supersedes the
    `Claude Fable 5.1` line recorded during planning), pushed to `origin main`
    (`git@github.com:carlosribeiro06/plotador-dessem.git`). Never force-push; never `git add -A`
    before `.gitignore` exists; never commit `exemplo/` data, generated HTML, logs, `.venv`,
    `.claude/settings.local.json` or secrets. The first commit of the session lands the plan itself
    (`plans/`, `plano_dashboard_dessem.md`, `logo/`, added by explicit path).
