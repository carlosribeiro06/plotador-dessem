# ticket-004 Add the audit logging setup module

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

This application supports formal ONS studies, so `CLAUDE.md` requires audit-grade logging: the
`logging` module, never `print()`, emitting simultaneously to a readable console and to a rotating
log file, with level, file path and rotation all configurable. A run must be reconstructable
afterwards from the log alone: which scenarios were read, how many decks and rows, how long each
stage took, and which warnings were raised. The legacy scripts produced no output at all beyond the
HTML files, which is why a failed run left no trace.

### Relation to Epic

`ticket-003` produced the `LoggingConfig` dataclass; this ticket consumes it and provides the single
`setup_logging` function that `ticket-006` calls once from the CLI entry point. Every Epic 2 to 5
module then only calls `logging.getLogger(__name__)` and never configures handlers.

### Current State

`src/dessem_dashboard/` contains `__init__.py`, `py.typed`, `errors.py` (with `DashboardError` and
`ConfigError`) and `config.py`. `rich` is installed in `.venv` as a runtime dependency. `logs/`
exists with a `.gitkeep` and is gitignored. No logging code exists yet. The `/new-project` template
provides a reference `logging_setup.py` whose comments must be translated to English and reduced.

## Specification

### Requirements

1. Create `src/dessem_dashboard/logging_setup.py` exposing
   `setup_logging(*, level: str = "INFO", log_file: Path | str = "logs/dashboard.log",
   max_bytes: int = 5_242_880, backups: int = 5, use_rich: bool = True) -> logging.Logger`,
   keyword-only after the first positional-free marker.
2. The function creates the parent directory of `log_file`, sets the root logger level, clears any
   pre-existing root handlers, then installs exactly two handlers: a console handler and a
   `RotatingFileHandler`.
3. The console handler is a `rich.logging.RichHandler` when `use_rich` is true and `rich` imports
   successfully; otherwise a `logging.StreamHandler` with the format
   `"%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"`.
4. The file handler always uses the full format
   `"%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"` with `encoding="utf-8"`, so accented
   Portuguese messages are written correctly.
5. An unknown `level` raises `ConfigError` with a Portuguese message naming the received value.
6. Calling `setup_logging` twice must leave exactly two handlers on the root logger, not four.
7. Add a helper `log_step(logger, message, *, elapsed_s=None, **fields)` that emits one INFO line
   with the step name, the optional elapsed time and any extra key-value fields, so later epics have
   one consistent way to log stage boundaries with volumes and timings.

### Inputs

The five keyword arguments above, normally taken from `Settings.logging`.

### Outputs and Behavior

Returns the module logger `logging.getLogger("dessem_dashboard")`. Side effects: the log directory
is created and the root logger is reconfigured. No message content is produced by the function
itself.

### Error Handling

`ConfigError` for an invalid level. `OSError` from directory creation or file opening propagates
unchanged so the caller sees the real filesystem error; do not swallow it. The `rich` import is
guarded with `except ImportError` only, never a bare `except`.

## Dependencies

- **Blocked By**: `ticket-002-create-pyproject-and-package-skeleton.md`,
  `ticket-003-add-settings-json-and-config-loader.md`
- **Blocks**: `ticket-006-add-cli-entry-point-and-pipeline-stub.md`

## Acceptance Criteria

- [ ] Given `log_file = tmp_path / "logs" / "run.log"`, when `setup_logging(level="INFO",
      log_file=log_file, use_rich=False)` is called and `logging.getLogger("dessem_dashboard.t")
      .info("cenário lido")` is emitted, then `log_file` exists and its text contains
      `cenário lido` and the substring `INFO`.
- [ ] Given a fresh root logger, when `setup_logging(...)` is called twice with the same arguments,
      then `len(logging.getLogger().handlers) == 2`.
