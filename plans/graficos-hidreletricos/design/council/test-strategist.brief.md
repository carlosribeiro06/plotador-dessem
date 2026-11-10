# Design brief — `test-strategist`

- **Domain:** Test strategy
- **Meets all stated requirements:** True
- **Chosen anchor:** `simplestViable`
- **Reversibility:** `two-way`
- **Rationale:** Test code is internal and unshipped and fixes no format, schema or public API, so every choice here is a two-way door: take the simplest plan that covers every stated requirement, and add any mostDurable item later when a requirement asks for it.
- **Confidence:** 82

Rendered by `/plan` P2 from the `design-council` workflow's returned data (schema: `~/.claude/skills/plan/references/design-brief.md`).

## simplestViable

**Description.** Three test deliverables plus manual-checklist content, with no new fixture machinery. (1) COUNT PINS (R22, R25): update every moved pin literal in place, in the SAME commit as the SPECS enable/reorder, so the per-commit quality gate never goes red. Measure values with enabled_specs()/all_specs() on the changed registry; the intake numbers are only the expected result: 31 enabled, 16 disabled, SIN group 8, fixture files 33/32/33, METADADOS 31, _UHE_ENTITY_COUNTS_IN_ORDER=(3,2,2,3,3,3,3,3). _SIN_UNITS_IN_ORDER gains three m3/s entries, so _THREE_DISTINCT_SIN_UNITS becomes _FOUR_DISTINCT_SIN_UNITS={MW,MWh,hm3,m3/s}. R25 also covers count-bearing test NAMES, comments and docstrings, which never fail: test_all_specs_has_forty_seven_entries_with_nineteen_disabled -> ..._sixteen_disabled; test_document_sin_chart_keys_equal_the_five_default_enabled_charts -> ..._eight_...; test_fixture_payload_sin_units_are_three_distinct_strings... -> four_distinct; the 'five SIN' comment in test_renderer_controls.py; the 'five sections'/'across five charts' docstrings in test_charts_sin.py; the '28 of the 47 ... 21 series' comments in test_integration_exemplo.py/test_parity.py; and the '19 disabled' comment in test_schemas.py. No new fixture-level test is needed for R1/R3/R6(data side)/R13/R14/R18: the existing tests iterate _SIN_CHART_KEYS, _UHE_CHART_KEYS_IN_ORDER, _ENABLED_KEYS_IN_ORDER, _ALL_SIN_CHART_KEYS and _ALL_ENABLED_CHART_KEYS, so they extend automatically. That covers registry order, document order, units, one entity, deck and chained axis lengths for both scenarios, and the new SIN keys being hidable via charts.disabled. (2) R27 REGRESSION TEST at the consolidation seam (tests/test_consolidate.py), behavioural and without mocks: give _build_settings a fictitious_codes knob defaulting to (11, 99) so existing tests stay unchanged. Add one parametrized test over build_dashboard_data with include_fictitious=False: fictitious_codes=(99,) -> '11' in data.entities('CMO_SBM'), '99' absent, and no warning containing 'código(s) de submercado do gráfico'; fictitious_codes=(2, 11, 99) -> '2' hidden and no dropped-code warning for 2. It must be shown RED on current main, where 11 is hidden by the hard-coded default and spuriously warned as dropped, and GREEN after the fix. Add one unit test in test_registries.py: load_registries(sintese_dir, fictitious_codes=(99,)) marks 11 non-fictitious. It is needed because the fixture's fictitious set {11, 99} equals the hard-coded default, which is why the defect is invisible today. (3) REAL-DATA TEST (R20): one new test in tests/test_integration_exemplo.py that reuses the existing exemplo_two_scenario_paths fixture (it skips when fewer than two scenarios qualify), _build_settings and _extract_payload, and runs pipeline.run on the pair. Its assertions are tree-agnostic, with no hard-coded 169 plants or 80 stages: payload chart keys of group SIN equal the R13 SIN order and of group UHE the R13 UHE order (insertion order, also via sections_by_chart_key on the document); each of QDEF_SIN/QTUR_SIN/QVER_SIN has unit 'm3/s', exactly one entity, a non-empty str subtitle, and, for both scenarios on every deck axis and the chained axis, a series whose length equals axes[k]['starts'] with at least one non-null value; no warning names any of the three keys. Optionally, pending the dessem seat, it also asserts on payload values that QDEF_SIN == QTUR_SIN + QVER_SIN per point within 3 * 10^-decimals / 2. That check uses dashboard output only and catches swapped source files or misaligned axes. Acceptance criteria: the test is PASSED, not SKIPPED, under DESSEM_DASHBOARD_EXEMPLO=<repo>/examples (shown with pytest -rs), and it SKIPS in milliseconds with the variable unset. (4) MANUAL CHECKLIST CONTENT handed to the doc seat (R20): build on examples/Oficial + examples/Modificado; 8 SIN sections in R13 order; the three SIN flow charts in Por deck x {Absoluto, Diferença} and Encadeado x {Absoluto, Diferença}; the UHE order; disabling one new SIN key hides it. Expected observation: Vazão Incremental in Diferença is identically zero for this pair, because both scenarios share the same hydrology. Run the quality gate as two chunked invocations, tests/test_[a-l]*.py then tests/test_[m-z]*.py with --cov-append, in the background. Defer K2 (fixture METADADOS fidelity) as recorded debt.

