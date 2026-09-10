# ticket-008 Verify the toolchain quality gates

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `type-lint-guardian`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

`pyproject.toml` configures `ruff`, `mypy --strict` and `pytest --cov`, but tickets 002 to 007 each
verified only their own files. A scaffold is only trustworthy once the four commands run clean over
the whole tree at once: `mypy --strict` in particular surfaces cross-module typing problems, such as
a `Settings` field annotated as `Path` but consumed as `str`, that a per-file run hides. This ticket
is the epic gate: it produces the first green baseline and records the exact commands in the README
so every later epic gate repeats them identically.

### Relation to Epic

Last ticket of the epic. It closes milestone M1 and produces the coverage baseline that Epic 2
tickets must not regress. Nothing in Epic 2 starts before this ticket is green.

### Current State

`src/dessem_dashboard/` holds `__init__.py`, `py.typed`, `errors.py`, `config.py`,
`logging_setup.py`, `manifest.py`, `pipeline.py` and `cli.py`. `tests/` holds `test_config.py`,
`test_logging_setup.py`, `test_manifest.py` and `test_cli.py`. `README.md` and `CLAUDE.md` exist
from ticket-007 but their `## Development` section lists the commands without verified output.

## Specification

### Requirements

1. Run, in this order, and drive each to a clean result: `ruff check src tests`,
   `ruff format --check src tests`, `mypy src`, and
   `pytest --cov=dessem_dashboard --cov-report=term-missing`.
2. Total coverage must be at or above 80 percent. If it is lower, add the missing tests to the
   existing test files rather than lowering the target.
3. Fixes to `src/` and `tests/` files created by tickets 002 to 007 are limited to lint findings,
   type annotations and added tests. No behavior change, no renamed public function, no new module.
4. Record in `README.md`, under `## Development`, the four commands verbatim and the measured
   coverage percentage of this baseline.
5. Add to `pyproject.toml` only what the tools require to stay clean without suppressing real
   findings: an explicit `[tool.ruff.lint]` `select` list, and per-module `mypy` overrides only if a
   third-party package genuinely lacks stubs, each override carrying an English comment naming the
   package.
6. Any `# type: ignore` added must carry a specific error code and any `# noqa` a specific rule
   code, per `rules/python.md`.

### Inputs

The repository as left by ticket-007.

### Outputs and Behavior

A green toolchain and a README `## Development` section stating the verified commands and the
coverage baseline. No new modules and no behavior change.

### Error Handling

If a `mypy --strict` finding can only be silenced by weakening a type (for example by widening a
return type to `object` or by adding a blanket `ignore_errors`), stop and report the finding with the
options rather than weakening it, per the anti-simplification rule in `CLAUDE.md`. The same applies
to a failing test: do not delete or skip it.

## Dependencies

- **Blocked By**: `ticket-007-add-project-claude-md-and-readme-skeleton.md`
- **Blocks**: `ticket-009-define-parquet-schema-contracts.md`

## Acceptance Criteria

- [ ] Given the repository root, when `.venv/bin/ruff check src tests` is run, then it exits 0 and
      prints `All checks passed!`.
- [ ] Given the repository root, when `.venv/bin/ruff format --check src tests` is run, then it
      exits 0 and reports no file would be reformatted.
- [ ] Given the repository root, when `.venv/bin/mypy src` is run, then it exits 0 and prints
      `Success: no issues found`.
- [ ] Given the repository root, when
      `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing` is run, then it exits 0 and
      the `TOTAL` line of the coverage table shows at least `80%`.
- [ ] Given `README.md`, when its `## Development` section is read, then it contains the four
      commands above verbatim and the coverage percentage measured in this ticket.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Run `ruff format src tests` first, then `ruff check --fix src tests`, then re-run both in check
   mode. Formatting before linting avoids fighting the two tools.
2. Run `mypy src` and fix findings by adding or correcting annotations. Common findings at this stage
   are a missing return annotation on a test helper, `Path | str` parameters not narrowed with
   `Path(...)` before use, and `Mapping[str, object]` values needing `cast` or an `isinstance`
   narrowing in `manifest._jsonable`.
3. Run the coverage command and read the `term-missing` column to find uncovered lines. Expect the
   `except ImportError` branch of `logging_setup` and the `git_sha is None` branch of `manifest` to
   need a test each.
4. Update the README `## Development` section with the four commands and the measured total.
5. Re-run all four commands one last time and paste their output into the completion report.

### Key Files to Create/Modify

- `pyproject.toml` (modify: `[tool.ruff.lint]` select list, and mypy overrides only if required)
- `README.md` (modify: `## Development` section only)

Files from tickets 002 to 007 under `src/dessem_dashboard/` and `tests/` may be edited **only** to
fix tool findings or to add the tests needed for the coverage floor.

### Patterns to Follow

- Fix the cause, not the symptom: add the annotation instead of an ignore comment.
- Keep the `ruff` `select` list explicit so future rule-set changes in `ruff` cannot silently alter
  the gate.
- Test names stay in English and follow `test_<function>_<scenario>_<expected>`.

### Pitfalls to Avoid

- Do not add `--cov-fail-under` to `pyproject.toml`: single-file `pytest` runs in later tickets would
  then fail on global coverage. The floor is checked by this ticket and by the epic gates.
- Do not add `ignore_missing_imports = true` globally; scope any override to the specific package
  that lacks stubs and comment why.
- Do not reformat `plano_dashboard_dessem.md`, `plans/**` or the legacy `Leitura/`, `Plotadores/` and
  `main_*.py` files. Restrict every command to `src` and `tests`.
- Do not raise coverage by deleting hard-to-test code or by adding tests that assert nothing.

### Out of Scope

- Any new module, class or function beyond test helpers.
- Renaming or changing the signature of anything created in tickets 002 to 007.
- Adding a pre-commit configuration or a CI workflow.
- Linting or typing the legacy scripts, which are deleted in ticket-038.

## Testing Requirements

### Unit Tests

Only additions needed to reach the 80 percent floor, placed in the existing four test files, most
likely: the `rich` unavailable branch of `logging_setup` (via `monkeypatch` making the import fail),
the non-git branch of `manifest._git_sha`, and the `DashboardError` path of `cli.main` returning
exit code 1.

### Integration Tests

The four gate commands themselves, executed at the repository root, with their output recorded in
the completion report.

## Definition of Done

- [ ] All four gate commands exit 0 and the coverage total is at or above 80 percent.
- [ ] The README `## Development` section lists the four commands and the measured coverage.
- [ ] No `# type: ignore` or `# noqa` without a specific code exists in `src/` or `tests/`, verified
      with `grep -rn "type: ignore$\|noqa$" src tests` printing nothing.
- [ ] No public signature created in tickets 002 to 007 was changed.

## Effort Estimate

**Points**: 2 · **Confidence**: Medium · **Agent time**: about 20 minutes
