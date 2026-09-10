# dessem-dashboard — Project Rules

Implementation Mode: Rigoroso. Identifiers, comments, docstrings, `README.md` and tests are
English; the only Portuguese is user-facing text (CLI flags/help, log and error messages, and
every dashboard UI string). See `~/.claude/CLAUDE.md` for the full mode policy — this file records
only what is specific to this project.

## Project-specific rules

- **Configuration**: every path, filename and tunable parameter is read from `settings.json` via
  `dessem_dashboard.config.load_settings`; never hard-code them in code. Relative paths inside
  `settings.json` resolve against the settings file's own directory, never against the current
  working directory. Loading fails fast with a `ConfigError` on a missing or malformed key.
- **Logging**: call `dessem_dashboard.logging_setup.setup_logging` exactly once, from
  `cli.main`. Every other module only calls `logging.getLogger(__name__)` and never adds handlers.
  The console uses a `RichHandler` when `logging.use_rich` is `true` and `rich` is installed,
  otherwise a plain `Formatter`; the rotating file handler is always attached.
- **Quality gate** (run from the repository root before every commit, in this order):

  ```bash
  .venv/bin/ruff check src tests
  .venv/bin/ruff format --check src tests
  .venv/bin/mypy src
  .venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing
  ```

## Required reading

- `plans/dashboard-dessem/planning-context.md` — binding user decisions and verified data,
  environment and brand facts. Never contradict it.
- `plans/dashboard-dessem/00-master-plan.md` — architecture, decision rationale and the
  `settings.json` contract (Appendix B).
