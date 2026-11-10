# Design brief — `python-task-automation-developer`

- **Domain:** Python CLI / automation
- **Meets all stated requirements:** True
- **Chosen anchor:** `simplestViable`
- **Reversibility:** `two-way`
- **Rationale:** Every choice here is a two-way door, so the simpler option wins: the order of a tuple literal, internal function signatures, and where test assertions live. No file format, settings key, CLI flag, exit code or chart key is created or changed. The `(11, 99)` default is removed anyway, because CLAUDE.md requires it, not because the door is one-way.
- **Confidence:** 80

Rendered by `/plan` P2 from the `design-council` workflow's returned data (schema: `~/.claude/skills/plan/references/design-brief.md`).

## simplestViable

**Description.** Five steps, each confined to source the intake already names. (1) charts/specs.py: delete `enabled=False` from QDEF_SIN, QTUR_SIN and QVER_SIN and move the three `_series(...)` calls out of the trailing disabled block into the enabled SIN block, right after VARMF_SIN. This costs the same diff as flipping them in place, renders identically (measured in the intake), and keeps the module docstring's 'enabled first, then disabled' layout true. Reorder the UHE block to GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER. Keys, titles, units and the `notes=` constants do not change. Rewrite the docstring counts to the measured 47 / 31 / 16. (2) data/schemas.py: move the three SIN flow FALLBACK_UNITS entries under the 'Enabled chart catalogue' comment. Replace the header comment's '23 ... 19' with the measured counts: 26 keys backing enabled charts (24 series keys plus CUSTOS and TEMPO, which back 7 scalar charts) and 16 disabled keys, 42 in total. (3) R27: `registries.load_registries(sintese_dir, *, fictitious_codes: Sequence[int])` becomes a required keyword with no `(11, 99)` default. CLAUDE.md forbids hard-coding a tunable, so keeping the default does not meet the stated rules. `consolidate._load_registries(scenarios, *, fictitious_codes)` forwards it at both call sites, and `build_dashboard_data` passes `settings.submarkets.fictitious_codes`. `_load_series` is left as it is: it already reads the same Settings object for the dropped-code set. Every direct caller gets the keyword: 27 in tests/test_registries.py through one module constant mirroring settings.json, and tests/test_parity.py:594 with the settings value. (4) Add one regression test in tests/test_consolidate.py. With `fictitious_codes=[99]` and `include_fictitious=false`, code 11 must appear among the SBM chart entities and no dropped-code warning may name 11. Today it fails both ways: 11 is hidden by the hard-coded flag and is then reported as dropped. (5) Update each count pin in place with the value measured through enabled_specs()/all_specs(), and add the real-data assertions to the existing tests/test_integration_exemplo.py behind its qualifying_scenarios skip guard.

**Forgoes.** One single point for the submarket fictitious policy. Classification stays baked into the loader (Submarket.fictitious is set at load time), while the dropped-code warning set is derived separately in _load_series from the same setting. The two stay consistent only because both read one Settings object, not because of how the code is structured. Also forgone: a dedicated real-data test module for the hydro flows, any count-pin centralisation (the operator rejected it in Q11), and a fixture-level check of the METADADOS subtitle (K2).

## mostDurable

**Description.** Everything in simplestViable, plus moving the fictitious-submarket policy out of the file loader. `load_registries` becomes a pure mirror of the files with no policy argument, and `Submarket` loses its `fictitious` field. `visible_submarket_codes(registries, *, include_fictitious, fictitious_codes)` applies the policy, and `build_dashboard_data` computes the codes once, `frozenset(settings.submarkets.fictitious_codes)`, and passes that one set to both visibility and the dropped-code warning in _load_series. No loader can then carry a hidden tunable default again, and visibility and warnings come from one source by construction.

**Costs.** Changes the Submarket dataclass and the signatures of three functions (load_registries, _build_submarkets, visible_submarket_codes). It means rewriting about 6 fictitious-flag tests in tests/test_registries.py and the visible_submarket_codes call in tests/test_parity.py. The 27 plain load_registries calls in the tests would need no edit. It also contradicts the literal wording of R27 ('fictitious_codes reaches registries.load_registries'), so it goes beyond the declared scope and would need operator confirmation (a CLARIFICATION REQUIRED under the bar) or a ticket of its own.

## gaps

