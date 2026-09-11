# ticket-034 Add the example-data integration test

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `monorepo-test-developer`
> Commands run in WSL bash at `/home/carlosribeiro/git/plotador-dessem` through `.venv/bin/`.
> **Dispatch order: strictly after ticket-033 and strictly before ticket-035.**
> **Data handling, read this twice.** This ticket is the *only* one in the plan authorised to make
> the test suite read `exemplo/`, and the authorisation is narrow: the new test may **run the
> pipeline over that tree through the library**, and nothing may **open, list, copy, move, delete or
> transcribe** anything under it. No value read *from `exemplo/`* may be written into this ticket,
> into a test file, into the README or into any plan document. Spec defect 17 of this plan was
> exactly that — "`FUTURO` is about 2.3e8 R$" attributed to data its author could not read.
> **One authorised source of real-data figures does exist**, and the epic-04 boundary review used it
> to close that defect properly: `plans/dashboard-dessem/reference/parquet-schemas.txt` is a
> committed 933-line dump of the reference deck (`exemplo/2024-03-03/caso_oficial/sintese`, which
> `planning-context.md` decision 15 verified byte-identical by blob hash to
> `exemplo/caso_oficial/2024-03-03/sintese`), carrying dtypes, unique value lists and sample rows for
> all 60 files. A figure taken from that file, **with the file cited**, is measured rather than
> fabricated. A figure taken from `exemplo/` itself is neither.

## Context

### Background

The master plan's Testing Strategy commits to "one end-to-end integration test in Epic 5 [that] runs
against a real scenario tree located via the `DESSEM_DASHBOARD_EXEMPLO` environment variable,
falling back to the repository's `exemplo/caso_oficial` and `exemplo/caso_gurobi`, and is **skipped**
when no valid tree is found". Master plan open question 5, resolved by the developer on 2026-09-10,
fixes the tree: `exemplo/caso_oficial/{2024-03-03,2024-03-04}/sintese` and
`exemplo/caso_gurobi/{2024-03-03,2024-03-04}/sintese`, 60 Parquet files each, rebuilt from git
history with `git archive HEAD` and blob-hash verified, and gitignored — so the tree exists only on
the developer's machine. `exemplo/sintese/` stays beside them as a flat *structure sample* and is
deliberately **not** a valid scenario.

Nothing in the repository references that environment variable yet: `grep -rn
"DESSEM_DASHBOARD_EXEMPLO" src/ tests/ docs/ README.md` returns **no match**, and so does
`grep -rn "os.environ\|getenv" src/ tests/`. This ticket introduces the project's first environment
variable, and it introduces it **in the test only**. Reading it in `src/` would create a second
configuration channel beside `settings.json`, which CLAUDE.md makes the single anchor for every path
and tunable; the variable's whole purpose is to let a *developer* point the *suite* at data that
lives outside the repository.

The value this test adds over the 602 synthetic tests is scale and shape that the fixtures cannot
reach. `tests/conftest.py`'s `scenario_tree` builds 50-stage decks with 3 hydro codes, 2 reservoir
codes, 2 thermal codes, 4 submarket codes and 2 interchange pairs. The real decks carry **68 and 64
stages**, **165 hydro plants** (118 of them reservoir plants), **89 thermal plants**, **6 submarket
registry rows** and **12 interchange pairs** (master plan Appendix A.2 to A.4, measured during
planning, and re-confirmable from the committed dump: `UHE.parquet  shape=(165, 6)`,
`UTE.parquet  shape=(89, 4)`, `TEMPO.parquet  shape=(9, 3)`, `CUSTOS.parquet  shape=(4, 3)`). Two
things only break at that scale: an array whose length disagrees with its axis, and a
non-rectangular coverage pattern — `VCALHA_UHE`'s 7,616 rows over 92 plants is explicitly *not* a
plant-times-stage product, and `VARMF_UHE` covers 118 plants where `GHID_UHE` covers 165.

Epic-03 learnings section 2 also hands this ticket one named measurement:
`DashboardData.stored_deck_dates(chart_key, entity_id, scenario)` is "a per-call O(n) scan with no
index — **ticket-034 should measure it at production scale** (165 plants × 30 decks × 3 scenarios)
before anyone optimises it". Thirty decks do not exist. Requirement 6 therefore narrows that to the
scale that does exist and turns it into a recorded figure rather than an assertion, because a timing
assertion in a test suite is flaky by construction.

