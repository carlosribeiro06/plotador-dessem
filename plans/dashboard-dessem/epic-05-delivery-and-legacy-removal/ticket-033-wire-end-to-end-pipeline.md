# ticket-033 Wire the end-to-end pipeline

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `python-task-automation-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: first ticket of the epic, strictly before ticket-034.** The whole epic is
> sequential; nothing here may run in parallel with another epic-05 ticket, because 034 tests what
> this ticket builds and 037 edits the same `cli.py` and the same `tests/test_cli.py`.
> **Never read, write, list or copy anything under `exemplo/`.** This ticket is fully exercised by
> the synthetic fixtures; the real tree belongs to ticket-034.

## Context

### Background

Every stage of the pipeline exists and is unit-tested, and none of them is connected. `pipeline.run`
still carries the Epic 1 stub: it logs the three resolved arguments through `log_step` and returns
`RunResult(output_file=output_file, data_volumes={"cenarios": len(scenario_dirs)})`, with its
`settings` parameter carrying a literal `# noqa: ARG001` because nothing reads it. Its own comment
names this ticket as the owner of the replacement, and `builder.plotly_bundle_bytes`' and
`builder.output_volumes`' docstrings both forward-reference "ticket-033's `pipeline.RunResult`".

The consequence today, measured: `dessem-dashboard --casos <dir>` reads **no Parquet file** and
produces **no HTML**. It writes only `logs/dashboard.log` and `output/run_manifest.json`, and the
README says so in a paragraph headed "Current output" that this ticket makes false (ticket-036
rewrites it).

Two settings keys and one CLI flag have **no consumer in `src/` at all**, verified by grep, and this
ticket is the only place where they can acquire one:

- `settings.discovery.sintese_dirname` — `discovery.discover_scenarios` takes it as
  `sintese_dirname: str = "sintese"` and has **zero call sites in `src/`**
  (`grep -rn "discover_scenarios" src/` matches only a docstring in `data/consolidate.py`). Every
  caller today is a test, and `tests/test_output_size.py::_build_data` calls
  `discover_scenarios(list(paths))` without the argument. A run that omits it would silently ignore
  a configured synthesis folder name.
- `--modo-inicial` — `cli.build_parser` declares it with `choices=("deck", "encadeado")` and
  `default="encadeado"`, `cli.main` records it in the manifest `params` as `modo_inicial`, and then
  **calls `pipeline.run` without it**. `pipeline.run` has no such parameter, and
  `builder.build_html` / `builder.write_dashboard` default `initial_mode` to `"encadeado"`. So the
  flag is accepted, documented in the README flag table and recorded in the manifest, and **changes
  nothing in the output**. This is the same class of defect as the `TEMPO` axis labelled `min` while
  carrying seconds (epic-03 learnings section 7a): two halves each correct in their own ticket, with
  no ticket owning the correspondence. Requirement 3 and acceptance criterion 3 make this ticket
  own it.
- `settings.paths.log_dir` is a third key with no consumer, and it is **not** this ticket's to fix:
  `logging.file` already carries a full path and `logging_setup.setup_logging` creates its parent.
  Documenting it honestly belongs to ticket-036; changing the settings contract is out of the epic's
  scope.

The third gap is the audit trail. `DashboardData.add_warning` appends to a list, de-duplicating by
message, and **never logs**. `builder._warnings_section` renders those messages into the HTML
`Avisos` section, and `manifest.write_run_manifest` takes a `warnings` argument that `cli.main`
already passes as `result.warnings` — which the stub leaves empty by default. So today the
degradation record reaches neither the log file nor the manifest. This ticket routes it into the
manifest and logs the **count**; ticket-037 owns making each message visible on the console and in
the rotating log file.

### Relation to Epic

The epic's first ticket and the precondition for every other one: ticket-034 runs this pipeline
against real data, ticket-035 compares its values against the legacy formulas, ticket-036 documents
what it does, and ticket-037 polishes the console output around it. It adds no chart, no payload key
and no settings key — it is pure composition of functions whose contracts are already pinned by 602
tests (measured with `pytest --collect-only -q` after the epic-04 boundary review landed; it was
601 before that review added one test to `tests/test_charts_times.py`).

### Current State

