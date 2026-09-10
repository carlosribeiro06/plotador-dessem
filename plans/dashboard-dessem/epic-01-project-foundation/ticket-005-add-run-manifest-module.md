# ticket-005 Add the run manifest module

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

The dashboards produced by this tool are attached to formal studies, so a reader must be able to
answer, months later, which code and which inputs produced a given `dashboard_dessem.html`. The
`/new-project` convention covers this with a `run_manifest.json` written on every run, recording the
UTC timestamp, the git commit, the interpreter and platform, the invocation parameters, the data
volumes processed and the elapsed time. The legacy scripts recorded nothing, so a chart could not be
traced back to its inputs.

### Relation to Epic

This is the last of the three infrastructure modules (`config`, `logging_setup`, `manifest`) that
`ticket-006` wires into the CLI. Epic 2 will pass real `data_volumes` (decks, rows read per chart)
and Epic 5 will add the output HTML size, so the signature defined here must already accept them.

### Current State

`src/dessem_dashboard/` contains `__init__.py`, `py.typed`, `errors.py`, `config.py` and
`logging_setup.py`. `output/` exists with a `.gitkeep` and is gitignored. There is no manifest code.
The repository is a git repository on branch `main`, so `git rev-parse HEAD` succeeds; the manifest
must nevertheless tolerate a non-git checkout.

## Specification

### Requirements

1. Create `src/dessem_dashboard/manifest.py` exposing
   `write_run_manifest(output_dir: Path | str, *, params: Mapping[str, object], elapsed_s: float,
   data_volumes: Mapping[str, int] | None = None, warnings: Sequence[str] = ()) -> Path`.
2. The function creates `output_dir` if needed and writes `run_manifest.json` inside it, returning
   the written path.
3. The JSON object contains exactly these keys, in this order: `timestamp_utc`, `git_sha`,
   `git_dirty`, `python`, `platform`, `package_version`, `params`, `data_volumes`, `warnings`,
   `elapsed_seconds`.
4. `timestamp_utc` is `datetime.now(tz=UTC).isoformat()`; `git_sha` is the 40-character HEAD sha or
   `None` outside a git checkout; `git_dirty` is a boolean from `git status --porcelain` being
   non-empty, or `None` when `git_sha` is `None`; `package_version` is `dessem_dashboard.__version__`;
   `elapsed_seconds` is rounded to three decimals.
5. The file is written with `indent=2` and `ensure_ascii=False`, so accented Portuguese warning
   messages stay readable.
6. Values in `params` that are `Path` objects are serialised as their POSIX string form; the
   function must not fail on a `Path` value.

### Inputs

The output directory, the invocation parameters, the elapsed seconds, and optionally the data
volumes and the accumulated warning messages.

### Outputs and Behavior

`output_dir/run_manifest.json`, overwritten on each run. A single INFO log line is **not** emitted
here; the caller logs the returned path.

### Error Handling

`subprocess.CalledProcessError` and `FileNotFoundError` from the git calls are caught individually
and yield `git_sha = None`; no other exception is caught. `OSError` from `mkdir` or from writing
propagates. A `params` value that is not JSON-serialisable after the `Path` conversion raises
`TypeError` from `json.dumps`, which propagates so the caller fixes the call site.

## Dependencies

- **Blocked By**: `ticket-002-create-pyproject-and-package-skeleton.md`
- **Blocks**: `ticket-006-add-cli-entry-point-and-pipeline-stub.md`

## Acceptance Criteria

- [ ] Given `tmp_path` as the output directory, when
      `write_run_manifest(tmp_path, params={"casos": [Path("/a")], "referencia": "a"},
      elapsed_s=1.23456)` is called, then `tmp_path/"run_manifest.json"` exists and
      `json.loads(...)` has exactly the ten keys listed in requirement 3, in that order.
- [ ] Given the same call, when the JSON is loaded, then `elapsed_seconds == 1.235` and
      `params["casos"] == ["/a"]`.
