# ticket-036 Write the user documentation

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `open-source-documentation-writer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-035 and strictly before ticket-037.**
> **Documentation language is English** (Rigoroso mode). The only Portuguese in this ticket's output
> is text **quoted** from the running program: CLI flags, `--help` strings, log and error messages,
> and dashboard UI labels. Quote them verbatim; do not translate them and do not paraphrase them.
> **Never read, list or quote anything under `exemplo/`.** The README's example command names those
> paths, which is a path and not data; no value from that tree may appear anywhere.

## Context

### Background

`README.md` is the Epic 1 skeleton written by ticket-007, 263 lines, and it has been falsified by
four epics of work. Measured against the repository as it stands, four of its claims are now
**false**, and a fifth becomes false the moment ticket-033 lands:

1. **The module map is wrong.** Lines 169-186 say "Only `src/dessem_dashboard/` is shown; modules
   under `models/`, `data/`, `charts/` and `dashboard/` are planned and do not exist yet", and mark
   four directories "planned (Epic 2)", "planned (Epic 3)", "planned (Epic 3-4)". All four exist and
   hold 14 modules plus three asset files. The same block describes `errors.py` as "DashboardError
   hierarchy (ConfigError today)"; it holds **seven** classes.
2. **The verified baseline is stale.** Lines 224-234 present a table "measured at the end of Epic 1"
   reporting `11 files already formatted`, `no issues found in 7 source files`, `47 passed` and
   "Total coverage is **95 %**". Re-measured now: `ruff format --check src tests` reports **57 files
   already formatted**, `mypy src` reports **26 source files**, and
   `pytest --collect-only -q` reports **602 tests** (601 before the epic-04 boundary review added
   one), and a full run measured **589 s (9:49)** at 601 tests with total coverage **99 percent**,
   against 564 s and 618 s in the two boundary runs — so budget **about 10 minutes**. Every one of
   those numbers must be re-measured again by this ticket rather than copied from this paragraph —
   three of the plan's twenty-one spec defects were stale counts carried forward by reading instead
   of measuring, and this very paragraph went stale once during refinement.
3. **The "Current output" paragraph** (lines 149-154) states that `pipeline.run` is a stub which
   "does not read any Parquet file and does not produce `dashboard_dessem.html`". True until
   ticket-033; false after it.
4. **The summary** (lines 5-15) says the tool "once Epic 5 lands, will emit a single self-contained,
   offline HTML file" and that the two view modes "are planned". Both shipped in Epic 3.
5. **The Roadmap** (lines 251-263) marks epic 1 "Complete" and the other four as future work, and
   item 5 promises "user-facing documentation with screenshots".

The configuration section is the part worth keeping: it already tables every `settings.json` leaf key
with a default and a meaning, grouped as the file groups them, which is exactly what
`rules/markdown.md` section 3 and CLAUDE.md's "Configuration via a settings file" require. What it
lacks is the behaviour four epics attached to those keys — the validation errors, the single
consumer of `time.unit_divisor`, and the fact that one key has **no consumer at all**.

### Relation to Epic

The epic's documentation ticket, placed after the parity check so it can point at the parity report
as the record of what the deleted scripts did, and before ticket-037 so the CLI polish has a document
to update. It is the last ticket that can still describe the tool to an operator who has never seen
it, and the first place a future maintainer will look for the registry extensibility promise the
master plan makes in goal 8.

### Current State

The README's nine sections today: `What it is`, `Requirements`, `Configuration` (ten grouped key
tables), `How to run`, `Structure`, `Logging and auditing`, `Development`, `Roadmap`. The
`Configuration` tables cover all 23 leaf keys of `settings.json` and are accurate.

Facts the new README must carry, each measured or read from the shipped code during refinement, and
each to be **re-verified by this ticket before it is written**:

- **`paths.log_dir` has no consumer.** `grep -rn "log_dir" src/` matches only `config.py:22` (the
  dataclass field) and `config.py:221` (the loader). `logging.file` carries a full path and
  `logging_setup.setup_logging` creates its parent, so the directory key is validated and then never
  read. Document it as such rather than implying it controls anything; changing the settings contract
  is out of the epic's scope.
- **`time.unit_divisor` is applied exactly once**, in `dashboard/scalars.py::aggregate_times`.
  `grep -rln "unit_divisor" src/` names only `config.py` and `dashboard/scalars.py`. Everything
  below that module keeps **seconds** on purpose (ticket-018), which is why `TEMPO.parquet`'s raw
  values are seconds and the chart's axis reads `min`. Since the epic-04 boundary review, a
  `unit_divisor` other than `60.0` also emits one Portuguese `logger.warning` naming the `min`
  label, because that label is hard-coded in `FALLBACK_UNITS` and would stop matching the values.
- **`CUSTOS` is in `10^3 R$`, not `R$`** (epic-04 boundary finding 1, propagated into
  `data/schemas.py`, master plan Appendix A.5 and A.6, and `planning-context.md`). The cost chart's
  Y axis therefore reads `10^3 R$`, and the legacy scripts labelled the same values `(R$)`. The
  evidence is in `plans/dashboard-dessem/reference/parquet-schemas.txt` and the reasoning is in the
  parity report; the README states the unit and points there.
- **Four settings values are rejected with a named error**, and an operator will meet all four:
  `charts.disabled` naming an unknown chart key raises `RegistryError` naming the key
  (`charts/registry.py`); `charts.disabled` naming the whole catalogue raises `ConfigError` naming
  `charts.disabled`; `TOTAL` inside `costs.total_parcels` raises `ConfigError` naming
  `costs.total_parcels`; a group named `TOTAL` in `time.stage_groups` raises `ConfigError` naming
  `time.stage_groups`. A parcel or a stage group configured but absent from the data is a
  **Portuguese warning plus omission**, never a crash.
- **`paths.logo_file` is a hard requirement.** A missing file or an extension outside
  `.png`, `.jpg`, `.jpeg`, `.svg` raises `ConfigError` naming `paths.logo_file` and the resolved
  absolute path. Master plan decision 18 makes a missing *data* file a warning; a missing logo is a
  configuration error, because the ONS visual identity is goal 7.
- **The chart catalogue is 23 enabled of 42 declared** (measured by calling `enabled_specs()` and
  `all_specs()`), with the 19 remaining shipped as disabled registry entries listed in master plan
  Appendix A.6.
- **The audit trail has three channels and they carry different things.** The rotating log file gets
  15 `log_step` INFO lines per run — `Cenário descoberto`, `Descoberta de cenários concluída`,
  `Timeline de deck carregada`, `Janela de encadeamento validada`,
  `Fase 1/5: timelines de deck carregadas` through `Fase 5/5: escalares consolidados`,
  `Registros carregados`, `Consolidação de dados concluída`, `Payload JSON construído`,
  `Payload JSON serializado`, `Payload embutido no documento HTML do dashboard`,
  `Dashboard HTML escrito em disco` — plus the one `pipeline.run` summary ticket-033 adds.
  `run_manifest.json` carries `timestamp_utc`, `git_sha`, `git_dirty`, `python`, `platform`,
  `package_version`, `params`, `data_volumes` (the six keys `cenarios`, `decks`, `graficos`,
  `valores`, `bytes_html`, `bytes_plotly`), `warnings` and `elapsed_seconds`. The dashboard's
  `Avisos` section carries the same warning list, rendered for the reader of the chart.
- **There are exactly eight degradation warning shapes**, emitted by `timeline.validate_chaining`
  (`lacuna`, `sobreposição`), `timeline.align_deck_dates` (`não possui deck para a data`),
  `consolidate._check_timeline_coverage` (`tem timeline divergente do eixo do deck de`),
  `consolidate._load_series` and `consolidate._load_scalars` (`não encontrado no cenário`), the
  submarket-coverage branch (`código(s) de submercado do gráfico`) and the absent-entity branch
  (`ausente(s) no cenário`). Dates in every one of them are `%d/%m/%Y`.
- **The dashboard UI**, whose every visible string is Portuguese: a header with the logo and
  `dashboard.title`; a level navigation of six buttons labelled `SIN`, `Submercado`, `Intercâmbio`,
  `Usinas hidrelétricas`, `Usinas termelétricas`, `Execução`; a control row with the `Por deck` /
  `Encadeado` mode toggle, a `Deck` selector that is `disabled` in `Encadeado` mode, the
  `Absoluto` / `Diferença` toggle and a reference-scenario label; an optional `Avisos` section; one
  stacked chart section per enabled chart of the active level, each with its curated heading, an
  optional subtitle from `METADADOS_OPERACAO`, an entity selector where the chart has one, and
  `Nome` / `Código` filters with the placeholders `Filtrar por nome` and `Filtrar por código` and
  the empty-result message `Nenhuma usina corresponde ao filtro` on the two plant levels; and the
  mandatory footer `Gerência de Ferramentas Energéticas - FEN`. The two `Execução` charts are
  grouped bars on a category axis whose labels read `<deck date> - <series name>`, for example
  `03/03/2024 - PRESENTE`.
- **Adding a chart takes two source edits and breaks a known set of pinned counts.** The two edits
  are one `FALLBACK_UNITS` entry in `data/schemas.py` (`_series` and `_scalar` both read
  `FALLBACK_UNITS[key]`, so a missing entry is a `KeyError` at import) and one `_series(...)` or
  `_scalar(...)` entry in `charts/specs.py`. No schema entry is needed: `SERIES_COLUMNS` and
  `ENTITY_KEYS` are per aggregation level, not per file. `tests/fixtures_sintese.py` writes one
  fixture file per `enabled_specs()` entry, so the fixtures follow automatically. The literal `23`
  is pinned in `tests/test_builder.py:36`, `tests/test_charts_costs.py:570`,
  `tests/test_charts_sin.py:483`, `tests/test_output_size.py:45`, `tests/test_payload.py:33` and
  `tests/test_registries.py:32`, and `tests/test_chart_specs.py` pins both an explicit 23-key
  `_ENABLED_KEYS_IN_ORDER` tuple and three `42` literals. **Re-measure that list with a grep before
  writing it; do not copy it from this paragraph.**
- **`DESSEM_DASHBOARD_EXEMPLO`** is a *test-only* environment variable, introduced by ticket-034,
  read by `tests/exemplo_tree.py` and by nothing under `src/`. It points at a directory whose
  immediate subdirectories are scenario directories, and it exists so the integration and parity
  tests can run against data outside the repository. `settings.json` remains the single
  configuration anchor for the program itself.
- **Two intentional divergences from the original spec** must be recorded:
  `planning-context.md` decision 11 keeps `logo/` and `*.md` **versioned** where the spec suggested
  ignoring them, and master plan decision 14 replaces the legacy `type='category'` X axis with a
  true datetime axis and `line_shape: "hv"`, so a 6-hour stage renders six times wider than a
  half-hour stage. Both point at their decision record; the axis one also points at the parity
  report ticket-035 wrote.

`docs/checklist-manual-dashboard.md` **needs no edit from this ticket**, and that is a change from
the outline's assumption. Refinement first found two stale statements in it — a title reading
`# Manual Release Checklist — Dashboard (Epic 3)` for a file that now covers epics 3 and 4, and an
intro sentence saying "Steps 21 onward cover Epic 4's plant name and code filters (ticket-028)"
while steps 27 to 32 are the cost and time bar charts of tickets 030 and 031 — and the epic-04
boundary review **fixed both while this refinement was being written**: the title is now
`# Manual Release Checklist — Dashboard` and the intro now reads "Steps 21 to 26 cover Epic 4's
plant name and code filters (ticket-028). Steps 27 to 32 cover Epic 4's cost and time bar charts
(tickets 030–031)." Re-read the file before concluding anything about it; if a stale statement
remains, fix only that statement. Neither the title nor the intro sentence is asserted by any test:
the ten checklist assertions in
`tests/test_renderer_contract.py` and `tests/test_charts_filters.py` match on `console`, `file://`,
the footer text, the six group labels, `Por deck`, `Encadeado`, `disabled`, `six times wider`,
`Absoluto`, `Diferença`, `04/03/2024 12:00`, `GHID_SIN`, `caso_oficial`, `caso_gurobi`,
`--casos exemplo/caso_oficial exemplo/caso_gurobi`, `MW (diferença)`, `Submercado`,
`Par de submercados`, `Not yet written`, the `## 8.` heading and section 8's own strings, plus
whatever section-9 guard ticket-034 added. Verified by reading all ten.