**Forgoes.** Gives up:
- automated execution of the client-side Diferença and Por deck rendering;
- value equality between payload and synthesized files on real data;
- the synthesizer identity SIN = Σ UHE;
- a fixture whose METADADOS carries real long names and no CUSTO_*/TEMPO_* rows (K2), so fixture documents keep never showing a subtitle for the SIN flows;
- a centralised count source (the operator rejected it in Q11);
- a structural test that pins the SPECS 'enabled first, then disabled' layout;
- a pinned-volume test for the examples pair.

## mostDurable

**Description.** Everything in simplestViable, plus:
- One measured source of truth for chart counts that every pin imports (the operator rejected this in Q11).
- A fixture-fidelity rework (K2): _metadados_operacao writes realistic long names that differ from titles for the flow keys, and stops writing rows for CUSTO_*/TEMPO_* keys, so the subtitle path is exercised on every fixture document.
- A real-data value-equality test that reads each SIN and UHE flow file and compares it to the payload rounded to output.decimals, on both the deck axis and the chained window. It would read the files through readers.read_series, or with pandas as test_parity.py already does.
- Synthesis-property tests on the real tree: SIN = Σ UHE per stage, and QDEF = QTUR + QVER per plant.
- A structural test that SPECS and FALLBACK_UNITS keep the 'enabled first, then disabled' grouping.
- A pinned-volume test for the examples/Oficial + Modificado pair, next to the caso_oficial/caso_gurobi pair test that currently skips.

**Costs.** Costs:
- Centralising the counts contradicts the operator's Q11 answer.
- The K2 rework needs a new operator-confirmed requirement. It also breaks every 'no subtitle on unmodified fixture' assertion (test_charts_sin, test_charts_hydro, test_charts_thermal, test_builder), may move the measured byte range in test_output_size.py, and so widens the feature diff across about 6 more files.
- Value equality only re-proves the key-agnostic _load_series/payload path, which the fixture tests already cover. It would also break test_integration_exemplo.py's stated rule of never opening files under the tree.
- SIN = Σ UHE validates the synthesizer, not this tool. It needs a tolerance of about 169 x 0.005 m3/s plus null handling, which makes it fragile.
- The layout test and the second pinned-volume test enforce no stated requirement, which the bar treats as over-engineering.
- Rough cost: 2 to 3 extra tickets and noticeably more pins to keep in sync.

## gaps