### Relation to Epic

The epic's validation ticket. ticket-033 wired the pipeline and proved it on synthetic data;
this ticket proves it on the real thing, and it is the natural moment for the manual browser walk
that epic-04 learnings section 10 records as outstanding for the whole feature — 32 steps across 9
sections of `docs/checklist-manual-dashboard.md`, none of which has been walked in a browser. Its
results are the input ticket-035 compares against the legacy formulas and ticket-036 documents.

### Current State

`pipeline.run` is real after ticket-033: `discover_scenarios(..., sintese_dirname=...)` →
`build_dashboard_data(..., settings=..., reference=...)` → `write_dashboard(..., initial_mode=...)`
→ `output_volumes(...)`, returning `RunResult(output_file, data_volumes, warnings)` with six integer
volume keys and one warning list.

`discovery.discover_scenarios` is deliberately **non-recursive**: only a scenario directory's
immediate subdirectories are candidate decks, and its module docstring states that a directory which
*itself* directly contains a synthesis folder — "the flat `exemplo/sintese/` structure sample" — has
zero decks and raises the same fatal error as any other empty scenario. The skip predicate must
therefore use the same non-recursive rule, or it will treat `exemplo/sintese` as a scenario and turn
a clean skip into a `DiscoveryError`.

`tests/` today references `exemplo` in exactly **one** place, measured:
`tests/test_renderer_contract.py:460`, `assert "--casos exemplo/caso_oficial exemplo/caso_gurobi" in
text`, which pins the build command inside `docs/checklist-manual-dashboard.md`. **Epic-02 learnings
section 5 says "No test may read `exemplo/` — verified by `grep -rn "exemplo" tests/` returning
nothing". That grep no longer returns nothing, and has not since ticket-024.** The rule's intent —
no test may *read* that data unconditionally — still holds and this ticket keeps it by skipping; the
grep is no longer the gate and must not be used as one.

`docs/checklist-manual-dashboard.md` holds **9 sections and 32 numbered steps**, ending at step 32,
title `# Manual Release Checklist — Dashboard (Epic 3)`. Eight of its nine sections are guarded by a
test that asserts their content: sections 1 to 7 by seven tests in `tests/test_renderer_contract.py`
(`test_checklist_file_has_a_numbered_step_list`,
`test_checklist_covers_offline_load_and_console_error_check`,
`test_checklist_covers_ons_identity_with_exact_footer_text`,
`test_checklist_covers_level_navigation_over_six_groups`,
`test_checklist_covers_deck_and_encadeado_modes_with_disabled_selector_and_stage_width`,
`test_checklist_covers_absoluto_diferenca_toggle_with_the_reproducible_case`,
`test_checklist_step_15_expected_result_covers_the_y_axis_title_switch`,
`test_checklist_covers_submarket_and_interchange_pair_selectors`,
`test_checklist_covers_avisos_section_on_a_scenario_missing_a_deck`) and section 8 by
`test_checklist_epic_4_section_replaces_the_ticket_028_placeholder` in the same file plus
`test_checklist_replaces_the_placeholder_with_plant_filter_steps` in
`tests/test_charts_filters.py`.

**Section 9 — `## 9. Cost and time bar charts`, steps 27 to 32, written by ticket-031 — is guarded
by nothing.** Measured: `grep -rn "checklist-manual\|_DOCS_CHECKLIST" tests/*.py` names only
`tests/test_renderer_contract.py` and `tests/test_charts_filters.py`, and
`grep -rn "checklist" tests/test_charts_times.py` returns no match. Ticket-031's requirement 9
appended the section and no requirement asked for a test. That section carries the two
load-bearing instructions of the whole epic-04 closure: step 30's "the Y axis reads `min` … never a
raw count of seconds", which is the only behavioural check on the defect ticket-031 fixed, and step
29's "**Read and record** the two magnitudes", which is the measurement that settles the open cost-
scale decision. A simplifier deleting either would break no test. Requirement 5 closes that gap.

