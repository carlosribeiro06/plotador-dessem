# Epic 05: Delivery, Validation and Legacy Removal

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **refined** (2026-09-11). The six tickets carry no `[OUTLINE]` marker and are
> dispatch-ready. Readiness scored in `.implementation-state.json`; mean **0.97**, minimum 0.93.
> Refined against the **built artefact**, not against the plan: every signature, settings key,
> log-field name, Portuguese string and test assertion quoted in these tickets was read from the
> shipped code or measured with a command, per the instruction in epic-04 learnings section 5.

## Goal

Close the feature: wire the real pipeline behind the CLI built in Epic 1, run it end to end on real
data, prove parity with the legacy charts, write the user documentation, make a run legible to its
operator, and only then delete the legacy scripts.

## Scope

In scope: replacing the `pipeline.run` stub with the real orchestration, the skip-guarded
integration test against a real scenario tree, the legacy parity check and its report, the CLI
output pass, the final documentation, and the removal of `Leitura/`, `Plotadores/` and the five
`main_*.py` drivers.

Out of scope: any new chart, any new filter, any change to the payload shape, and any change to the
`settings.json` contract — all of which belong to earlier epics or to a future feature. Also out of
scope: any change to a shipped Portuguese message's text, and any `ChartSpec` addition, including
the cost-chart and time-chart splits ticket-035 puts on the developer's desk.

## Tickets

| Ticket | Title | Points | Outline points | Detail | Readiness |
| ------ | ----- | ------ | -------------- | ------ | --------- |
| ticket-033 | Wire the end-to-end pipeline | 3 | 3 | refined | 1.00 |
| ticket-034 | Add the example-data integration test | 3 | 3 | refined | 1.00 |
| ticket-035 | Run the legacy parity check | 3 | 3 | refined | 0.97 |
| ticket-036 | Write the user documentation | **3** | 2 | refined | 0.97 |
| ticket-037 | Polish the CLI usability and error messages | 2 | 2 | refined | 0.95 |
| ticket-038 | Remove the legacy scripts | 1 | 1 | refined | 0.93 |

**Total: 15 points**, up from the outline's 14. One ticket was re-estimated and five held.

- **ticket-036: 2 → 3.** The outline treated it as "replace the Epic 1 README skeleton". Refinement
  measured the skeleton and found it **false in five places** — a module map declaring four existing
  packages "planned", a seven-class `errors.py` described as one-class, a four-number quality
  baseline stale in all four numbers, a paragraph asserting `pipeline.run` is a stub, and a summary
  in the future tense — and added two sections the outline did not have (Reading the dashboard, and
  Extending the chart catalogue, whose two-file recipe plus seven pinned-count locations is the most
  valuable page for a future maintainer).
- **ticket-033 held at 3** because the two directions cancelled: every open question the outline
  raised turned out to be "already handled, add nothing", while the real file count is four rather
  than three — `cli.py` must thread `--modo-inicial`, a flag that today changes nothing.
- **ticket-035 held at 3** although its content changed more than any other ticket's: the comparison
  method moved from "maybe run the legacy scripts" to an independent recomputation, which is cheaper
  and stronger.
- **ticket-037 held at 2** because refinement **removed** its largest implied item, a style audit of
  66 `raise` sites, and replaced it with three additive changes.
- **ticket-038 held at 1**: thirteen deletions and one sentence, with the effort dominated by
  verification, which is the right shape for an irreversible change.

## Dependency Order

```text
ticket-033 -> ticket-034 -> ticket-035 -> ticket-036 -> ticket-037 -> ticket-038
```

**Strictly sequential, and every edge is load-bearing.** Dispatch notes:

- **ticket-035 before ticket-038 is a hard constraint, never to be reordered.** 038 deletes
  `Plotadores/`, which is 035's reference implementation, and 038's requirement 2 additionally
  makes 035's parity report a precondition it verifies before deleting anything.
- **033 and 037 both write `src/dessem_dashboard/cli.py` and `tests/test_cli.py`**, so they can
  never be parallelised even if the graph allowed it.
- **036, 037 and 038 all write `README.md`.** 036 rewrites it, 037 updates three enumerated places
  in it, 038 adds one sentence to the Legacy scripts subsection 036 wrote.
- **034 and 036 both touch `docs/checklist-manual-dashboard.md`** — 034 adds the guard test for its
  section 9, 036 verifies its prose — so neither may run beside the other.
