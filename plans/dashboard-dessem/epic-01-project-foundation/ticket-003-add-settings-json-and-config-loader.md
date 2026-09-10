# ticket-003 Add `settings.json` and the validating config loader

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-01-project-foundation` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.

## Context

### Background

`CLAUDE.md` forbids hard-coded paths, filenames and tunable parameters: everything must come from a
validated project settings file. The legacy code violates this at its very first line
(`caminho_pasta = Path("C:/Users/carlo/OneDrive/...")`), which is why it only ran on one machine.
Appendix B of the master plan fixes the complete `settings.json` contract for this project: 23 keys
across ten groups, covering paths, logging, deck discovery, chaining, cost parcels, computational
time groupings, submarket filtering, dashboard identity, output sizing and the disabled chart list.
Every later module reads its parameters from the `Settings` object produced here, so the field names
chosen in this ticket become a hard contract for Epics 2 to 5.

### Relation to Epic

This ticket introduces both the configuration anchor and the shared error hierarchy
(`errors.py`), which `ticket-004` and every Epic 2 module extend with their own subclasses. It runs
after the package exists and before the CLI wires everything together.

### Current State

`src/dessem_dashboard/` contains only `__init__.py` and `py.typed`. There is no `settings.json`, no
`errors.py`, no `config.py` and no `tests/` directory. The `/new-project` template in
`~/.claude/skills/new-project/SKILL.md` provides a reference `config.py` with a `_require` helper, a
`ConfigError` and frozen dataclasses; it must be adapted to the 23-key contract and its comments
translated to English and reduced to the minimum, per Rigoroso mode.

## Specification

### Requirements

1. Create `settings.json` at the repository root with exactly the keys, defaults and nesting of
   Appendix B of the master plan.
2. Create `src/dessem_dashboard/errors.py` with `DashboardError(Exception)` as the base of the whole
   domain hierarchy and `ConfigError(DashboardError)` as its first subclass. Both carry an English
   docstring; the messages they are raised with are Portuguese.
3. Create `src/dessem_dashboard/config.py` exposing frozen dataclasses `Paths`, `LoggingConfig`,
   `DiscoveryConfig`, `ChainingConfig`, `CostsConfig`, `TimeConfig`, `SubmarketsConfig`,
   `DashboardConfig`, `OutputConfig`, `ChartsConfig` and the aggregate `Settings`, plus
   `load_settings(path: str | Path = "settings.json") -> Settings`.
4. `load_settings` validates every key: presence, JSON type, and for `logging.level` membership in
   `{"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}`. It raises `ConfigError` with a Portuguese
   message naming the offending key on the first violation.
5. Every path-valued key resolves to an absolute `Path` relative to the **directory of the settings
   file**, not to the current working directory.
6. `chaining.stages_per_deck` must be a positive `int`; `output.decimals` a non-negative `int`;
   `output.size_warning_mb` a positive number; `costs.total_parcels` a non-empty list of `str`;
   `time.stage_groups` a mapping from `str` to non-empty lists of `str`; `submarkets.fictitious_codes`
   a list of `int`; `charts.disabled` a list of `str` that may be empty.

### Inputs

A path to a JSON file. Default `"settings.json"`, interpreted relative to the current directory.

### Outputs and Behavior

A `Settings` instance with resolved absolute paths and native Python types. The function performs no
I/O beyond reading the file and never creates directories.

### Error Handling

`ConfigError` for a missing file, malformed JSON (`raise ... from err` on `json.JSONDecodeError`), a
missing key, a wrong JSON type, or a value failing a range or membership rule. No bare `except`, no
`except Exception`. Messages are Portuguese and always name the full dotted key, for example
`Chave obrigatória ausente em settings.json: 'chaining.stages_per_deck'`.

## Dependencies

- **Blocked By**: `ticket-002-create-pyproject-and-package-skeleton.md`
- **Blocks**: `ticket-006-add-cli-entry-point-and-pipeline-stub.md`,
  `ticket-007-add-project-claude-md-and-readme-skeleton.md`

## Acceptance Criteria

- [ ] Given the repository `settings.json`, when `load_settings(Path("settings.json"))` is called,
      then it returns a `Settings` whose `output.default_filename` equals `"dashboard_dessem.html"`,
      whose `chaining.stages_per_deck` equals `48`, and whose
      `dashboard.footer_text` equals `"Gerência de Ferramentas Energéticas - FEN"`.
- [ ] Given a settings file written in `tmp_path` with the `chaining` group deleted, when
      `load_settings` is called, then it raises `ConfigError` and
      `pytest.raises(..., match="chaining")` matches the message.
- [ ] Given a settings file in `tmp_path` where `output.decimals` is the string `"2"`, when
      `load_settings` is called, then it raises `ConfigError` whose message contains `decimals`.
- [ ] Given a settings file at `tmp_path/"settings.json"` with `paths.output_dir` set to `"output"`,
      when `load_settings` is called from a different working directory, then
      `settings.paths.output_dir == tmp_path / "output"`.
- [ ] Given the repository root, when
      `.venv/bin/pytest tests/test_config.py -q && .venv/bin/mypy src/dessem_dashboard/config.py`
      is run, then both commands exit 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Write `settings.json` by transcribing Appendix B of `00-master-plan.md` verbatim, keeping the
   group order of the appendix.
2. Write `errors.py` first: two classes, docstrings only, no logic.
3. Write `config.py` adapting the `/new-project` template:
   - keep the `_require(mapping, key, expected, *, prefix)` helper shape but add a `prefix` argument
     so error messages carry the dotted path;
   - add `_require_int_ge(mapping, key, minimum, *, prefix)` and
     `_require_str_list(mapping, key, *, prefix, allow_empty)` helpers to avoid repeating range
     checks;
   - build one small `_load_<group>` function per settings group, each returning its frozen
     dataclass, then compose them in `load_settings`.
4. Write `tests/test_config.py` with a `_valid()` helper returning the full valid mapping and a
   `_write(tmp_path, data)` helper, then one test per acceptance criterion plus a test asserting
   that the repository `settings.json` itself loads.
5. Run the two commands of the last acceptance criterion.

### Key Files to Create/Modify

- `settings.json` (create)
- `src/dessem_dashboard/errors.py` (create)
- `src/dessem_dashboard/config.py` (create)
- `tests/test_config.py` (create)

### Patterns to Follow

- `from __future__ import annotations` first in every module; `X | None` over `Optional[X]`;
  `Mapping`/`Sequence` from `collections.abc` for parameters and concrete types for returns, per
  `rules/python.md`.
- `@dataclass(frozen=True)` for every settings group, so configuration cannot be mutated at runtime.
- Test names follow `test_<function>_<scenario>_<expected>`, in English.
- `pytest.raises(ConfigError, match=...)` for every error path.

### Pitfalls to Avoid

- `isinstance(True, int)` is `True` in Python: validate `bool`-typed keys **before** `int`-typed
  ones, or reject `bool` explicitly where an `int` is expected.
- `time.stage_groups` keys and values are user-facing Portuguese strings such as
  `"Leitura de Dados e Impressão"`; do not normalise, strip accents or lowercase them, since they
  must match `TEMPO.parquet` values exactly.
- Resolve paths against `path.resolve().parent`, not against `Path.cwd()`.
- Do not create `logs/` or `output/` here; `logging_setup` and `manifest` create their own
  directories.
- Do not import `logging` in `config.py` and do not log during loading: the logger is configured
  after the settings are read.

### Out of Scope

- Configuring logging or reading `logging.*` at runtime (ticket-004 consumes `LoggingConfig`).
- The CLI `--settings` flag (ticket-006).
- Documenting the keys in `README.md` (ticket-007).
- Any Parquet, chart or dashboard concern.

## Testing Requirements

### Unit Tests

`tests/test_config.py`, all in `tmp_path`, no real I/O outside `tmp_path` except the one test that
loads the repository `settings.json`:

- valid mapping loads, spot-checking one key per group (10 assertions);
- relative path resolution against the settings file directory;
- missing group raises `ConfigError` matching the group name;
- missing leaf key raises `ConfigError` matching the dotted key;
- wrong type for `output.decimals`, `chaining.stages_per_deck` and `charts.disabled`;
- `logging.level = "VERBOSO"` raises `ConfigError` matching `VERBOSO`;
- `chaining.stages_per_deck = 0` raises `ConfigError`;
- `costs.total_parcels = []` raises `ConfigError`;
- malformed JSON raises `ConfigError` chained from `json.JSONDecodeError`;
- missing file raises `ConfigError` naming the resolved path.

### Integration Tests

None beyond the test that loads the real `settings.json` from the repository root.

## Definition of Done

- [ ] The four files exist and all five acceptance criteria pass.
- [ ] `.venv/bin/ruff check src tests` and `.venv/bin/ruff format --check src tests` exit 0.
- [ ] `.venv/bin/mypy src` exits 0.
- [ ] `settings.json` matches Appendix B of the master plan key for key, with no extra keys.
- [ ] Every `ConfigError` message is Portuguese and names the offending dotted key.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 30 minutes