Measured baselines for this ticket, all re-measurable in seconds and none to be trusted from this
document: `pytest --collect-only -q` reports **602 tests** after the epic-04 boundary review (601
before it); a full run took **589 s (9:49)** at 601 tests with total coverage **99 percent**, and
the two boundary runs took 564 s and 618 s, so budget **about 10 minutes**; `enabled_specs()`
returns **23** specs of **42** declared; `ruff check src tests`, `ruff format --check src tests`
(57 files) and `mypy src` (26 source files) all exit 0.

The epic-04 boundary review also changed one fact this ticket asserts: `FALLBACK_UNITS["CUSTOS"]`
is now **`10^3 R$`**, not `R$` (boundary finding 1, propagated into `data/schemas.py`, master plan
Appendix A.5 and A.6, and `planning-context.md`). Verify the current value by calling
`enabled_specs()` rather than trusting any document, including this one.

## Specification

### Requirements

1. Create `tests/exemplo_tree.py`, a **shared helper module** with three public functions and no
   `test_*` function of its own, following the precedent of `tests/fixtures_sintese.py` and
   `tests/dashboard_document.py` (pytest's default collection never picks it up, and ticket-035
   imports it rather than duplicating the resolution or reaching into a private helper of a sibling
   test module):
   - `exemplo_root() -> Path` returns `Path(os.environ["DESSEM_DASHBOARD_EXEMPLO"])` when that
     variable is set to a non-empty value, otherwise `<repository root>/exemplo` derived from
     `Path(__file__).resolve().parent.parent`.
   - `qualifying_scenarios(root) -> tuple[Path, ...]` returns the root's immediate subdirectories,
     sorted by name, that **qualify** as a scenario: a directory with at least one immediate
     subdirectory containing a `sintese/` child directory that holds `EST.parquet`. The rule must be
     non-recursive, mirroring `discovery._decks_of`, so that `exemplo/sintese/` does not qualify.
   - `documented_pair(root) -> tuple[Path, Path] | None` returns `(caso_oficial, caso_gurobi)` in
     that documented order when both qualify under `root`, and `None` otherwise.
   Then create `tests/test_integration_exemplo.py`, importing those three and adding the skip
   mechanism: every test is skipped, with an English skip reason naming both
   `DESSEM_DASHBOARD_EXEMPLO` and the resolved default path, when fewer scenarios qualify than it
   needs. A missing root, a root that is a file, an unreadable root and a root with one qualifying
   scenario must each produce a skip rather than an error, and neither module may raise at import or
   collection time under any filesystem condition.
2. Write the universal invariants test, which must hold for **any** real tree with at least two
   qualifying scenarios and must assert nothing that depends on which study the data came from.
   Assert, against a run into `tmp_path`: the six `data_volumes` keys in order with every value an
   `int`, `cenarios == 2`, `graficos == 23`, `valores > 0`,
   `bytes_html == output_file.stat().st_size`, `bytes_html > bytes_plotly`; the document contains
   `Gerência de Ferramentas Energéticas - FEN`, the prefix `data:image/png;base64,`, exactly 23
   `<section class="chart"` occurrences, and the three script ids `plotly-js`, `dashboard-payload`
   and `dashboard-js` in that order; the embedded payload parses with `json.loads` after the
   `<` escape is reversed, carries `schema_version == 1` and exactly the ten documented
   top-level keys, and every chart entry carries exactly the nine documented keys.
3. In the same test, assert the **length invariant** that only real scale exercises: for every
   `SERIES` chart, every entity, every scenario and every axis key in its `series` mapping,
   `len(values) == len(payload["axes"][axis_key]["starts"])`. This is the single strongest assertion
   available on unknown data, and it is what a silent reindex onto the wrong axis would break.
4. In the same test, classify the warnings instead of counting them. `RunResult.warnings` must be
   non-`None`, and **every** message must match one of the eight shapes the data layer can emit,
   matched on a distinctive substring of each: `Encadeamento apresenta lacuna entre os decks de`,
   `Encadeamento apresenta sobreposição entre os decks de`, `não possui deck para a data`,
   `tem timeline divergente do eixo do deck de`, `não encontrado no cenário` (which covers both the
   series and the scalar file-missing shapes), `código(s) de submercado do gráfico`, and
   `ausente(s) no cenário`. **Do not assert that the warning list is empty and do not assert that it
   is non-empty**: the real tree's coverage is not recorded anywhere in this plan, so either
   assertion would be a claim about data no agent on this plan may read. A message matching none of
   the eight shapes is a finding and must fail the test.