`CLAUDE.md` (the project rules file) states the mode, the `settings.json` rule, the logging rule, the
quality gate and the required reading. Every one of those statements is still true, so it needs no
edit; requirement 7 forbids a gratuitous one.

## Specification

### Requirements

1. Rewrite `README.md` in English, keeping the `rules/markdown.md` section order — what it is,
   requirements, configuration, how to run, structure, logging and auditing — and adding two
   sections after "How to run": **Reading the dashboard** and **Extending the chart catalogue**.
   Correct all five falsified claims of the Background section. Every command goes in a fenced block
   with a language tag.
2. Document every `settings.json` leaf key with its meaning and its default, keeping the existing
   grouped tables, and add for each group the behaviour the code actually attaches: the four named
   validation errors, the warning-plus-omission degradation rule, the single application point of
   `time.unit_divisor` **and the Portuguese warning `dashboard/scalars.py` now emits when it is not
   60.0**, naming the `min` label that `FALLBACK_UNITS["TEMPO"]` hard-codes independently (epic-04
   boundary finding 3), and — explicitly — that `paths.log_dir` is validated but read by no module,
   with `logging.file` carrying the effective path. Give the four keys an operator actually changes
   (`chaining.stages_per_deck`, `costs.total_parcels`, `time.stage_groups`, `charts.disabled`) a
   short paragraph each beyond the table row, as the outline asked.