- [ ] Given the repository root as the current working directory, when the manifest is written, then
      `git_sha` matches the regular expression `^[0-9a-f]{40}$` and `git_dirty` is `True`, because
      the tree has uncommitted changes.
- [ ] Given `output_dir = tmp_path / "nao" / "existe"`, when the manifest is written, then the
      nested directory is created and the returned path equals
      `tmp_path / "nao" / "existe" / "run_manifest.json"`.
- [ ] Given the repository root, when `.venv/bin/pytest tests/test_manifest.py -q` and
      `.venv/bin/mypy src/dessem_dashboard/manifest.py` are run, then both exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Adapt the `/new-project` `manifest.py` template
   (`~/.claude/skills/new-project/SKILL.md`, section `src/<PKG>/manifest.py`), then extend it with
   `git_dirty`, `package_version` and `warnings`, and translate the comments to English, keeping
   them minimal.
2. Implement two small private helpers, `_git_sha() -> str | None` and
   `_git_dirty() -> bool | None`, each running one `subprocess.run([...], capture_output=True,
   text=True, check=True)` call with an explicit `cwd=Path.cwd()`.
3. Implement `_jsonable(value: object) -> object` handling `Path`, `Sequence` and `Mapping`
   recursively, leaving scalars untouched.
4. Build the manifest as a `dict[str, object]` in the exact key order of requirement 3; Python
   dictionaries preserve insertion order, and `json.dumps` follows it.
5. Write `tests/test_manifest.py` using `tmp_path` and `monkeypatch.chdir` for the git assertions.

### Key Files to Create/Modify

- `src/dessem_dashboard/manifest.py` (create)
- `tests/test_manifest.py` (create)

### Patterns to Follow

- `datetime.now(tz=UTC)` never `datetime.now()`, per `rules/python.md`.
- `Mapping`/`Sequence` from `collections.abc` for parameters, concrete `Path` for the return type.
- Keyword-only arguments after `output_dir`.

### Pitfalls to Avoid

- `subprocess.run(..., check=True)` raises `CalledProcessError`, not `FileNotFoundError`, when git
  exists but the directory is not a repository; catch both explicitly and never use a bare `except`.
- Do not use `shell=True`; pass the argument list.
- `json.dumps` with `ensure_ascii=True` would escape every accented character in the Portuguese
  warnings, making the manifest unreadable; `ensure_ascii=False` is required.
- Do not import `pandas` here: the manifest must stay importable without the data stack.
- Do not log inside this module; the CLI logs the returned path.

### Out of Scope

- Calling `write_run_manifest` (ticket-006).
- Populating real `data_volumes` and `warnings`, which arrive with Epic 2 consolidation.
- Recording the output HTML size, which ticket-032 adds through `data_volumes`.
- Any manifest reader, diff tool or schema versioning.

## Testing Requirements

### Unit Tests

`tests/test_manifest.py`:

- key set and key order of the written JSON;
- `elapsed_seconds` rounding to three decimals;
- `Path` values inside `params` serialised as POSIX strings, including a nested list and a nested
  mapping;
- nested output directory created;
- `data_volumes=None` yields an empty object and `warnings=()` an empty array;
- accented warning text round-trips unescaped, asserted by reading the raw file text and searching
  for the accented substring;
- with `monkeypatch.chdir(tmp_path)` in a non-git directory, `git_sha` is `None` and `git_dirty` is
  `None`;
- with `monkeypatch.chdir(repository root)`, `git_sha` matches the 40-hex pattern.

### Integration Tests

None. The end-to-end check that a real run writes `output/run_manifest.json` belongs to ticket-006.

## Definition of Done

- [ ] Both files exist and all five acceptance criteria pass.
- [ ] `.venv/bin/ruff check src tests` and `.venv/bin/ruff format --check src tests` exit 0.
- [ ] `.venv/bin/mypy src` exits 0.
- [ ] The written `run_manifest.json` is valid JSON with the ten keys in the specified order.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 20 minutes