- **034 creates `tests/exemplo_tree.py`, which 035 imports.** A shared non-test helper module,
  following the `tests/fixtures_sintese.py` and `tests/dashboard_document.py` precedent, so the two
  tickets do not duplicate the tree resolution or reach into each other's private helpers.

**One pre-identified seam, recorded rather than acted on.** ticket-035 delivers two artefacts — a
test module and a report document — and is the only ticket in the epic that could be read as having
two objectives. It is dispatched whole because splitting it would renumber ticket-036 to ticket-039
across five documents, exactly the reasoning that kept ticket-030 whole in epic 4. The seam, if the
orchestrator wants it, is requirements 1 to 4 (the test module) against requirements 5 to 7 (the
report), and the report depends on the test only for section (c)'s verdict column.

## Epic Decisions

Resolved during refinement, each with the evidence that settled it. Cite the decision; do not
re-derive it.

| # | Decision | Rationale and evidence |
| - | -------- | ---------------------- |
| **E5-1** | **The legacy parity check is an independent recomputation plus a documented presentation comparison. The legacy scripts are never executed.** | Three measured reasons. (a) `.venv/bin/python -c "import Leitura.leitor_arquivos"` raises `FileNotFoundError: 'C:/Users/carlo/OneDrive/Documentos/git/plotador-dessem/exemplo'` — the path is hard-coded at line 9 and iterated at module level on line 13 — and all twelve other legacy modules carry `from Leitura.leitor_arquivos import *`, so every one fails at import. (b) They require the date-first layout `exemplo/<data>/<caso>/sintese`; decision 15 rebuilt the tree scenario-first, so `leitor_arquivos` would hand scenario names to `pd.to_datetime`. (c) `main_custos.py:17` binds `df_cp, df_cd` and line 19 passes `df_cf`, and `main_tempo.py:19` passes `df_pls` instead of its own `df_tempo_pl`: both work only through star-imported globals, so "just fix the path" is not a mechanical edit. Editing them would produce a *modified* reference, which is worse than none. |
| **E5-2** | **The legacy scripts are deleted outright. No `legacy/` directory.** | The objection on the record was that the open cost-presentation decision's only evidence is `Plotadores/Custos.py`. ticket-035 removes that premise by transcribing the evidence into a versioned document — seven modules, twelve `write_html` call sites, 21 runtime output filenames, every axis and figure title with a `file:line` reference, the verbatim scalar formulas, four implementation defects, and the unit divergence of E5-3. ticket-038 requirement 2 makes that report's existence a hard precondition. Measured: nothing in `src/`, `tests/`, `docs/`, `README.md`, `CLAUDE.md` or `pyproject.toml` references the thirteen files, and all of them sit outside every quality gate. |
| **E5-3** | **The `(R$)`-versus-`10^3 R$` cost-unit divergence is the epic's most consequential parity finding, and the new dashboard is the correct side.** | The epic-04 boundary review established from `reference/parquet-schemas.txt` that `CUSTOS.valor_esperado` is in `10^3 R$`: `PRESENTE = 58667.5674` tracks `COP_SIN`'s reference-deck sum (`406.6581 R$/h × 144 h`, ratio 1.0019) and `FUTURO = 228420390.34615` tracks `CFU_SIN = 228917.0446721` at `10^6 R$` (ratio 0.9978 as `10^3 R$`, 1000× off as plain `R$`); `METADADOS_OPERACAO.unidade` never contains plain `R$`. The legacy axes are labelled `(R$)` at `Plotadores/Custos.py` lines 34, 52 and 77. So the legacy label was wrong by 1000×; `FALLBACK_UNITS["CUSTOS"]` is now `10^3 R$`. ticket-035 records it in the report's own section (g) as a divergence the new tool introduces deliberately. |
| **E5-4** | **`reference/parquet-schemas.txt` is the authorised source of real-data figures. `exemplo/` may be run over but never transcribed.** | That committed 933-line dump covers all 60 files of the reference deck `exemplo/2024-03-03/caso_oficial/sintese`, which decision 15 verified byte-identical by blob hash to `exemplo/caso_oficial/2024-03-03/sintese`. A figure quoted from it, with the file cited, is measured; a figure read from `exemplo/` is not available to any agent on this plan. This is the proper closure of spec defect 17, and it is what lets ticket-035 pin two absolute real-data values (`CUSTOS.TOTAL = 228479057.91`, `TEMPO.TOTAL = 198.12` min) instead of settling for relative comparisons. |
| **E5-5** | **A warning never changes the exit code. Exactly three exit codes: 0, 1, 2.** | Master plan decision 18 makes a degraded run a deliberate success — "a partially comparable dashboard is more useful than none". A batch caller detects degradation from `run_manifest.json`'s `warnings` array, which is machine-readable, complete (the log is capped, the manifest is not), and already written. A fourth exit code would make every missing file a build failure. |
| **E5-6** | **`DESSEM_DASHBOARD_EXEMPLO` is read by `tests/exemplo_tree.py` only, never by `src/`.** | `settings.json` is the single configuration anchor for the program (CLAUDE.md); an environment variable in `src/` would be a second channel. The variable exists to point the *suite* at data outside the repository, which is a test concern. Measured: `grep -rn "os.environ\|getenv" src/ tests/` returned no match before this epic, so the epic introduces the project's first environment-variable read and puts it in the only place it belongs. |
| **E5-7** | **No pytest marker for the integration and parity tests, and no `markers` entry in `pyproject.toml`.** | `[tool.pytest.ini_options]` declares only `addopts` and `testpaths` and does not set `--strict-markers`, so a custom marker warns until registered. On any machine without the data — every CI runner, since `exemplo/` is gitignored — the modules skip in milliseconds; on the developer's machine the run is wanted. A marker would add configuration for a selection nobody would use. |
| **E5-8** | **No screenshots in the documentation, and no second documentation file.** | `.gitignore` ignores generated `*.html` but not images, so a screenshot of a real run would commit ONS study values — plant names, costs, load curves — into a repository that is pushed to a remote. A plain-text page-layout figure carries the same structural information with no data. And `rules/markdown.md` makes the README the single entry point: a second guide would duplicate the `settings.json` table, the one thing in the project guaranteed to drift. |
| **E5-9** | **The categorical X axis is not offered as an option, and `plano_dashboard_dessem.md` stays at the repository root.** | Master plan decision 14 settles the axis: with stage durations of 0.5, 2, 6 and 8 hours a categorical axis gives an 8-hour stage the same width as a 30-minute one, and the legacy's own `tickformat` was inert under `type='category'` anyway. A second axis mode would be a new settings key, which this epic's scope excludes. The spec file stays put because `planning-context.md`'s Sources table names it at the repo root and `.gitignore` keeps `*.md` versioned by decision 11. |