3. Replace the "Current output" paragraph with what a real run produces after ticket-033: one
   self-contained HTML at `paths.output_dir/output.default_filename` (overridable with `--saida`),
   one `run_manifest.json` beside it, and the rotating log file. Document the manifest's eleven
   fields and the six `data_volumes` keys by name. Document the flag table including
   `--modo-inicial`'s real effect — the pre-selected view mode, which also decides whether the deck
   selector starts `disabled`.
4. Write **Reading the dashboard** from the DOM and label facts in Current State: the six levels,
   the two view modes and what `Encadeado` concatenates (the first `chaining.stages_per_deck` stages
   of each deck in deck-date order), the deck selector's inert state in `Encadeado`, the
   `Absoluto` / `Diferença` toggle and how the reference scenario is chosen, the plant name and code
   filters and their combination, the two grouped bar charts and their `<deck date> - <series name>`
   category labels, the `Avisos` section with the eight warning shapes described in one sentence
   each, and the offline guarantee (no network at build time or view time; Plotly is inlined from
   the installed package). Quote every Portuguese label verbatim. Point at
   `docs/checklist-manual-dashboard.md` as the release gate.
5. Write **Extending the chart catalogue** from the two-edit recipe in Current State, with the
   pinned-count list **re-measured by grep at writing time**, a worked example naming one of the 19
   disabled specs and how `charts.disabled` toggles it, and the statement that
   `enabled_specs()` returns 23 of 42 declared specs — both figures re-measured by running them, not
   copied.
