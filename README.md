# dessem-dashboard

## What it is

`dessem-dashboard` compares the results of two or more DESSEM study scenarios and, once Epic 5
lands, will emit a single self-contained, offline HTML file with interactive comparative charts at
the SIN / submarket / hydro-plant / thermal-plant levels. A "scenario" is a directory passed via
`--casos`; each of its immediate subdirectories that contains a `sintese/` folder is a "deck" (one
DESSEM run), and the deck date comes from `EST.parquet`, never from the folder name. Two view modes
are planned — **por deck** (each deck's full original horizon) and **encadeado** (the first *N*
stages of each deck chained end to end, default 48 half-hour stages) — because that mirrors how the
legacy scripts and the developer already analyse chained results; see
[`plans/dashboard-dessem/00-master-plan.md`](plans/dashboard-dessem/00-master-plan.md) for the full
rationale and decision log. The project is under active development: see [Roadmap](#roadmap) for
what exists today versus what is planned.

## Requirements

- Python `>=3.12`.
- [`uv`](https://docs.astral.sh/uv/) to create and manage the virtual environment.
- Runtime dependencies (declared in `pyproject.toml`): `pandas>=3.0`, `pyarrow>=17`, `plotly>=6`
  (used only as the source of the embedded `plotly.min.js`), `rich>=13`.
- Development dependencies: `pytest>=8`, `pytest-cov>=5`, `ruff>=0.6`, `mypy>=1.11`.
- Target platform: WSL Ubuntu or a Linux server. The system Python is not used directly; `uv`
  manages an isolated `.venv`.

## Configuration

Every path, filename and tunable parameter is read from `settings.json` at the repository root
(`dessem_dashboard.config.load_settings`); nothing is hard-coded. Relative paths inside
`settings.json` resolve against **the settings file's own directory**, not the current working
directory, so the project stays portable across machines. Loading fails fast with a Portuguese
`ConfigError` message when a required key is missing or has the wrong JSON type. The tables below
list every leaf key with its default and meaning, grouped exactly as `settings.json` groups them.

### General

| Key | Default | Meaning |
| --- | --- | --- |
| `project` | `"dessem-dashboard"` | Project label used in log lines and in the run manifest. |

### Paths

| Key | Default | Meaning |
| --- | --- | --- |
| `paths.output_dir` | `"output"` | Destination of the dashboard HTML and of `run_manifest.json`. |
| `paths.log_dir` | `"logs"` | Directory for the rotating log file. |
| `paths.logo_file` | `"logo/MarcasONS_Secundarias_verticais_Verde.png"` | ONS logo file. |

### Logging

| Key | Default | Meaning |
| --- | --- | --- |
| `logging.level` | `"INFO"` | Root log level (`DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`). |
| `logging.file` | `"logs/dashboard.log"` | Rotating log file path. |
| `logging.rotate_max_bytes` | `5242880` | Rotation size in bytes (5 MiB). |
| `logging.rotate_backups` | `5` | Number of rotated backups kept. |
| `logging.use_rich` | `true` | Use a `RichHandler` console; falls back to a plain `Formatter`. |

### Discovery

| Key | Default | Meaning |
| --- | --- | --- |
| `discovery.sintese_dirname` | `"sintese"` | Name of the subfolder that marks a deck directory. |

### Chaining

| Key | Default | Meaning |
| --- | --- | --- |
| `chaining.stages_per_deck` | `48` | Stages taken from each deck in **encadeado** mode. |

### Costs

| Key | Default | Meaning |
| --- | --- | --- |
| `costs.total_parcels` | `["PRESENTE", "FUTURO"]` | Parcels summed into total cost. |

### Time

| Key | Default | Meaning |
| --- | --- | --- |
| `time.stage_groups` | see below | `TEMPO.parquet` `etapa` groupings used by the time chart. |
| `time.unit_divisor` | `60.0` | Divisor applied to convert seconds to minutes. |

The default `time.stage_groups` value is a JSON object mapping a group label to the list of
`TEMPO.parquet` `etapa` values it aggregates:

```json
{
  "MILP": ["MILP"],
  "PL": ["PL", "PL.Int.Fix", "PL.CalcCMO"],
  "Leitura": ["Leitura de Dados e Impressão"]
}
```

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
| `dashboard.date_format` | `"%d/%m/%Y %H:%M"` | X-axis tick and hover timestamp format. |

### Output

| Key | Default | Meaning |
| --- | --- | --- |
| `output.default_filename` | `"dashboard_dessem.html"` | Output name when `--saida` is omitted. |
| `output.decimals` | `2` | Decimal rounding applied to embedded chart values. |
| `output.size_warning_mb` | `50` | Warn when the generated HTML exceeds this size, in MB. |

### Charts

| Key | Default | Meaning |
| --- | --- | --- |
| `charts.disabled` | `[]` | Chart registry keys excluded from a given run. |

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

Run the tool against the two bundled example scenarios (`exemplo/` is gitignored developer data;
see `plans/dashboard-dessem/planning-context.md` decision 15 for how it was rebuilt):

```bash
dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi
```

**Current output.** Until Epic 5 (`plans/dashboard-dessem/00-master-plan.md`) is complete,
`pipeline.run` is a stub: it logs the resolved scenario directories, output path and reference
scenario, and returns a scenario count — it does not read any Parquet file and does not produce
`dashboard_dessem.html`. A real invocation today produces only the audit log
(`logs/dashboard.log`, or the path set by `paths.log_dir` / `logging.file`) and the run manifest
(`output/run_manifest.json`, or the path set by `paths.output_dir`).

The command-line flags, all Portuguese by binding decision (see `CLAUDE.md`):

| Flag | Required | Default | Meaning |
| --- | --- | --- | --- |
| `--casos` | yes | — | Scenario directories; legend label is each directory's basename. |
| `--saida` | no | `paths.output_dir/output.default_filename` | Output HTML file path. |
| `--referencia` | no | First `--casos` basename | Reference scenario for the difference view. |
| `--settings` | no | `settings.json` | Path to the project configuration file. |
| `--modo-inicial` | no | `encadeado` | Initial dashboard view mode: `deck` or `encadeado`. |
| `--nivel-log` | no | `logging.level` | Overrides the log level for this run. |

## Structure

Only `src/dessem_dashboard/` is shown; modules under `models/`, `data/`, `charts/` and `dashboard/`
are planned and do not exist yet.

```text
src/dessem_dashboard/
├── __init__.py          # package version (__version__)
├── py.typed             # PEP 561 marker: ships inline type information
├── errors.py            # DashboardError hierarchy (ConfigError today)
├── config.py            # settings.json loading, validation and typed Settings dataclasses
├── logging_setup.py     # console (Rich or plain) + rotating file handler, log_step helper
├── manifest.py          # run_manifest.json writer (audit trail of a run)
├── pipeline.py          # run(): orchestration entry point called by cli.main (Epic 1 stub)
├── cli.py               # argparse entry point: --casos/--saida/--referencia/--settings/...
├── models/              # planned (Epic 2): ScenarioRef/DeckRef/DashboardData dataclasses
├── data/                # planned (Epic 2): discovery, typed readers, registries, timeline
├── charts/              # planned (Epic 3): ChartSpec registry and the declared chart catalogue
└── dashboard/           # planned (Epic 3-4): theme, JSON payload, HTML builder, CSS/JS assets
```

## Logging and auditing

`cli.main` calls `logging_setup.setup_logging` exactly once, before the pipeline runs; library
modules only call `logging.getLogger(__name__)` and never add handlers themselves. Two handlers are
always attached to the root logger:

- **Console** — a `rich.logging.RichHandler` when `logging.use_rich` is `true` and `rich` is
  importable, otherwise a plain `logging.Formatter`.
- **File** — a `logging.handlers.RotatingFileHandler` writing to `logging.file` (default
  `logs/dashboard.log`), rotating at `logging.rotate_max_bytes` bytes and keeping
  `logging.rotate_backups` backups, formatted as
  `timestamp | level | logger name | message`.

The level comes from `logging.level` in `settings.json`, overridable per run with `--nivel-log`.
`logging_setup.log_step` logs one structured `INFO` line per pipeline step, with optional key-value
fields and elapsed seconds, so a run can be reconstructed from the log alone.

Every run also writes `run_manifest.json` inside `paths.output_dir` (`manifest.write_run_manifest`),
with these fields: `timestamp_utc`, `git_sha`, `git_dirty`, `python` (interpreter version),
`platform`, `package_version`, `params` (the resolved CLI parameters), `data_volumes`, `warnings`
and `elapsed_seconds`. `git_sha` and `git_dirty` are `null` outside a git checkout.

## Development

Quality gate, run from the repository root, in this order:

```bash
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src
.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing
```

`ruff format --check` only reports formatting problems; it never rewrites files (`ruff format`
without `--check` does).

All four commands must exit 0. Verified baseline, measured at the end of Epic 1:

| Command | Result |
| ------- | ------ |
| `ruff check src tests` | `All checks passed!` |
| `ruff format --check src tests` | `11 files already formatted` |
| `mypy src` | `Success: no issues found in 7 source files` |
| `pytest --cov=dessem_dashboard --cov-report=term-missing` | `47 passed`, total coverage **95 %** |

Total coverage is **95 %**, against a required floor of 80 % (raised to 85 % in Epic 5). Later
epics must not regress below that floor.

`[tool.ruff.lint]` in `pyproject.toml` selects 20 rule families explicitly, because ruff's default
set (`E4`, `E7`, `E9`, `F`) is narrower than this project needs. Four families are deliberately not
selected, since they contradict binding plan decisions instead of revealing defects: `TRY003`
(error messages must name the offending settings key), `PLC0415` (the `rich` import is guarded
inside `try`/`except` by design), `T201` (the stderr message for an invalid `settings.json` is
specified behaviour) and `PLR2004` (literal comparisons are intentional in tests). The rationale is
repeated as a comment next to the `select` list.

## Roadmap

Full architecture, rationale and decision log live in
[`plans/dashboard-dessem/00-master-plan.md`](plans/dashboard-dessem/00-master-plan.md); binding
decisions live in
[`plans/dashboard-dessem/planning-context.md`](plans/dashboard-dessem/planning-context.md).

1. **Project foundation** (this epic) — `pyproject.toml`, `settings.json` with validation, audit
   logging, run manifest, CLI entry point, `README.md`, project `CLAUDE.md`. Complete.
2. **Data layer** — scenario/deck discovery, typed Parquet readers with schema validation,
   registries (`UHE`/`UTE`/`SBM`/`METADADOS_OPERACAO`), deck timeline from `EST.parquet`, per-deck
   and chained consolidation into an in-memory data model.
3. **Dashboard core** — brand theme module, HTML template with inlined Plotly.js and logo, the
   hand-written JavaScript renderer (mode toggle, deck selector, level navigation, absolute/
   difference toggle), SIN and submarket charts including interchange pairs.
4. **Plant-level views & scalar charts** — hydro/thermal plant charts with name and code filters,
   the `CUSTOS` and `TEMPO` bar charts, and the output-size warning strategy.
5. **CLI end-to-end validation, docs and legacy removal** — full `--casos`/`--saida`/`--referencia`/
   `--settings` pipeline run against `exemplo/`, user-facing documentation with screenshots, a
   parity check against the legacy scripts, then their deletion.