## Live Defects and Gaps This Epic Closes

Found by reading the shipped code against the plan, which is the technique epic-04 learnings
section 5 prescribes for a late epic's refinement.

| Gap | Owner | Evidence |
| --- | ----- | -------- |
| `--modo-inicial` is accepted, documented and recorded in the manifest, and **changes nothing in the output**: `cli.main` never passes it to `pipeline.run`, which has no such parameter, and `write_dashboard` defaults to `"encadeado"`. | ticket-033 requirement 3, acceptance criterion 3 | Read from `cli.py:144` and `cli.py:150-155` against `pipeline.py:29-42` and `builder.py:366-372`. Same shape as the `TEMPO` axis defect: two correct halves, no ticket owning the correspondence. |
| `settings.discovery.sintese_dirname` has **no consumer in `src/`**: `discover_scenarios` has zero `src/` call sites. | ticket-033 requirement 1, acceptance criterion 4 (with a negative case, so the assertion cannot pass on a hard-coded `"sintese"`) | `grep -rn "discover_scenarios" src/` matches only a docstring in `data/consolidate.py`. |
| `DashboardData.add_warning` **never logs**, so the degradation record reaches the HTML `Avisos` section and (after 033) the manifest, but never the operator's console or the log file. | ticket-033 requirement 2 (the manifest and the count), ticket-037 requirement 2 (each message plus a cap) | `store.py:278-285`. CLAUDE.md requires logging that lets one reconstruct an official run. |
| Checklist **section 9 is the only one of nine guarded by no test**. It carries the two load-bearing instructions of the epic-04 closure: step 30's `min`-not-seconds check and step 29's "read and record" measurement. | ticket-034 requirement 5, with a non-vacuity proof | `grep -rn "checklist-manual\|_DOCS_CHECKLIST" tests/*.py` names only `test_renderer_contract.py` and `test_charts_filters.py`; `grep -rn "checklist" tests/test_charts_times.py` returns nothing. |
| `settings.paths.log_dir` is validated and then **read by no module**. | ticket-036 requirement 2 (documented honestly; the settings contract is not changed) | `grep -rn "log_dir" src/` matches only `config.py:22` and `config.py:221`. |
| `README.md` is **false in five places** after four epics. | ticket-036 requirements 1 and 3 | Measured against `find src/dessem_dashboard`, `errors.py`, and the four gate commands. |
| Epic-02 learnings section 5's rule "verified by `grep -rn "exemplo" tests/` returning nothing" is **stale**: it has matched `tests/test_renderer_contract.py:460` since ticket-024. | ticket-034 Current State and Pitfalls | The rule's intent holds; the grep is no longer the gate. |
| The legacy implementation carries **four defects** that parity must not reproduce: `.values[0]` silently discarding a repeated `etapa`; y values in concatenation order paired against a `np.unique`-sorted x array; `df_datas` taken from the first scenario only; and the `(R$)` labels of E5-3. | ticket-035 requirement 4 and report section (f) | Read from `Plotadores/Tempo.py:22-24`, `Plotadores/Ghid_SIN.py:26-30` and `Plotadores/Custos.py:34,52,77`. |
| The `CUSTOS` 3-figures-to-1-chart presentation collapse has an **unrecorded twin**: `Plotadores/Tempo.py` emits **four** figures (`Tempo MILP`, `Tempo PL`, `Tempo Leitura de Dados e Impressão`, `Tempo Total`) where the dashboard ships one. | ticket-035 requirement 6 (both go to the developer as open decisions) | `Plotadores/Tempo.py` lines 33, 51, 69, 94. Only the cost case was on the record. |