6. Add a short **Legacy scripts** subsection under Structure recording that `Leitura/`,
   `Plotadores/` and the five `main_*.py` drivers were the tool this project replaces, that their
   behaviour is documented in `plans/dashboard-dessem/epic-05-parity-report.md`, and that
   ticket-038 removes them. Write it so it is true **both before and after** ticket-038 runs — state
   what the parity report holds and where to look, not whether the directories are still present.
   Requirement 4 of ticket-038 updates this subsection with the removal commit; do not write a
   sentence that ticket-038 must delete.
7. Re-read `docs/checklist-manual-dashboard.md` and change **nothing** unless a statement in it is
   still false. The epic-04 boundary review already corrected its title and its intro paragraph, and
   the file is expected to need no edit. If a residual inaccuracy is found, fix only that sentence
   and change **no numbered step, no expected result and no quoted UI string** — ten tests assert
   checklist content and every one of them must keep passing unchanged. Report either way: "no edit
   needed, verified by reading" is the expected outcome and is a result, not an omission.
8. Record the two intentional divergences of Current State in the README, each naming its decision
   number and, for the axis, pointing at the parity report.
9. Document `DESSEM_DASHBOARD_EXEMPLO` in the Development section as a test-only variable, with the
   statement that `settings.json` is the single configuration anchor for the program itself.
10. **No screenshots.** Ship a plain-text figure of the page layout instead. The reason is not
    storage: `.gitignore` ignores generated `*.html` but not images, so a screenshot of a real run
    would commit ONS study values — plant names, costs, load curves — into a repository that is
    pushed to a remote. A text figure carries the same structural information with no data. Record
    that reasoning in the README's own prose so it is not re-litigated.
