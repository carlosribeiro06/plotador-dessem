# ticket-002 Create `pyproject.toml` and the package skeleton

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem`; Python through the
> `uv`-managed `.venv`.

## Context

### Background

The repository has no packaging metadata: the legacy scripts are imported by relative path from the
root, which is why `Leitura/leitor_arquivos.py` carries a hard-coded absolute Windows path. The
target architecture is a `src/` layout package `dessem_dashboard` installed in editable mode, so
every later module can be imported as `dessem_dashboard.<module>` from tests and from the console
script without path manipulation. `planning-context.md` fixes the toolchain: WSL Ubuntu, `uv` at
`/snap/bin/uv`, `requires-python = ">=3.12"`, runtime dependencies `pandas>=3.0`, `pyarrow`,
`plotly>=6` and `rich`, development dependencies `pytest`, `pytest-cov`, `ruff` and `mypy` in strict
mode.

### Relation to Epic

This is the ticket that makes every following ticket in the epic runnable: `ticket-003` to
`ticket-006` add modules inside the package created here, and `ticket-008` runs the tools configured
here.

### Current State

After `ticket-001`, the repository root has `.gitignore`, `logs/.gitkeep` and `output/.gitkeep`, the
legacy scripts, `exemplo/`, `logo/`, the brand PDF, `LICENSE`, `plano_dashboard_dessem.md` and
`plans/`. There is no `pyproject.toml`, no `src/`, and no `.venv`. The system interpreter in WSL is
Python 3.14.4 and `uv` is version 0.12.6.

## Specification

### Requirements

1. Create `pyproject.toml` declaring: `name = "dessem-dashboard"`, `version = "0.1.0"`, a
   description, `requires-python = ">=3.12"`, the four runtime dependencies with lower bounds
   (`pandas>=3.0`, `pyarrow>=17`, `plotly>=6`, `rich>=13`), and an optional `dev` group with
   `pytest>=8`, `pytest-cov>=5`, `ruff>=0.6` and `mypy>=1.11`.
2. Declare the console script `dessem-dashboard = "dessem_dashboard.cli:main"`, the `setuptools`
   build backend, and `[tool.setuptools.packages.find] where = ["src"]` plus package data inclusion
   for `dessem_dashboard.dashboard.assets`.
3. Configure `[tool.ruff]` with `line-length = 100` and `src = ["src", "tests"]`;
   `[tool.mypy]` with `python_version = "3.12"`, `strict = true` and `files = ["src"]`;
   `[tool.pytest.ini_options]` with `addopts = "--cov=dessem_dashboard --cov-report=term-missing"`
   and `testpaths = ["tests"]`.
4. Create the package root `src/dessem_dashboard/__init__.py` exposing `__version__ = "0.1.0"` and
   nothing else, with `from __future__ import annotations` as its first statement, plus the marker
   file `src/dessem_dashboard/py.typed`.
5. Create the virtual environment and install the project in editable mode with the dev extra.

### Inputs

None. The versions above are fixed by this ticket.

### Outputs and Behavior

An importable, editable installation: `.venv/bin/python -c "import dessem_dashboard"` succeeds and
`dessem_dashboard.__version__` is `"0.1.0"`. `ruff`, `mypy` and `pytest` are available inside
`.venv/bin`.

### Error Handling

If `uv venv --python 3.12` cannot obtain a managed CPython 3.12 (no network, or the download is
blocked), fall back to `uv venv` using the system interpreter, which satisfies `>=3.12`, and record
in the completion report which interpreter was used and its exact version. Do **not** lower
`requires-python`. If a runtime dependency has no wheel for the chosen interpreter, stop and report
the failing package and interpreter rather than removing the dependency or relaxing its bound.

## Dependencies

- **Blocked By**: `ticket-001-configure-gitignore-and-untrack-data.md`
- **Blocks**: `ticket-003-add-settings-json-and-config-loader.md`,
  `ticket-004-add-logging-setup-module.md`, `ticket-005-add-run-manifest-module.md`

## Acceptance Criteria

- [ ] Given the repository root in WSL bash, when
      `uv venv --python 3.12 .venv && uv pip install -e ".[dev]"` is run, then it exits 0 and
      `.venv/bin/python -c "import dessem_dashboard as d; print(d.__version__)"` prints `0.1.0`.
- [ ] Given `pyproject.toml`, when
      `.venv/bin/python -c "import tomllib,pathlib;c=tomllib.loads(pathlib.Path('pyproject.toml').read_text());print(c['project']['requires-python'],c['tool']['mypy']['strict'],c['tool']['ruff']['line-length'])"`
      is run, then it prints `>=3.12 True 100`.
- [ ] Given the installed environment, when
      `.venv/bin/python -c "import pandas, pyarrow, plotly, rich"` is run, then it exits 0.
- [ ] Given the installed environment, when `.venv/bin/ruff --version`, `.venv/bin/mypy --version`
      and `.venv/bin/pytest --version` are run, then all three exit 0.
- [ ] Given the repository root, when `git status --short -- .venv` is run, then it prints nothing,
      proving `.venv` is ignored by the `.gitignore` from ticket-001.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `pyproject.toml` following the `/new-project` template
   (`~/.claude/skills/new-project/SKILL.md`, section "pyproject.toml"), adapted to the dependency
   set and the Python floor above.
2. Create the package files:

   ```bash
   mkdir -p src/dessem_dashboard
   printf 'from __future__ import annotations\n\n__version__ = "0.1.0"\n' > src/dessem_dashboard/__init__.py
   : > src/dessem_dashboard/py.typed
   ```

3. Create the environment and install:

   ```bash
   cd /home/carlosribeiro/git/plotador-dessem
   uv venv --python 3.12 .venv
   uv pip install -e ".[dev]"
   ```

4. Run the acceptance-criteria commands and report the interpreter version actually used.

### Key Files to Create/Modify

- `pyproject.toml` (create)
- `src/dessem_dashboard/__init__.py` (create)
- `src/dessem_dashboard/py.typed` (create, empty)

### Patterns to Follow

- `from __future__ import annotations` as the first statement of every Python module, per
  `rules/python.md`.
- Keep `__init__.py` free of imports from sibling modules, so import order never becomes a
  constraint.
- Package data declaration now, even though `src/dessem_dashboard/dashboard/assets/` is only created
  in Epic 3, so the manifest does not have to be revisited later.

### Pitfalls to Avoid

- Do not add a `[tool.pytest.ini_options]` `--cov-fail-under` entry: later tickets run `pytest` on a
  single test file and a global coverage floor would make those runs fail. The floor is checked at
  the epic gate instead (ticket-008).
- Do not pin exact versions yet; the lock happens once the feature is complete.
- Do not create `src/dessem_dashboard/cli.py` here; `ticket-006` owns it. The console script entry
  point may be declared before the module exists, but do not run `dessem-dashboard` in this ticket.
- Do not use `pip` directly; use `uv pip` so the environment stays reproducible.

### Out of Scope

- `settings.json` and the configuration loader (ticket-003).
- The `logging_setup`, `manifest`, `errors`, `cli` and `pipeline` modules (tickets 003 to 006).
- Any `tests/` file: the first test file arrives with ticket-003.
- Creating `src/dessem_dashboard/dashboard/assets/` or any subpackage directory.

## Testing Requirements

### Unit Tests

None. There is no behavior to test yet; `__init__.py` only carries `__version__`, which acceptance
criterion 1 verifies.

### Integration Tests

The five acceptance-criteria commands are the integration check. Paste the exact output of
`.venv/bin/python --version` into the completion report so later tickets know the interpreter.

## Definition of Done

- [ ] `pyproject.toml`, `src/dessem_dashboard/__init__.py` and `src/dessem_dashboard/py.typed` exist.
- [ ] `.venv` exists and all five acceptance criteria pass.
- [ ] The completion report states the interpreter version used and whether the 3.12 download
      succeeded or the fallback was taken.
- [ ] No file outside the three listed above was created or modified.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 25 minutes