- [ ] Given `use_rich=False`, when `setup_logging(...)` is called, then exactly one root handler is
      an instance of `logging.StreamHandler` that is not a `RotatingFileHandler`, and exactly one is
      a `RotatingFileHandler`.
- [ ] Given `level="VERBOSO"`, when `setup_logging(...)` is called, then it raises `ConfigError` and
      `pytest.raises(..., match="VERBOSO")` matches the message.
- [ ] Given the repository root, when `.venv/bin/pytest tests/test_logging_setup.py -q` and
      `.venv/bin/mypy src/dessem_dashboard/logging_setup.py` are run, then both exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Validate the level against `logging.getLevelNamesMapping()` restricted to the five standard names
   and raise `ConfigError` before touching any handler, so a bad level never leaves the logger half
   configured.
2. `Path(log_file).parent.mkdir(parents=True, exist_ok=True)`.
3. `root = logging.getLogger(); root.setLevel(level); root.handlers.clear()`.
4. Build the console handler inside a `try: from rich.logging import RichHandler` /
   `except ImportError:` block guarded by `use_rich`; give `RichHandler` a
   `logging.Formatter("%(message)s", datefmt="[%X]")` so the console stays uncluttered while the
   file keeps the full detail.
5. Build the `RotatingFileHandler` with `maxBytes=max_bytes`, `backupCount=backups`,
   `encoding="utf-8"`.
6. Implement `log_step` as a thin wrapper that formats `fields` as `key=value` pairs joined by two
   spaces and appends `(%.3f s)` when `elapsed_s` is not `None`.
7. Write `tests/test_logging_setup.py` with an autouse fixture that snapshots and restores
   `logging.getLogger().handlers` and level around each test, so tests cannot leak global state.

### Key Files to Create/Modify

- `src/dessem_dashboard/logging_setup.py` (create)
- `tests/test_logging_setup.py` (create)

### Patterns to Follow

- Configure logging only here and only when called from the entry point, per `rules/python.md`.
- Keyword-only parameters for every option, so call sites are self-documenting.
- English identifiers and docstrings; the messages that later modules pass through this logger are
  Portuguese.

### Pitfalls to Avoid

- Forgetting `root.handlers.clear()` makes repeated runs, and the test suite, duplicate every line.
- `pytest` installs its own handlers: the autouse restore fixture is mandatory or unrelated tests
  start failing.
- `RichHandler` writes to `stdout` through its own console; asserting on `capsys` is unreliable, so
  assert on the **file** contents instead.
- `RotatingFileHandler` keeps the file open; on Windows-mounted paths the test must close handlers
  before deleting `tmp_path`. Call `logging.shutdown()` in the restore fixture.
- Do not read `settings.json` inside this module: it receives plain arguments so it stays testable.

### Out of Scope

- Calling `setup_logging` from anywhere (ticket-006 does that).
- Logging any domain message such as scenario or deck counts (Epic 2).
- Log analysis tooling or structured JSON logs.
- Changing `logging.file` defaults in `settings.json` (owned by ticket-003).

## Testing Requirements

### Unit Tests

`tests/test_logging_setup.py`:

- file handler writes an accented message, verified by reading the file;
- idempotence: two calls leave two handlers;
- handler types with `use_rich=False`;
- with `use_rich=True`, the console handler is a `RichHandler` when `rich` is importable;
- invalid level raises `ConfigError`;
- missing parent directory is created;
- `log_step` output contains the step name, the formatted fields and the elapsed time with three
  decimals;
- autouse fixture restoring root handlers, root level and calling `logging.shutdown()`.

### Integration Tests

None. The end-to-end check that a real run writes `logs/dashboard.log` belongs to ticket-006.

## Definition of Done

- [ ] Both files exist and all five acceptance criteria pass.
- [ ] `.venv/bin/ruff check src tests` and `.venv/bin/ruff format --check src tests` exit 0.
- [ ] `.venv/bin/mypy src` exits 0.
- [ ] No module other than the two listed files was created or modified.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 25 minutes