11. **No new documentation file.** Everything belongs in `README.md`, beside the existing
    `docs/checklist-manual-dashboard.md` and the plan documents. The outline's
    `docs/dashboard-guide.md` is dropped: `rules/markdown.md` makes the README the single entry
    point, and a second guide would duplicate the configuration table, which is the one thing in the
    project guaranteed to drift.
12. Touch no file under `src/` or `tests/`, and do not edit `CLAUDE.md`: every statement it makes is
    still true, verified in Current State. Do not edit `settings.json`, `pyproject.toml` or
    `.gitignore`.

### Inputs

The shipped code, read directly: `config.py` for the key list and the error messages,
`charts/specs.py` and `data/schemas.py` for the catalogue and the units, `dashboard/builder.py` for
the DOM and the Portuguese labels, `dashboard/scalars.py` for the aggregation rules,
`data/consolidate.py` and `data/timeline.py` for the warning shapes, `cli.py` for the flags and the
help text, `manifest.py` for the manifest fields, `pipeline.py` for the run sequence. The measured
gate output from `ruff check src tests`, `ruff format --check src tests`, `mypy src` and
`pytest --cov=dessem_dashboard --cov-report=term-missing`, all four run by this ticket.
`plans/dashboard-dessem/epic-05-parity-report.md` for the legacy record. `settings.json` for the
defaults.

### Outputs and Behavior

One rewritten `README.md` in which no statement contradicts the code, every `settings.json` key is
documented with meaning and default, every quoted number was measured by this ticket, and an
operator who has never seen the project can install it, configure it, run it, read the dashboard and
extend the catalogue. `docs/checklist-manual-dashboard.md` is expected to be left **unchanged**,
having been corrected at the epic-04 boundary; if it is edited at all, the diff is one sentence and
no numbered step.

### Error Handling

Documentation has no runtime error handling. The failure mode this ticket must avoid is a **false
statement**, and requirement 2, 3, 5 and the Definition of Done treat it as one: every claim about a
count, a duration, a file list or a behaviour is either re-measured by a command recorded in the
completion report, or removed. A claim that cannot be verified must not be written.

## Dependencies

- **Blocked By**: `ticket-035-run-legacy-parity-check.md` (requirements 6 and 8 point at the parity
  report it creates)
- **Blocks**: `ticket-037-polish-cli-usability-and-errors.md`, which invalidates three specific
  README places and is required to update them
- **Dispatch-order constraint, not a graph edge**: must not run concurrently with
  `ticket-034-add-example-data-integration-test.md`, which writes the guard test for
  `docs/checklist-manual-dashboard.md`'s section 9, nor with ticket-037 or ticket-038, both of which
  edit `README.md`.

## Acceptance Criteria

- [ ] Given the rewritten `README.md`, when its Structure section is compared against
      `find src/dessem_dashboard -name "*.py" -o -name "*.css" -o -name "*.js" -o -name "*.html"`,
      then every listed module exists, every existing module is listed, no entry is marked "planned"
      or "do not exist yet", and `errors.py` is described as the seven-class hierarchy naming all
      seven.
- [ ] Given the rewritten `README.md`, when its Configuration section is compared against
      `settings.json`, then every one of the 23 leaf keys appears exactly once with a default equal
      to the shipped value and a meaning; `paths.log_dir` is documented as validated but read by no
      module; `time.unit_divisor` is documented as applied once in `dashboard/scalars.py`; and the
      four named validation errors are each documented with their exception class and the dotted key
      their message names.
- [ ] Given the rewritten `README.md`, when its Development section is read, then the four
      quality-gate numbers — formatted file count, mypy source-file count, passed-test count and
      total coverage percentage — equal the output of the four commands run by this ticket, and the
      completion report quotes that output; and no sentence claims `pipeline.run` is a stub or that
      any module is planned.
- [ ] Given the rewritten `README.md`, when its Reading the dashboard section is read, then it names
      all six level labels, both mode labels, both value-mode labels, the two filter placeholders,
      the no-match message and the exact footer text, each spelled as `builder.py` emits it; and its
      Extending the chart catalogue section names the two files to edit and the pinned-count
      locations re-measured by grep.