- On fixtures, the METADADOS subtitle path of the newly enabled SIN flow charts is not exercised, because tests/fixtures_sintese.py writes nome_longo_variavel = spec.title (K2). Only the skip-guarded real-data test covers it, so CI machines without examples/ never check it.
- `mypy src` does not cover tests/. Making the load_registries keyword required can therefore leave tests/test_parity.py, which only runs with real data, broken without notice unless the ticket greps every caller and runs that module once with DESSEM_DASHBOARD_EXEMPLO=<repo>/examples.

## oneWayDoors

- The keys QDEF_SIN, QTUR_SIN and QVER_SIN freeze once they are enabled by default. Operators may name them in charts.disabled (R18), and renaming one later would turn those settings into a RegistryError. The plan must keep the existing keys and must not rename them.

## twoWayDoors

- Where the three SIN specs sit in SPECS: moved into the enabled SIN block or flipped in place. Render order is identical either way; the move is recommended for layout symmetry.
- UHE order inside SPECS. It is a tuple-literal reorder with no data effect.
- Removing the `(11, 99)` default from load_registries. It is an internal signature; tests/test_parity.py:594 must be edited and checked under DESSEM_DASHBOARD_EXEMPLO, because `mypy src` does not type-check tests and a missed keyword only fails when real data is present.
- Moving the fictitious policy out of the loader (the mostDurable option). It can be deferred to its own ticket without rework, since the simplestViable signature change is a subset of it.
- Where the R27 regression test lives (test_consolidate.py end to end, or test_registries.py at unit level). The recommendation is test_consolidate, because the defect is in consolidation's plumbing.
- Whether the real-data assertions go into test_integration_exemplo.py or a new module. Extending the existing module is the default.

## contracts

- Catalogue after the change: all_specs()=47, enabled_specs()=31, disabled=16. The SIN group has 8 charts (GTER_SIN, GHID_SIN, GUNS_SIN, EARMF_SIN, VARMF_SIN, QDEF_SIN, QTUR_SIN, QVER_SIN), the UHE group 8 (GHID_UHE, VARMF_UHE, VARPF_UHE, QAFL_UHE, QINC_UHE, QDEF_UHE, QTUR_UHE, QVER_UHE), and SBM stays at 6, unchanged. SERIES charts rise from 21 to 24. Downstream must measure these numbers, not copy them.
- Unchanged identity: QDEF_SIN 'Defluência', QTUR_SIN 'Turbinamento' and QVER_SIN 'Vertimento' are all m3/s, group SIN, selector NONE. On real data each shows its METADADOS long name as a subtitle ('Vazão Defluente', 'Vazão Turbinada', 'Vazão Vertida'). With the fixture it shows none, because of the K2 gap.
- `load_registries(sintese_dir: Path, *, fictitious_codes: Sequence[int]) -> Registries` is a required keyword with no default. `_load_registries(scenarios, *, fictitious_codes)` is fed from `settings.submarkets.fictitious_codes` in `build_dashboard_data`. With the shipped settings ([11, 99]) the dashboard output is identical.
- R27 regression contract for test-strategist: fictitious_codes=[99] with include_fictitious=false must make code 11 a visible SBM entity and produce no 'código de submercado descartado' warning naming 11. Both assertions fail on main, which proves the test detects the defect.
- No CLI, stdout or exit-code change, no new settings.json key, no new dependency. No change to consolidation, payload or renderer for the feature: enabling the three specs flows through the existing _load_series → DashboardData.add_series → payload → dashboard.js path.
- The real-data assertions extend tests/test_integration_exemplo.py and reuse its qualifying_scenarios skip guard. They run under DESSEM_DASHBOARD_EXEMPLO=<repo>/examples, and expected values come from the files rather than literals such as 169 plants or 80 stages.
- For the doc seat (R24): README 'Enabling an already-declared chart' is factually wrong today. ChartRegistry.enabled_specs filters on `spec.enabled`, so turning on a shipped-disabled spec is a source edit in charts/specs.py (deleting `enabled=False`, then updating the pins); charts.disabled can only take charts away. The replacement example has to describe that mechanism, not only swap QDEF_SIN for another key.

## questionsForUser

- R27 can be done two ways. Option A (recommended) threads a required `fictitious_codes` keyword into `registries.load_registries`, which matches R27's wording and stays in scope. Option B widens R27 to move fictitious classification out of the loader into `visible_submarket_codes`: it removes `Submarket.fictitious` and gives one policy point, but it contradicts R27's literal 'reaches load_registries' and goes beyond the ticket. Which one do you want?
