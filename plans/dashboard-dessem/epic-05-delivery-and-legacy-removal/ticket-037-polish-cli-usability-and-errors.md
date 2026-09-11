# ticket-037 Polish the CLI usability and error messages

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md. Identifiers, comments,
> docstrings and test names in English; **every string this ticket emits to an operator is
> Portuguese**, matching the 66 `raise` sites, 10 `logger.warning` sites and 15 `log_step` lines
> already shipped.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-036 and strictly before ticket-038.** It must not run
> concurrently with ticket-033, which also modifies `cli.py` and `tests/test_cli.py`, nor with
> ticket-036 or ticket-038, both of which edit `README.md`.
> **Never read anything under `exemplo/`.** This ticket is fully exercised by the synthetic fixtures.

## Context

### Background

The operator-facing surface is already large and already consistent, and refinement measured it
rather than assuming it needed an audit. In `src/dessem_dashboard`: **66 `raise <...>Error` sites**
(27 `ConfigError`, 12 `StoreError`, 9 `SchemaError`, 8 `RegistryError`, 4 `DiscoveryError`, 2
`DataFileError`, 4 `ValueError`), **10 `logger.warning` sites** (9 before the epic-04 boundary
review added the `time.unit_divisor` mismatch warning to `dashboard/scalars.py`), **15 distinct
`log_step` INFO messages** and **8 degradation-warning shapes** pushed into `DashboardData` and
rendered in the
dashboard's `Avisos` section. Every message is Portuguese, every one names the offending value or
the dotted settings key, and dates in all of them are `%d/%m/%Y` (epic-02 learnings section 2
records the shipped vocabulary). `ruff`'s `TRY003` is deliberately deselected in `pyproject.toml`
precisely so that those messages can name the key.

So the outline's first question — "a single message style: whether errors name the offending value
first or the expected value first" — is **not** worth reopening. A rewrite of 66 messages would
change text that the test suite asserts in dozens of places, for a stylistic gain no requirement
asks for, and epic-02 learnings section 2 already fixed the dialect. This ticket therefore adds
output and changes none, with the diff discipline of requirement 7 enforcing it.

What is genuinely missing is **three gaps, all found by reading the shipped code**:

1. **The degradation record never reaches the log or the console.**
   `DashboardData.add_warning(message)` appends to a list and de-duplicates by message; it does
   **not** log. Those messages reach exactly two places: the HTML `Avisos` section, via
   `builder._warnings_section`, and — after ticket-033 — `run_manifest.json`, via
   `RunResult.warnings`. An operator watching the console of an official run sees **nothing** about a
   missing deck, a missing file or an absent entity. CLAUDE.md requires audit-grade logging that
   lets one "reconstruct what an official run did"; a run that silently dropped a deck currently
   reconstructs as a clean run unless someone opens the HTML.
2. **The console does not say where the artefact went in a machine-readable way.** `write_dashboard`
   logs `Dashboard HTML escrito em disco  caminho=… bytes=… tamanho_mib=…`, which is a log line
   whose format is rich-decorated and not pipeable. `rules/python.md` explicitly permits the one
   thing that would fix it: "A short CLI printing its **final result** to stdout is fine;
   audit/progress/diagnostics go through `logging`." Nothing is printed to stdout today — the single
   `print` in `src/` is `cli.py:116`, the `ConfigError` message on **stderr**.
3. **`--help` has no example.** `build_parser` sets `prog` and `description` and six arguments with
   Portuguese help strings, and no `epilog`. The one command an operator needs is the one the README
   and `docs/checklist-manual-dashboard.md` both carry, and it is not reachable from `--help`.