- R6 client-side behaviour (Diferença subtraction, Por deck selector) for the three new SIN charts is never executed automatically, because there is no Node.js and dashboard.js is only checked statically. Automated evidence stops at payload shape plus the existing static renderer contract, so the manual checklist is the only gate for it.
- The R20 automated test skips on every CI runner and on any machine without the gitignored examples/ tree. It only has effect when run locally with DESSEM_DASHBOARD_EXEMPLO=<repo>/examples, so its ticket must require evidence of a PASSED (not SKIPPED) run.
- The optional payload-level assertion QDEF_SIN == QTUR_SIN + QVER_SIN is blocked until the dessem seat confirms that this is an identity of every DESSEM synthesis at SIN level, with no bypass or desvio term. It holds on the examples pair, but a tree-agnostic test must not encode a property of one study.

## oneWayDoors

_none_

## twoWayDoors

- Put the real-data test in tests/test_integration_exemplo.py, reusing its skip and settings infrastructure, rather than in a new module.
- Update count pins in place rather than centralising them (operator Q11).
- Defer K2 (fixture METADADOS fidelity) as recorded debt rather than adding a ticket, since no requirement asks for it and the subtitle path is already covered by test_builder/test_payload with a modified METADADOS.
- Include or omit the payload-level QDEF = QTUR + QVER assertion, pending the dessem seat.
- Add a fictitious_codes knob to test_consolidate._build_settings, defaulting to (11, 99).
- Keep or drop load_registries' hard-coded (11, 99) default (K4). If it is dropped, the roughly 25 test_registries.py call sites pass the fixture's codes explicitly through one module-level constant or helper, and the regression test is unchanged.
- Add no test that enforces the SPECS 'enabled first, then disabled' layout. The module docstring and review cover K5.

## contracts

- Pin-update manifest for the feature ticket. For each file and symbol it gives the before -> after value and the count-bearing test names, comments and docstrings to rename, all measured with enabled_specs()/all_specs(). It lands in the same commit as the SPECS change.
- R27 regression spec: a parametrized behavioural test in tests/test_consolidate.py over build_dashboard_data, using a non-default fictitious set; it must be red on main and green after the fix. Plus one load_registries unit test with fictitious_codes=(99,) in tests/test_registries.py.
- Real-data test spec: one test in tests/test_integration_exemplo.py on exemplo_two_scenario_paths, with tree-agnostic assertions: R13 SIN/UHE order, SIN flow unit m3/s, one entity, non-empty subtitle, per-scenario series on every deck axis and the chained axis with length equal to axis starts and at least one non-null value, and no warning naming the three keys. Acceptance criteria: PASSED with DESSEM_DASHBOARD_EXEMPLO=<repo>/examples, SKIPPED without it.
- Manual-checklist test content for open-source-documentation-writer: the examples-pair build command; 8 SIN sections in order; each SIN flow chart in the 4 mode combinations; the UHE order; disabling a new SIN key hides it; QINC_UHE Diferença identically zero as the expected observation for Oficial x Modificado.
- Ticket ordering constraints: the feature ticket and the R27 ticket both edit tests/test_registries.py, so serialize them. The real-data test depends on the feature ticket. The docs and checklist counts depend on the feature ticket's measured values.
- Quality-gate invocation for every ticket: ruff check, ruff format --check, mypy src, then pytest as two chunked runs (tests/test_[a-l]*.py, then tests/test_[m-z]*.py with --cov-append) in the background, with coverage at or above 85%.

## questionsForUser

- Confirm that K2 (the fixture METADADOS writes the title as the long name, plus rows for CUSTO_*/TEMPO_* keys) is recorded as debt and not fixed in this plan. Fixing it would need a new requirement and would touch about 6 more test files.
- Should the real-data test assert QDEF_SIN == QTUR_SIN + QVER_SIN on the payload, within rounding tolerance? Recommended only if the dessem-specialist confirms it is a universal identity of the synthesis at SIN level.
