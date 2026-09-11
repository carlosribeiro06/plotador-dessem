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
analyse chained results. See
[`plans/dashboard-dessem/00-master-plan.md`](plans/dashboard-dessem/00-master-plan.md) for the full
architecture, rationale and decision log, and
[`plans/dashboard-dessem/planning-context.md`](plans/dashboard-dessem/planning-context.md) for the
binding user decisions.

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
(`dessem_dashboard.config.load_settings`); nothing is hard-coded. Relative paths inside
`settings.json` resolve against **the settings file's own directory**, not the current working
directory, so the project stays portable across machines. Loading fails fast with a Portuguese
`ConfigError` message when a required key is missing or has the wrong JSON type. The tables below
list every one of the 23 leaf keys with its shipped default and meaning, grouped exactly as
`settings.json` groups them; a short paragraph follows the table for the four keys an operator is
actually expected to change.

### General

| Key | Default | Meaning |
| --- | --- | --- |
| `project` | `"dessem-dashboard"` | Project label used in log lines and in the run manifest. |

### Paths

| Key | Default | Meaning |
| --- | --- | --- |
| `paths.output_dir` | `"output"` | Destination of the dashboard HTML and of `run_manifest.json`. |
| `paths.log_dir` | `"logs"` | Validated at load time (must resolve to a path), but **read by no module**: no consumer of this key exists under `src/` (`grep -rn "log_dir" src/` matches only the `Paths` dataclass field and the loader in `config.py`). The rotating log file's actual location is `logging.file`, which already carries a full path and whose parent directory `logging_setup.setup_logging` creates itself. Changing `paths.log_dir` alone has no observable effect; change `logging.file` instead. |
| `paths.logo_file` | `"logo/MarcasONS_Secundarias_verticais_Verde.png"` | ONS logo file, embedded as a base64 `data:` URI in the dashboard header. This is a **hard requirement**: `dashboard.builder._logo_data_uri` raises `ConfigError` naming `paths.logo_file` and the resolved absolute path when the file is missing, or when its suffix is not one of `.png`, `.jpg`, `.jpeg` or `.svg`. A missing *data* file (a scenario's Parquet) degrades to a warning; a missing logo does not, because the ONS visual identity is a project goal. |

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

`charts.disabled` names zero or more of the 42 declared `ChartSpec` keys (see
[Extending the chart catalogue](#extending-the-chart-catalogue) below for the full catalogue).
Naming a key the registry never registered raises `RegistryError` naming the unknown key
(`charts.registry.ChartRegistry.enabled_specs`); naming every currently-enabled key leaves nothing
to render, and `dashboard.builder.build_html` raises `ConfigError` naming `charts.disabled` rather
than let `_level_nav`/`_chart_sections` fail on an empty catalogue with a bare `IndexError`. Use it
to hide a shipped-but-uninteresting chart, or, following the worked example below, to enable one
of the 19 charts shipped disabled by editing the catalogue instead.

## How to run

The commands below run inside WSL Ubuntu (or a Linux server), from the repository root.

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

### Command-line flags

All flags and help text are Portuguese, by binding decision (see `CLAUDE.md`). `dessem-dashboard
--help` prints:

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
                        settings.json.
  --referencia NOME     Nome do cenário de referência usado na visão de
                        diferença. Padrão: nome do primeiro diretório
                        informado em --casos.
  --settings ARQUIVO    Arquivo de configuração do projeto. Padrão:
                        settings.json.
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
| `--saida` | no | `paths.output_dir/output.default_filename` | Output HTML file path. |
| `--referencia` | no | First `--casos` basename | Reference scenario for the `Diferença` view; must name one of the `--casos` labels. |
| `--settings` | no | `settings.json` | Path to the project configuration file. |
| `--modo-inicial` | no | `encadeado` | Dashboard view mode pre-selected on load: `deck` or `encadeado`. Also decides whether the `Deck` selector starts `disabled` (it does, exactly when the initial mode is `encadeado`). |
| `--nivel-log` | no | `logging.level` | Overrides the log level for this run only; never written back to `settings.json`. |

### What a run produces

A run writes exactly three things: the self-contained dashboard HTML at `--saida` (default
`paths.output_dir/output.default_filename`), a `run_manifest.json` beside it inside
`paths.output_dir`, and the rotating log file at `logging.file`. The dashboard embeds every value
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
not one evenly-spaced tick per stage (master plan decision 14; see
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
derives its own entity list; coverage is not uniform across the catalogue — see Appendix A.2 of
the master plan). The two plant levels (`Usinas hidrelétricas`, `Usinas termelétricas`)
additionally carry two independent, combinable text filters immediately below the selector: `Nome`
with placeholder `Filtrar por nome`, and `Código` with placeholder `Filtrar por código`. Both
filters narrow the same `<select>` as the operator types, matched case- and accent-insensitively;
the two fields combine with **AND**, never widening the match. When nothing matches, the message
`Nenhuma usina corresponde ao filtro` appears and the chart keeps showing whatever it displayed
before the filter stopped matching — it never blanks. Every selector and filter pair is
independent per chart section: picking an entity or typing a filter on one chart never affects
another, and both survive a level round trip.

### The two Execução charts

`Custo Presente, Futuro e Total` and `Tempo Computacional` are the catalogue's only two grouped-bar
charts (`kind=SCALAR_BY_DECK`); every other enabled chart is a line chart. Both share one category
axis built from every deck date crossed with every displayed series name, with labels of the exact
form `<deck date> - <series name>` — for example `03/03/2024 - PRESENTE` — never a raw or
re-parsed timestamp, and independent of the active view mode and `Deck` selector: both charts
always show every deck at once. **`CUSTOS` is reported in `10^3 R$`, not plain `R$`** — a unit the
Y-axis label states explicitly. This matters because the epic-04 boundary review found the legacy
scripts had mislabelled the same values `(R$)`, a 1000x error caught by cross-checking `CUSTOS`
against `COP_SIN`/`CFU_SIN` on the committed reference dump
(`plans/dashboard-dessem/reference/parquet-schemas.txt`): `CUSTOS.PRESENTE`'s raw value tracks
`COP_SIN`'s reference-deck sum at ratio 1.0019, and `CUSTOS.FUTURO`'s raw value tracks `CFU_SIN` at
ratio 0.9978 when read as `10^3 R$` — versus 1000x too small when read as plain `R$` (see the
comment above `FALLBACK_UNITS["CUSTOS"]` in `data/schemas.py`, and master plan Appendix A.5). A
reader comparing this dashboard against a raw DESSEM report should multiply `CUSTOS` values by
1000 to reach plain reais.

### Avisos: the eight warning shapes

The optional `Avisos` section appears only when there is at least one warning, listing every
distinct message from `DashboardData.warnings()` (`dashboard.builder._warnings_section`) — the same
list `run_manifest.json`'s `warnings` field carries; the log file separately records these same
events as part of a much larger operational log (see [Logging and auditing](#logging-and-auditing)
below). Every warning degrades the affected chart or deck rather than aborting the run (master plan
decision 18), and there are exactly eight distinct shapes, all measured directly from
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
7. **Submarket code dropped** (`data.consolidate._load_series`) — a submarket code present in a
   chart's data is neither in the visible registry nor configured as fictitious, and is discarded.
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

The chart catalogue (`dessem_dashboard.charts.specs.SPECS`) declares 42 `ChartSpec` entries, of
which **23 are enabled by default** and 19 ship disabled as registry entries only — both figures
re-measured for this document by importing the registry and calling `all_specs()` /
`enabled_specs()` directly, not copied from an earlier count. `dessem_dashboard.charts` registers
every entry at import time (`charts/__init__.py`), so `enabled_specs()`/`all_specs()` reflect
`SPECS` as soon as the package is imported.

### Enabling an already-declared chart

Every one of the 19 disabled entries is a fully valid spec already carrying its own
`FALLBACK_UNITS` entry; enabling one needs **no source change at all**. For example, `QDEF_SIN`
(`Defluência`, unit `m3/s`, group `SIN`) ships disabled; nothing needs to change in
`charts/specs.py` to turn it on — only `settings.json`, by making sure it is not named in
`charts.disabled` (it never is, by default). Conversely, an operator who wants fewer charts adds
entries — enabled or disabled — to `charts.disabled` and they disappear from that run without
touching a single source file.

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

**This recipe was verified, not assumed**, by actually performing it in a scratch copy of the
repository — adding one new enabled `SIN`-level entry and its `FALLBACK_UNITS` key, then running
the full test suite — and recording exactly what failed. The count is pinned in **twelve** test
files (not seven, which is what a plain `grep` for the literal `23` and `42` finds — the other five
only surface by actually running the suite):

| File | What breaks |
| --- | --- |
| `tests/test_chart_specs.py` | The `_ENABLED_KEYS_IN_ORDER` 23-key tuple and three literal `42` counts. |
| `tests/test_builder.py` | `_ENABLED_CHART_COUNT = 23`, used directly and in one subtraction. |
| `tests/test_charts_costs.py` | A literal `len(sections) == 23`. |
| `tests/test_charts_sin.py` | A literal `_ALL_ENABLED_CHART_KEYS` 23-tuple, used both for a length check and — more subtly — as the `disabled` argument of a test that disables "every" chart: a 24th enabled chart not in that tuple survives disabling, so the test that expects `ConfigError` for an empty catalogue instead fails with "DID NOT RAISE". |
| `tests/test_output_size.py` | `_ENABLED_CHART_COUNT = 23`, checked against `output_volumes()["graficos"]`. |
| `tests/test_payload.py` | `_ENABLED_CHART_COUNT = 23`, checked against the payload's chart count. |
| `tests/test_registries.py` | `_ENABLED_CHART_KEY_COUNT = 23`, checked against `METADADOS_OPERACAO`'s registered variable count. |
| `tests/test_fixtures_sintese.py` | Three tests pinning the fixture generator's file count at exactly 30 (23 enabled charts plus 7 registry files). |
| `tests/test_schemas.py` | `test_fallback_units_has_exactly_forty_two_keys`. |
| `tests/test_pipeline.py` | `pipeline.run`'s own `data_volumes["graficos"]`, checked against the same `_ENABLED_CHART_COUNT`. |
| `tests/test_parity.py` | The same `_ENABLED_CHART_COUNT` pinned chart-section count, inside a test whose main subject — the datetime X axis and the single inlined-Plotly output file, both parity findings — is unaffected. |
| `tests/test_renderer_controls.py` | A test that disables every `SIN` chart and asserts the active group shifts to `SBM`; a new `SIN` entry changes which charts that disabling call must name. |

This is the complete, measured list for a new *enabled* chart added to the `SIN` group; a chart
added disabled, or to a different group, changes exactly which of the group-specific assertions
above are hit, but the same twelve files are where to look.

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
│   └── specs.py                       # SPECS: the 42-entry default catalogue (23 enabled)
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
diverges from it — is transcribed and checked in
[`plans/dashboard-dessem/epic-05-parity-report.md`](plans/dashboard-dessem/epic-05-parity-report.md);
consult that report rather than the scripts themselves for what they did. Removing them from the
repository is ticket-038's job, with the parity report above as the record of what they did.

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
fields and elapsed seconds — 15 such lines per run plus one final pipeline summary, covering
scenario discovery, deck timelines, time-axis construction, registry loading, series and scalar
consolidation, and the two document-build steps — so a run can be reconstructed from the log alone.

The rotating log file, `run_manifest.json`'s `warnings` field, and the dashboard's own `Avisos`
section carry overlapping but not identical information. The **eight warning shapes** described in
[Reading the dashboard](#reading-the-dashboard) above reach all three, but not through the same
mechanism: `DashboardData.add_warning` only appends to the list the `Avisos` section renders and
`run_manifest.json` stores; it is `cli.main` that turns that list into console and log-file output,
logging each distinct message as one `logger.warning` line right after the pipeline returns and
before the manifest is written. That loop is capped at `cli._MAX_LOGGED_WARNINGS` (20) lines — a
single (scenario, deck) whose synthesis folder is missing can otherwise raise up to 23 per-chart
warnings on its own, and up to 92 across two scenarios and two decks — so one malformed tree cannot
flood the console; past the cap, one further `logger.warning` line names how many messages were
omitted and points back to `run_manifest.json` and `Avisos`, both of which always keep the
complete, uncapped list regardless of what the console shows. The log file additionally
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
| `pytest --cov=dessem_dashboard --cov-report=term-missing` | `631 passed, 1 warning in 501.95s (0:08:21)`; total coverage **99%** (1543 statements, 14 missed) |

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

Two behaviours deliberately depart from the original spec, each recorded as a planner decision:

- **`.gitignore` keeps `logo/` and `*.md` versioned** (`planning-context.md` decision 11), where
  the original spec suggested ignoring both; `.gitignore` itself is the evidence, since it excludes
  neither path.
- **The line-chart X axis is a true datetime axis with `line_shape: "hv"` step interpolation**, not
  the legacy scripts' `type='category'` axis (master plan decision 14): in `Por deck` mode stage
  durations vary (0.5, 2, 6 and 8 hours), and a categorical axis would give a 30-minute stage and an
  8-hour stage the same width, visually misrepresenting the horizon. This is a deliberate,
  documented improvement, checked against the legacy behaviour in
  [`plans/dashboard-dessem/epic-05-parity-report.md`](plans/dashboard-dessem/epic-05-parity-report.md).