The outline's last question — "are the warnings grouped by cause in the summary, since a missing
deck can generate one warning per chart and flood the console at 23 charts" — is **based on a false
premise, corrected here**. A missing **deck** produces exactly **one** warning, from
`timeline.align_deck_dates`: `Cenário '<label>' não possui deck para a data <dd/mm/yyyy>, presente
em outro(s) cenário(s)`. It is a missing **file** that warns per chart: `consolidate._load_series`
adds one message per SERIES chart and `consolidate._load_scalars` one per SCALAR chart, so a
(scenario, deck) whose synthesis folder is empty yields up to **23** distinct messages — and with
two scenarios and two decks, up to **92**. Epic-02 learnings section 3 records this three-case split
and warns that it "must not be collapsed". Requirement 2 therefore caps the *log* output rather than
grouping the *messages*: grouping would mean changing `consolidate.py`, an epic-02 module, and the
epic's scope excludes it.

### Relation to Epic

The last behavioural ticket of the plan and of the feature: after it, the only remaining work is
deleting the superseded scripts. It closes the audit loop ticket-033 opened — 033 put the warnings
into the manifest, 037 puts them in front of the operator — and it is the last chance to make a
normal run readable at a glance before the project is handed over.

### Current State

`cli.build_parser()` builds an `argparse.ArgumentParser` with
`prog="dessem-dashboard"`, a Portuguese `description`, no `epilog`, no explicit
`formatter_class`, and six arguments: `--casos` (`nargs="+"`, `type=Path`, `required=True`,
`metavar="DIRETORIO"`), `--saida`, `--referencia`, `--settings` (default `Path("settings.json")`),
`--modo-inicial` (`choices=("deck", "encadeado")`, default `"encadeado"`) and `--nivel-log`
(`choices` over the five level names, default `None`).

`cli.main(argv)` in order: parses; loads settings inside `try/except ConfigError` that
`print(str(err), file=sys.stderr)` and `raise SystemExit(2) from err`; calls `setup_logging(...)`
once; resolves labels through `_resolve_labels`, which calls `parser.error` (exit 2) on a duplicate
basename; resolves `reference` and calls `parser.error` on an unknown one; resolves `output_file`
and creates its parent; builds the `params` dict; times `pipeline.run` with `time.perf_counter`
inside `try/except DashboardError` that calls `logger.exception("Falha ao executar o pipeline do
dashboard")` and `return 1`; calls `write_run_manifest(...)`; emits
`logger.info("Manifesto de execução escrito em %s", manifest_path)`; returns `0`.

So there are exactly **three exit codes**: `0`, `1` for a `DashboardError`, and `2` for an argparse
or configuration error. `_resolve_labels`' duplicate-basename check duplicates a rule
`discovery.discover_scenarios` also enforces, with different wording; after ticket-033 the CLI check
runs first, so the library one becomes unreachable from the CLI while remaining a valid library
invariant. Both are correct at their own layer and requirement 8 keeps both.

`tests/test_cli.py` holds 12 tests, five of them amended by ticket-033. Three use `capsys` and
assert only on `.err`: `"--casos"`, `"caso_z"`, `"caso_a"`, plus
`"settings.json inválido" in captured.err` with `"Traceback" not in captured.err` and
`"Traceback" not in captured.out`. One asserts `"cenário" in build_parser().format_help()` and the
presence of all six flag strings. **No test asserts the text of
`"Manifesto de execução escrito em %s"`** — measured with `grep -rn "Manifesto" tests/` — so that
one line may be restructured. `logging_setup.log_step(logger, message, *, elapsed_s=None, **fields)`
renders `message  key=value  key=value  (0.123 s)` and is the established shape for a step line.

Measured gate state before this ticket: **602 tests** collected (601 before the epic-04 boundary
review), a full run measured at 589 s / 564 s / 618 s across three runs — budget **about
10 minutes** — with 99 percent total coverage and `cli.py` at **100 percent**;
`ruff check src tests`, `ruff format --check src tests` (57 files) and `mypy src` (26 source files)
all exit 0. Re-measure every one of these; each went stale at least once during this plan.

## Specification

### Requirements