## Measured Baselines

Every figure below was measured during refinement and **must be re-measured** before it is quoted
again; the plan has shipped five spec defects that were stale counts carried forward by reading.

| Item | Value | Command |
| ---- | ----- | ------- |
| Collected tests | **602** (601 before the epic-04 boundary review added one to `tests/test_charts_times.py`) | `.venv/bin/pytest --collect-only -q` |
| Full-suite duration | **about 10 minutes** — 589 s measured here at 601 tests, 564 s and 618 s at the epic-04 boundary. The "about 220 s" of an early ticket-032 draft is stale and was corrected at that boundary. | `.venv/bin/pytest` |
| Total coverage | **99 percent**; `config.py` 94, `logging_setup.py` 95, `cli.py` and `pipeline.py` 100 | `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing` |
| Enabled chart specs | **23** of **42** declared | `enabled_specs()` / `SPECS` |
| `CUSTOS` / `TEMPO` units | **`10^3 R$`** and `min` | `enabled_specs()` |
| `raise` sites in `src/` | **66** (27 `ConfigError`, 12 `StoreError`, 9 `SchemaError`, 8 `RegistryError`, 4 `DiscoveryError`, 2 `DataFileError`, 4 `ValueError`) | `grep -rh "raise [A-Za-z]*Error" src/dessem_dashboard --include="*.py" \| wc -l` |
| `logger.warning` sites in `src/` | **10** (9 before the boundary review added the `time.unit_divisor` mismatch warning) | `grep -rh "logger.warning" src/dessem_dashboard --include="*.py" \| wc -l` |
| Distinct `log_step` messages | **15** in the pipeline chain, plus `pipeline.py`'s own | `grep -rn "log_step(" src/` |
| Degradation warning shapes | **8**, from `timeline.validate_chaining` (2), `align_deck_dates`, `_check_timeline_coverage`, `_load_series`, `_load_scalars`, the submarket-coverage branch and the absent-entity branch | read from `timeline.py` and `consolidate.py` |
| `errors.py` classes | **7** | `grep -c "^class " src/dessem_dashboard/errors.py` |
| Tracked legacy files | **13** | `git ls-files Leitura Plotadores main_*.py` |
| Tracked `__pycache__` paths | **0**; `.gitignore` line 2 is `__pycache__/` | `git ls-files \| grep -c __pycache__` |
| Lint and types | clean; `ruff format --check` 57 files, `mypy src` 26 source files | the three gate commands |

## Quality Gate for the Epic

