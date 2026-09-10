# Epic 1 Learnings — Project Foundation

Captured at the epic boundary on 2026-09-10, after all 8 tickets passed the guardian (mean quality
0.9875, min 0.90). These are the facts Epics 2 to 5 must build on. Where this file and the master
plan disagree, **this file wins**: it records what the code actually does.

## 1. Interpreter and toolchain actually used

`uv venv --python 3.12 .venv` selected an **already-installed** managed CPython at
`~/.local/share/uv/python/cpython-3.12-linux-x86_64-gnu/bin/python3.12`. No download was needed and
**the documented fallback to the system 3.14 interpreter was never taken**. The master plan's risk
"no `plotly` wheel for the chosen interpreter" did not materialise.

- `.venv/bin/python --version` -> `Python 3.12.14`
- Resolved versions: `pandas 3.0.5`, `pyarrow 25.0.1`, `plotly 7.0.0`, `rich 15.0.0`,
  `pytest 9.1.1`, `pytest-cov 7.1.0`, `ruff 0.16.6`, `mypy 2.3.1`.
- All exceed the declared floors, which is intended: ticket-002 forbids exact pins until the feature
  is complete.

**Verified for Epic 3**: `plotly.offline.get_plotlyjs()` still exists in **plotly 7.0.0** and returns
4 293 280 bytes (~4.29 MB) of `plotly.js v4.0.0`. Binding decision 6 (inline Plotly.js, offline
dashboard) is therefore safe on the installed stack. Consequence for ticket-032: **every** output
HTML carries a fixed ~4.29 MB floor before any data is embedded, against the
`output.size_warning_mb` default of 50.

## 2. The `Settings` contract (hard contract for Epics 2 to 5)

All eleven dataclasses are `@dataclass(frozen=True)`; frozen-ness was verified by a real
`FrozenInstanceError` probe, not by inspection.

```text
Settings(project: str, paths, logging, discovery, chaining, costs, time, submarkets, dashboard, output, charts)
  Paths(output_dir: Path, log_dir: Path, logo_file: Path)
  LoggingConfig(level: str, file: Path, rotate_max_bytes: int, rotate_backups: int, use_rich: bool)
  DiscoveryConfig(sintese_dirname: str)
  ChainingConfig(stages_per_deck: int)
  CostsConfig(total_parcels: list[str])
  TimeConfig(stage_groups: dict[str, list[str]], unit_divisor: float)
  SubmarketsConfig(include_fictitious: bool, fictitious_codes: list[int])
  DashboardConfig(title: str, footer_text: str, date_format: str)
  OutputConfig(default_filename: str, decimals: int, size_warning_mb: float)
  ChartsConfig(disabled: list[str])
```

Three details that are easy to get wrong:

1. **Every path-valued key arrives as a resolved absolute `Path`**, not a string — `paths.output_dir`,
   `paths.log_dir`, `paths.logo_file` and `logging.file`. They resolve against the **directory of the
   settings file**, never against `Path.cwd()`.
2. `output.size_warning_mb` and `time.unit_divisor` are typed `float` even though `settings.json`
   writes `50` and `60.0`. Both accept a JSON `int` or `float` and both reject a non-positive value.
3. `Settings.logging` and `Settings.time` shadow stdlib module names as *attributes*. This is safe,
   but a module doing `import logging` and reading `settings.logging.level` must not confuse them.

`load_settings(path: str | Path = "settings.json") -> Settings` performs no I/O beyond reading the
file and **never creates directories**.

## 3. Error hierarchy

`errors.py` currently holds exactly two classes:

- `DashboardError(Exception)` — base of the whole domain hierarchy.
- `ConfigError(DashboardError)` — raised by `load_settings` and by `setup_logging` for a bad level.

Epic 2 adds its own subclasses of `DashboardError`. Two conventions are already established and must
be kept: docstrings are English, **the raised message is Portuguese and names the offending item**
(for config, the full dotted key, e.g. `Chave obrigatória ausente em settings.json:
'chaining.stages_per_deck'`).

`cli.main` catches `ConfigError` -> exit 2 with the message on stderr and **no traceback**, and
`DashboardError` -> `logger.exception` and exit 1. Any new Epic 2 exception that should be an
operator error rather than a crash must therefore derive from `DashboardError`.

## 4. Logger naming convention

- `setup_logging(...)` returns `logging.getLogger("dessem_dashboard")` and is called **once**, from
  `cli.main`, after the settings are loaded.
- Every other module does `logger = logging.getLogger(__name__)` at module level, producing
  `dessem_dashboard.pipeline`, `dessem_dashboard.cli`, and so on. **No Epic 2 module may configure
  handlers.**
- `log_step(logger, message, *, elapsed_s=None, **fields)` is the single agreed way to log a stage
  boundary. It emits one INFO line joining the message, `key=value` pairs separated by two spaces,
  and `(%.3f s)` when `elapsed_s` is given. Epic 2 should use it for deck counts, row counts and
  per-stage timings.
- The level is validated **before** any handler is installed, so a bad `logging.level` can never
  leave the root logger half-configured.

## 5. CLI arguments as implemented