1. Add an `epilog` to `build_parser()` with `formatter_class=argparse.RawDescriptionHelpFormatter`,
   carrying one worked Portuguese example — the same command the README and
   `docs/checklist-manual-dashboard.md` step 12 already use,
   `dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi` — plus one sentence saying
   that the first `--casos` directory is the reference scenario unless `--referencia` says otherwise,
   and one sentence naming `settings.json` as the source of every path and tunable. Add no new
   argument and change no existing `help` string.
2. In `cli.main`, after `pipeline.run` returns and before the manifest is written, emit each distinct
   message of `result.warnings` as one `logger.warning` line, capped by a module-level constant
   `_MAX_LOGGED_WARNINGS = 20`. When the list is longer, log the first 20 and then exactly one
   further Portuguese `logger.warning` naming how many were omitted and where the complete list
   lives — `run_manifest.json` and the dashboard's `Avisos` section. The cap exists because a
   (scenario, deck) with an empty synthesis folder produces up to 23 messages, and four such
   combinations produce up to 92; the full list is preserved in two places, so truncating the
   console does not lose the audit trail.
3. Replace `cli.main`'s final `logger.info("Manifesto de execução escrito em %s", manifest_path)`
   with one `log_step` line reporting the run's artefacts: the resolved output file, the manifest
   path, the warning count and the elapsed seconds. Keep the substring `Manifesto` somewhere in the
   message so a reader grepping the log for it still finds it. Do **not** repeat the six data
   volumes here — `pipeline.run`'s own closing `log_step` (ticket-033 requirement 4) already reports
   them, and two lines carrying the same fields is the duplication this ticket exists to avoid.
4. Print the resolved output path to **stdout**, as exactly one line containing nothing but the path,
   and only on the success path immediately before `return 0`. `rules/python.md` permits a short CLI
   printing its final result to stdout; `ruff`'s `T201` is already deselected in `pyproject.toml`
   for the existing stderr `print`. Every failure path must leave stdout **empty**, so
   `dessem-dashboard ... > /dev/null` and `saida=$(dessem-dashboard ...)` both behave.
5. Keep exactly **three** exit codes and record the decision: `0` on success **including a degraded
   run**, `1` for a `DashboardError`, `2` for an argparse or configuration error. A warning must
   **not** change the exit code. Master plan decision 18 makes a degraded run a deliberate success —
   "a partially comparable dashboard is more useful than none" — and a batch caller that needs to
   detect degradation reads `run_manifest.json`'s `warnings` array, which is machine-readable, is
   already written, and is complete where the console is capped. Add a test that a run with one
   scenario missing a deck exits `0` and leaves a non-empty `warnings` array.
6. Reject, and record each rejection with its reason in the ticket's completion report:
   `--quiet` / `--verbose` (`--nivel-log` already spans the five level names and a second mechanism
   would need a precedence rule); `--dry-run` (`output_volumes`' `bytes_html` stats a written file,
   so a dry run would need a second volumes shape, and the CLI surface is fixed by the spec plus
   ticket-006); grouping warnings by cause (it would change `consolidate.py`, an epic-02 module, and
   epic-02 learnings section 3 forbids collapsing the three-case split); a fourth exit code for a
   degraded run (requirement 5); and `KeyboardInterrupt` handling (unrequested behaviour, and the
   default traceback is the honest signal for an interrupted official run).
7. **The diff to `src/` must be additive in operator-facing text.** No existing Portuguese string
   may be deleted or reworded, with exactly one authorised exception: the
   `"Manifesto de execução escrito em %s"` line that requirement 3 restructures, which no test
   asserts (measured). Verify with `git diff -U0 src/ | grep '^-'` and confirm that every removed
   line is either that one `logger.info` call or code carrying no operator-facing text.
8. `errors.py` stays at exactly **seven** classes — `DashboardError`, `ConfigError`, `SchemaError`,
   `DataFileError`, `RegistryError`, `DiscoveryError`, `StoreError`. This ticket needs no eighth:
   every condition it touches already has one, and epic-02 learnings section 9 requires a ticket
   adding a class to append it and prove it. Do not consolidate `cli._resolve_labels`' duplicate-
   basename check with `discovery.discover_scenarios`' own: both are correct at their own layer, the
   CLI one produces argparse's exit 2 with usage text and the library one guards a public function
   called by tests.
