# ticket-006 Add the CLI entry point and the pipeline stub

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The feature spec fixes the invocation shape `--casos caso_oficial caso_gurobi caso_teste` and the
default output name `dashboard_dessem.html`. `planning-context.md` decision 2 requires the CLI flags
and `--help` text to be Portuguese, and decision 8 adds `--referencia` to choose the reference
scenario for the difference view. Fixing the whole argument surface now, before any data code
exists, means Epics 2 to 5 extend the pipeline behind a stable interface instead of renaming flags
later. The pipeline itself is a stub in this ticket: it logs the parameters and writes the manifest,
which is exactly the audit skeleton every later epic fills in.

### Relation to Epic

This ticket joins the three infrastructure modules from tickets 003 to 005 into one runnable
command, which is milestone M1 of the master plan. `ticket-007` documents the resulting commands and
`ticket-008` runs the quality gate over them.

### Current State

`src/dessem_dashboard/` contains `__init__.py`, `py.typed`, `errors.py`, `config.py`,
`logging_setup.py` and `manifest.py`. `pyproject.toml` already declares
`dessem-dashboard = "dessem_dashboard.cli:main"` from ticket-002, but `cli.py` does not exist, so the
console script currently fails. `settings.json` exists at the repository root with the full
Appendix B contract.

## Specification

### Requirements

1. Create `src/dessem_dashboard/pipeline.py` exposing
   `run(*, scenario_dirs: Sequence[Path], output_file: Path, reference: str,
   settings: Settings) -> RunResult`, where `RunResult` is a frozen dataclass with fields
   `output_file: Path`, `data_volumes: dict[str, int]` and `warnings: list[str]`.
2. The Epic 1 body of `run` logs one INFO line per scenario directory using `log_step`, logs the
   resolved output path and the reference scenario, returns a `RunResult` with
   `data_volumes = {"cenarios": len(scenario_dirs)}` and no warnings, and writes no HTML. It carries
   a single English comment stating that Epic 5 ticket-033 replaces the body.
3. Create `src/dessem_dashboard/cli.py` exposing `build_parser() -> argparse.ArgumentParser` and
   `main(argv: Sequence[str] | None = None) -> int`.
4. The parser uses Portuguese `help` strings and a Portuguese `description`, program name
   `dessem-dashboard`, and these arguments:

   | Flag | Type | Required | Default | Meaning |
   | ---- | ---- | -------- | ------- | ------- |
   | `--casos` | one or more paths, `nargs="+"` | yes | — | scenario directories to compare |
   | `--saida` | path | no | `paths.output_dir / output.default_filename` | output HTML file |
   | `--referencia` | string | no | basename of the first `--casos` entry | reference scenario for the difference view |
   | `--settings` | path | no | `settings.json` | settings file location |
   | `--modo-inicial` | choice of `deck` or `encadeado` | no | `encadeado` | view mode preselected in the dashboard |
   | `--nivel-log` | choice of the five logging levels | no | value of `logging.level` | overrides the configured level |

5. `main` loads the settings first, then configures logging, then validates the arguments, then
   calls `pipeline.run`, then writes the manifest with `params` covering every parsed argument, and
   returns `0`.
6. `--referencia` must name the basename of one of the `--casos` entries; otherwise `main` exits
   with code 2 and a Portuguese message naming the received value and listing the valid names.
7. Duplicate `--casos` basenames exit with code 2 and a Portuguese message naming the duplicate,
   because the basename is the legend label and must be unique.
8. Elapsed time is measured with `time.perf_counter()` around the `pipeline.run` call and passed to
   the manifest.

### Inputs

Command-line arguments, plus the settings file they point at.

### Outputs and Behavior

Exit code `0` on success, `2` on argument validation failure. Side effects: `logs/dashboard.log`
receives the run trace and `output/run_manifest.json` is written. No HTML is produced in this epic.

### Error Handling

`ConfigError` from `load_settings` is caught in `main`, reported on `stderr` with its Portuguese
message, and turned into exit code `2`; it must not surface as a traceback, since a bad
`settings.json` is a user error. `argparse` handles missing `--casos` itself with exit code 2.
`DashboardError` raised from `pipeline.run` is logged with `logger.exception` and returns exit code
`1`. No bare `except` and no `except Exception`.

## Dependencies

- **Blocked By**: `ticket-003-add-settings-json-and-config-loader.md`,
  `ticket-004-add-logging-setup-module.md`, `ticket-005-add-run-manifest-module.md`
- **Blocks**: `ticket-007-add-project-claude-md-and-readme-skeleton.md`

## Acceptance Criteria

- [ ] Given no arguments, when `main([])` is called, then it raises `SystemExit` with code `2` and
      the captured `stderr` contains `--casos`.
- [ ] Given `--help`, when the parser prints its help, then the output contains `--casos`, `--saida`,
      `--referencia`, `--settings`, `--modo-inicial`, `--nivel-log` and the Portuguese word
      `cenário`.