5. Add the missing guard for checklist section 9 to `tests/test_renderer_contract.py`, as one new
   test beside the nine that guard sections 1 to 8. Scope it to section 9's **own slice** — from
   `## 9. Cost and time bar charts` to the next `\n## ` or end of file — following the narrowed shape
   of `test_checklist_epic_4_section_replaces_the_ticket_028_placeholder`, and assert inside that
   slice: `Custo Presente, Futuro e Total`, `Tempo Computacional`, `03/03/2024 - PRESENTE`,
   `Read and record`, the Y-axis claim `min`, and ` (diferença)`. **Do not assert that nothing
   follows section 9** — ticket-036 may append, and an assertion that a later ticket has not run yet
   is cross-ticket collision 6 of this plan, which was authored by exactly this reasoning error.
   Prove the new test fails against a copy of the checklist with section 9 removed.
6. Write the single-scenario test: one qualifying scenario, `reference` equal to its basename.
   Assert `cenarios == 1`, `payload["reference"] == label`, and
   `payload["theme"]["scenario_colors"] == {label: "#486018"}` — the reference always takes brand
   green whatever its position, which is `theme.scenario_colors`' documented rule and has never been
   exercised with a single scenario. This answers the outline's second open question with a yes: the
   spec allows one `--casos` argument, the difference view then has nothing to compare against, and
   one extra assertion set is the cheapest possible coverage of that case.
7. Record three measurements in the completion report, none of them asserted in a test: the
   wall-clock duration of `tests/test_integration_exemplo.py`; the `elapsed_s` field of the
   `Payload JSON construído` log line from the two-scenario run, which is the `stored_deck_dates`
   scan cost epic-03 learnings section 2 asked this ticket to measure, together with the
   `valores` count it covered; and the `bytes_html` and `bytes_plotly` volumes, so the controlled
   share of the real document is on the record for ticket-036's documentation. State explicitly in
   the report that no study value was read or transcribed.
8. Add **no** pytest marker and **no** `markers` entry to `pyproject.toml`. `[tool.pytest.ini_options]`
   declares only `addopts` and `testpaths` and does not set `--strict-markers`, so a custom marker
   would emit `PytestUnknownMarkWarning` until registered, and registering it buys nothing: on any
   machine without the data — every CI runner, since `exemplo/` is gitignored — the module skips in
   milliseconds, and on the developer's machine the run is wanted.
9. Write the artefact into `tmp_path`, never into `output/`. `output/` is gitignored but it is still
   the repository tree, and the manual checklist's step 12 command is the thing that is supposed to
   write there. Never write, create, rename or delete any path under `exemplo/`.
10. Touch no file under `src/`. If any assertion of requirements 2 to 4 fails, that is a **finding**:
    stop, report the failure verbatim, and do not change a source module to make the test pass. The
    prediction this ticket is testing is that ticket-033's pipeline is correct at real scale; a
    source change here would destroy the evidence.

### Inputs

The environment variable `DESSEM_DASHBOARD_EXEMPLO`, when set, else `<repo>/exemplo`. From the
resolved root: the qualifying scenario directories, read only through `pipeline.run`. A
`settings.json` written into `tmp_path` whose values match the repository's own file except that
`paths.logo_file` points at `<repo>/logo/MarcasONS_Secundarias_verticais_Verde.png` — the pattern
`tests/test_output_size.py::_REPO_LOGO` established. `reference` is the first scenario of the
documented order `caso_oficial`, `caso_gurobi` when both qualify under the default root, and the
first sorted qualifying scenario otherwise; the documented order is preferred so that the automated
run and the operator's manual walk of checklist step 12 describe the same artefact.

### Outputs and Behavior

On a machine with the tree: three dashboard documents built into `tmp_path` (two-scenario,
single-scenario, and whatever the section-9 guard needs — nothing, it reads a document file), every
assertion of requirements 2 to 4 and 6 passing, and the three measurements of requirement 7 recorded.
On a machine without it: every test in the module reports `SKIPPED` with a reason naming the
environment variable and the resolved default path, the rest of the suite is unaffected, and the
exit status is unchanged. The section-9 guard of requirement 5 runs **always** — it reads a
versioned document, not the data.