9. Extend `tests/test_cli.py` with the new cases under Testing Requirements. Every one of the 12
   existing tests — including the five ticket-033 amended — must pass **unchanged**; requirement 7
   is what guarantees it, and if one fails, that is a finding to report rather than a test to edit.
10. Update the three places in `README.md` that this ticket invalidates, and only those: the flag
    table or the How-to-run section gains the `--help` example note, the run-output description gains
    the stdout line and its pipeable contract, and the Logging section gains the per-warning lines,
    the cap and the statement that the complete list lives in the manifest and in `Avisos`. Change
    no other README text: ticket-036 rewrote the file two tickets ago and its content is otherwise
    current.

### Inputs

`sys.argv` through `argparse`; the loaded `Settings`; `pipeline.RunResult`'s `output_file`,
`data_volumes` and `warnings`; the manifest path returned by `write_run_manifest`. No new settings
key and no environment variable.

### Outputs and Behavior

A successful run prints exactly one line to stdout — the resolved output path — and writes to the
console and the rotating log file: the 15 existing `log_step` lines, `pipeline.run`'s closing volume
line, up to 20 `logger.warning` lines plus at most one truncation line, and one closing artefact
line naming the output file, the manifest and the warning count. `--help` ends with a worked
example. A `DashboardError` still logs a traceback into the log file and returns `1` with stdout
empty; a malformed `settings.json` still prints its Portuguese message to stderr and exits `2` with
stdout empty; a duplicate `--casos` basename and an unknown `--referencia` still exit `2` through
`parser.error` with stdout empty.

### Error Handling

No new exception, no new handler, no new exit code. The two existing handlers stay exactly as they
are: `except ConfigError` around `load_settings` (stderr `print`, `SystemExit(2)`, no traceback on
stderr) and `except DashboardError` around `pipeline.run` (`logger.exception`, `return 1`). Bare
`except` and `except Exception` remain banned by `rules/python.md`. The new `logger.warning` loop
cannot raise: it iterates a `list[str]` that `pipeline.run` built from `DashboardData.warnings()`.

## Dependencies

- **Blocked By**: `ticket-036-write-user-documentation.md` (requirement 10 edits the README it
  rewrote)
- **Blocks**: `ticket-038-remove-legacy-scripts.md`
- **Dispatch-order constraint, not a graph edge**: must not run concurrently with
  `ticket-033-wire-end-to-end-pipeline.md` (same `cli.py`, same `tests/test_cli.py`) or with
  `ticket-038-remove-legacy-scripts.md` (same `README.md`).

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture and a settings file whose `paths.logo_file` is the
      repository logo, when `main(["--casos", <caso_a>, <caso_b>, "--settings", <path>])` runs, then
      it returns `0` and `capsys.readouterr().out.strip()` equals `str(output_file)` with no other
      character on stdout; and when the same call is made with a malformed `settings.json`, with a
      duplicate `--casos` basename and with an unknown `--referencia`, then stdout is empty in all
      three cases.
- [ ] Given a tree in which `caso_b` has only the first deck, when `main` runs over both scenarios,
      then it returns `0`, `run_manifest.json`'s `warnings` array is non-empty, at least one
      `WARNING` record of the `dessem_dashboard.cli` logger contains both `caso_b` and `04/03/2024`,
      and the rotating log file at `logging.file` contains that same message text.
- [ ] Given a `RunResult` carrying 25 distinct warnings, when `main` processes it, then exactly 20
      `WARNING` records of the `dessem_dashboard.cli` logger reproduce individual messages, exactly
      one further `WARNING` names the number `5` and mentions both `run_manifest.json` and `Avisos`,
      and the manifest's `warnings` array still holds all 25 — proving the cap truncates the console
      and not the audit trail.