- [ ] Given `docs/checklist-manual-dashboard.md`, when
      `.venv/bin/pytest tests/test_renderer_contract.py tests/test_charts_filters.py -q` is run,
      then it exits 0 with every checklist test passing unchanged, and
      `git diff --stat docs/checklist-manual-dashboard.md` shows either **no change at all** or a
      diff confined to one prose sentence, with no numbered step touched.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Run the four gate commands **first** and paste their exact output into a scratch note. Every
   number that goes into the Development section comes from that note. Do not start writing before
   you have them: the section you are replacing is stale precisely because it was written from a
   measurement that later drifted, and copying this ticket's own figures would reproduce the defect
   one generation later.
2. Read the code before writing each section, in this order: `settings.json` and `config.py` for the
   configuration section; `cli.py` for the flags; `pipeline.py` and `manifest.py` for the run
   output; `builder.py` for every Portuguese UI label; `consolidate.py` and `timeline.py` for the
   warning shapes; `charts/specs.py` and `data/schemas.py` for the catalogue. Quote, do not
   paraphrase.
3. Keep the existing grouped configuration tables and extend them rather than restructuring: they
   are already correct and already match `settings.json`'s own grouping, which is what makes them
   checkable against the file.
4. Write the Structure section from an actual `find`, not from the master plan's target-state tree.
   The two agree today, and a `find` is the only version that stays true.
5. For **Reading the dashboard**, walk the built document rather than the source where you can: open
   the HTML from a real or fixture build and read the labels off the page. That is how a label typo
   gets caught. The text figure of requirement 10 can be built from the DOM contract: header, level
   nav, controls, optional Avisos, one chart section per enabled chart of the active level, footer.
6. For **Extending the chart catalogue**, actually perform the two edits in a scratch copy of the
   tree, run `pytest -q`, and record which assertions fail. That converts the pinned-count list from
   a claim into a measurement, and it is the only way to be sure the list is complete.
7. Re-read the checklist and expect to change nothing: the epic-04 boundary review corrected its
   title and intro. If you do edit a sentence, run the two test modules that assert against it and
   use `git diff --stat` to prove the diff is confined to prose.
8. Write the Legacy scripts subsection in the present-perfect, describing where the behaviour is
   recorded rather than whether the files are there. A sentence like "the scripts are still present
   under `Plotadores/`" is an assertion that ticket-038 has not run yet, which is the collision shape
   this plan hit twice; a sentence like "their behaviour is transcribed in the parity report" is true
   before and after.
9. Do not add a sentence anywhere claiming the README is complete or final. ticket-037 changes the
   CLI's console output and its `--help`, and is required to update three places here.
10. Read the whole file once at the end, against the code, hunting for any remaining sentence in the
    future tense or any count you did not measure. Both are the failure mode.

### Key Files to Create/Modify

- `README.md` (modify: rewrite; keep and extend the configuration tables, correct the five falsified
  claims, add two sections and the legacy subsection)
- `docs/checklist-manual-dashboard.md` (**expected: no change**; at most one prose sentence, and
  only if a statement in it is still false)

### Patterns to Follow

- `rules/markdown.md`'s README section order and style: short paragraphs, lists over prose, a
  language tag on every fenced block, the *why* alongside the *what*, tables narrow enough to read
  in a terminal.
- The existing README's grouped key tables — one table per `settings.json` group, three columns
  (`Key`, `Default`, `Meaning`) — which are the part of the skeleton worth preserving.
- `docs/checklist-manual-dashboard.md`'s own convention of quoting interface strings exactly, in
  Portuguese, inside English prose.
- The master plan's Appendix B as the authority for the key list, and `settings.json` as the
  authority for the values; where they disagree, the file wins and the disagreement is a finding.

### Pitfalls to Avoid

- Do not copy a number from this ticket, from the master plan or from the old README. All four
  Development-section figures were stale once already; re-measure.
- Do not describe `paths.log_dir` as controlling where logs go. It is validated and then read by no
  module; `logging.file` carries the effective path.
- Do not claim the tool will do something "once Epic 5 lands". Epic 5 is this epic.
- Do not add screenshots. A screenshot of a real run embeds ONS study values in a pushed repository.
- Do not create `docs/dashboard-guide.md` or any second documentation file. One README, one
  checklist.
- Do not translate a Portuguese UI string, log message or flag into English. Quote it.
- Do not renumber, reword or delete a checklist step, and do not re-fix the checklist's title or
  intro: the epic-04 boundary review already corrected both, and editing them again would be churn
  on a file ten tests assert against.
- Do not write any sentence asserting that a later ticket has not run yet — not "the legacy scripts
  are still present", not "the README is final", not "no further change is needed".
