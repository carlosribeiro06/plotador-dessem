# Design-council sign-off (2026-11-09)

Rendered by `/plan` P3 from the `design-council` workflow (`stage: signoff`). Each seat saw
only the synthesized decisions of its own domain plus the chain contracts (independence
rule, `~/.claude/skills/plan/references/design-brief.md`).

| Seat | Domain | Verdict | Objections |
| --- | --- | --- | --- |
| `dessem-specialist` | DESSEM | **APPROVE** | 0 |
| `python-task-automation-developer` | Python CLI / automation | **APPROVE** | 0 |
| `test-strategist` | Test strategy | **APPROVE** | 0 |
| `open-source-documentation-writer` | Documentation | **OBJECT** | 1 |

## `dessem-specialist` — APPROVE

**Reasoning.** DESSEM specialist sign-off, Consultant mode, 2026-11-09. Sources: skill refs 42-metodologia-hidreletricas §5 (MM 22.3.0 §9.6, diversion), §7 (MM §9.8, eqs. 9.6/9.7, pumping), §11 (MM §9.12, MU §III.3 obs., inflow types) and 22-saidas-deck-b §2 (pdo_hidr Qincr = dadvaz, Qdesv column). Evidence: examples/Oficial and examples/Modificado 2026-08-15 sintese (VERSAO 22.4.1, which is not yet official at ONS). No raw deck is on this machine (~/modelos/dessem/references/decks is missing), so validate_outputs.py does not apply here. The dashboard reads only the sintese Parquet files.

Verified on both scenarios:
(1) Both folders ship the same 65 files. The flow files (unit m3/s in METADADOS_OPERACAO) are exactly QAFL_UHE, QINC_UHE and QDEF/QTUR/QVER at UHE and SIN. There is no Q*_SBM, QAFL_SIN, QINC_SIN, diversion, pumping or evaporation file. VCALHA_UHE is 'Volume Armazenado na Calha' in hm3, a volume, so C-COMP holds.
(2) QDEF_SIN/QTUR_SIN/QVER_SIN are declared at specs.py:337-360 with enabled=False. Their METADADOS long names are 'Vazão Defluente', 'Vazão Turbinada' and 'Vazão Vertida', in m3/s, which matches C-ID.
(3) Each SIN file equals the per-stage sum over the 169 UHE within 3e-11, so deriving SIN would duplicate the shipped files.
(4) QDEF − (QTUR + QVER) is at most 4e-12, min(QAFL − QINC) = 0, and min QINC = 0. The pair shares hydrology.

ADR-003 is correct. It is the operator's binding rule R26, and C-COMP shows it leaves no shipped hydro flow without a chart.

ADR-006 is correct. Contract-only assertions avoid encoding synthesizer properties as DESSEM identities. The prohibition list in C-RD (QDEF == QTUR + QVER, QINC Diferença == 0, QINC >= 0, any balance identity) is right: defluência has a diversion term (MM 22.3.0 §9.6), and no source states QINC >= 0.

ADR-001 is correct. It enables the shipped files with no aggregation code, and the move into the enabled SIN block is layout-only.

Non-blocking notes for the synthesizer. They are fixes to wording and contracts, not objections to the ADRs:

