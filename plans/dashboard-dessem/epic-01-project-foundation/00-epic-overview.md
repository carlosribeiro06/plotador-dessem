# Epic 01: Project Foundation and Repository Hygiene

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **detailed** (tickets are ready for dispatch).

## Goal

Turn a repository of loose legacy scripts into an installable, typed, configured, logged and tested
Python project, and stop versioning the input data. At the end of this epic
`dessem-dashboard --casos <dir>` runs, validates `settings.json`, writes an audit log and a run
manifest, and `ruff`, `mypy --strict` and `pytest` are green. No DESSEM data is read yet.

## Scope

In scope:

- `.gitignore`, untracking of `exemplo/**` and `**/__pycache__/**` from the git index, `logs/` and
  `output/` placeholders.
- `pyproject.toml` with `ruff`, `mypy --strict` and `pytest` configuration, the `src/` layout, the
  `dessem_dashboard` package and the `uv`-managed `.venv`.
- The full `settings.json` contract of Appendix B of the master plan, plus a validating loader.
- Audit logging, the run manifest, the domain error hierarchy.
- The final CLI argument surface with a pipeline stub, so the argument surface is decided once.
- Project `CLAUDE.md`, project `.claude/settings.json`, and the README skeleton.
- A toolchain verification pass.

Out of scope, and explicitly deferred:

- Reading any Parquet file, discovering scenarios, or building charts (Epic 2 onwards).
- Deleting the legacy `Leitura/`, `Plotadores/` and `main_*.py` files (ticket-038).
- Restoring or deleting anything inside the `exemplo/` working tree (master plan open question 4,
  resolved: the staged deletions are committed and pushed by ticket-001).
- Branch operations or force-pushes: every ticket commits and pushes on `main` only.

## Tickets

| Ticket | Title | Points | Agent time | Agent |
| ------ | ----- | ------ | ---------- | ----- |
| ticket-001 | Configure `.gitignore` and untrack input data | 1 | ~15 min | docker-linux-server-architect |
| ticket-002 | Create `pyproject.toml` and the package skeleton | 2 | ~25 min | python-task-automation-developer |
| ticket-003 | Add `settings.json` and the validating config loader | 3 | ~30 min | python-task-automation-developer |
| ticket-004 | Add the audit logging setup module | 2 | ~25 min | python-task-automation-developer |
| ticket-005 | Add the run manifest module | 2 | ~20 min | python-task-automation-developer |
| ticket-006 | Add the CLI entry point and the pipeline stub | 3 | ~30 min | python-task-automation-developer |
| ticket-007 | Add the project `CLAUDE.md` and the README skeleton | 2 | ~25 min | open-source-documentation-writer |
| ticket-008 | Verify the toolchain quality gates | 2 | ~20 min | type-lint-guardian |

Total: 17 points, about 3 hours of agent time.

## Dependency Order

```text
ticket-001 -> ticket-002 -> ticket-003 -> ticket-006 -> ticket-007 -> ticket-008
                        \-> ticket-004 -/
                        \-> ticket-005 -/
```

## Definition of Done for the Epic

- [ ] `git ls-files exemplo | wc -l` prints `0` and `git check-ignore -v exemplo/sintese` succeeds.
- [ ] `uv pip install -e ".[dev]"` succeeds in `.venv` and `dessem-dashboard --help` prints
      Portuguese help listing `--casos`, `--saida`, `--referencia` and `--settings`.
- [ ] `dessem-dashboard --casos <any-dir>` exits 0, appends to `logs/dashboard.log` and writes
      `output/run_manifest.json`.
- [ ] `ruff check src tests`, `ruff format --check src tests` and `mypy src` all exit 0.
- [ ] `pytest --cov=dessem_dashboard --cov-report=term-missing` passes with total coverage at or
      above 80 percent.
- [ ] `README.md` documents every `settings.json` key with its default.

## Learnings to Capture for Later Epics

Record in `epic-01-learnings.md` at the epic boundary: the interpreter actually used by `uv venv`
and whether the 3.12 download worked; the exact `Settings` dataclass shape and field names; the
`DashboardError` subclass names; the logger naming convention; the CLI argument names as
implemented; and any deviation from the `/new-project` template.