- [ ] Given `build_parser().format_help()`, when it is inspected, then it still contains all six
      flag strings and the word `cenário` (the existing assertion), and it additionally contains
      `--casos exemplo/caso_oficial exemplo/caso_gurobi` and the word `referência`; and
      `errors.py` still declares exactly seven classes, verified with
      `grep -c "^class " src/dessem_dashboard/errors.py` returning `7`.
- [ ] Given the whole repository, when `git diff -U0 src/ | grep '^-'` is inspected, then every
      removed line is either the single `logger.info("Manifesto de execução escrito em %s", ...)`
      call or a line carrying no operator-facing string; and
      `.venv/bin/pytest tests/test_cli.py tests/test_pipeline.py tests/test_manifest.py
      tests/test_logging_setup.py -q && .venv/bin/mypy src && .venv/bin/ruff check src tests`
      exits 0 with the 12 pre-existing `tests/test_cli.py` tests passing unchanged.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Do the `epilog` first — it is three lines, it cannot break anything, and it gives an immediate
   check that `RawDescriptionHelpFormatter` is preserving the newlines you intend. Keep the example
   inside a plain indented block in the epilog string; argparse will not reflow it under that
   formatter.
2. Add the warning loop as a small private helper, `_log_warnings(messages)`, so `main` stays
   readable and the cap logic is unit-testable without building a dashboard. Put
   `_MAX_LOGGED_WARNINGS` beside `_LOG_LEVELS` and `_VIEW_MODES` at module level, with a comment
   giving the measured reason for the number: 23 enabled charts, up to 23 messages per (scenario,
   deck).
3. Write the truncation message so it names the count of omitted messages, not the total, and names
   both surviving locations. A message saying "92 avisos" when 20 were shown tells the operator
   less than one saying "72 aviso(s) adicional(is)".
4. Restructure the manifest line into `log_step(logger, "<...>Manifesto<...>", saida=…,
   manifesto=…, avisos=…, elapsed_s=…)`, using the same Portuguese field-name style as the 15
   existing lines (`caminho`, `cenarios`, `decks`, `graficos`, `valores`, `bytes`, `tamanho_mib`).
   Do not re-log the volumes.
5. Put the stdout `print` on the last line before `return 0`, after the manifest write and after the
   closing `log_step`, so a caller capturing stdout gets the path only once every artefact exists.
   Use `print(output_file)` with no prefix, no label and no trailing text: the value of a pipeable
   line is that it is exactly the path.
6. For acceptance criterion 3, do not build 25 real warnings — monkeypatch `pipeline.run` to return
   a `RunResult` with 25 synthetic messages, following the existing
   `test_main_dashboard_error_from_pipeline_is_logged_and_returns_1` pattern, which already
   monkeypatches `pipeline.run` with a `def _raise(**_: object)` signature. That keeps the test fast
   and makes the cap the only thing under test.
7. For criterion 2, build the degraded tree by calling `make_sintese_dir` for `caso_a`'s two decks
   and only the first deck of `caso_b`, rather than deleting anything from a fixture. The expected
   message text is `Cenário 'caso_b' não possui deck para a data 04/03/2024, presente em outro(s)
   cenário(s)` — assert on the two substrings, not the whole sentence, so a future rewording of the
   library message does not fail a CLI test.
8. Assert the log **file** as well as `caplog` in criterion 2. `caplog` proves the record was
   emitted; reading `tmp_path/logs/dashboard.log` proves the rotating handler wrote it, which is the
   audit requirement. `tests/test_cli.py` already reads that file in two tests.
9. Run `git diff -U0 src/ | grep '^-'` before declaring done and read every removed line. That is
   requirement 7's gate and it takes five seconds.