- Do not edit `CLAUDE.md`. Every claim it makes was verified true during refinement; an edit would be
  churn.
- Do not read or quote anything under `exemplo/`. The example command names the paths, which is all
  the README needs.
- Do not document a behaviour you have not read in the code. The warning shapes, the error classes
  and the UI labels are all quotable from specific modules; anything else is invention.

### Out of Scope

- Any change under `src/` or `tests/`, and any change to `settings.json`, `pyproject.toml`,
  `.gitignore` or `CLAUDE.md`.
- Any numbered checklist step, expected result or quoted UI string.
- The console run summary, the stdout output path and the `--help` epilogue, all of which land in
  ticket-037 and which ticket-037 documents.
- Deleting the legacy scripts or writing the removal note's commit reference (ticket-038).
- The parity report's content (ticket-035 owns it; this ticket links to it).
- Any new settings key, any change to a warning message, any translation of a Portuguese string.

## Testing Requirements

### Unit Tests

None: this ticket writes no code. The verification is the four gate commands plus the two test
modules that assert checklist content.

### Integration Tests

None new. `tests/test_renderer_contract.py` and `tests/test_charts_filters.py` are the automated
guard on requirement 7 and must pass **unchanged** — that is the falsifiable prediction this ticket
makes about the checklist, whether or not it edits a sentence in it.

### Documentation Verification

- Every `settings.json` leaf key appears exactly once in the README's tables, checked by listing the
  keys from the file and diffing against the keys in the document.
- Every module found by `find src/dessem_dashboard` appears in the Structure section, and vice versa.
- Every Portuguese string quoted in the Reading the dashboard section appears verbatim in
  `src/dessem_dashboard/dashboard/builder.py` or in `src/dessem_dashboard/cli.py`, checked with a
  grep per string.
- Every command in a fenced block was executed once and exited as the document claims.

## Definition of Done

- [ ] All five acceptance criteria pass.
- [ ] The completion report quotes the verbatim output of `ruff check src tests`,
      `ruff format --check src tests`, `mypy src` and
      `pytest --cov=dessem_dashboard --cov-report=term-missing`, and every number in the README's
      Development section matches it. Total coverage is at or above **85 percent**, the Epic 5 floor.
- [ ] No sentence in `README.md` is in the future tense about a delivered capability, and no module
      is described as planned.
- [ ] The Extending the chart catalogue section's pinned-count list was produced by performing the
      two edits in a scratch tree and running the suite, and the report says which assertions failed.
- [ ] `git diff --stat docs/checklist-manual-dashboard.md` shows no change, or a diff confined to
      one prose sentence, and `.venv/bin/pytest tests/test_renderer_contract.py
      tests/test_charts_filters.py -q` exits 0.
- [ ] `git status --short` shows only `README.md`, plus
      `docs/checklist-manual-dashboard.md` if and only if a residual false statement was found there.
- [ ] No file under `exemplo/` was read, listed or quoted; no value from it appears in the README.

## Effort Estimate

**Points**: 3 · **Confidence**: High · **Agent time**: about 45 minutes. **Re-estimated up from the
outline's 2 points**, and the reason is measurement rather than caution. The outline treated this as
"replace the Epic 1 README skeleton" and asked three questions whose answers turn out to add work:
a separate guide file is **out** (one README), screenshots are **out** (they would commit study
data), and the extensibility section is **in** and is the most valuable part for a future
maintainer. Refinement then found that the skeleton is not merely thin but **false in five places** —
a module map declaring four existing packages "planned", a seven-class error module described as
one-class, a four-number quality baseline stale in all four numbers, a paragraph describing the
pipeline as a stub, and a summary in the future tense. It also found three behaviours the README has
never documented and an operator will certainly meet: the four named configuration errors, the fact
that `paths.log_dir` has no consumer, and the eight degradation warning shapes. One item refinement
found was **taken away again** before dispatch: the two stale statements in
`docs/checklist-manual-dashboard.md` were corrected by the epic-04 boundary review while this
refinement was being written, which is why requirement 7 now asks for a verification rather than an
edit — and why the ticket keeps 3 points rather than gaining a fourth. Confidence is High because every claim the ticket must make is readable
from a specific shipped module or measurable with one command, and the ticket's own Definition of
Done turns each into a measurement.