### Error Handling

The module must not raise at import or collection time under any filesystem condition. A missing
root, a root that is a file, a root containing only `exemplo/sintese`, a root whose single
qualifying scenario is fine for requirement 6 but insufficient for requirement 2, and a
`PermissionError` while listing the root must all resolve to a skip. Inside a test, every exception
propagates: a `DiscoveryError`, `SchemaError`, `DataFileError`, `RegistryError`, `StoreError` or
`ConfigError` raised by the pipeline on real data is precisely the finding this test exists to
surface, and must not be caught.

## Dependencies

- **Blocked By**: `ticket-033-wire-end-to-end-pipeline.md`
- **Blocks**: `ticket-035-run-legacy-parity-check.md`, which imports the three
  `tests/exemplo_tree.py` helpers requirement 1 creates
- **Dispatch-order constraint, not a graph edge**: must not run concurrently with
  `ticket-036-write-user-documentation.md`, which may append to
  `docs/checklist-manual-dashboard.md`, the file requirement 5 asserts against.

## Acceptance Criteria

- [ ] Given an environment with no `DESSEM_DASHBOARD_EXEMPLO` and no `exemplo/` directory, when
      `.venv/bin/pytest tests/test_integration_exemplo.py -q` runs, then every test in the module
      reports `SKIPPED`, the exit status is 0, and the skip reason names both
      `DESSEM_DASHBOARD_EXEMPLO` and the resolved default path — verified by running with
      `DESSEM_DASHBOARD_EXEMPLO` pointed at an empty temporary directory, which reaches the same
      predicate without touching the real tree.
- [ ] Given a tree with at least two qualifying scenarios, when the two-scenario test runs, then the
      six `data_volumes` keys appear in the order `cenarios, decks, graficos, valores, bytes_html,
      bytes_plotly`, `cenarios == 2`, `graficos == 23`, `bytes_html == output_file.stat().st_size`,
      `bytes_html > bytes_plotly`, the document holds exactly 23 `<section class="chart"`
      occurrences and the exact footer text, and the embedded payload parses with
      `schema_version == 1` and exactly the ten top-level keys `schema_version, scenarios,
      reference, deck_dates, chained_key, axes, charts, theme, formats, labels`.
- [ ] Given the same run, when every `SERIES` chart's `series` mapping is walked, then for every
      (entity, scenario, axis key) triple `len(values) == len(payload["axes"][axis_key]["starts"])`,
      and the walk visited at least one entity of at least one `UHE`-group chart, so the assertion is
      proven non-vacuous rather than passing over an empty mapping.
- [ ] Given the same run, when `RunResult.warnings` is inspected, then every message contains at
      least one of the eight documented substrings, and a deliberately injected message
      (`"mensagem desconhecida"` appended to a copy of the list) makes the same check fail — proving
      the classification rejects an unknown shape instead of accepting anything.
- [ ] Given `docs/checklist-manual-dashboard.md`, when the new section-9 guard runs, then it passes
      against the shipped file and fails against an in-memory copy with the
      `## 9. Cost and time bar charts` section removed; and
      `.venv/bin/pytest tests/test_renderer_contract.py tests/test_charts_filters.py
      tests/test_integration_exemplo.py -q && .venv/bin/mypy src && .venv/bin/ruff check src tests`
      exits 0.

## Implementation Guide (Technical Details)

### Suggested Approach

1. Build the module skeleton and the skip path **first**, and verify it by pointing
   `DESSEM_DASHBOARD_EXEMPLO` at an empty temporary directory. Getting the skip right before the
   data path exists is what guarantees the module never breaks CI, and it is testable without the
   real tree.
2. Put the three resolution helpers in `tests/exemplo_tree.py` and keep them free of any pytest
   import, so ticket-035 can reuse them without inheriting a fixture. Express the skip in
   `tests/test_integration_exemplo.py` as a `pytest.fixture` that calls `pytest.skip`, not as a
   module-level `pytest.mark.skipif` expression: the fixture evaluates at call time rather than at
   import time, so a filesystem error cannot break collection, and it can return the resolved
   scenario tuple to the test that needs it.