10. Prove the new assertions can fail: set `_MAX_LOGGED_WARNINGS` to 100 and confirm criterion 3's
    "exactly 20" fails; delete the `print` and confirm criterion 1 fails; move the `print` before the
    `except DashboardError` return and confirm criterion 1's empty-stdout-on-failure half fails;
    remove the `referência` sentence from the epilog and confirm criterion 4 fails. Restore each.
11. Update the three README places last, with the CLI already final, and keep the diff to those three
    places — verify with `git diff README.md` before committing.

### Key Files to Create/Modify

- `src/dessem_dashboard/cli.py` (modify: the `epilog` and `formatter_class`, `_MAX_LOGGED_WARNINGS`,
  the `_log_warnings` helper and its call, the restructured artefact `log_step`, the stdout `print`)
- `tests/test_cli.py` (modify: four new tests; the 12 existing ones untouched)
- `README.md` (modify: three enumerated places only)

### Patterns to Follow

- `log_step(logger, "<Portuguese sentence>", campo=valor, elapsed_s=...)` exactly as the 15 existing
  call sites use it: a capitalised Portuguese sentence, `snake_case` Portuguese field names,
  `elapsed_s` last.
- The Portuguese vocabulary of epic-02 learnings section 2 — `cenário`, `deck`, `gráfico`, `aviso`,
  `%d/%m/%Y` dates — and the message shape of `scalars.py`'s warnings, which name the dotted settings
  key.
- `cli.py`'s own existing structure: module-level `_UPPER_CASE` constants for the argparse choice
  tuples, small private helpers with docstrings stating the exit code they cause, and one `try` per
  failure class.
- `tests/test_cli.py`'s `monkeypatch.setattr(pipeline, "run", ...)` pattern for injecting a
  `RunResult`, and its `_isolated_root_logger` autouse fixture, which snapshots and restores the root
  logger around every test — required, because `setup_logging` clears the root handlers.
- `rules/python.md`: a short CLI may print its final result to stdout; everything else goes through
  `logging`.

### Pitfalls to Avoid

- Do not reword or delete any existing Portuguese message. Dozens of assertions across
  `tests/test_config.py`, `tests/test_discovery.py`, `tests/test_consolidate.py`,
  `tests/test_registries.py`, `tests/test_store.py`, `tests/test_charts_costs.py` and
  `tests/test_charts_times.py` match on message fragments, and epic-02 learnings section 2 already
  settled the dialect.
- Do not print anything to stdout on a failure path. A caller doing `saida=$(dessem-dashboard ...)`
  must get an empty string when the run fails, not a half-built path.
- Do not print the path through `logger.info`. A rich-decorated, timestamped line is not pipeable,
  which is the whole point of requirement 4.
- Do not log the six data volumes again. `pipeline.run`'s closing line already carries them, and a
  duplicate is the noise this ticket is supposed to remove.
- Do not assume a missing **deck** floods the log. It produces exactly one warning; a missing
  **file** is the per-chart case. Getting this backwards is the outline's own error, corrected in
  Background.
- Do not group or rewrite the warning messages. Grouping means editing `consolidate.py`, and
  epic-02 learnings section 3 records that the three degradation cases are governed by different
  binding decisions and must not be collapsed.
- Do not make a warning change the exit code. Decision 18 makes a degraded run a success; the
  manifest is the machine-readable channel for degradation.
- Do not add an eighth class to `errors.py`, and do not remove either duplicate-basename check.
- Do not add `--quiet`, `--verbose`, `--dry-run` or a `KeyboardInterrupt` handler. Each is rejected
  with a reason in requirement 6.
- Do not truncate the manifest's warning list. The cap is on the log only, and criterion 3 asserts
  the manifest still holds all 25.
- Do not touch any README section beyond the three requirement 10 names. ticket-036 rewrote the file
  and the rest of it is current.

### Out of Scope

- Any change to a message emitted by `config.py`, `discovery.py`, `readers.py`, `registries.py`,
  `timeline.py`, `consolidate.py`, `store.py`, `scalars.py`, `payload.py` or `builder.py`.
- Any change to `consolidate.py`'s warning construction, including grouping, counting or
  deduplicating by cause.