| Flag | dest | Type | Default |
| ---- | ---- | ---- | ------- |
| `--casos` | `casos` | `Path`, `nargs="+"`, required | — |
| `--saida` | `saida` | `Path` | `paths.output_dir / output.default_filename` |
| `--referencia` | `referencia` | `str` | basename of the first `--casos` entry |
| `--settings` | `settings` | `Path` | `Path("settings.json")` |
| `--modo-inicial` | `modo_inicial` | choice of `deck`, `encadeado` | `encadeado` |
| `--nivel-log` | `nivel_log` | choice of the five level names | `settings.logging.level` |

`main(argv: Sequence[str] | None = None) -> int`; `build_parser()` is a pure function so help text is
assertable without invoking `main`. Order inside `main` is fixed and load-bearing: **load settings ->
configure logging -> validate arguments -> `pipeline.run` -> write manifest -> return 0**.

Validation owned here is only **basename uniqueness** and **`--referencia` membership**.
`ticket-013` still owns checking that a scenario directory exists and contains decks — a run with
non-existent directories currently reaches `pipeline.run` and exits 0, which was verified
deliberately.

`pipeline.run(*, scenario_dirs, output_file, reference, settings) -> RunResult`, with
`RunResult(output_file: Path, data_volumes: dict[str, int], warnings: list[str])` frozen. **ticket-033
replaces the body and must then remove the `# noqa: ARG001` on the `settings` parameter**, which
exists only because the stub does not read it yet.

## 6. Deviations from the `/new-project` template

- Module set extended with `errors.py` (the template has no shared hierarchy) and `pipeline.py`.
- `settings.json` follows Appendix B's 23-key contract instead of the template's generic schema.
- No `--cov-fail-under` in `pyproject.toml`, deliberately: per-ticket runs execute a single test file
  and a global floor would fail them. The floor is enforced at the epic gate instead.
- `[tool.ruff.lint]` declares 20 rule families explicitly; ruff's default is only `E4, E7, E9, F`.
  Four families are excluded because they contradict binding decisions rather than reveal defects:
  `TRY003`, `PLC0415`, `T201`, `PLR2004`. Selecting them would require 35 suppressions against the
  project's own design. Rationale is recorded beside the `select` list and in `README.md`.

## 7. Test conventions that Epic 2 must follow

- **No test may write into the repository `logs/` or `output/`.** The working pattern: write a full
  valid settings payload into `tmp_path/settings.json`. Because relative path keys resolve against
  the settings file's own directory, `logs/` and `output/` land under `tmp_path` automatically with
  no change to the key values.
- **Never assert a fixed `git_dirty` value against the real repository.** It depends on ambient tree
  state and would fail on a clean checkout, which is exactly what the epic gate produces. Cover the
  clean -> dirty transition in a throwaway `git init` repo built inside `tmp_path`; at the repo root
  assert only the 40-hex `git_sha` shape.
- A test file that touches global `logging` state **must** carry an autouse fixture snapshotting and
  restoring root handlers and level and calling `logging.shutdown()`. Without it, `test_config.py`
  and every later test file break. Order-independence was verified in both directions.
- `pytest.raises(..., match=...)` must escape regex metacharacters — `re.escape("a.b")` — or the dots
  silently match any character and the assertion is weaker than intended.
- Baseline to not regress: **47 tests, 95 % total coverage**, floor 80 % (85 % in Epic 5).

## 8. Process learning: the ticket specifications contain self-contradictions

Four were found and resolved during this epic. Epic 2's ten tickets should be read with the same
suspicion, and the pattern is always the same — a requirement and its own acceptance criterion or
"Pitfalls" section disagree:

1. **ticket-001** — required directory patterns `logs/`/`output/` plus a final `!**/.gitkeep`
   negation, but `gitignore(5)` prunes an excluded directory without listing it, so the negation can
   never re-include the placeholder. Resolved with the content form `logs/*`, `output/*`.
2. **ticket-005** — AC3 asserted `git_dirty is True` from ambient repo state. Resolved by
   demonstrating it once and making the persisted test deterministic (see section 7).
3. **ticket-006** — AC3 required using the repository `settings.json` and asserting the real
   `output/run_manifest.json`, while its own Pitfalls and DoD forbade leaving artifacts in the
   repository. Resolved with a `tmp_path` settings copy.
4. **ticket-007** — AC5 required `grep -c '^```$' README.md` to be `0` "proving every fenced block
   declares a language tag", but a closing fence is always bare and matches that pattern. Resolved
   by tagging every opening fence and verifying with a fence-parity `awk` check.

Also note **ticket-008 named `type-lint-guardian`**, a read-only agent, for a ticket whose
requirements 3 to 5 all require writing. Later tickets that nominate an agent should be checked
against that agent's actual capabilities before dispatch.

## 9. Environment and process facts

- The repository is in WSL Ubuntu at `/home/carlosribeiro/git/plotador-dessem`; the Claude session
  runs on the Windows side, so every shell command goes through `wsl.exe -e bash -lc '<cmd>'`. Avoid
  single quotes inside that wrapper — they terminate it. Use a `bash <<"EOF"` heredoc for anything
  containing quotes.
- The `file-guard.sh` hook blocks `rm -rf` on `/tmp/...` paths as a false-positive root delete. Two
  throwaway verification directories (`/tmp/dessem_demo`, `/tmp/dessem_verify_scenario`) could not be
  removed and remain outside the repository; they are harmless.
- Git discipline in force: one conventional commit per ticket after the guardian passes, pushed to
  `origin main`, message in Portuguese focused on the *why*, trailer
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>` (amended from the
  `Claude Fable 5.1` line recorded during planning). Never `git add -A`; never force-push.