3. Copy the settings/`_REPO_LOGO` builders from `tests/test_output_size.py` rather than importing a
   private helper from a sibling module — `tests/dashboard_document.py` exists because ticket-027
   needed shared helpers under public names, and the same rule applies here. Reuse
   `dashboard_document.chart_section_slices` and `sections_by_chart_key` for the document
   assertions instead of writing a third slicer.
4. Extract the payload with the two constants `tests/test_output_size.py` already defines —
   `'<script id="dashboard-payload" type="application/json">'` and `"</script>"` — then reverse
   `payload_json`'s escape with `.replace("\\u003C", "<")` before `json.loads`. `payload_json`
   writes `allow_nan=False`, so a successful parse is itself the proof that no `NaN` or infinity
   reached the payload from real data.
5. For the length invariant, walk `payload["charts"]` and skip entries whose `kind` is
   `SCALAR_BY_DECK`; count the triples visited and assert the count is greater than zero, and
   separately assert that at least one visited chart had `group == "UHE"`. A walk that silently
   visits nothing is the vacuous shape this plan has recorded three times.
6. For the warning classification, put the eight substrings in one module-level tuple with a comment
   naming the function that emits each: `timeline.validate_chaining` for the two `Encadeamento`
   shapes, `timeline.align_deck_dates` for `não possui deck para a data`,
   `consolidate._check_timeline_coverage` for `tem timeline divergente`,
   `consolidate._load_series` and `consolidate._load_scalars` for `não encontrado no cenário`,
   `consolidate`'s submarket-coverage branch for `código(s) de submercado do gráfico`, and
   `consolidate`'s absent-entity branch for `ausente(s) no cenário`. Then assert
   `all(any(shape in message for shape in SHAPES) for message in warnings)` and, for non-vacuity,
   that the same expression is `False` over `[*warnings, "mensagem desconhecida"]`.
7. Write the documented-tree assertions as a **second** test, guarded by its own predicate: the
   default root is in use, exactly the two documented scenario basenames qualify, and the run's
   `deck_dates` are exactly `["03/03/2024", "04/03/2024"]`. Only inside that guard assert the
   Appendix A figures: `len(axes["03/03/2024"]["starts"]) == 68`,
   `len(axes["04/03/2024"]["starts"]) == 64`, `len(axes["encadeado"]["starts"]) == 96`
   (48 stages × 2 decks), `len(charts["GHID_UHE"]["entities"]) == 165`,
   `len(charts["VARMF_UHE"]["entities"]) == 118`, `len(charts["GTER_UTE"]["entities"]) == 89`,
   `len(charts["CMO_SBM"]["entities"]) == 4` (codes 1 to 4, `include_fictitious` false),
   `len(charts["INT_SBP"]["entities"]) == 12`, `set(charts["CUSTOS"]["scalars"]) == {"PRESENTE",
   "FUTURO", "TOTAL"}`, `set(charts["TEMPO"]["scalars"]) == {"MILP", "PL", "Leitura", "TOTAL"}` and
   `charts["CUSTOS"]["unit"] == "10^3 R$"` with `charts["TEMPO"]["unit"] == "min"`. Every one of
   those figures is transcribed from master plan Appendix A.2, A.4, A.6,
   `planning-context.md` and `reference/parquet-schemas.txt`, all of which measured them; **none is
   measured by this ticket**, and if one fails the failure is the finding. Read the two units from
   `FALLBACK_UNITS` at test time rather than hard-coding the strings, so the assertion follows a
   future unit correction instead of contradicting it — that is the pairing lesson of epic-04
   boundary finding 3.
8. Assert the `TEMPO` internal consistency the same way, without touching the data: for each
   scenario and deck key present in all four series, `TOTAL` equals `MILP + PL + Leitura` within
   `10 ** -settings.output.decimals`. That is a real check on `scalars.aggregate_times` at real
   scale and it needs no external figure. Do **not** add a magnitude bound on the minute values: the
   only bound that would catch a seconds-versus-minutes regression needs the raw seconds, which this
   ticket may not read, and checklist step 30 already covers it with a human.