- Any new CLI argument, any new exit code, any new settings key, any new `errors.py` class.
- Any change to `pipeline.py` — including its closing `log_step`, which ticket-033 owns.
- The legacy removal and its README note (ticket-038), and any other README section (ticket-036).
- Translating, reformatting or restructuring the 15 existing `log_step` lines.

## Testing Requirements

### Unit Tests

`tests/test_cli.py`, four new tests:

- `test_main_success_prints_only_the_output_path_to_stdout` — acceptance criterion 1, including the
  three empty-stdout failure paths;
- `test_main_degraded_run_exits_zero_and_logs_the_missing_deck_warning` — acceptance criterion 2,
  asserting `caplog` **and** the rotating log file;
- `test_main_truncates_logged_warnings_at_the_cap_and_names_the_remainder` — acceptance criterion 3,
  with `pipeline.run` monkeypatched to return 25 synthetic messages;
- `test_build_parser_epilog_carries_the_worked_example_and_the_reference_rule` — acceptance
  criterion 4's help half.

Plus the four non-vacuity mutations of Suggested Approach step 10, each observed to fail before
restoration.

### Integration Tests

None new. The end-to-end path is already covered by `tests/test_pipeline.py` (ticket-033) and
`tests/test_integration_exemplo.py` (ticket-034); this ticket adds console and stdout behaviour,
which is assertable through `capsys` and `caplog` on the synthetic fixtures.

### Regression

Every existing test module passes **unchanged**, `tests/test_cli.py`'s 12 tests included. This is a
falsifiable prediction and requirement 7 is the mechanism that makes it true: an additive diff in
operator-facing text cannot break a message assertion. If one breaks, report it.

## Definition of Done

- [ ] All five acceptance criteria pass, and the four non-vacuity mutations were each observed to
      fail and then restored.
- [ ] `git diff -U0 src/ | grep '^-'` contains no removed operator-facing string except the single
      authorised `logger.info` line, and the report quotes the command's output.
- [ ] `grep -c "^class " src/dessem_dashboard/errors.py` returns `7`.
- [ ] A successful run prints exactly one line to stdout and every failure path prints none.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
      `.venv/bin/mypy src` exit 0; `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing`
      passes with total coverage at or above **85 percent** and `cli.py` at 100 percent, which it is
      today.
- [ ] The completion report records the five rejections of requirement 6 with their reasons, the
      collected test count from `pytest --collect-only -q`, and the exact `_MAX_LOGGED_WARNINGS`
      value with the measured justification.
- [ ] `git status --short` shows only `src/dessem_dashboard/cli.py`, `tests/test_cli.py` and
      `README.md`.

## Amendment of 2026-09-11 — requirement 11, after the guardian rejected this ticket

**The stdout contract this ticket exists to deliver does not hold under the shipped default
configuration.** Acceptance criterion 1 and requirement 4 promise that a successful run prints
exactly the output path to stdout, so that `saida=$(dessem-dashboard ...)` works — and the README
paragraph this ticket added states that promise to the operator. Measured from a real subprocess
with the streams separated, under the shipped `settings.json`:

```
$ dessem-dashboard --casos caso_a caso_b --settings settings.json --saida out/d.html \
    >only_stdout.txt 2>only_stderr.txt ; echo $?
0
stdout: 47-53 lines (the whole Rich log, with the path merely last)
stderr: 0 lines
```

### The mechanism, pinned

- `logging_setup._build_console_handler` constructs `RichHandler(rich_tracebacks=True,
  show_path=False)` with **no `console=` argument**, so it uses a default `rich.console.Console()`.
  Measured: `Console().file` is `<stdout>`, `Console(stderr=True).file` is `<stderr>`, and the
  fallback `logging.StreamHandler()` is already `<stderr>`.
- So the defect exists **only when `rich` is importable and `logging.use_rich` is true** — which is
  `settings.json`'s shipped value and the configuration of every real run.