(a) C-SEM amendment (my brief's C1 was too strong). 'Vazão Afluente = incremental + upstream outflows' does not hold at every plant. Sobradinho (169) receives a regularized inflow (dadvaz itp=3) in ONS decks since 2023-02-28, and with that inflow type the plant's balance does not add upstream outflows (MU §III.3 obs.). In the example, QAFL_169 = QINC_169 = 940 m3/s at every stage, while Três Marias (156) is upstream. The README for ticket-009 should:
- say that QINC is the deck's inflow input (dadvaz, unchanged by decisions);
- say that for most plants QINC is the natural incremental inflow, and QAFL adds upstream outflows (lagged by travel time where it exists);
- say that where the deck gives a regularized inflow (Sobradinho), the upstream outflows are already included and QAFL equals QINC;
- not call QINC 'natural' for every plant.

(b) ADR-003's rejected-option text says plain sums 'double-count cascade water'. That is true for QAFL, QDEF, QTUR and QVER, but not for QINC, because incremental inflows add without double counting. The decision rests on R26, so only the wording needs fixing.

(c) ADR-006's rework trigger points to the inequality forms in my brief. Form (c), QAFL >= QINC, needs two caveats:
- It is an equality at regularized-inflow plants.
- It may fail at a reservoir that a pumping station draws from, because MM eq. 9.7 subtracts Qb at the origin reservoir.
A future synthesis-property module must exclude or verify those plants before it asserts (c).

## `python-task-automation-developer` — APPROVE

**Reasoning.** I checked all five decisions against the live tree at main dfae1ed. Each one is sound for the Python CLI / automation domain, and none should be reversed.

ADR-001 (enable-and-move): SPECS in charts/specs.py follows the layout its docstring describes: 28 enabled entries, then a trailing block of entries with `enabled=False`, which now holds the three SIN flows. The intake measured that render order is the same whether the specs are moved or flipped in place. Moving them costs the same diff and keeps the docstring true. The no-derivation alternative is correctly rejected under R9/R26. Groups are listed in order of first occurrence and GTER_SIN opens the SIN group, so the section order does not change.

ADR-002 (reorder only, keep identity): this is correctly marked a one-way door. The keys are operator-facing through charts.disabled, and renaming one would raise a RegistryError. Reordering is a tuple-literal edit with no data, payload or renderer effect, and it matches Q10 (no sub-headings, no DOM/CSS/JS work).

ADR-004 (measured literals, updated in place in the same commit): this follows the operator's Q11 answer. It is also forced by the per-ticket gate, because a reorder or enable commit without its pin updates would fail pytest. The two-way label and the rework trigger (a separate centralisation plan) are right.

ADR-005 (required fictitious_codes keyword): the defect is real. registries.py:225 hard-codes `(11, 99)`. consolidate.py calls load_registries at two sites, in the primary read and in the loop over the other decks, without the keyword. settings.submarkets.fictitious_codes only reaches the dropped-code set at consolidate.py:430. The regression contract does detect the defect. With fictitious_codes=[99] on main, code 11 is still flagged fictitious, so it is not visible. Because 11 is not in the configured set, it then also lands in dropped_submarket_codes and gets a warning. After the fix, both assertions hold. With the shipped [11, 99], output stays byte-identical because the configured value equals the old default. Option A matches R27's wording and the operator's answer A3.

The gap I raised in my brief is covered. `mypy src` does not type-check tests, so the real-data-only caller at tests/test_parity.py:594 must be edited by hand. C-ORD puts tests/test_parity.py and tests/test_registries.py in ticket 002's scope. Since ticket 001 runs first, ticket 002 can run test_parity.py under DESSEM_DASHBOARD_EXEMPLO=<repo>/examples and see a missed keyword. A grep shows the only callers are the two in consolidate.py, test_registries.py and test_parity.py.

ADR-009 (measured deck pairs, defects epic first): `_check_custos/_check_tempo_scalars_match_legacy` count one visit per sintese_dir in context.dirs_by_scenario. They skip a pair only when a stored scalar is missing. Comparing against sum(len(dirs)) with a deck_pairs > 0 guard is therefore exact: it gives 2 on examples/ (one deck per scenario) and 4 on the two-deck pair. A missing scalar still shows up as a failure. Putting both pre-existing defects first means no feature ticket has to accept a known red test.

Non-blocking notes for synthesis, not objections:
- C-CAT says only charts/specs.py changes for the feature. R25 still requires the FALLBACK_UNITS regroup and the comment-count fix in data/schemas.py. Ticket 004 or 005 must explicitly own that comment-and-structure-only edit.
- `_load_registries` currently takes only `scenarios`, so ticket 002 has to add a `fictitious_codes` keyword to it and pass the value from build_dashboard_data. "Passes the settings value on both call sites" implies that signature change, and the ticket should state it.

## `test-strategist` — APPROVE

**Reasoning.** I checked each decision against the repository at main dfae1ed. I did not take the intake's word for it.

ADR-009 / C-PAR: I ran `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples pytest tests/test_parity.py` on main. The result is 1 failed, 10 passed, 4 skipped. The failure is at tests/test_parity.py:608 (`assert 2 == (2 * 2)`), and the 4 skips are the documented-pair reference-deck tests, so "11 passed, 4 skipped" after the fix is correct. Lines 590 and 606 count scenarios and hold on any tree, so lines 608-609 are the only lines that assume two decks per scenario. Counting deck pairs from context.dirs_by_scenario, with a `> 0` guard, keeps the test non-vacuous: it gives 2 on examples/ and 4 on the two-deck documented pair. It also keeps the old intent that every deck stores its scalars. Fixing the known red test first (epic 01) is correct, because later tickets can then require a full green test_parity.py run on examples/ instead of carrying accepted-failure clauses.

ADR-005 / C-R27: load_registries has a hard-coded `fictitious_codes=(11, 99)` default (registries.py:225). It is called only at consolidate.py:365 and :373, 27 times in tests/test_registries.py, and once at tests/test_parity.py:594. No monkeypatch or mock of it exists, so making the keyword required is a contained change. C-ORD already serializes the edits to test_registries.py and test_parity.py. The regression test is genuinely red on main. The fixture defaults to submarket codes (1, 2, 11, 99). With `fictitious_codes=[99]` and `include_fictitious=false`, main still marks 11 fictitious through the default, so 11 is hidden. Since 11 is neither visible nor in the configured set {99}, consolidate.py:182 also warns that it was dropped. Both assertions in the contract therefore fail before the fix and pass after it, and they check behaviour at the consolidation seam without mocks. The extra load_registries unit test with `(99,)` already passes on main. It documents the loader's behaviour rather than proving the fix, which is fine because the consolidation test carries the regression.

ADR-006 / C-RD: Extending test_integration_exemplo.py reuses its skip guard, its settings built from the repository's own file, and `_extract_payload`, instead of copying them into a third real-data module. Reading the expected values with pandas gives an oracle that shares no code with `readers.read_series`. test_parity.py already uses this approach, comparing exactly through `_round_like_payload`, which mirrors the payload's `round()`. On examples/, the SIN flow files have one row per stage (80 rows, unique `estagio`), so the oracle needs no filtering. Keeping synthesizer properties out (A1/A2, C3) is correct for a test of this tool. The documented exemplo/ pair also ships QDEF_SIN, QTUR_SIN and QVER_SIN (68 rows in the archived schema dump), so the test is meaningful on both trees it can run on.

ADR-007 / C-CHK: Sections 8 and 9 each have a guard test that pins their strings (test_charts_filters.py:652, test_renderer_contract.py:532). Steps 1-32 are pinned too: test_checklist_step_15_* pins step 15, and exemplo_tree.py cites the step-12 build command. So appending section 10 with its own guard test, without renumbering, follows the existing pattern. Classing the step numbers as a one-way door is correct.

ADR-004: The operator chose literals updated in place (Q11). Updating them in the same commit as the catalogue change keeps the gate green on every commit. The two chunk patterns in C-ORD (tests/test_[a-l]*.py, then tests/test_[m-z]*.py with --cov-append) cover all 31 test modules, and `addopts` already passes `--cov=dessem_dashboard`.

Notes for ticket-006, none of which blocks approval:
(a) "Zero warnings" is the only assertion in C-RD that depends on the tree. It also reverses the module's earlier rule of classifying warnings instead of counting them. It holds on both known trees (the examples baseline has 0 warnings; the archived plan records zero warnings on the documented pair), and the operator chose it in A1. A false failure would be loud and could only appear on some other tree pointed to by DESSEM_DASHBOARD_EXEMPLO, so I accept it. The assertion message should list the warnings it found.
(b) The payload sets subtitle to `registry_title` only when it differs from `spec.title`, and to None otherwise (payload.py:159). The expected subtitle should be derived with the same rule, or the test should first assert that the file's long name differs from the title.
(c) "The first chaining.stages_per_deck chained stages" only checks the first deck's segment on multi-deck trees. That is a valid subset, not an error.

## `open-source-documentation-writer` — OBJECT

**Reasoning.** I checked these decisions against the live tree: README.md, docs/checklist-manual-dashboard.md, tests/test_renderer_contract.py, charts/registry.py, cli.py, settings.json and the examples/ synthesis folders. ADR-002 and ADR-008 are sound for the Documentation domain. ADR-007 is sound in shape, but its absolute wording conflicts with a stated requirement.

ADR-002 (APPROVE). Keeping every key, title and unit unchanged is the right call for the docs. Keys are identifiers that operators name in charts.disabled, and an unknown key raises RegistryError (registry.enabled_specs, lines 100-102). Calling it a one-way door is correct. The README has no per-level chart order list (a grep for the UHE titles and keys only finds the QDEF_SIN worked example), so reordering SPECS leaves no README order text to fix. The R13 order only needs to appear in the new hydro-flow semantics text and the new checklist section, and both are covered.

ADR-008 (APPROVE). Two serialized README tickets with measured literals is the right size. Three things support it:
- Nothing machine-parses the README, so this is a two-way door.
- Rejecting the docs-drift test is correct: R24 and R28 ask for docs that match the code, not drift-proof docs.
- Running R28 last keeps its quality-gate table final for this plan. That table currently reads 643 passed / 99%.

The shared Logging-and-auditing paragraph is handled properly: R24 sets the 26/104 figures and R28 rewrites the Avisos references around them. I also confirmed that the recipe rewrite C-DOC requires is needed, not cosmetic. registry.enabled_specs keeps only spec.enabled specs, so charts.disabled can only remove charts, and the README line "needs no source change at all" (lines 444-449) is false today. Placing ticket-009 after R27 (ticket-002) correctly lets it re-check the submarkets.fictitious_codes row and warning shape 7.

ADR-007 (OBJECT). Appending section 10 as steps 33+ with a static guard test is the right shape. The guard test is particularly needed: test_checklist_section_9_* exists only because section 9 once had no guard. The figures C-CHK cites also check out: chaining.stages_per_deck is 48, each example deck has 80 stages, and there is one deck per scenario. Dropping "Defluência = Turbinamento + Vertimento" as a checklist relation, which my own brief had proposed, is the correct correction per C-SEM and A2.

The problem is the clause "steps 1-32 are never renumbered or reworded", repeated in C-CHK as "steps 1-32 stay verbatim". It forbids an edit that R24 explicitly requires, and ADR-007 lists R24 among the requirements it satisfies. R24 says: "docs/checklist-manual-dashboard.md SIN count (five -> eight)". That text sits inside two numbered steps:
- line 33, step 3's expected result: "five initially visible SIN charts";
- line 56, step 7's expected result: "the five SIN charts disappear".

No ticket in C-DOC or C-ORD is given this edit, and as written the contract forbids it. Leaving it unchanged makes both steps false once ticket-004 enables the three SIN specs. The checklist's own Purpose paragraph says no step should require interpretation, so a release walker would mark steps 3 and 7 as failed on a correct build. No test pins the word "five" (grep of tests/ finds none), so the edit breaks nothing.

The real one-way door is step numbering plus the test-pinned strings, not the full text. The rule should be narrowed to protect exactly that and to let the R24 count fix through.

**Objections.**

- `ADR-007`: "Steps 1-32 are never renumbered or reworded" (and C-CHK's "steps 1-32 stay verbatim") forbids the edit R24 requires: change the SIN chart count from five to eight in docs/checklist-manual-dashboard.md line 33 (step 3's expected result, "five initially visible SIN charts") and line 56 (step 7's expected result, "the five SIN charts disappear"). No ticket owns this edit. If it is left out, both steps become false after ticket-004, and a release walker records a fail on a correct build. No test pins "five", so the edit is safe. Required change: narrow the rule to "steps 1-32 keep their numbers and every test-pinned string (step 12's build command, '04/03/2024 12:00', 'MW (diferença)', the seven group labels, the section 8 and 9 strings); the only rewording allowed is the SIN count in steps 3 and 7, five -> eight, measured from the SIN group count (C-CAT)". Assign that edit to ticket-007, the checklist ticket. Also have ticket-007 add one sentence to the Purpose paragraph for the new 33+ range. That paragraph sits outside the numbered steps and lists each existing step range, so the new range belongs there.

## Operator resolution (2026-11-09)

| Objection | Resolution | Applied by |
| --- | --- | --- |
| `open-source-documentation-writer` on `ADR-007` — the absolute clause "steps 1-32 are never renumbered or reworded" (and C-CHK "steps 1-32 stay verbatim") forbids the R24 edit "SIN count five -> eight" in steps 3 and 7 of `docs/checklist-manual-dashboard.md` (lines 33 and 56; no test pins the word "five"). | **Accepted — narrow ADR-007.** The one-way door is "steps 1-32 keep their numbers and every test-pinned string (step 12's build command, '04/03/2024 12:00', 'MW (diferença)', the seven group labels, the section 8 and 9 strings)". The only rewording allowed is the SIN count in steps 3 and 7 (five -> eight, measured from the SIN group count, C-CAT) plus one sentence in the Purpose paragraph naming the new 33+ range. Ticket-007 keeps that edit and its "Out of scope" line is corrected to match. | P4 REVISION (planner), round 1 |

Non-blocking notes returned with the `APPROVE` verdicts are forwarded to the same REVISION dispatch:

- `dessem-specialist` (a) C-SEM / README wording for ticket-009: QINC is the deck's inflow input (dadvaz); for most plants it is the natural incremental inflow and QAFL adds upstream outflows (lagged by travel time where it exists); where the deck gives a regularized inflow (Sobradinho, dadvaz itp=3, since 2023-02-28) upstream outflows are already included and QAFL equals QINC — never call QINC "natural" for every plant. (b) ADR-003 rejected-option text: plain sums double-count cascade water for QAFL/QDEF/QTUR/QVER, not for QINC. (c) ADR-006 rework trigger: the inequality form QAFL >= QINC is an equality at regularized-inflow plants and may fail at a reservoir a pumping station draws from (MM eq. 9.7).
- `python-task-automation-developer`: C-CAT's "only charts/specs.py changes for the feature" must not hide R25's comment-and-grouping edit to `data/schemas.py` (`FALLBACK_UNITS`) — ticket-004 or ticket-005 must own it explicitly; ticket-002 must state the `_load_registries(scenarios, *, fictitious_codes)` signature change fed from `build_dashboard_data`.
- `test-strategist` for ticket-006: (a) the zero-warnings assertion message lists the warnings found; (b) the expected subtitle follows `payload.py:159` (subtitle only when the file's long name differs from `spec.title`) or the test first asserts they differ; (c) "first `chaining.stages_per_deck` chained stages" is a valid subset on multi-deck trees.