9. Add the section-9 guard last, and prove it fails: read the checklist, delete the section-9 slice
   from the string in memory, run the same assertions against the mutated copy, and confirm they
   raise. Write the proof into the test's docstring, as
   `test_checklist_epic_4_section_replaces_the_ticket_028_placeholder` does for its own.
10. Walk the manual checklist. Build with the documented command
    `dessem-dashboard --casos exemplo/caso_oficial exemplo/caso_gurobi` — which writes into
    `output/`, is gitignored, and is the step-12 reproduction case that
    `tests/test_renderer_contract.py:460` pins — open the file from `file://`, and record a pass or
    fail for each of the 32 steps in the completion report. Step 29 asks the operator to read and
    record the `PRESENTE` and `FUTURO` magnitudes; **record them in the walk report handed to the
    developer, and not in any file under `plans/` or `tests/`**, because that is the boundary spec
    defect 17 crossed.

### Key Files to Create/Modify

- `tests/exemplo_tree.py` (create: `exemplo_root`, `qualifying_scenarios`, `documented_pair`;
  imported by `tests/test_integration_exemplo.py` here and by `tests/test_parity.py` in ticket-035)
- `tests/test_integration_exemplo.py` (create: the skip fixture, the two-scenario universal test,
  the documented-tree test, the single-scenario test, the skip-reason test)
- `tests/test_renderer_contract.py` (modify: one new test, the section-9 checklist guard; change
  nothing else in the file)

### Patterns to Follow

- `tests/test_output_size.py`'s `_REPO_LOGO`, `_settings_dict`, `_build_settings` and `_build_data`
  quartet, and its `_PAYLOAD_OPEN_TAG` / `_SCRIPT_CLOSE_TAG` payload extraction.
- `tests/dashboard_document.py`'s public slicing helpers, for every document assertion.
- `test_checklist_epic_4_section_replaces_the_ticket_028_placeholder`'s **narrowed** slice pattern —
  heading to next `\n## ` or end of file — and its docstring convention of recording how the
  assertion was proven able to fail.
- The plan-wide non-vacuity discipline: every set-membership or classification assertion is paired
  with a mutated input that makes it fail.
- `tests/conftest.py`'s fixture style: a docstring stating what the fixture guarantees, and
  deterministic resolution with no hidden global state.

### Pitfalls to Avoid

- Do not let the module raise at import or collection time. A `Path.iterdir()` on a missing root
  raises `FileNotFoundError`; the predicate must guard it. Measured precedent: importing
  `Leitura.leitor_arquivos` raises exactly that, because it iterates a hard-coded path at module
  level.
- Do not treat `exemplo/sintese/` as a scenario. It is a flat structure sample with no deck
  subdirectory; `discovery`'s docstring names it explicitly. A recursive qualification rule would
  pick it up and turn a skip into a `DiscoveryError`.
- Do not use `grep -rn "exemplo" tests/` as a gate on anything. It already matches
  `tests/test_renderer_contract.py:460` and has since ticket-024; epic-02 learnings section 5 is
  stale on this point.
- Do not assert that the real run produces no warnings, or that it produces some. Nothing in this
  plan records the real tree's coverage, and both directions would be claims about unreadable data.
- Do not hard-code any study value — no `valor`, no cost, no duration, no plant name. Only the
  Appendix A structural counts, and only inside the documented-tree guard.
- Do not assert a wall-clock bound. Requirement 7 records timings; a timing assertion in a 9:49
  suite on a developer laptop is flaky by construction.
- Do not write into `output/` from a test, and never write anywhere under `exemplo/`.
- Do not register a pytest marker. `--strict-markers` is not set, so an unregistered marker warns,
  and registering one adds a `pyproject.toml` key for a selection nobody will use.
- Do not read the environment variable from `src/`. `settings.json` is the single configuration
  anchor per CLAUDE.md; the variable exists to redirect the **suite**.
- Do not assert that nothing follows checklist section 9, and do not assert that any file is
  unchanged by a later ticket. That is cross-ticket collision 6, and it was authored by an amendment
  written to fix the very same shape one level up.
- Do not fix a source module to make an assertion pass. Report the failure; requirement 10 makes
  that the deliverable.

### Out of Scope