```python
# src/dessem_dashboard/pipeline.py (whole body, as shipped)
@dataclass(frozen=True)
class RunResult:
    output_file: Path
    data_volumes: dict[str, int]
    warnings: list[str] = field(default_factory=list)


def run(
    *,
    scenario_dirs: Sequence[Path],
    output_file: Path,
    reference: str,
    settings: Settings,  # noqa: ARG001
) -> RunResult:
    # Epic 5 ticket-033 replaces this body with parquet reading, consolidation and HTML generation.
    for scenario_dir in scenario_dirs:
        log_step(logger, "cenário recebido", diretorio=str(scenario_dir))
    log_step(logger, "arquivo de saída resolvido", saida=str(output_file))
    log_step(logger, "cenário de referência resolvido", referencia=reference)
    return RunResult(output_file=output_file, data_volumes={"cenarios": len(scenario_dirs)})
```

The four functions to compose, with their real signatures as shipped:

```python
# dessem_dashboard.data.discovery
discover_scenarios(paths: Sequence[Path], *, sintese_dirname: str = "sintese") -> tuple[ScenarioRef, ...]
# dessem_dashboard.data.consolidate
build_dashboard_data(scenarios: Sequence[ScenarioRef], *, settings: Settings, reference: str) -> DashboardData
# dessem_dashboard.dashboard.builder
write_dashboard(data: DashboardData, *, settings: Settings, output_file: Path, initial_mode: str = "encadeado") -> Path
output_volumes(data: DashboardData, *, settings: Settings, output_file: Path) -> dict[str, int]
```

`output_volumes` returns exactly six `int` keys in this order — `cenarios`, `decks`, `graficos`,
`valores`, `bytes_html`, `bytes_plotly` — and `bytes_html` is `output_file.stat().st_size`, so it
**must** be called after `write_dashboard`. Its docstring already states that the mapping is
"directly usable as `manifest.write_run_manifest`'s `data_volumes` argument and as ticket-033's
`pipeline.RunResult.data_volumes`". `tests/test_output_size.py::test_output_volumes_round_trips_through_write_run_manifest`
already proves that round trip; this ticket does not re-prove it.