- [ ] Given two existing directories `tmp_path/"caso_a"` and `tmp_path/"caso_b"` and the repository
      `settings.json`, when
      `main(["--casos", str(a), str(b), "--settings", "settings.json", "--saida", str(tmp_path/"d.html")])`
      is called, then it returns `0`, the log file named in `settings.json` contains `caso_a` and
      `caso_b`, and `output/run_manifest.json` exists with `params["referencia"] == "caso_a"`.
- [ ] Given `--casos <a> <b> --referencia caso_z`, when `main` is called, then it raises
      `SystemExit` with code `2` and `stderr` contains `caso_z`.
- [ ] Given `--casos <tmp_path/caso_a> <tmp_path/outro/caso_a>`, when `main` is called, then it
      raises `SystemExit` with code `2` and `stderr` contains `caso_a`.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `pipeline.py` first: `RunResult` dataclass, then `run` with the four keyword arguments, a
   `logger = logging.getLogger(__name__)` at module level, and a body of at most fifteen lines.
2. Write `build_parser()` as a pure function returning the configured `ArgumentParser`, so the help
   text can be asserted in a test without invoking `main`.
3. In `main`: `args = build_parser().parse_args(argv)`; resolve `settings_path`; wrap
   `load_settings` in `try/except ConfigError` printing to `sys.stderr` and
   `raise SystemExit(2) from err`; call `setup_logging` with `args.nivel_log or settings.logging.level`.
4. Validate the scenario basenames with a small `_resolve_labels(paths) -> dict[str, Path]` helper
   that raises `SystemExit(2)` through `parser.error` so the message formatting stays consistent with
   argparse.
5. Compute the default output path as `settings.paths.output_dir / settings.output.default_filename`
   when `--saida` is absent, and create its parent directory before calling `run`.
6. Measure elapsed time, call `write_run_manifest(settings.paths.output_dir, params=..., elapsed_s=...,
   data_volumes=result.data_volumes, warnings=result.warnings)` and log the returned path.
7. Write `tests/test_cli.py` using `capsys`, `tmp_path` and `pytest.raises(SystemExit)`.

### Key Files to Create/Modify

- `src/dessem_dashboard/pipeline.py` (create)
- `src/dessem_dashboard/cli.py` (create)
- `tests/test_cli.py` (create)

### Patterns to Follow

- `main` returns an `int` so the setuptools console-script wrapper turns it into the exit status;
  never call `sys.exit` from library code other than through `parser.error`.
- Portuguese `help=` and `description=` strings; English identifiers, docstrings and test names.
- `argparse` `type=Path` for path arguments, so no manual string conversion is needed.

### Pitfalls to Avoid

- Configuring logging **before** loading the settings would ignore `logging.level` and
  `logging.file`; load first, configure second.
- `parser.error()` exits with code 2 and writes to `stderr`; do not reimplement it with `print` plus
  `SystemExit`.
- Do not validate that the `--casos` directories exist or contain decks here: that is
  `data/discovery.py` in ticket-013, which produces the domain-specific Portuguese message. This
  ticket only validates uniqueness and the `--referencia` membership.
- Do not import `pandas`, `pyarrow` or `plotly` in `cli.py` or `pipeline.py` in this ticket; keeping
  the startup import graph light makes `--help` instant.
- The test that runs `main` successfully writes into the real `logs/` and `output/` directories when
  it passes the repository `settings.json`. Point `--settings` at a settings file written in
  `tmp_path` instead, so the test leaves no artifacts, and keep only the assertion on the log file
  named by that temporary settings file.

### Out of Scope

- Any Parquet reading, scenario discovery, consolidation or HTML generation.
- Checking that the scenario directories exist or hold decks (ticket-013).
- Wiring the real pipeline (ticket-033).
- Shell completion, a configuration wizard or subcommands.

## Testing Requirements

### Unit Tests

`tests/test_cli.py`:

- missing `--casos` exits 2 with `--casos` in `stderr`;
- `build_parser().format_help()` contains all six flags and the word `cenário`;
- successful run with a settings file written in `tmp_path` returns 0, writes the log file and the
  manifest, and records `referencia` as the first basename;
- explicit `--referencia caso_b` is honoured in the manifest params;
- unknown `--referencia` exits 2 naming the value;
- duplicate basenames exit 2 naming the duplicate;
- `--nivel-log DEBUG` results in a root logger level of `DEBUG`;
- default `--saida` equals `paths.output_dir / output.default_filename` from the settings used;
- a malformed settings file exits 2 with the Portuguese `ConfigError` message on `stderr` and no
  traceback in the captured output;
- `pipeline.run` returns a `RunResult` whose `data_volumes["cenarios"]` equals the number of
  `--casos` entries.

### Integration Tests

One test invoking the installed console script through
`subprocess.run([".venv/bin/dessem-dashboard", "--help"], ...)` asserting exit code 0 and `--casos`
in `stdout`, marked to be skipped when `.venv/bin/dessem-dashboard` does not exist.

## Definition of Done

- [ ] The three files exist and all five acceptance criteria pass.
- [ ] `.venv/bin/dessem-dashboard --help` prints Portuguese help listing the six flags.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
      `.venv/bin/mypy src` all exit 0.
- [ ] No test leaves files in the repository `logs/` or `output/` directories.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