- **The orchestrator's first explanation of why no test caught it was wrong, and the guardian
  disproved it by experiment.** The orchestrator said pytest's logging capture intercepts the
  handler. It does not: `capsys` captures the pollution perfectly well under `use_rich: True`. The
  real reason is narrower and worse — `tests/test_cli.py`'s `_settings_dict` hardcodes
  `"use_rich": False`, so **the one module that drives `cli.main` end to end is the one module that
  detunes the logging configuration**, and the buggy path is never entered. Every other test module
  sets `True`.
- A finer unowned correspondence sits underneath: `tests/test_logging_setup.py` asserts that
  `use_rich=True` selects a `RichHandler` — the handler's **type** — and nothing anywhere asserts
  which **stream** it writes to.

This is the plan's signature defect class once more: the stdout contract belongs to this ticket, the
handler's stream was chosen in ticket-004, each is correct alone, and nothing asserted the pairing.

### Requirement 11 — what to change

1. In `src/dessem_dashboard/logging_setup.py`, pass an explicit stderr console to the handler:
   `RichHandler(console=Console(stderr=True), rich_tracebacks=True, show_path=False)`. This file is
   **outside this ticket's original Key Files list**, which is why it needs this amendment rather
   than a silent patch. Change nothing else in that module: the rotating file handler, the level
   handling and the fallback all stay exactly as they are.
2. Add a regression test that would have caught this on day one, under the **shipped** default
   rather than the suite's convenience value: drive `cli.main` with a settings dict whose
   `logging.use_rich` is `True` and assert `capsys.readouterr().out.strip()` equals the output path
   exactly. Put it wherever it reads best — `tests/test_cli.py` alongside the existing stdout test,
   or `tests/test_logging_setup.py` next to the handler-type assertions — and say which and why.
3. **Prove it discriminates**: revert the `Console(stderr=True)` argument, confirm the new test
   fails, restore. A test that passes both with and without the fix is worth nothing here, and this
   ticket has already produced one vacuous assertion that only running the mutation exposed.
4. Leave `tests/test_cli.py`'s existing `use_rich: False` as it is for the other tests. Flipping it
   suite-wide would change captured output for sixteen tests to no purpose; the new test carries the
   shipped configuration on its own.
5. `rules/python.md` is the authority for the split being fixed here: a short CLI printing its final
   result to stdout is fine, and audit, progress and diagnostic output goes through logging. Sending
   the log to stderr is what makes both halves true at once.

### What stays

Nine of ten requirements, three of four acceptance criteria, the diff discipline, the class count,
the five rejected features and all five mutations were verified and passed. The guardian was
explicit that this is not sloppy work. Re-verify only requirement 4, acceptance criterion 1, and the
two Definition-of-Done items that depend on them.

## Effort Estimate

**Points**: 2 · **Confidence**: High · **Agent time**: about 30 minutes. Unchanged from the
outline's 2 points, and the reason it stayed small is that refinement **removed** the largest item
the outline implied. The outline's first key decision — settle "a single message style" across the
error surface — would have meant auditing 66 `raise` sites and rewording messages that dozens of
tests assert; measurement showed the dialect is already consistent, already names the offending key,
and is already recorded in epic-02 learnings section 2, so the ticket became purely additive.
Three of the outline's questions resolve to no (`--quiet`/`--verbose`, a warning-driven exit code,
warning grouping) and two to yes (the stdout path, which `rules/python.md` explicitly permits, and
the end-of-run summary, narrowed to the artefacts because ticket-033 already reports the volumes).
Refinement also corrected a false premise in the outline — it is a missing *file*, not a missing
*deck*, that produces one warning per chart — and found the gap that justifies the ticket at all:
`DashboardData.add_warning` never logs, so today the degradation record reaches the HTML and the
manifest but never the operator's console. Confidence is High: the whole diff is inside one module
that is already at 100 percent coverage, and every assertion is decidable with `capsys` and `caplog`.