- `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
  `.venv/bin/mypy src` exit 0 after every ticket.
- `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing` passes with total coverage at
  or above **85 percent** — the Epic 5 floor from the master plan's Testing Strategy, raised from the
  80 percent of Epics 1 to 4. Measured at 99 percent before the epic starts, so the floor is not a
  constraint in practice; it is a regression guard.
- Every ticket's completion report quotes the collected test count it measured, never one read from a
  document.
- The 32-step manual browser walk of `docs/checklist-manual-dashboard.md` happens once, in
  ticket-034, against a real-data build. It is outstanding for the whole feature by design under
  epic decision E3-1.

## Open Decisions for the Developer

None blocks a ticket. The first two are produced by this epic; the last two are carried from epic 4
and are still unowned.

1. **The two presentation collapses.** `CUSTOS`: three legacy figures with their own axes versus one
   grouped bar chart. `TEMPO`: four legacy figures versus one. ticket-035 records both with their
   options — accept, or add three or four `ChartSpec` entries in a follow-up — and the evidence the
   developer needs: checklist step 29's recorded cost magnitudes and step 30's four time bars.
   Neither is chosen by any ticket.
2. **The cost-scale caveat, now measurable.** `PRESENTE` and `FUTURO` differ by about four orders of
   magnitude on the reference deck (`5.87e4` against `2.28e8` in `10^3 R$`, from
   `reference/parquet-schemas.txt`), so on a shared linear axis the `PRESENTE` bar may be invisible.
   A log axis is ruled out — it cannot render the signed Diferença view. The unified hover and a box
   zoom are the workarounds shipped.
3. **Plant labels carry the name without the code.** Adding the code is a one-line label change.
   Carried from epic 4; no ticket owns it.
4. **`output.decimals` is global, not per chart.** Carried from epic 4; no ticket owns it.

## Refinement Inputs Consumed

- `epic-04-learnings.md`, all ten sections. Section 5's instruction — refine a late epic against the
  built artefact, re-reading `payload.py`, `scalars.py`, `builder.py` and the asset before writing —
  is what produced the Live Defects table above. Section 10's five open items are all placed:
  the manual walk to ticket-034, the cost-parity tension to ticket-035, the 035-before-038 ordering
  to ticket-038's banner, the `__pycache__` question dropped by measurement, and the three unseen
  developer decisions to Open Decisions above.
- `epic-03-learnings.md`: the ten payload keys, the nine chart keys, the `KEYS` contract, the DOM
  contract, the five single-file invariants, and section 2's named measurement for ticket-034.
- `epic-02-learnings.md`: section 1's public API, section 2's Portuguese vocabulary, section 3's
  three-case degradation split, section 6's eight spec-defect shapes (every requirement in these six
  tickets was screened against them) and section 7's vacuous-test patterns.
- `.implementation-state.json`'s four epic-05 refinement inputs, all four honoured: the ordering
  risk, the cost-parity tension, the answered `__pycache__` question and the
  delete-versus-`legacy/` argument.
- The shipped code: `pipeline.py`, `cli.py`, `config.py`, `manifest.py`, `logging_setup.py`,
  `errors.py`, `dashboard/builder.py`, `dashboard/payload.py`, `dashboard/scalars.py`,
  `dashboard/theme.py`, `data/discovery.py`, `data/consolidate.py`, `data/schemas.py`,
  `charts/specs.py`, `assets/dashboard.js`, `settings.json`, `pyproject.toml`, `.gitignore`,
  `README.md`, `docs/checklist-manual-dashboard.md`, the thirteen legacy modules, and thirteen test
  modules.

## Amendment Note

These six tickets were refined while the epic-04 boundary `code-simplifier` and `code-reviewer`
were still running, and **the boundary's findings landed mid-refinement**. One amendment pass was
applied afterwards, on 2026-09-11, correcting: `FALLBACK_UNITS["CUSTOS"]` from `R$` to `10^3 R$`
(boundary finding 1) in tickets 034, 035 and 036; the new `time.unit_divisor` mismatch warning
(boundary finding 3) in tickets 036 and 037, taking the `logger.warning` count from 9 to 10; the
collected test count from 601 to 602; the suite duration to about 10 minutes; and ticket-036's
requirement 7, which had asked for two checklist fixes the boundary review had already made — that
requirement is now a verification rather than an edit, which is why ticket-036 kept 3 points instead
of gaining a fourth. The amendment is itself an instance of the discipline: the tickets were
re-verified against the artefact rather than against the draft.
