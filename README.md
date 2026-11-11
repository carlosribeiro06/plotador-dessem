# dessem-dashboard

## What it is

`dessem-dashboard` compares the results of two or more DESSEM study scenarios and emits a single
self-contained, offline HTML file with interactive comparative charts at the SIN / submarket /
interchange-pair / hydro-plant / thermal-plant / execution levels. A "scenario" is a directory
passed via `--casos`; each of its immediate subdirectories that contains a `sintese/` folder is a
"deck" (one DESSEM run), and the deck date comes from `EST.parquet`, never from the folder name.
The dashboard offers two view modes — **Por deck** (each deck's full original horizon) and
**Encadeado** (the first *N* stages of each deck chained end to end, default 48 half-hour stages,
`chaining.stages_per_deck`) — because that mirrors how the legacy scripts and the developer already
analyse chained results.

## Requirements

- Python `>=3.12`.
- [`uv`](https://docs.astral.sh/uv/) to create and manage the virtual environment.
- Runtime dependencies (declared in `pyproject.toml`): `pandas>=3.0`, `pyarrow>=17`, `plotly>=6`
  (used only as the source of the embedded `plotly.min.js`), `rich>=13`.
- Development dependencies: `pytest>=8`, `pytest-cov>=5`, `ruff>=0.6`, `mypy>=1.11`,
  `pandas-stubs>=3.0`, `numpy>=2.0` (used by the test fixtures, not by the shipped program).
- Target platform: WSL Ubuntu or a Linux server. The system Python is not used directly; `uv`
  manages an isolated `.venv`.

## Configuration

Every path, filename and tunable parameter is read from `settings.json` at the repository root
(`dessem_dashboard.config.load_settings`); nothing is hard-coded. The tool always reads that file
(`dessem_dashboard.config.DEFAULT_SETTINGS_FILE`), whatever folder it runs from, so neither
`settings.json` nor `logo/` is ever copied into a study folder; `--settings` overrides it
explicitly. Relative paths inside `settings.json` resolve as follows:

- `paths.output_dir` against **the working directory**, so each study folder the tool runs from
  receives its own dashboard and `run_manifest.json`;
- `paths.log_dir` and `logging.file` against **the settings file's own directory**, so the logs of
  every run land together in the repository's `logs/`;
- `paths.logo_file` against **the repository root**, because the logo is a versioned asset of the
  repository and not an output of a run.

The repository root is derived from the installed package's location
(`<root>/src/dessem_dashboard/`), so it requires the documented editable install from a checkout.
Absolute paths are used as-is. Loading fails fast with a Portuguese `ConfigError` message when a
required key is missing or has the wrong JSON type. The tables below list every one of the 23 leaf
keys with its shipped default and meaning, grouped exactly as `settings.json` groups them; a short
paragraph follows the table for the four keys an operator is actually expected to change.

### General

| Key | Default | Meaning |
| --- | --- | --- |
| `project` | `"dessem-dashboard"` | Validated at load time (must be a string), but **read by no module**: no consumer of this key exists under `src/` (`grep -rn "project" src/` matches only the `Settings` dataclass field and the loader call in `config.py`). Neither the log lines nor `run_manifest.json` carry a project label: `manifest.write_run_manifest` writes exactly the ten fields enumerated in [What a run produces](#what-a-run-produces) below, none of them `project`. Changing this value has no observable effect. |

### Paths

| Key | Default | Meaning |
| --- | --- | --- |
| `paths.output_dir` | `"output"` | Destination of the dashboard HTML and of `run_manifest.json`. A relative value resolves against the **working directory** the tool runs from, not against the settings file's directory. |
| `paths.log_dir` | `"logs"` | Validated at load time (must resolve to a path), but **read by no module**: no consumer of this key exists under `src/` (`grep -rn "log_dir" src/` matches only the `Paths` dataclass field and the loader in `config.py`). The rotating log file's actual location is `logging.file`, which already carries a full path and whose parent directory `logging_setup.setup_logging` creates itself. Changing `paths.log_dir` alone has no observable effect; change `logging.file` instead. |
| `paths.logo_file` | `"logo/MarcasONS_Secundarias_verticais_Verde.png"` | ONS logo file, embedded as a base64 `data:` URI in the dashboard header. A relative value resolves against the **repository root**, not against the settings file's directory. This is a **hard requirement**: `dashboard.builder._logo_data_uri` raises `ConfigError` naming `paths.logo_file` and the resolved absolute path when the file is missing, or when its suffix is not one of `.png`, `.jpg`, `.jpeg` or `.svg`. A missing *data* file (a scenario's Parquet) degrades to a warning; a missing logo does not, because the ONS visual identity is a project goal. |

### Logging

| Key | Default | Meaning |
| --- | --- | --- |
| `logging.level` | `"INFO"` | Root log level (`DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`). |
| `logging.file` | `"logs/dashboard.log"` | Rotating log file path; the effective log location (see `paths.log_dir` above). |
| `logging.rotate_max_bytes` | `5242880` | Rotation size in bytes (5 MiB). |
| `logging.rotate_backups` | `5` | Number of rotated backups kept. |
| `logging.use_rich` | `true` | Use a `RichHandler` console; falls back to a plain `Formatter` when `rich` is not importable. |

### Discovery

| Key | Default | Meaning |
| --- | --- | --- |
| `discovery.sintese_dirname` | `"sintese"` | Name of the subfolder that marks a deck directory. |

### Chaining

| Key | Default | Meaning |
| --- | --- | --- |
| `chaining.stages_per_deck` | `48` | Stages taken from the start of each deck to build the **Encadeado** chained axis. |

`chaining.stages_per_deck` must be `>= 1` (`ConfigError` otherwise). It bounds
`data.timeline.chaining_window`, which every deck's chained segment is built from; a deck with
fewer stages than this value contributes a shorter window and `data.timeline.validate_chaining`
emits a Portuguese warning naming the deck date and the stage shortfall, rather than failing the
run. The default of 48 half-hour stages covers exactly one operating day, so consecutive decks
chain with no gap when their windows are contiguous.

### Costs

| Key | Default | Meaning |
| --- | --- | --- |
| `costs.total_parcels` | `["PRESENTE", "FUTURO"]` | `CUSTOS.parquet` parcels summed into the `TOTAL` bar of the `Custo Presente, Futuro e Total` chart. |

`costs.total_parcels` may name any subset of `CUSTOS.parquet`'s `parcela` values (also
`VIOLACOES` and `PEQUENAS PENALIDADES` exist in the file but are not summed by default); it must
not contain a parcel literally named `TOTAL`, since that name is reserved for the computed series
(`ConfigError` naming `costs.total_parcels` otherwise). A configured parcel absent from a scenario's
data is a Portuguese `logger.warning` naming the parcel and the key, and that parcel — never a
partial sum — is omitted from both the chart and the total for that (scenario, deck) cell.

### Time

| Key | Default | Meaning |
| --- | --- | --- |
| `time.stage_groups` | see below | `TEMPO.parquet` `etapa` groupings displayed as bars in the `Tempo Computacional` chart. |
| `time.unit_divisor` | `60.0` | Divisor applied once to convert `TEMPO.parquet`'s raw seconds into the chart's `min` axis. |

The default `time.stage_groups` value is a JSON object mapping a group label to the list of
`TEMPO.parquet` `etapa` values it aggregates:

```json
{
  "MILP": ["MILP"],
  "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
  "Leitura": ["Leitura de Dados e Impressão"]
}
```

Like `costs.total_parcels`, no group in `time.stage_groups` may be named `TOTAL`
(`ConfigError` naming `time.stage_groups`). A configured group whose members are all absent from
the data is a warning naming the group and the key, omitted entirely; an `etapa` present in the
data but covered by no configured group is a separate warning naming the `etapa` and the key,
contributing to no bar and no total. `time.unit_divisor` is applied exactly once, in
`dashboard.scalars.aggregate_times` (`grep -rln "unit_divisor" src/` names only `config.py` and
that one module); every other layer keeps `TEMPO.parquet`'s values in **seconds**. The `min` axis
label itself is not derived from this setting — it is hard-coded in `data.schemas.FALLBACK_UNITS`
— so setting `time.unit_divisor` to anything other than `60.0` makes the axis label and the
displayed values disagree; `dashboard.scalars.aggregate_times` detects exactly that case and emits
one Portuguese `logger.warning` naming the `min` label and the configured divisor.

### Submarkets

| Key | Default | Meaning |
| --- | --- | --- |
| `submarkets.include_fictitious` | `false` | Show fictitious submarket codes in submarket charts. |
| `submarkets.fictitious_codes` | `[11, 99]` | Codes treated as fictitious submarkets. |

### Dashboard

| Key | Default | Meaning |
| --- | --- | --- |
| `dashboard.title` | `"Comparação de Resultados do DESSEM"` | HTML `<title>` and header text. |
| `dashboard.footer_text` | `"Gerência de Ferramentas Energéticas - FEN"` | Mandatory footer. |
| `dashboard.date_format` | `"%d/%m/%Y %H:%M"` | X-axis tick and hover timestamp format for every line chart. |

### Output

| Key | Default | Meaning |
| --- | --- | --- |
| `output.default_filename` | `"dashboard_dessem.html"` | Output name when `--saida` is omitted. |
| `output.decimals` | `2` | Decimal rounding applied to every embedded chart value, including `Diferença` values computed client-side. |
| `output.size_warning_mb` | `50` | Warn (log only, the run still completes) when the generated HTML exceeds this size, in MB. |

### Charts

| Key | Default | Meaning |
| --- | --- | --- |
| `charts.disabled` | `[]` | Chart registry keys excluded from a given run. |

`charts.disabled` names zero or more of the 47 declared `ChartSpec` keys (see
[Extending the chart catalogue](#extending-the-chart-catalogue) below for the full catalogue).
Naming a key the registry never registered raises `RegistryError` naming the unknown key
(`charts.registry.ChartRegistry.enabled_specs`); naming every currently-enabled key leaves nothing
to render, and `dashboard.builder.build_html` raises `ConfigError` naming `charts.disabled` rather
than let `_level_nav`/`_chart_sections` fail on an empty catalogue with a bare `IndexError`. Use it
to hide a shipped-but-uninteresting chart. It can only remove keys from the enabled set, so it
cannot enable any of the 16 charts shipped disabled: enabling one means editing the catalogue, as
described in [Enabling an already-declared chart](#enabling-an-already-declared-chart).

## How to run

The commands below run inside WSL Ubuntu (or a Linux server). Set up the environment once, from
the repository root.

Create the virtual environment and activate it:

```bash
uv venv
source .venv/bin/activate
```

Install the project in editable mode, with development dependencies:

```bash
uv pip install -e ".[dev]"
```

Run the tool against two scenario directories, each holding one or more decks (each deck a
subdirectory with its own `sintese/` folder):

```bash
dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi
```

The tool runs from any folder: it always reads the repository's `settings.json` and `logo/`, and
writes the dashboard to `output/` inside the folder it runs from. From a study folder holding
only its scenario directories:

```bash
cd ~/estudos/semana-45
dessem-dashboard --casos caso_oficial caso_gurobi
# -> ~/estudos/semana-45/output/dashboard_dessem.html
```

### Command-line flags

All flags and help text are Portuguese, by binding decision. `dessem-dashboard --help` prints:

```text
usage: dessem-dashboard [-h] --casos DIRETORIO [DIRETORIO ...]
                        [--saida ARQUIVO] [--referencia NOME]
                        [--settings ARQUIVO] [--modo-inicial {deck,encadeado}]
                        [--nivel-log {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

Gera um dashboard HTML comparando resultados de simulações do DESSEM entre
cenários.

options:
  -h, --help            show this help message and exit
  --casos DIRETORIO [DIRETORIO ...]
                        Diretórios de cenário a comparar; o rótulo de cada
                        cenário na legenda é o nome do diretório.
  --saida ARQUIVO       Arquivo HTML de saída. Padrão:
                        paths.output_dir/output.default_filename definidos em
                        settings.json, com paths.output_dir relativo ao
                        diretório de execução.
  --referencia NOME     Nome do cenário de referência usado na visão de
                        diferença. Padrão: nome do primeiro diretório
                        informado em --casos.
  --settings ARQUIVO    Arquivo de configuração do projeto. Padrão:
                        settings.json na raiz do repositório, qualquer que
                        seja o diretório de execução.
  --modo-inicial {deck,encadeado}
                        Modo de visão pré-selecionado no dashboard. Padrão:
                        encadeado.
  --nivel-log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Nível de log, sobrepondo logging.level definido em
                        settings.json.

Exemplo de uso:

  dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi

O primeiro diretório informado em --casos é o cenário de referência da
visão de diferença, a menos que --referencia indique outro nome.
settings.json é a fonte de todo caminho e todo parâmetro ajustável do
programa.
```

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--casos` | yes | — | Scenario directories; legend label is each directory's basename. Two directories sharing a basename is a fatal error naming the duplicate. |
| `--saida` | no | `paths.output_dir/output.default_filename` | Output HTML file path; by default under `output/` in the folder the tool runs from. |
| `--referencia` | no | First `--casos` basename | Reference scenario for the `Diferença` view; must name one of the `--casos` labels. |
| `--settings` | no | Repository's `settings.json` | Path to the project configuration file; the default ignores the working directory. |
| `--modo-inicial` | no | `encadeado` | Dashboard view mode pre-selected on load: `deck` or `encadeado`. Also decides whether the `Deck` selector starts `disabled` (it does, exactly when the initial mode is `encadeado`). |
| `--nivel-log` | no | `logging.level` | Overrides the log level for this run only; never written back to `settings.json`. |

### What a run produces

A run writes exactly three things: the self-contained dashboard HTML at `--saida` (default
`paths.output_dir/output.default_filename`), a `run_manifest.json` inside `paths.output_dir`,
and the rotating log file at `logging.file`. The dashboard embeds every value
it needs — Plotly.js, the theme, the renderer script and the JSON data payload — so no other file
is required to view it, and no network access is used at build time or view time.

On success, and only on success, `dessem-dashboard` also prints the resolved `--saida` path to
**stdout** as its one and only line — no label, no prefix, nothing else — so a caller can capture
it directly, for example `saida=$(dessem-dashboard --casos ...)` or
`dessem-dashboard --casos ... > /dev/null` to discard everything but the exit code. Every failure
path (a `DashboardError` from the pipeline, a malformed `settings.json`, or an argparse/
configuration error such as a duplicate `--casos` basename or an unknown `--referencia`) leaves
stdout empty; all diagnostics, progress and the per-warning lines described in
[Logging and auditing](#logging-and-auditing) below go through `logging` instead, never stdout.

`run_manifest.json` (`dessem_dashboard.manifest.write_run_manifest`) carries ten top-level fields:
`timestamp_utc`, `git_sha` (the 40-character commit sha of the installed package's checkout, or
`null` outside a git checkout), `git_dirty` (boolean, or `null` alongside a `null` `git_sha`),
`python` (interpreter version), `platform`, `package_version`, `params` (the resolved CLI
parameters — `casos`, `saida`, `referencia`, `settings`, `modo_inicial`, `nivel_log`),
`data_volumes`, `warnings` (the same warning list the dashboard's own `Avisos` section renders —
see [Reading the dashboard](#reading-the-dashboard) below) and `elapsed_seconds`. `data_volumes`
itself has six integer keys, in order: `cenarios`, `decks`, `graficos` (the number of enabled
charts actually rendered), `valores` (total stored series values plus scalars), `bytes_html` and
`bytes_plotly` (the size of the inlined Plotly bundle, memoised per process since it depends only
on the installed `plotly` version).

## Reading the dashboard

The document has one fixed layout, in this order: a header with the ONS logo and
`dashboard.title`; a level navigation bar; a control row; an optional `Avisos` section; one chart
section per enabled chart of the currently active level; and a mandatory footer. As plain text
(built from the DOM contract in `dashboard/builder.py` and `dashboard/assets/dashboard.html`,
never from a screenshot — see the note at the end of this section):

```text
┌──────────────────────────────────────────────────────────────────┐
│ [logo]  Comparação de Resultados do DESSEM                        │  <- header
├──────────────────────────────────────────────────────────────────┤
│ [SIN] [Submercado] [Intercâmbio] [Usinas hidrelétricas]            │  <- level-nav
│ [Usinas termelétricas] [Execução]                                  │
├──────────────────────────────────────────────────────────────────┤
│ [Por deck] [Encadeado]   Deck: [ 03/03/2024 v ]                    │  <- controls
│ [Absoluto] [Diferença]   Referência: caso_oficial                  │
├──────────────────────────────────────────────────────────────────┤
│ Avisos                                                              │  <- optional
│  - <one Portuguese warning message per line>                       │
├──────────────────────────────────────────────────────────────────┤
│ Geração Térmica                                                     │  <- one <section>
│ [optional subtitle from METADADOS_OPERACAO]                        │     per enabled
│ [optional entity <select>] [optional Nome/Código filters]          │     chart of the
│ [ plot ]                                                             │     active level
├──────────────────────────────────────────────────────────────────┤
│ ... one further section per remaining enabled chart of the level   │
├──────────────────────────────────────────────────────────────────┤
│ Gerência de Ferramentas Energéticas - FEN                          │  <- footer
└──────────────────────────────────────────────────────────────────┘
```

### Levels and navigation

The level navigation (`#level-nav`) shows one button per chart group that holds at least one
enabled chart, in registration order, labelled `SIN`, `Submercado`, `Intercâmbio`,
`Usinas hidrelétricas`, `Usinas termelétricas` and `Execução` (`dashboard.builder.GROUP_LABELS`).
Clicking a button re-renders in place — the browser never navigates — showing only that group's
chart sections and marking that button `aria-pressed="true"`.

### View modes and the Deck selector

The mode toggle (`#mode-toggle`) shows two buttons, `Por deck` and `Encadeado`
(`dashboard.builder.MODE_LABELS`), and `--modo-inicial` decides which one starts pressed.
`Por deck` plots one deck's own full stage horizon, selected with the `Deck` dropdown. `Encadeado`
concatenates the first `chaining.stages_per_deck` stages of every deck, in deck-date order, into
one continuous axis, and the `Deck` selector carries the `disabled` attribute while this mode is
active — present but inert, not hidden, since the chained axis does not read from a single deck.
Every line chart's X axis is a true datetime axis with step interpolation (`line_shape: "hv"`),
not one evenly-spaced tick per stage (see
[Intentional divergences](#intentional-divergences-from-the-original-specification) below): a
6-hour stage therefore renders six times wider than a 30-minute stage of the same deck.

### Absoluto and Diferença

The value-mode toggle (`#value-toggle`) shows `Absoluto` and `Diferença`
(`dashboard.builder.VALUE_LABELS`); `Absoluto` is always the value mode selected on load. In
`Diferença`, every point becomes `scenario − reference`, computed in the browser from the
embedded absolute series (never precomputed and shipped, to keep the payload half its size); the
reference scenario is chosen by `--referencia` (default: the first `--casos` basename) and is
named next to the toggle as `Referência: <name>`. A point is `null` whenever either side is
`null`. Each chart's Y-axis title carries the chart's `unit` in `Absoluto` and gains the suffix
` (diferença)` in `Diferença`.

### Entity selectors and plant filters

A chart whose selector is not `NONE` carries a `<select>` labelled `Submercado`,
`Par de submercados`, `Usina hidrelétrica` or `Usina termelétrica`
(`dashboard.builder.SELECTOR_LABELS`), populated from that chart's own source file (each chart
derives its own entity list; coverage is not uniform across the catalogue). The two plant levels (`Usinas hidrelétricas`, `Usinas termelétricas`)
additionally carry two independent, combinable text filters immediately below the selector: `Nome`
with placeholder `Filtrar por nome`, and `Código` with placeholder `Filtrar por código`. Both
filters narrow the same `<select>` as the operator types, matched case- and accent-insensitively;
the two fields combine with **AND**, never widening the match. When nothing matches, the message
`Nenhuma usina corresponde ao filtro` appears and the chart keeps showing whatever it displayed
before the filter stopped matching — it never blanks. Every selector and filter pair is
independent per chart section: picking an entity or typing a filter on one chart never affects
another, and both survive a level round trip.

### Hydro flow charts

The `SIN` and `Usinas hidrelétricas` levels carry the flow charts, all in `m3/s`, each plotting one
synthesized file exactly as shipped. On `SIN`, `Defluência`, `Turbinamento` and `Vertimento` plot
`QDEF_SIN`, `QTUR_SIN` and `QVER_SIN`, each the per-stage sum over all plants of the matching
`QDEF_UHE`, `QTUR_UHE` or `QVER_UHE` flow. They are aggregate indicators, not flows of distinct
water: water that flows down a cascade is counted again at each plant that releases it through its
turbines (`Turbinamento`), its spillway (`Vertimento`) or either (`Defluência`). `Defluência` is
the synthesized *Vazão Defluente*; the dashboard neither derives it from `Turbinamento` and
`Vertimento` nor checks it against them. In DESSEM a plant's outflow also includes the flow it
diverts to another plant (*desvio*), but the synthesis ships no file for that diverted flow and
does not state whether its *Vazão Defluente* includes it.

On `Usinas hidrelétricas`, `Vazão Afluente` (`QAFL_UHE`) and `Vazão Incremental` (`QINC_UHE`) join
the three flows above, one plant at a time. `Vazão Incremental` is the deck's inflow input
(`dadvaz`), which no decision of the run changes. For most plants, `Vazão Incremental` is the
natural incremental inflow, and `Vazão Afluente` adds the outflows of the upstream plants, lagged
by the travel time where one exists. Where the deck gives a regularized inflow instead, that input
already includes the upstream outflows, so `Vazão Afluente` equals `Vazão Incremental`. Sobradinho
(plant 169) is an example whenever the deck gives its inflow as regularized (`dadvaz` inflow type
`itp=3`), as recent ONS decks do.

Two scenarios built from the same inflow input therefore show a zero `Diferença` on `Vazão
Incremental` at every plant, while `Vazão Afluente`, `Defluência`, `Turbinamento` and `Vertimento`
can still differ. Section 10 of
[`docs/checklist-manual-dashboard.md`](docs/checklist-manual-dashboard.md) (steps 33 to 41) walks
these charts on a real build.

### The two Execução charts

`Custo Presente, Futuro e Total` and `Tempo Computacional` are the catalogue's only two grouped-bar
charts (`kind=SCALAR_BY_DECK`); every other enabled chart is a line chart. Both share one category
axis built from every deck date crossed with every displayed series name, with labels of the exact
form `<deck date> - <series name>` — for example `03/03/2024 - PRESENTE` — never a raw or
re-parsed timestamp, and independent of the active view mode and `Deck` selector: both charts
always show every deck at once. **`CUSTOS` is reported in `10^3 R$`, not plain `R$`** — a unit the
Y-axis label states explicitly. This matters because a review during development found the legacy
scripts had mislabelled the same values `(R$)`, a 1000x error caught by cross-checking `CUSTOS`
against `COP_SIN`/`CFU_SIN` on a reference deck: `CUSTOS.PRESENTE`'s raw value tracks
`COP_SIN`'s reference-deck sum at ratio 1.0019, and `CUSTOS.FUTURO`'s raw value tracks `CFU_SIN` at
ratio 0.9978 when read as `10^3 R$` — versus 1000x too small when read as plain `R$` (see the
comment above `FALLBACK_UNITS["CUSTOS"]` in `data/schemas.py`). A
reader comparing this dashboard against a raw DESSEM report should multiply `CUSTOS` values by
1000 to reach plain reais.

### Avisos: the eight warning shapes

The optional `Avisos` section appears only when there is at least one warning, listing every
distinct message from `DashboardData.warnings()` (`dashboard.builder._warnings_section`) — the same
list `run_manifest.json`'s `warnings` field carries; the log file separately records these same
events as part of a much larger operational log (see [Logging and auditing](#logging-and-auditing)
below). Every warning degrades the affected chart or deck rather than aborting the run, and there
are exactly eight distinct shapes, all measured directly from
`data/consolidate.py` and `data/timeline.py`:

1. **Short chaining window** (`data.timeline.validate_chaining`) — a deck has fewer stages than
   `chaining.stages_per_deck` in its chaining window.
2. **Chaining gap** (`data.timeline.validate_chaining`) — two consecutive decks' chaining windows
   leave a time gap between them.
3. **Chaining overlap** (`data.timeline.validate_chaining`) — two consecutive decks' chaining
   windows overlap in time.
4. **Missing deck for a shared date** (`data.timeline.align_deck_dates`) — a scenario has no deck
   for a date another scenario does have.
5. **Divergent timeline** (`data.consolidate._check_timeline_coverage`) — a non-primary scenario's
   deck at a shared date has a different stage count or start time than the deck the time axis was
   built from.
6. **Chart file not found** (`data.consolidate._load_series` and `_load_scalars`) — a chart's
   source Parquet is missing for a (scenario, deck); that (scenario, deck) contributes no values
   for it.
7. **Submarket code dropped** (`data.consolidate._load_series`) — on a `Submercado`-level chart, a
   submarket code present in the data that is neither in the `SBM.parquet` registry nor listed in
   `submarkets.fictitious_codes` is discarded with this warning. The registry's fictitious flag
   reads the same setting (`data.registries.load_registries`), so a listed code is hidden without a
   warning unless `submarkets.include_fictitious` is `true`, and a registry code that is not listed
   is shown as an ordinary submarket.
8. **Entity absent, filled with null** (`data.consolidate._load_series`) — an entity present for
   one scenario/deck but not another is stored with `null` values rather than omitted, so every
   scenario's series for a chart stays aligned on the same entity set.

### Offline guarantee and the release checklist

The dashboard makes no network request at build time or at view time: Plotly.js is inlined from
the installed `plotly` package (`plotly.offline.get_plotlyjs()`), the CSS and renderer script are
inlined from the package's own assets, and the JSON payload is embedded in a `<script
type="application/json">` element. Because no automated test can execute this file's JavaScript in
this environment (`node`/`npm` are not installed; `dashboard.js` carries only static Python-side
assertions in `tests/test_renderer_contract.py`), the full interactive behaviour described above is
verified manually, once per release, by walking
[`docs/checklist-manual-dashboard.md`](docs/checklist-manual-dashboard.md) against a real built
file. That checklist is the release gate for everything this section describes.

No screenshot of a real dashboard is included in this document. `.gitignore` excludes generated
`*.html` files but not images, so a screenshot of an actual run would embed real ONS study values —
plant names, costs, load curves — into a repository that is pushed to a remote; the text figure
above carries the same structural information with none of that risk.

## Extending the chart catalogue

The chart catalogue (`dessem_dashboard.charts.specs.SPECS`) declares 47 `ChartSpec` entries, of
which **31 are enabled by default** (24 line charts plus 7 bar charts) and 16 ship disabled as
registry entries only — both figures re-measured for this document by importing the registry and
calling `all_specs()` / `enabled_specs()` directly, not copied from an earlier count.
`dessem_dashboard.charts` registers every entry at import time (`charts/__init__.py`), so
`enabled_specs()`/`all_specs()` reflect `SPECS` as soon as the package is imported.

The enabled charts, by level and in display order (the order of the level's chart sections; a
chart's position within its level is its position in `SPECS`):

| Level | Enabled charts, in display order |
| --- | --- |
| `SIN` | `Geração Térmica`, `Geração Hidrelétrica`, `Geração Não Simulada`, `EARMF`, `Volume Armazenado`, `Defluência`, `Turbinamento`, `Vertimento` |
| `Submercado` | `Carga (Mercado de Energia)`, `Geração Hidráulica`, `Geração Térmica`, `Geração Não Simulada`, `CMO`, `Volume Armazenado` |
| `Intercâmbio` | `Intercâmbios` |
| `Usinas hidrelétricas` | `Geração`, `Volume Armazenado (hm3)`, `Volume Armazenado (%)`, `Vazão Afluente`, `Vazão Incremental`, `Defluência`, `Turbinamento`, `Vertimento` |
| `Usinas termelétricas` | `Geração` |
| `Custo` | `Custo Presente`, `Custo Futuro`, `Custo Total` |
| `Tempo` | `Tempo MILP`, `Tempo PL`, `Tempo de Leitura de Dados e Impressão`, `Tempo Total` |

The 16 entries that ship disabled, in `SPECS` order, are `MER_SIN`, `MERL_SBM`, `MERL_SIN`,
`GUNSD_SIN`, `GUNSD_SBM`, `EARMF_SBM`, `VARMI_SIN`, `VARMI_SBM`, `VARMI_UHE`, `VARPI_UHE`,
`VAGUA_UHE`, `VCALHA_UHE`, `CFU_SIN`, `COP_SIN`, `CUNS_SIN` and `CUNS_SBM`.

Each chart plots one file that the DESSEM synthesis ships, and the dashboard never derives a series
from other files. The synthesis ships flow files per plant (`QAFL_UHE`, `QINC_UHE`, `QDEF_UHE`,
`QTUR_UHE`, `QVER_UHE`) and, as SIN totals, only three flows (`QDEF_SIN`, `QTUR_SIN`, `QVER_SIN`).
There is no `QAFL_SIN` or `QINC_SIN` file to plot, so `SIN` has no `Vazão Afluente` or `Vazão
Incremental` chart, and `Submercado` has no flow chart.

### Enabling an already-declared chart

Each of the 16 disabled entries is a fully valid spec already carrying its own `FALLBACK_UNITS`
entry. Enabling one is a catalogue edit, not a setting: `charts.disabled` only removes keys from
`enabled_specs()` (`charts/registry.py`), so it can never turn a disabled chart on.

For example, `MER_SIN` (`Mercado de Energia`, unit `MW`, level `SIN`) ships disabled. To enable it:

1. Delete `enabled=False` from its `_series(...)` call in `charts/specs.py`.
2. Move that call to where the chart should appear, because a chart's position within its level is
   its position in `SPECS`.
3. Update the count pins listed in the table of the next subsection, and the enabled-source-file counts in the comments
   above `FALLBACK_UNITS` (`data/schemas.py`) and `_MAX_LOGGED_WARNINGS` (`cli.py`).

If a deck's synthesis lacks `MER_SIN.parquet`, that (scenario, deck) contributes no values and
raises one "file not found" warning (warning shape 6 in [Reading the dashboard](#reading-the-dashboard)).

Conversely, an operator who wants fewer charts adds entries — enabled or disabled — to
`charts.disabled` and they disappear from that run without touching a single source file.

### Adding a genuinely new chart

Registering a chart under a key the catalogue has never declared takes exactly two source edits:

1. One entry in `FALLBACK_UNITS` (`data/schemas.py`), keyed by the new chart's key.
2. One `_series(...)` or `_scalar(...)` call added to the `SPECS` tuple (`charts/specs.py`).

Both `_series` and `_scalar` read `FALLBACK_UNITS[key]` directly (not `.get`) while building the
`ChartSpec` at module import time, so a new entry in `SPECS` without a matching `FALLBACK_UNITS`
key raises `KeyError` the moment `dessem_dashboard.charts` is imported — the catalogue is
deliberately impossible to leave half-wired. No schema entry is needed: `SERIES_COLUMNS` and
`ENTITY_KEYS` are declared per aggregation level, not per source file, so any new `SERIES` chart at
an existing level (`SIN`, `SBM`, `SBP`, `UHE`, `UTE`) is already covered. `tests/fixtures_sintese.py`
builds one synthetic fixture file per entry of `enabled_specs()`, driven by the registry itself, so
a newly enabled chart's test fixtures follow automatically with no test-side edit.

The catalogue's size and order are pinned in 13 test files. Twelve of them had to change when
`QDEF_SIN`, `QTUR_SIN` and `QVER_SIN` were enabled, and `tests/test_schemas.py` is also hit when a
new `FALLBACK_UNITS` key is added. A plain `grep -rln _ENABLED_CHART_COUNT tests/` finds only six of
the 13 files; the other seven pin the catalogue under other names.

| File | What pins the catalogue |
| --- | --- |
| `tests/test_chart_specs.py` | `_ENABLED_KEYS_IN_ORDER` (31 keys, display order), `len(all_specs) == 47` (three tests), `16` disabled, per-level counts (`SIN: 8`, `SBM: 6`, `SBP: 1`, `UHE: 8`, `UTE: 1`, `CUSTO: 3`, `TEMPO: 4`), `len(remaining) == 29`. |
| `tests/test_builder.py` | `_ENABLED_CHART_COUNT = 31` and `_SIN_CHART_COUNT = 8`. |
| `tests/test_charts_costs.py` | A literal `len(sections) == 31`. |
| `tests/test_charts_sin.py` | `_ALL_ENABLED_CHART_KEYS`, a 31-key tuple used for a length check and as the `disabled` argument of the empty-catalogue test: a 32nd enabled chart missing from the tuple survives, so the `ConfigError` test fails with "DID NOT RAISE". |
| `tests/test_fixtures_sintese.py` | The generator's file count: `33` (26 enabled source files plus 7 registry files) in two tests, and `32` with one file omitted. |
| `tests/test_integration_exemplo.py` | `_ENABLED_CHART_COUNT = 31`; runs only when the example tree is present. |
| `tests/test_output_size.py` | `_ENABLED_CHART_COUNT = 31`, checked against `volumes["graficos"]`. |
| `tests/test_parity.py` | `_ENABLED_CHART_COUNT = 31`, the chart-section count; runs only when the example tree is present. |
| `tests/test_payload.py` | `_ENABLED_CHART_COUNT = 31` and `_VALUE_COUNT = 18_068`, the stored-value count. |
| `tests/test_pipeline.py` | `_ENABLED_CHART_COUNT = 31`, checked against `data_volumes["graficos"]`. |
| `tests/test_registries.py` | `_ENABLED_CHART_KEY_COUNT = 31`, one `METADADOS_OPERACAO` row per enabled chart key. |
| `tests/test_renderer_controls.py` | `_ALL_SIN_CHART_KEYS`, the eight `SIN` keys a test disables to move the active level to `Submercado`. |
| `tests/test_schemas.py` | `_ENABLED_CHART_KEYS` (26 source files), `_DISABLED_CHART_KEYS` (16) and `len(FALLBACK_UNITS) == 42`. Hit only by a new `FALLBACK_UNITS` key. |

`tests/test_charts_hydro.py` and `tests/test_charts_filters.py` pin the `Usinas hidrelétricas`
chart order; they changed when that order was set. A chart added to another level, or added
disabled, hits a different subset of these files.

## Structure

```text
src/dessem_dashboard/
├── __init__.py             # package version (__version__)
├── py.typed                # PEP 561 marker: ships inline type information
├── errors.py                # DashboardError hierarchy: ConfigError, SchemaError, DataFileError,
│                             # RegistryError, DiscoveryError, StoreError (seven classes total)
├── config.py                 # settings.json loading, validation and typed Settings dataclasses
├── logging_setup.py          # console (Rich or plain) + rotating file handler, log_step helper
├── manifest.py                # run_manifest.json writer (audit trail of a run)
├── pipeline.py                 # run(): discovery -> consolidation -> HTML write -> volumes
├── cli.py                       # argparse entry point: --casos/--saida/--referencia/--settings/...
├── models/
│   ├── __init__.py                 # package marker, no logic
│   ├── entities.py                  # DeckRef, ScenarioRef, Stage, DeckTimeline dataclasses
│   └── store.py                      # DashboardData: in-memory mirror of the embedded JSON payload
├── data/
│   ├── __init__.py                  # package marker, no logic
│   ├── discovery.py                  # scenario/deck discovery (non-recursive, sintese/-marked)
│   ├── timeline.py                    # EST.parquet -> DeckTimeline; chaining validation/warnings
│   ├── readers.py                      # the only module allowed to call pandas.read_parquet
│   ├── registries.py                    # UHE/UTE/SBM/REE/METADADOS_OPERACAO -> Portuguese labels
│   ├── schemas.py                        # column/dtype contracts, FALLBACK_UNITS
│   └── consolidate.py                     # joins discovery+timeline+readers+registries into DashboardData
├── charts/
│   ├── __init__.py                  # registers SPECS into REGISTRY at import time
│   ├── registry.py                   # ChartSpec, ChartRegistry, REGISTRY singleton
│   └── specs.py                       # SPECS: the 47-entry default catalogue (31 enabled)
└── dashboard/
    ├── __init__.py                    # package marker, no logic
    ├── theme.py                        # ONS brand colors, Plotly layout template, CSS custom properties
    ├── scalars.py                       # CUSTOS/TEMPO aggregation into displayed bar series
    ├── payload.py                        # DashboardData -> compact JSON-ready payload
    ├── builder.py                         # DOM assembly, single-substitution HTML document build
    └── assets/
        ├── __init__.py                     # packaging marker: makes package-data discoverable
        ├── dashboard.html                   # string.Template shell with the $placeholders builder.py fills
        ├── dashboard.css                     # stylesheet, reading every color from theme.py's :root block
        └── dashboard.js                       # hand-written renderer: mode/level/value toggles, filters
```

26 Python files (20 modules plus 6 package `__init__.py` markers) and 3 static assets, matching
`find src/dessem_dashboard -name "*.py" -o -name "*.css" -o -name "*.js" -o -name "*.html"`.

### Legacy scripts

`Leitura/leitor_arquivos.py`, the seven `Plotadores/*.py` chart modules and the five `main_*.py`
driver scripts at the repository root are the tool this project replaces. Their exact behaviour —
what each one plotted, which unit and axis convention it used, and where this project intentionally
diverges from it — is recomputed independently and checked by `tests/test_parity.py`, without
importing or running the scripts. The commit that removed
these thirteen files is the one whose message names the legacy removal, findable with
`git log --oneline -- Plotadores`; any single file can still be recovered from history, for example
`git show <sha>^:Plotadores/Custos.py`, with `<sha>` replaced by that commit's hash.

## Logging and auditing

`cli.main` calls `logging_setup.setup_logging` exactly once, before the pipeline runs; every other
module only calls `logging.getLogger(__name__)` and never adds a handler. Two handlers are always
attached to the root logger:

- **Console** — a `rich.logging.RichHandler` when `logging.use_rich` is `true` and `rich` is
  importable, otherwise a plain `logging.Formatter`.
- **File** — a `logging.handlers.RotatingFileHandler` writing to `logging.file` (default
  `logs/dashboard.log`), rotating at `logging.rotate_max_bytes` bytes and keeping
  `logging.rotate_backups` backups, formatted as
  `timestamp | level | logger name | message`.

The level comes from `logging.level` in `settings.json`, overridable per run with `--nivel-log`.
`logging_setup.log_step` logs one structured `INFO` line per pipeline step, with optional key-value
fields and elapsed seconds. The line count is not fixed — it scales with the run's own shape: 11
lines are logged exactly once per run regardless of scenario or deck count (scenario-discovery
completion, the five data-consolidation phase markers, consolidation completion, and the two
payload-build and two document-build steps), plus two lines per scenario (`Cenário descoberto`,
`Janela de encadeamento validada`) and two lines per deck (`Timeline de deck carregada`,
`Registros carregados`), plus the pipeline's own completion summary and `cli.main`'s
manifest-written line. Measured directly against the two-scenario, two-deck-per-scenario tree
`tests/fixtures_sintese.make_sintese_dir` builds — the shape used throughout this README's own
worked example — that totals **25** lines, so a run of that shape can be reconstructed from the
log alone.

The rotating log file, `run_manifest.json`'s `warnings` field, and the dashboard's own `Avisos`
section carry overlapping but not identical information. The **eight warning shapes** described in
[Reading the dashboard](#reading-the-dashboard) above reach all three, but not through the same
mechanism: `DashboardData.add_warning` only appends to the list the `Avisos` section renders and
`run_manifest.json` stores; it is `cli.main` that turns that list into console and log-file output,
logging each distinct message as one `logger.warning` line right after the pipeline returns and
before the manifest is written. That loop is capped at `cli._MAX_LOGGED_WARNINGS` (20) lines — a
single (scenario, deck) that lacks every chart source file raises 26 per-chart warnings, one per
enabled source file (24 series files plus `CUSTOS` and `TEMPO`), and two scenarios by two decks
raise 104 — so one malformed tree cannot flood the console; past the cap, one further
`logger.warning` line names how many messages were omitted and points back to
`run_manifest.json` and `Avisos`, both of which always keep the complete, uncapped list regardless
of what the console shows. The log file additionally
records several warnings that never reach the manifest or the `Avisos` section, because they are
operational detail rather than something the chart's own values are missing — for example a
renamed plant detected between two decks' registries (`data.consolidate._warn_on_renamed_plants`),
a chart present in the store but excluded from a run's own catalogue
(`dashboard.payload._warn_omitted_charts`), the output-size warning (`dashboard.builder.write_dashboard`),
and the `costs.total_parcels`/`time.stage_groups`/`time.unit_divisor` configuration warnings
described in [Configuration](#configuration) above.

Every run also writes `run_manifest.json` inside `paths.output_dir` (`manifest.write_run_manifest`);
its ten fields and `data_volumes`' six keys are listed in full in
[How to run](#how-to-run) above. `git_sha` and `git_dirty` are `null` outside a git checkout.

## Development

Quality gate, run from the repository root, in this order:

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src
.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing
```

`ruff format --check` only reports formatting problems; it never rewrites files (`ruff format`
without `--check` does). All four commands must exit 0. Measured for this document, on the
repository as it stands at the end of this ticket:

| Command | Result |
| ------- | ------ |
| `ruff check src tests` | `All checks passed!` |
| `ruff format --check src tests` | `61 files already formatted` |
| `mypy src` | `Success: no issues found in 26 source files` |
| `pytest --cov=dessem_dashboard --cov-report=term-missing` | `643 passed, 1 warning` across two chunked invocations totalling 441.2s (0:07:21); total coverage **99%** (1542 statements, 14 missed) |

Measured as two sequential chunked invocations, `tests/test_[a-l]*.py` then `tests/test_[m-z]*.py`
(the second with `--cov-append` so the reported coverage combines both), rather than as the single
command shown above: on this development machine, a single `pytest --cov` run across the whole
suite at once has repeatedly been killed by the OS for low memory. 338 passed in the first chunk
and 305 in the second (338 + 305 = 643), zero skipped, one warning; wall clock was 4m44.5s +
2m36.7s = 7m21.2s; the combined `.coverage` data reports 1542 statements with 14 missed (99%).

Total coverage is **99%**, well above the Epic 5 convention of an **85% floor** (raised from 80%
at the Epic 4/5 boundary). That floor is a convention checked by reading this number on every
ticket, the same way a reviewer or a specialist agent has checked it throughout this plan — **not**
a threshold `pytest` itself enforces: `pyproject.toml`'s `[tool.pytest.ini_options]` has no
`--cov-fail-under`, and no `setup.cfg` or other configuration adds one anywhere in the repository.
Wiring an enforced floor (`--cov-fail-under=85`) is a small, legitimate follow-up, but it is a code
change and is out of this documentation ticket's scope.

`[tool.ruff.lint]` in `pyproject.toml` selects 20 rule families explicitly, because ruff's default
set (`E4`, `E7`, `E9`, `F`) is narrower than this project needs. Four families are deliberately not
selected, since they contradict binding plan decisions instead of revealing defects: `TRY003`
(error messages must name the offending settings key), `PLC0415` (the `rich` import is guarded
inside `try`/`except` by design), `T201` (the stderr message for an invalid `settings.json` is
specified behaviour) and `PLR2004` (literal comparisons are intentional in tests). The rationale is
repeated as a comment next to the `select` list.

`DESSEM_DASHBOARD_EXEMPLO` is a **test-only** environment variable, read exclusively by
`tests/exemplo_tree.py` (and, through it, `tests/test_integration_exemplo.py` and
`tests/test_parity.py`) to point the integration and parity tests at a copy of the example scenario
tree living outside the repository. Nothing under `src/` reads it: `settings.json` remains the
single configuration anchor for the program itself, and this variable only ever redirects the test
*suite*.

### Intentional divergences from the original specification

Two behaviours deliberately depart from the original spec:

- **`.gitignore` keeps `logo/` and the documentation (`README.md`, `docs/`) versioned**, where the
  original spec suggested ignoring `logo/` and `*.md`; only the local planning material (`plans/`,
  `plano_dashboard_dessem.md`) and `CLAUDE.md` are excluded, and `.gitignore` itself is the
  evidence.
- **The line-chart X axis is a true datetime axis with `line_shape: "hv"` step interpolation**, not
  the legacy scripts' `type='category'` axis: in `Por deck` mode stage
  durations vary (0.5, 2, 6 and 8 hours), and a categorical axis would give a 30-minute stage and an
  8-hour stage the same width, visually misrepresenting the horizon. This is a deliberate,
  documented improvement, checked against the legacy behaviour by `tests/test_parity.py`.