Per-stage timing is **already instrumented** and must not be duplicated. `log_step(..., elapsed_s=)`
call sites in the chain, counted per module: `data/discovery.py` 2, `data/timeline.py` 2,
`data/registries.py` 1, `data/consolidate.py` 6, `dashboard/payload.py` 2, `dashboard/builder.py` 2.
`pipeline.py` has 3 (the stub's own). A second timing layer around each phase would put two INFO
lines on every step of an audited run.

`cli.main` already: loads settings, calls `setup_logging` once, resolves labels with its own
duplicate-basename check (`_resolve_labels`, exit 2), resolves `reference` and rejects an unknown
one (exit 2), resolves `output_file` and creates its parent, times `pipeline.run` with
`time.perf_counter`, catches `DashboardError` into `return 1` with `logger.exception`, and calls
`write_run_manifest(settings.paths.output_dir, params=params, elapsed_s=elapsed_s,
data_volumes=result.data_volumes, warnings=result.warnings)`. None of that changes except the one
new argument of requirement 3.

`tests/test_cli.py` holds 12 tests. Four of them build scenario directories with `caso_a.mkdir()`
and **no deck at all**, then assert `exit_code == 0`; one asserts
`result.data_volumes == {"cenarios": 3}` over three directories that do not exist on disk. Measured
against the real chain: `discover_scenarios` on a directory with no immediate subdirectory holding a
`sintese/` child raises

```text
DiscoveryError: Cenário 'caso_a' não contém nenhum deck: nenhum subdiretório imediato de
'/tmp/.../caso_a' possui uma pasta 'sintese'
```

and `DiscoveryError` is a `DashboardError`, which `cli.main` turns into `return 1`. Reading each of
the 12 tests against the new code path identifies **five** that this ticket's requirements force to
change (requirement 6 lists them by name) and seven that hold unchanged. That count was derived by
reading, not by running: requirement 6 therefore makes running the module the **first** step, before
any test is edited, and makes the specialist report the actual failure list. Three of the plan's
twenty-one spec defects were exactly this — a claim about the suite made without running it.

`tests/test_cli.py::_settings_dict()` sets `"logo_file": "logo/MarcasONS_Secundarias_verticais_Verde.png"`
and its docstring states that every path is relative so that all three resolve inside the temporary
directory. Once the pipeline builds a real document, `builder._logo_data_uri` resolves that relative
path under `tmp_path`, finds no file, and raises `ConfigError` naming `paths.logo_file`. The helper
must point at the repository logo, and **its docstring must stop claiming otherwise in the same
edit** — a test helper whose docstring misdescribes it is spec defect 20 in this plan's catalogue.
`tests/test_output_size.py` already has the pattern to copy:

```python
_REPO_LOGO = (
    Path(__file__).resolve().parent.parent / "logo" / "MarcasONS_Secundarias_verticais_Verde.png"
)
```

`tests/conftest.py` provides the `scenario_tree` fixture: `caso_a` and `caso_b`, each with
`deck_um` (2024-03-03) and `deck_dois` (2024-03-04), `n_stages=50, half_hour_stages=48,
long_stage_hours=6.0`, one distinct seed per (scenario, deck). `enabled_specs()` returns **23**
specs (measured by running it), so a full fixture build writes 23 chart sections and a document of
about 4.5 MB, of which about 4.3 MB is the inlined plotly bundle (epic-03 learnings section 5
measured `plotly.offline.get_plotlyjs()` at 4,293,280 chars on the installed version; re-measure
with `builder.plotly_bundle_bytes()` rather than trusting that figure).

## Specification

### Requirements

1. Replace `pipeline.run`'s body with the real chain, in exactly this order, and remove the
   `# noqa: ARG001` from the `settings` parameter:
   `discover_scenarios(scenario_dirs, sintese_dirname=settings.discovery.sintese_dirname)` →
   `build_dashboard_data(scenarios, settings=settings, reference=reference)` →
   `write_dashboard(data, settings=settings, output_file=output_file, initial_mode=initial_mode)` →
   `output_volumes(data, settings=settings, output_file=output_file)`. `output_volumes` must be
   called **after** `write_dashboard`, because its `bytes_html` value stats the written file. Keep
   the existing `RunResult` dataclass exactly as it is: no new field, no changed type.
2. Return `RunResult(output_file=<the Path write_dashboard returned>, data_volumes=<the
   output_volumes mapping>, warnings=list(data.warnings()))`. `data.warnings()` returns
   `tuple[str, ...]` and `RunResult.warnings` is `list[str]`, so the conversion is explicit. This is
   what puts the degradation record into `run_manifest.json`, which `cli.main` already writes from
   `result.warnings`.
3. Add a keyword-only `initial_mode: str = "encadeado"` parameter to `pipeline.run` and pass
   `args.modo_inicial` from `cli.main`. The default matches `build_html`'s and `write_dashboard`'s
   own default and argparse's `default="encadeado"`, so the three agree by construction. Do **not**
   add validation here: `argparse`'s `choices` and `builder._validate_initial_mode` already cover it,
   and `_validate_initial_mode`'s docstring states that reaching it with another value is a
   programming error rather than an operator error.
4. Emit exactly **one** new `log_step` INFO line at the end of `pipeline.run`, after
   `output_volumes` returns, carrying the six volume fields plus `avisos=<len of the warning list>`
   and the whole-run `elapsed_s`. Delete the stub's three `log_step` calls: `discover_scenarios`
   already logs one line per discovered scenario plus a summary, and `write_dashboard` already logs
   the resolved path. Add **no** other logging: the 15 `log_step` sites already in the chain are the
   per-stage audit trail, and a second timing layer would double every line of an audited run.
5. Create `tests/test_pipeline.py` covering `pipeline.run` directly against the `scenario_tree`
   fixture, with the cases listed under Testing Requirements. It must include the
   `discovery.sintese_dirname` non-vacuity pair of acceptance criterion 4 and the `initial_mode`
   round trip of acceptance criterion 3.
6. **Amend `tests/test_cli.py`, authorised here because this ticket's own requirements force the
   change.** Before editing anything, run `.venv/bin/pytest tests/test_cli.py -q` against the new
   `pipeline.py` and record the actual list of failures in the completion report; if it differs from
   the five below, the difference is a finding and must be reported rather than quietly absorbed.
   The five identified by reading are:
   `test_main_successful_run_writes_manifest_and_log_with_first_basename_as_reference`,
   `test_main_explicit_referencia_is_honoured_in_manifest_params`,
   `test_main_nivel_log_debug_sets_root_logger_level`,
   `test_main_default_saida_equals_settings_output_dir_and_default_filename` (all four assert
   `exit_code == 0` over scenario directories with no deck) and
   `test_pipeline_run_returns_data_volumes_matching_number_of_casos` (asserts
   `data_volumes == {"cenarios": 3}`). Rebuild each on the `scenario_tree` fixture, keeping its name
   and the property it was written to prove, and make every amended assertion **stronger** than the
   one it replaces — the `data_volumes` test becomes an assertion on the six-key set rather than a
   one-key dict. Change nothing in the seven tests that pass unchanged.
7. In the same edit, point `tests/test_cli.py::_settings_dict()`'s `paths.logo_file` at the
   repository logo through a module constant built from `Path(__file__)`, following
   `tests/test_output_size.py::_REPO_LOGO`, **and** rewrite that helper's docstring so it no longer
   claims every path is relative and resolves inside the temporary directory. `output_dir`,
   `log_dir` and `logging.file` stay relative.
8. Touch no other source file. In particular: no change to `discovery.py`, `consolidate.py`,
   `builder.py`, `payload.py`, `scalars.py`, `store.py`, `config.py`, `manifest.py`,
   `logging_setup.py`, `errors.py`, `settings.json`, `dashboard.js`, `dashboard.css`,
   `dashboard.html` or `docs/checklist-manual-dashboard.md`. `errors.py` stays at exactly seven
   classes; this ticket needs no new one.

### Inputs

From `cli.main`: `scenario_dirs` (the `--casos` paths, ≥1 guaranteed by `nargs="+"`), `output_file`
(resolved, parent already created), `reference` (validated against the label set), `settings` (a
loaded `Settings`) and `initial_mode` (`args.modo_inicial`, one of the two argparse choices). From
disk: the Parquet files under each deck's synthesis folder, and the logo file named by
`paths.logo_file`. From `settings`: `discovery.sintese_dirname`, `chaining.stages_per_deck`,
`costs.total_parcels`, `time.stage_groups`, `time.unit_divisor`, `submarkets.*`, `dashboard.*`,
`output.*` and `charts.disabled`, all consumed by the functions being composed rather than by this
module.

### Outputs and Behavior

One dashboard HTML file at `output_file`, one `RunResult` whose `data_volumes` carries the six
integer keys and whose `warnings` carries every distinct degradation message the consolidation
recorded, and one new INFO line summarising the run. `cli.main` then writes `run_manifest.json` with
those volumes and warnings and returns 0. With `--modo-inicial deck` the document's `<body>` carries
`data-initial-mode="deck"` and the deck `<select id="deck-selector">` carries no `disabled`
attribute; with `encadeado` (the default) the attribute reads `encadeado` and the selector is
`disabled`. A scenario with zero decks, a duplicate scenario basename reaching the library, a
malformed Parquet schema or a missing logo raises the corresponding `DashboardError` subclass, which
`cli.main` logs with a traceback into the log file and turns into exit code 1.

A run in which every source file is missing still writes a valid HTML document with 23 empty charts
and one `Avisos` entry per (chart, scenario, deck), and still exits 0. That is master plan decision
18 — a missing file or a missing deck degrades to a warning plus a gap — and this ticket must not
convert it into a failure.

### Error Handling

No new exception type and no new `try`/`except`. Every failure mode already raises a
`DashboardError` subclass from the layer that owns it: `DiscoveryError` for a missing directory, a
zero-deck scenario or a duplicate label; `SchemaError` for a malformed frame; `DataFileError` for an
unreadable file; `RegistryError` for an unknown `charts.disabled` key; `StoreError` for a store
invariant; `ConfigError` for a missing logo, an unsupported logo extension, a fully disabled chart
catalogue, `TOTAL` inside `costs.total_parcels` or `TOTAL` as a `time.stage_groups` key.
`cli.main`'s existing `except DashboardError` is the single handler, and `pipeline.run` must let
every one of them propagate unchanged — wrapping them would lose the message that names the
offending path or settings key.

## Dependencies

- **Blocked By**: `ticket-032-enforce-output-size-strategy.md` (completed: it created
  `output_volumes` and `plotly_bundle_bytes`, which requirement 1 composes)
- **Blocks**: `ticket-034-add-example-data-integration-test.md`
- **Dispatch-order constraint, not a graph edge**: must not run concurrently with
  `ticket-037-polish-cli-usability-and-errors.md`, which modifies the same `src/dessem_dashboard/cli.py`
  and the same `tests/test_cli.py`.

## Acceptance Criteria

- [ ] Given the `scenario_tree` fixture and a `settings.json` whose `paths.logo_file` points at the
      repository logo, when `pipeline.run` is called with both scenario directories,
      `reference="caso_a"` and the default `initial_mode`, then the returned
      `RunResult.data_volumes` keys are exactly `["cenarios", "decks", "graficos", "valores",
      "bytes_html", "bytes_plotly"]` with `cenarios == 2`, `decks == 2`, `graficos == 23`,
      `bytes_html == output_file.stat().st_size` and `bytes_html > bytes_plotly`; and
      `output_file.read_text(encoding="utf-8")` contains `Gerência de Ferramentas Energéticas - FEN`.
- [ ] Given the same fixture, when `pipeline.run` is called through `cli.main` with
      `--casos <caso_a> <caso_b> --settings <path>`, then the call returns `0`,
      `output/run_manifest.json` exists under the settings directory, its `data_volumes` object
      equals the six-key mapping, and its `warnings` array equals `list(data.warnings())` for the
      same inputs — proving the degradation record reaches the manifest rather than being dropped as
      it is by the stub.
- [ ] Given the same fixture, when `pipeline.run` is called once with `initial_mode="deck"` and once
      with `initial_mode="encadeado"`, then the first document contains `data-initial-mode="deck"`
      and the substring `<select id="deck-selector">`, the second contains
      `data-initial-mode="encadeado"` and the substring `<select id="deck-selector" disabled>`, and
      the two documents differ — proving `--modo-inicial` reaches the output, which it does not
      today.
- [ ] Given a scenario tree whose synthesis folders are named `resultados` instead of `sintese`,
      when `pipeline.run` is called with `settings.discovery.sintese_dirname == "resultados"`, then
      it completes and writes the document; and when the same tree is run with the default
      `"sintese"`, then `DiscoveryError` is raised naming both the scenario label and the string
      `sintese` — proving the settings key is consumed and that the assertion is not vacuous.
- [ ] Given the whole repository, when
      `.venv/bin/pytest tests/test_pipeline.py tests/test_cli.py tests/test_output_size.py
      tests/test_builder.py -q && .venv/bin/mypy src && .venv/bin/ruff check src tests` is run,
      then it exits 0, and `grep -rn "noqa: ARG001" src/` returns no match.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Rewrite `pipeline.run` first, in one pass. It is roughly ten lines: four calls, one
   `time.perf_counter` bracket, one `log_step`, one `return`. Keep the module docstring's claim that
   this module "owns the single top-level entry point the CLI calls" — it becomes true rather than
   aspirational.
2. Add `initial_mode` as the last keyword parameter so the existing call in `cli.main` keeps reading
   naturally, then add `initial_mode=args.modo_inicial` to that call. Do not reorder the other
   keywords: `test_main_dashboard_error_from_pipeline_is_logged_and_returns_1` monkeypatches
   `pipeline.run` with `def _raise(**_: object)`, which tolerates any keyword set, but a positional
   change would not be tolerated by the real signature's `*`.
3. Run `.venv/bin/pytest tests/test_cli.py -q` **before** editing any test, and paste the failure
   list into the completion report. Then fix them one at a time, smallest first.
4. For the four exit-code tests, replace the bare `caso_a.mkdir()` / `caso_b.mkdir()` with the
   `scenario_tree` fixture and keep each test's own assertion target: the manifest's
   `params["referencia"]`, the explicit `--referencia`, the root logger level, and the default
   `--saida` path. Add the `scenario_tree` fixture argument and write `settings.json` into the same
   `tmp_path` the fixture used, so the relative `output_dir` and `logging.file` still resolve beside
   it.
5. For `test_pipeline_run_returns_data_volumes_matching_number_of_casos`, keep the name — it still
   describes what it proves — and make the assertion the six-key set plus `cenarios == 2`. Do not
   leave a bare `len(volumes) == 6`: a length assertion naming no key is the vacuous shape this plan
   has recorded three times.
6. Write `tests/test_pipeline.py` with its own `_settings_dict` / `_build_settings` pair copied from
   `tests/test_output_size.py`'s pattern, including `_REPO_LOGO`. Do not import a private helper
   from a sibling test module: `tests/dashboard_document.py` exists precisely because ticket-027
   needed shared slicing helpers, and the same rule applies to settings builders.
7. For the `sintese_dirname` pair, build the tree with
   `make_sintese_dir(root / "caso_a" / "deck_um" / "resultados", first_stage_start=...)` — the
   generator writes into whatever directory it is given, and `make_sintese_dir`'s signature is in
   epic-02 learnings section 5. Assert the success case and the `DiscoveryError` case in two tests,
   or in one test with `pytest.raises` after the success path; either way both directions must be
   asserted, because the success case alone passes with a hard-coded `"sintese"`.
8. For the `initial_mode` criterion, assert on the **written file**, not on `build_html`'s return
   value: the point is that the flag survives `cli.main` → `pipeline.run` → `write_dashboard`. The
   exact substring `<select id="deck-selector" disabled>` comes from `builder._deck_selector`, which
   emits `f'<select id="deck-selector"{disabled_attribute}>'` with `disabled_attribute = " disabled"`.
9. Prove the new assertions can fail before declaring done: drop `initial_mode` from the
   `write_dashboard` call and confirm criterion 3 fails; drop `sintese_dirname=` from the
   `discover_scenarios` call and confirm criterion 4's success case fails; replace
   `warnings=list(data.warnings())` with the default and confirm criterion 2's manifest assertion
   fails; call `output_volumes` before `write_dashboard` and confirm criterion 1's `bytes_html`
   assertion fails with a `FileNotFoundError`. Restore each.
10. Record the wall-clock time of `tests/test_cli.py` before and after the amendment in the
    completion report. The four amended tests each build a full 4.5 MB document where they
    previously built nothing, and the epic-05 gate needs the real figure rather than an estimate —
    the suite is 602 tests and about 10 minutes today — measured at 589 s (601 tests) during this
    epic's refinement and at 564 s and 618 s in the two epic-04 boundary runs. Do not quote the
    "about 220 s" figure an earlier ticket-032 draft carried; it was corrected at that boundary.

### Key Files to Create/Modify

- `src/dessem_dashboard/pipeline.py` (modify: the whole `run` body, the new `initial_mode`
  parameter, the removed `noqa`)
- `src/dessem_dashboard/cli.py` (modify: one added keyword argument in the `pipeline.run` call)
- `tests/test_pipeline.py` (create)
- `tests/test_cli.py` (modify: five amended tests and the `_settings_dict` logo path plus its
  docstring)

### Patterns to Follow

- `tests/test_output_size.py`'s `_REPO_LOGO`, `_settings_dict(...)`, `_build_settings(tmp_path, ...)`
  and `_build_data(paths, *, settings, reference)` quartet. It already composes
  `discover_scenarios` → `build_dashboard_data` → `write_dashboard` → `output_volumes` →
  `write_run_manifest` in a test, which is exactly the chain `pipeline.run` must perform in `src/`.
- `log_step(logger, "<Portuguese message>", campo=valor, elapsed_s=...)` for the one new INFO line,
  matching the 15 existing call sites: a capitalised Portuguese sentence, `snake_case` Portuguese
  field names, `elapsed_s` last.
- The Portuguese operator vocabulary already shipped (epic-02 learnings section 2): `cenário`,
  `deck`, `gráfico`, `aviso`, dates as `%d/%m/%Y`. Reuse it; do not invent synonyms.
- `errors.py`'s seven-class hierarchy and the "let it propagate" discipline: only `cli.main`
  catches.

### Pitfalls to Avoid

- Do not call `output_volumes` before `write_dashboard`. `bytes_html` is
  `output_file.stat().st_size` and the file does not exist yet.
- Do not forget `sintese_dirname=`. `discover_scenarios` defaults it to `"sintese"`, so omitting it
  produces a working pipeline that silently ignores a configured folder name — and no existing test
  would catch it, because every existing caller omits it too.
- Do not forget `initial_mode`. `write_dashboard` defaults it to `"encadeado"`, so omitting it
  produces a working pipeline in which `--modo-inicial deck` changes nothing. That is the live
  defect this ticket closes.
- Do not add an atomic temp-file-and-rename write. `write_dashboard` owns the write, returns the
  `Path`, and three call sites in `tests/test_output_size.py` depend on that return type;
  ticket-032's pitfall list forbids changing it. The output directory is gitignored and a partial
  file after a crash is visible and re-runnable, so the temp-file dance buys nothing here.
- Do not turn a degraded run into a failure. A missing file, a missing deck and an absent entity are
  warnings by decision 18; only a scenario with **zero** decks is fatal, and `discover_scenarios`
  already raises for it.
- Do not validate `--modo-inicial` against the modes "actually available". `argparse` and
  `_validate_initial_mode` already restrict the value, and a deck shorter than
  `chaining.stages_per_deck` is already reported by `timeline.validate_chaining`'s `lacuna` warning.
  Adding a third check would be unrequested behaviour.
- Do not add a dry-run flag. `output_volumes`' `bytes_html` requires a written file, so a dry run
  would need a second volumes shape, and the CLI surface is fixed by the spec plus ticket-006.
- Do not re-instrument the phases with new timing. 15 `log_step` sites with `elapsed_s` already
  exist inside the chain.
- Do not leave `tests/test_cli.py::_settings_dict`'s docstring claiming every path is relative once
  `logo_file` is absolute. A helper whose docstring misdescribes it is spec defect 20 of this plan.
- Do not weaken an amended assertion to make it green. Both cross-ticket collisions of epic 4 were
  resolved by replacements **stronger** than what they replaced, and that is the standard here.
- Do not claim which tests fail without running them. Five of this plan's twenty-one spec defects
  were claims about the test suite made without executing it.

### Out of Scope

- The console run summary, the per-warning log lines, the stdout output path and the `--help`
  epilogue (ticket-037).
- The integration test against the real `exemplo/` tree, and any reading of that tree
  (ticket-034).
- The README rewrite, including the now-false "Current output" paragraph and the "planned and do not
  exist yet" module map (ticket-036).
- Any new chart, payload key, settings key or `errors.py` class; any change to the `settings.json`
  contract; any change to `paths.log_dir`'s (absent) consumer.
- Atomic writes, a dry-run flag, a mode-availability check, warning grouping, and any change to a
  warning message's text.

## Testing Requirements

### Unit Tests

`tests/test_pipeline.py`:

- acceptance criteria 1, 3 and 4;
- **acceptance criterion 2 — added 2026-09-11, spec defect 22.** The Testing Requirements
  originally enumerated `test_pipeline.py`'s and `test_cli.py`'s cases exhaustively and assigned
  AC2 to neither, so the full `cli.main` to written-manifest round trip had no owner. The
  specialist verified it by measurement with a throwaway script and escalated the scope question
  rather than silently widening one of the five requirement-6 tests, which was the right call: an
  acceptance criterion whose only verification is a discarded script is not gated. The gap matters
  here more than it would elsewhere, because the round trip is precisely the correspondence this
  ticket exists to repair — `tests/test_cli.py` already asserts `result.data_volumes` on the
  `RunResult` object and `tests/test_manifest.py` already asserts that `write_run_manifest` writes
  back the dict it is handed, so both halves were tested and only the join was not. A future change
  that stopped threading `warnings` into the manifest would re-introduce the silent-degradation
  defect with the suite green. Drive `cli.main` end to end over a tree where `caso_b` lacks its
  second deck and assert on the **written manifest file**: the six-key `data_volumes`, a `warnings`
  list compared against an independently rebuilt `data.warnings()` rather than a hard-coded string,
  and exit code 0 per E5-5 and master-plan decision 18. Prove it discriminates by dropping
  `warnings=list(data.warnings())` and confirming this test fails alongside the object-level one —
  one guards the object, one guards the file.

  > **Spec defect 22 is a new shape for the catalogue: an acceptance criterion with no assigned
  > test in the ticket's own Testing Requirements.** Readiness scoring gave this ticket 1.00 and
  > could not catch it, because scoring checks that criteria are *verifiable*, not that each one
  > was actually *assigned an owner*. Worth a cheap gate in future refinements — but phrase it
  > carefully. The orchestrator applied a first draft of the gate to tickets 034 to 038 immediately
  > after recording it, asking whether each acceptance criterion is **referenced by number** in
  > Testing Requirements, and got **two false positives**: ticket-036 verifies through a
  > `Documentation Verification` section of four content properties (it writes no code), and
  > ticket-038 through a `Regression` section requiring the whole suite to pass with an identical
  > collected count. Both are strong verification that names no criterion number. The correct
  > question is therefore **"does every acceptance criterion have some named verification
  > somewhere"**, not "is every criterion numbered in a list" — and the answer for tickets 034 to
  > 038 is yes. Defect 22 is real in ticket-033 alone, where AC2's only verification was a script
  > the specialist ran and discarded.
- `RunResult.warnings` equals `list(data.warnings())` for a tree where `caso_b` is missing the
  second deck, built by deleting nothing and simply not creating that deck — assert at least one
  message contains `caso_b` and `04/03/2024`, the wording epic-02 learnings section 2 records;
- a scenario directory with no deck raises `DiscoveryError` out of `pipeline.run` unchanged, with
  the message naming the label and the configured synthesis folder name;
- `pipeline.run` writes the file at `output_file` and creates its parent when it does not exist
  (`write_dashboard` does this; the test pins that `pipeline.run` does not require a pre-created
  directory);
- the single new `log_step` line appears exactly once in `caplog` and carries all six volume fields
  plus `avisos=`, asserted by field name and not by a substring of the whole message;
- the four non-vacuity mutations of Suggested Approach step 9, each confirmed to fail before
  restoration.

`tests/test_cli.py`: the five tests of requirement 6, amended and no others.

### Integration Tests

None against real data — that is ticket-034, by design. `tests/test_pipeline.py`'s first criterion
is itself the synthetic end-to-end test: it exercises discovery, timeline, registries, readers,
consolidation, payload, theme, builder, asset inlining and volume measurement in one call.

### Regression

`tests/test_output_size.py`, `tests/test_builder.py`, `tests/test_payload.py`,
`tests/test_manifest.py`, `tests/test_discovery.py`, `tests/test_consolidate.py` and every
`tests/test_charts_*.py` module must pass **unchanged**: this ticket adds no behaviour inside any
module they cover. `tests/test_cli.py` passes **as amended** by requirements 6 and 7, which this
ticket's own requirements force to change.

## Definition of Done

- [ ] `pipeline.run` composes the four functions in the required order, `grep -rn "noqa: ARG001"
      src/` returns no match, and the stub comment naming ticket-033 is gone.
- [ ] All five acceptance criteria pass, and the four non-vacuity mutations were each observed to
      fail and then restored.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
      `.venv/bin/mypy src` exit 0.
- [ ] `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing` passes with total coverage
      at or above **85 percent** (the Epic 5 floor from the master plan's Testing Strategy, raised
      from the 80 percent of Epics 1 to 4), and `src/dessem_dashboard/pipeline.py` is at 100 percent.
- [ ] The completion report states: the actual `tests/test_cli.py` failure list observed before any
      edit; the collected test count from `.venv/bin/pytest --collect-only -q`; and the measured
      wall-clock time of `tests/test_cli.py` before and after the amendment. No count or duration is
      cited without being measured.
- [ ] `--modo-inicial deck` and `--modo-inicial encadeado` produce different documents, verified on
      the written file rather than on a return value.
- [ ] `settings.discovery.sintese_dirname` has at least one consumer in `src/`, and the negative
      case proves the assertion can fail.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 40 minutes. Unchanged from the
outline's 3 points, and the reason the estimate held is that refinement found the scope smaller than
the outline feared in one dimension and larger in another, and the two cancel. Smaller: every open
question the outline raised resolves to "already handled, add nothing" — per-stage timing is already
instrumented at 15 sites, atomic writes are forbidden by ticket-032's return-type pin, the
zero-usable-charts case is already decision 18, and the dry-run flag is out of scope. Larger: the
outline listed three files and the real scope is four, because `cli.py` must thread `--modo-inicial`
(a flag that currently changes nothing) and five tests in `tests/test_cli.py` must be rebuilt on a
real fixture with the repository logo. Confidence is High because every function being composed is
already unit-tested and its signature is pinned, and the only genuinely uncertain item — which
existing tests break — is handled by running the module before editing it rather than by predicting.