- Any change under `src/`, including `pipeline.py`, and any change to `settings.json`,
  `pyproject.toml` or `.gitignore`.
- Any new checklist step or section. Requirement 5 adds a **guard** for the section ticket-031
  already wrote; ticket-036 owns the checklist's prose, its stale title and its stale intro
  paragraph.
- The legacy parity comparison and the parity report (ticket-035).
- The README's `DESSEM_DASHBOARD_EXEMPLO` documentation (ticket-036).
- Any performance optimisation of `stored_deck_dates`. Requirement 7 measures; whether to optimise is
  a later decision that needs the measurement first.
- A second integration test over a three-scenario or thirty-deck tree. Neither exists.

## Testing Requirements

### Unit Tests

None. This ticket adds no unit-testable code beyond the two resolution helpers, which are exercised
by the skip criterion.

### Integration Tests

`tests/test_integration_exemplo.py`, four tests:

- `test_exemplo_two_scenarios_universal_invariants` — acceptance criteria 2, 3 and 4;
- `test_exemplo_documented_tree_pinned_volumes` — Suggested Approach steps 7 and 8, skipped when the
  tree is not the documented one;
- `test_exemplo_single_scenario_reference_takes_brand_green` — requirement 6;
- `test_exemplo_skip_reason_names_env_var_and_default_path` — acceptance criterion 1, run with
  `DESSEM_DASHBOARD_EXEMPLO` pointed at an empty `tmp_path` so it exercises the predicate on every
  machine, including one that has the real tree.

### Regression

`tests/test_renderer_contract.py` passes **as amended** by requirement 5, which adds one test and
changes none. Every other test module passes **unchanged**: this ticket writes no source and edits no
existing assertion.

## Definition of Done

- [ ] All five acceptance criteria pass, and the two non-vacuity proofs — the injected unknown
      warning and the checklist copy with section 9 removed — were each observed to fail before
      restoration.
- [ ] `.venv/bin/pytest tests/test_integration_exemplo.py -q` reports four skips with a reason naming
      `DESSEM_DASHBOARD_EXEMPLO` when the root is empty, and four passes when the real tree is
      present.
- [ ] `.venv/bin/ruff check src tests`, `.venv/bin/ruff format --check src tests` and
      `.venv/bin/mypy src` exit 0; `.venv/bin/pytest --cov=dessem_dashboard --cov-report=term-missing`
      passes with total coverage at or above **85 percent** (the Epic 5 floor; measured at 99 percent
      before this ticket).
- [ ] Checklist section 9 is guarded by a test, so all nine sections of
      `docs/checklist-manual-dashboard.md` are now guarded.
- [ ] The 32 manual checklist steps were walked in a browser against a real-data build, and a pass
      or fail is recorded for each in the completion report. Step 29's two magnitudes are reported to
      the developer and written into **no** repository file.
- [ ] The completion report carries the three measurements of requirement 7 — module duration,
      payload-build `elapsed_s` with its `valores` count, and the two byte volumes — plus the
      collected test count from `pytest --collect-only -q`. No count or duration is cited without
      being measured.
- [ ] The report states explicitly that no value from `exemplo/` was transcribed into any file, and
      that no path under `exemplo/` was created, modified or deleted.
- [ ] `git status --short` shows only the three files this ticket owns.

## Effort Estimate

**Points**: 3 · **Confidence**: Medium · **Agent time**: about 45 minutes plus the manual browser
walk. Unchanged from the outline's 3 points. What changed is the content rather than the size: the
outline's three open questions all resolve here — a second single-scenario test is **in** (one
cheap assertion set over a case the spec allows and nothing covers), a pytest marker is **out**
(unregistered markers warn and CI skips anyway), and the artefact goes to `tmp_path` — and refinement
added two items the outline did not have: the missing guard for checklist section 9, found by
grepping the suite rather than by reading the plan, and the classification-not-count treatment of
warnings, which is the only way to assert something strong about data the plan may not read.
Confidence is Medium rather than High for one structural reason: the ticket's strongest assertions
are the Appendix A counts, and those were measured during planning on a tree that was later
flattened and rebuilt from git history. If a count is off, the ticket cannot distinguish a
regression from a stale appendix without the developer, and requirement 10 deliberately forbids
guessing.
