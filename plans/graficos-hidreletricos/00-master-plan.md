---
requirements:
  - id: R1
    text: "The SIN section shows three hydro flow charts read from the synthesized files: Defluência (QDEF_SIN), Turbinamento (QTUR_SIN) and Vertimento (QVER_SIN); Vazão Afluente and Vazão Incremental are not shown at SIN because the synthesis ships no SIN file for them."
    kind: functional
    source: clarification
  - id: R2
    text: "Confirmed scope decision: the Submercado section gets no hydro flow chart. The raw spec asked for the five flows there, but none exists as an SBM synthesis file, and the operator applied the no-file-no-chart rule (R26); the Submercado section is unchanged."
    kind: constraint
    source: clarification
  - id: R3
    text: "The Usinas hidrelétricas section shows the five flow charts per plant (QAFL_UHE, QINC_UHE, QDEF_UHE, QTUR_UHE, QVER_UHE, already declared and enabled) and keeps them."
    kind: functional
    source: spec
  - id: R4
    text: "Within each section, charts follow a deliberate, domain-meaningful order; the concrete order is R13."
    kind: functional
    source: spec
  - id: R5
    text: "All chart data comes from each deck's sintese/ Parquet files (settings discovery.sintese_dirname); no other DESSEM output is read."
    kind: constraint
    source: spec
  - id: R6
    text: "Every chart of R1 and R3 supports Por deck (with the Deck selector), Encadeado, Absoluto and Diferença with the existing line-chart semantics; 'análise por caso' means Por deck mode plus one trace per scenario in Absoluto, and no new filter is added."
    kind: functional
    source: clarification
  - id: R7
    text: "The change is consistent with the repository as a whole (catalogue -> consolidation -> DashboardData -> payload -> renderer), not a local patch that is correct for one layer and wrong for another."
    kind: constraint
    source: spec
  - id: R9
    text: "SIN Defluência / Turbinamento / Vertimento are delivered by enabling the existing declared specs QDEF_SIN / QTUR_SIN / QVER_SIN; no derivation or aggregation code is added."
    kind: functional
    source: clarification
  - id: R13
    text: "Order (water balance): SIN = GTER_SIN, GHID_SIN, GUNS_SIN, EARMF_SIN, VARMF_SIN, QDEF_SIN, QTUR_SIN, QVER_SIN; UHE = GHID_UHE, VARMF_UHE, VARPF_UHE, QAFL_UHE, QINC_UHE, QDEF_UHE, QTUR_UHE, QVER_UHE; Submercado order unchanged (MER, GHID, GTER, GUNS, CMO, VARMF)."
    kind: functional
    source: clarification
  - id: R14
    text: "The existing UHE flow charts keep their key, title, unit and enabled state; only their position in SPECS changes."
    kind: constraint
    source: clarification
  - id: R18
    text: "No new settings.json key; the only operator-facing configuration effect is that charts.disabled can now hide the three newly enabled SIN keys."
    kind: constraint
    source: clarification
  - id: R20
    text: "Real-data validation on examples/Oficial + examples/Modificado: an automated test that skips when the data is absent (run with DESSEM_DASHBOARD_EXEMPLO=<repo>/examples), plus a manual CLI run and new manual-checklist entries covering the SIN flow charts and the UHE order in all four mode combinations."
    kind: nonfunctional
    source: clarification
  - id: R21
    text: "No new performance budget: the run stays well below output.size_warning_mb (baseline 6.6 MB HTML, 1.7 s on the example pair); growth is limited to three one-entity SIN charts."
    kind: nonfunctional
    source: clarification
  - id: R22
    text: "The CLAUDE.md quality gate passes (ruff check, ruff format --check, mypy src, pytest --cov) with coverage >= 85%; each moved count-pin literal is updated in place with the value measured through enabled_specs()/all_specs() (no centralisation)."
    kind: constraint
    source: clarification
  - id: R23
    text: "CLAUDE.md invariants hold: readers.py stays the only pandas.read_parquet caller; missing data degrades through DashboardData.add_warning; the output stays one offline HTML file; colors live only in theme.py; the CLI exit/stdout contract is unchanged; UI, log and error text is Portuguese, identifiers, comments, docs and tests are English."
    kind: constraint
    source: clarification
  - id: R24
    text: "Feature-touched documentation matches the code: README catalogue counts, chart catalogue text, a still-disabled chart replacing QDEF_SIN as the 'Enabling an already-declared chart' example, the test-pin table, the Structure comment on specs.py, the per-chart warning counts in Logging and auditing (23 -> 26, 92 -> 104); docs/checklist-manual-dashboard.md SIN count (five -> eight)."
    kind: constraint
    source: clarification
  - id: R25
    text: "No dead code or stale text is left: module docstrings and comments carrying counts or groupings (charts/specs.py '47 ... 28 ... 19', data/schemas.py FALLBACK_UNITS '23 keys ... 19 disabled' and its enabled/disabled grouping comments, test_schemas.py's '19 disabled' comment) are updated."
    kind: constraint
    source: clarification
  - id: R26
    text: "Governing rule: a chart exists at a level only when the synthesis ships a file for that variable at that level; this plan adds no derived or aggregated series at any level."
    kind: constraint
    source: clarification
  - id: R27
    text: "Own ticket: settings.submarkets.fictitious_codes reaches registries.load_registries from consolidation, so submarket visibility honours the configured codes instead of the hard-coded (11, 99) default."
    kind: functional
    source: clarification
  - id: R28
    text: "Own doc ticket: README content that is stale independently of this feature is corrected: the removed Avisos section (layout figure, 'Avisos: the eight warning shapes', manifest and log paragraphs), Execução vs Custo/Tempo (level list, layout figure), 'The two Execução charts' -> seven dedicated bar charts, and the measured quality-gate table."
    kind: constraint
    source: clarification
  - id: R29
    text: "Own ticket, test-only: the real-data Group B parity test (tests/test_parity.py::test_group_b_series_and_scalar_parity_matches_legacy_expressions) derives its expected CUSTOS/TEMPO scalar visit count from the measured decks in context.dirs_by_scenario instead of assuming two decks per scenario, so it PASSES on any qualifying tree (including examples/ with one deck per scenario) and still on the documented two-deck exemplo/ pair by construction; no product code changes."
    kind: constraint
    source: clarification
decisions:
  - id: ADR-001
    title: "Deliver the SIN flow charts by enabling the declared QDEF_SIN/QTUR_SIN/QVER_SIN specs, moved into the enabled SIN block right after VARMF_SIN"
    status: accepted
    requirements: [R1, R7, R9, R13, R21]
    options:
      - name: "enable-and-move"
        complexity: low
        durability: "Same render order as enable-in-place, and keeps the specs.py docstring layout 'enabled first, then disabled' true; no rework known."
      - name: "enable-in-place"
        complexity: low
        durability: "Renders identically but leaves three enabled specs inside the trailing disabled block, an asymmetry a later reader must untangle."
      - name: "derive-sin-sums-from-uhe"
        complexity: medium
        durability: "Adds aggregation code that duplicates synthesized files and contradicts R9/R26; would be removed as soon as noticed."
    chosen: "enable-and-move"
    reversibility: two-way
    rework_trigger: "none known"
    council: { recommended_by: [python-task-automation-developer, test-strategist] }
  - id: ADR-002
    title: "Keep every existing chart key, title and unit unchanged; reorder the UHE block in SPECS only (no DOM, CSS or JS change)"
    status: accepted
    requirements: [R4, R13, R14, R18]
    options:
      - name: "reorder-specs-tuple-keep-identity"
        complexity: low
        durability: "Keys stay valid for operators' charts.disabled; order change is a tuple-literal edit."
      - name: "rename-keys-or-add-sub-headings"
        complexity: medium
        durability: "Renaming breaks any settings.json naming the old keys (RegistryError); sub-headings need builder/CSS/JS work the operator declined (Q10)."
    chosen: "reorder-specs-tuple-keep-identity"
    reversibility: one-way
    rework_trigger: "none known"
    council: { recommended_by: [python-task-automation-developer] }
  - id: ADR-003
    title: "No synthesized file, no chart: no derived or aggregated flow series at SIN or Submercado level"
    status: accepted
    requirements: [R1, R2, R5, R26]
    options:
      - name: "synthesized-files-only"
        complexity: low
        durability: "Every shipped flow file gets a chart (dessem contract C4); nothing to maintain beyond the catalogue."
      - name: "derive-missing-levels"
        complexity: high
        durability: "Plain sums over plants are aggregate indicators: for QAFL, QDEF, QTUR and QVER they count cascade water at every plant it passes (double counting), while QINC sums add without double counting. Either way it means a new store path, null semantics and fixture rules to maintain, against R26."
    chosen: "synthesized-files-only"
    reversibility: two-way
    rework_trigger: "The synthesizer starts shipping Q*_SBM, QAFL_SIN or QINC_SIN files (declare/enable specs for them), or the operator asks for cascade-aware aggregates (a new plan)."
    council: { recommended_by: [dessem-specialist] }
    amended: "2026-11-09, design critique round 1 (DES-02), from dessem-specialist sign-off note (b): the derive-missing-levels durability text no longer claims double counting for QINC. The chosen option, requirements, reversibility and trigger are unchanged."
  - id: ADR-004
    title: "Update every moved count pin in place with the value measured through enabled_specs()/all_specs(), in the same commit as the catalogue change it follows"
    status: accepted
    requirements: [R22, R25]
    options:
      - name: "in-place-measured-literals"
        complexity: low
        durability: "Every future chart change edits the pins again by hand (the cost the operator accepted in Q11)."
      - name: "centralised-measured-constant"
        complexity: medium
        durability: "Removes drift but was rejected by the operator (Q11)."
    chosen: "in-place-measured-literals"
    reversibility: two-way
    rework_trigger: "The operator asks for pin centralisation (its own plan)."
    council: { recommended_by: [test-strategist, python-task-automation-developer] }
  - id: ADR-005
    title: "R27 fix: required fictitious_codes keyword on registries.load_registries (default (11, 99) removed); consolidate._load_registries passes settings.submarkets.fictitious_codes on both call sites; behavioural regression test"
    status: accepted
    requirements: [R27, R23]
    options:
      - name: "option-a-required-keyword"
        complexity: low
        durability: "Matches R27 wording. A later move to Option B partly reverts this plumbing: it removes the fictitious_codes keyword from load_registries and _load_registries, strips it from the 27 tests/test_registries.py call sites and tests/test_parity.py:594, drops the _FICTITIOUS_CODES constant, and deletes or rewrites the loader-level unit test that asserts Submarket.fictitious. The consolidation-seam regression test and the _build_settings fictitious_codes knob carry over unchanged."
      - name: "option-b-policy-in-visible_submarket_codes"
        complexity: medium
        durability: "Single policy point, but removes Submarket.fictitious and exceeds R27's confirmed scope (rejected, answer A3)."
      - name: "keep-default-and-pass-explicitly"
        complexity: low
        durability: "Leaves a hard-coded tunable in a signature, against CLAUDE.md."
    chosen: "option-a-required-keyword"
    reversibility: two-way
    rework_trigger: "A second consumer of the fictitious-submarket policy or a request to separate classification from loading (Option B as its own ticket)."
    council: { recommended_by: [python-task-automation-developer, test-strategist] }
    amended: "2026-11-09, design critique round 1 (DES-04): the option-a durability text now states what Option B would revert. The earlier 'superset with no rework' claim was false. The chosen option, reversibility and trigger are unchanged."
  - id: ADR-006
    title: "Real-data validation asserts the dashboard contract only, as one new test in tests/test_integration_exemplo.py that derives expected values from the files with pandas"
    status: accepted
    requirements: [R20, R6, R22, R23]
    options:
      - name: "extend-integration-module-contract-only"
        complexity: low
        durability: "Reuses the module's skip guard, settings and payload helpers; its docstring's no-read rule is narrowed explicitly. No synthesizer coupling."
      - name: "new-real-data-module"
        complexity: low
        durability: "Duplicates _build_settings/_extract_payload/skip helpers, a third real-data module to keep aligned."
      - name: "contract-plus-synthesis-property-module"
        complexity: medium
        durability: "Couples the dashboard suite to the synthesizer; rejected by the operator (A1/A2)."
    chosen: "extend-integration-module-contract-only"
    reversibility: two-way
    rework_trigger: "A synthesizer regression or a deck with active diversion motivates the synthesis-property module. That module may assert only the inequality forms in the master plan's amended C-SEM: (a) X_SIN = sum of X_UHE per stage within tolerance, for X in QDEF, QTUR, QVER; (b) QDEF_UHE >= QTUR_UHE + QVER_UHE - tol; (d) QTUR, QVER, QDEF >= -tol; and (c) QAFL_UHE >= QINC_UHE - tol only with both caveats. Form (c) is an equality at regularized-inflow plants (Sobradinho, dadvaz itp=3), and it may fail at a reservoir a pumping station draws from (MM eq. 9.7 subtracts Qb at the origin), so those plants must be excluded or verified first."
    council: { recommended_by: [dessem-specialist, python-task-automation-developer, test-strategist] }
    amended: "2026-11-09, design critique round 1 (DES-02), from dessem-specialist sign-off note (c): the rework_trigger now cites form (c) with both caveats instead of pointing at the uncorrected brief. The chosen option and reversibility are unchanged."
  - id: ADR-007
    title: "Extend the manual checklist by appending section 10 (steps 33+) with its own examples-pair build command, guarded by a static test like sections 8 and 9; steps 1-32 are never renumbered or reworded"
    status: superseded
    superseded_by: ADR-010
    requirements: [R20, R24]
    options:
      - name: "append-section-10-with-guard-test"
        complexity: low
        durability: "Existing step ids, the strings tests pin and past release records stay valid; the new section cannot be silently deleted."
      - name: "renumber-or-insert-sub-steps"
        complexity: low
        durability: "Breaks step ids that tests (test_checklist_step_15_*), exemplo_tree.py ('step 12') and release records cite."
      - name: "append-without-guard-test"
        complexity: low
        durability: "Leaves the asymmetry the epic-04 Live Defects table flagged for section 9: a simplifier can delete the section unnoticed."
    chosen: "append-section-10-with-guard-test"
    reversibility: one-way
    rework_trigger: "none known"
    council: { recommended_by: [open-source-documentation-writer, test-strategist] }
  - id: ADR-008
    title: "README is edited by two serialized tickets: R24 (feature facts, measured, recipe rewritten) after epics 01-02, then R28 (independently stale content and the measured quality-gate table) last"
    status: accepted
    requirements: [R24, R28]
    options:
      - name: "two-serialized-tickets-measured-literals"
        complexity: low
        durability: "Volatile literals must be re-measured at the next chart change; R28 last keeps its quality-gate snapshot final for this plan."
      - name: "single-readme-ticket"
        complexity: low
        durability: "One oversized ticket mixing feature and unrelated corrections; harder to review."
      - name: "drift-proof-readme-with-docs-test"
        complexity: high
        durability: "Formula-only text plus a docs-drift test; not asked for by R24/R28 (over-engineering)."
    chosen: "two-serialized-tickets-measured-literals"
    reversibility: two-way
    rework_trigger: "A requirement for drift-proof documentation (docs-drift test) arrives."
    council: { recommended_by: [open-source-documentation-writer] }
  - id: ADR-009
    title: "Group B parity counts the measured (scenario, deck) pairs from context.dirs_by_scenario; the two pre-existing defects (R29, R27) run as epic 01, before the feature, so no ticket accepts a known failure"
    status: accepted
    requirements: [R29, R27, R22]
    options:
      - name: "measured-deck-count-defects-epic-first"
        complexity: low
        durability: "Group B is valid on any qualifying tree and unchanged on the documented pair (4 = 2 x 2 by construction); later tickets can require a full test_parity.py pass on examples/."
      - name: "measured-deck-count-first-ticket-of-feature-epic-r27-after-feature"
        complexity: low
        durability: "Same test fix, but mixes a pre-existing test defect into the feature epic and keeps R27 split away from the other planning-time defect."
      - name: "skip-group-b-on-single-deck-trees"
        complexity: low
        durability: "Removes the failure by removing real-data parity coverage on examples/, the only tree available on this machine."
      - name: "leave-as-is-and-accept-in-acceptance-criteria"
        complexity: low
        durability: "Every ticket touching test_parity.py must carry an accepted-failure clause; a new Group B regression would hide behind the known one."
    chosen: "measured-deck-count-defects-epic-first"
    reversibility: two-way
    rework_trigger: "none known"
    decided_by: "operator chose the fix (own ticket, measured deck count, 2026-11-09); the planner chose the placement"
  - id: ADR-010
    title: "Extend the manual checklist by appending section 10 (steps 33+) with its own examples-pair build command, guarded by a literal-pin static test like sections 8 and 9. Steps 1-32 keep their numbers and every test-pinned string; the only rewording allowed is the SIN count in steps 3 and 7 (five -> eight, measured from the SIN group count) plus one Purpose sentence naming the 33+ range"
    status: accepted
    supersedes: ADR-007
    requirements: [R20, R24]
    options:
      - name: "append-section-10-freeze-numbers-and-pinned-strings"
        complexity: low
        durability: "Step ids and every test-pinned string stay valid: step 12's build command, '04/03/2024 12:00', 'MW (diferença)', the seven group labels, and the section 8 and 9 strings. R24's SIN count fix lands in steps 3 and 7, which would otherwise be false after ticket-004. The new section cannot be silently deleted."
      - name: "append-section-10-freeze-full-text-of-steps-1-32"
        complexity: low
        durability: "The superseded ADR-007 rule. It forbids R24's five -> eight edit in steps 3 and 7, so both steps fail a release walk on a correct build (documentation seat objection, accepted by the operator 2026-11-09)."
      - name: "renumber-or-insert-sub-steps"
        complexity: low
        durability: "Breaks step ids that tests (test_checklist_step_15_*), exemplo_tree.py ('step 12') and release records cite."
      - name: "append-without-guard-test"
        complexity: low
        durability: "Leaves the asymmetry the epic-04 Live Defects table flagged for section 9: a simplifier can delete the section unnoticed."
    chosen: "append-section-10-freeze-numbers-and-pinned-strings"
    reversibility: one-way
    rework_trigger: "none known"
    council: { recommended_by: [open-source-documentation-writer, test-strategist] }
    decided_by: "operator, 2026-11-09 (sign-off objection by open-source-documentation-writer accepted; applied in design critique round 1 REVISION)"
---

# Master Plan: Hydro flow charts in the SIN and Usinas hidrelétricas sections

## Executive Summary

Enable the three synthesized SIN hydro flow charts (`QDEF_SIN` Defluência, `QTUR_SIN` Turbinamento,
`QVER_SIN` Vertimento) and reorder the Usinas hidrelétricas section into water-balance order, with
no derived series anywhere (no file, no chart). First, fix two defects found during planning: the
real-data parity test's two-decks-per-scenario premise (R29) and the `fictitious_codes` plumbing
defect (R27). Alongside the feature, remove stale count/section text, add a real-data contract test and checklist steps, and bring
the README back in line with the code.

**Branch (all tickets):** `feat/graficos-de-vazao-no-sin`. The operator merges into `main` with
`--no-ff` after the plan completes. Commit messages are Portuguese conventional commits.

## Goals & Non-Goals

### Goals

- SIN shows 8 charts: `GTER, GHID, GUNS, EARMF, VARMF, QDEF, QTUR, QVER` (R1, R13).
- UHE shows its 8 charts as `GHID, VARMF, VARPF, QAFL, QINC, QDEF, QTUR, QVER` (R3, R13, R14).
- All of them work in Por deck / Encadeado x Absoluto / Diferença through the existing,
  key-agnostic pipeline (R6, R7).
- `settings.submarkets.fictitious_codes` actually controls submarket visibility (R27).
- `tests/test_parity.py` Group B passes on any qualifying real tree, including `examples/` (R29).
- Quality gate green, coverage >= 85 %, every moved pin measured (R22); docs match code (R24, R28).

### Non-Goals (confirmed)

- Any chart in Submercado for the flows (R2), SIN Vazão Afluente / Incremental (R1), any derived or
  aggregated series (R26).
- REE level, limit bands, flows in other sections, new UI controls or sub-headings, new
  `settings.json` keys (R18), performance work (R21), pin centralisation (Q11).
- Synthesis-property tests (answer A1): never assert `QDEF == QTUR + QVER` nor `QINC Diferença == 0`
  (answer A2, dessem contract C3).
- Fixing the fixture `METADADOS_OPERACAO` fidelity gap (answer A4, recorded as debt below).

## Architecture Overview

### Current State

- `charts/specs.py::SPECS` declares 47 specs, 28 enabled, 19 disabled. `QDEF_SIN`, `QTUR_SIN`,
  `QVER_SIN` sit at the very end, `enabled=False`.
- Order of sections is the order of `SPECS` (`builder._level_nav` / `_chart_sections`).
- Every SERIES chart flows `consolidate._load_series -> DashboardData.add_series -> payload ->
  dashboard.js` with no chart-key-specific code, so enabling a spec needs no pipeline change.
- `consolidate._load_registries` calls `load_registries(...)` without `fictitious_codes`, so
  `Submarket.fictitious` always comes from the hard-coded `(11, 99)` default.
- `tests/test_parity.py::test_group_b_series_and_scalar_parity_matches_legacy_expressions` expects
  `len(context.scenarios) * 2` scalar visits (lines 608-609). On `examples/` (one deck per scenario)
  it fails today with `assert 2 == (2 * 2)` (measured on `main`, 2026-11-09).
- README carries counts from an older catalogue (42/23/19), a removed `Avisos` section and an
  `Execução` tab that no longer exist.

### Target State

- `SPECS`: 47 declared, 31 enabled, 16 disabled; SIN 8, UHE 8 (reordered), SBM 6 unchanged; 24
  SERIES charts; measured on the change with `enabled_specs()`/`all_specs()`.
- `load_registries(sintese_dir, *, fictitious_codes)` with a required keyword; consolidation passes
  `settings.submarkets.fictitious_codes`.
- Group B counts the measured (scenario, deck) pairs; `tests/test_parity.py` on `examples/`: 11
  passed, 4 skipped (the documented-pair pins), measured in a scratch simulation of the fix.
- Example pair build: 31 charts, 0 warnings, HTML ~6.63 MB (measured in a scratch simulation:
  6,632,093 bytes vs 6,623,439 baseline), far below `output.size_warning_mb` (R21).

### Key Design Decisions

The frontmatter is the source of truth; this is the narrative.

- **ADR-001** Enable the three SIN specs and move them after `VARMF_SIN`: identical render order to
  flipping in place, but the module stays "enabled first, then disabled".
- **ADR-002** Identity is frozen: the keys become default-enabled and operators may name them in
  `charts.disabled`, so no key is renamed (the only one-way door, flagged by the python seat). The
  UHE reorder is a tuple edit; no UI work.
- **ADR-003** No file, no chart. SIN flows are the synthesized files: per-stage sums over all
  plants. They are an aggregate indicator that counts cascade water at every plant it passes
  (QDEF, QTUR, QVER). Plain sums of QINC would not double count, which is why the amended C-SEM
  below no longer says double counting applies to every flow. Amended 2026-11-09 (DES-02).
- **ADR-004** Pins updated in place, in the same commit as the change that moves them, so every
  commit's gate is green.
- **ADR-005** R27 Option A (answer A3). Moving to Option B later would partly revert the keyword
  plumbing. Only the consolidation-seam regression test and the settings knob would survive
  (amended 2026-11-09, DES-04).
- **ADR-006** One real-data test, dashboard contract only (answers A1/A2), in the existing
  integration module; expected values come from the files via pandas (the `test_parity.py` Group B
  pattern), and the module docstring's "never opens anything under the tree" rule is narrowed.
  Its rework path, a synthesis-property module, carries the amended C-SEM caveats on QAFL >= QINC
  (amended 2026-11-09, DES-02).
- **ADR-010** (supersedes ADR-007, 2026-11-09). The checklist is appended as section 10, steps 33
  and up, with a literal-pin guard test like those for sections 8 and 9. The one-way door is
  narrowed to the step numbers plus every test-pinned string in steps 1-32. The only rewording
  allowed in sections 1-9 is R24's SIN count in steps 3 and 7 (five -> eight) and one Purpose
  sentence naming the 33+ range. The operator accepted the documentation seat's sign-off
  objection.
- **ADR-008** Two serialized README tickets; R28 is the plan's last ticket.
- **ADR-009** Group B measures its deck count (operator's choice of fix). The planner placed both
  planning-time defects (R29, R27) in epic 01, before the feature, so no acceptance criterion in
  the plan carries an accepted-failure clause.

## Technical Approach

### Tech Stack

Python 3.12, pandas, Plotly (inlined), pytest/ruff/mypy, `uv`-managed `.venv` (editable install).
No Node.js: `dashboard.js` is checked statically only.

### Specialist chain

```
dessem-specialist (semantics: C-SEM as amended at sign-off, assertions C2/C3) -- consulted; reviews
  ticket-009's hydro-flow semantics paragraph at refinement
  -> python-task-automation-developer (parity fix, R27, catalogue, pins, cleanup, real-data test, guard test)
  -> open-source-documentation-writer (checklist, README R24, README R28)
test-strategist: cross-cutting (pin manifest, real-data test spec, R27 regression spec) -- embedded
```

### Domain contracts (dessem-specialist; C-SEM amended at sign-off, 2026-11-09)

The council brief's C1 was too strong. This amended C-SEM replaces it wherever the two differ.
Source: `design/signoff.md`, dessem-specialist non-blocking notes (a) to (c).

- **SIN flow charts.** Each one shows the synthesized SIN file (`QDEF_SIN`, `QTUR_SIN`,
  `QVER_SIN`), which is the per-stage sum over all plants of the matching `*_UHE` flow, in m3/s.
  It is an aggregate indicator. For QAFL, QDEF, QTUR and QVER, water flowing down a cascade is
  counted at every plant it passes. Plain sums of QINC do not double count.
- **Defluência** is the synthesized "Vazão Defluente". Do not write "Defluência = Turbinamento +
  Vertimento" as a definition, because DESSEM's defluência includes diversion (MM 22.3.0 §9.6).
- **QINC (Vazão Incremental)** is the deck's inflow input (dadvaz), unchanged by decisions:
  - For most plants QINC is the natural incremental inflow, and QAFL (Vazão Afluente) adds the
    upstream outflows, lagged by travel time where it exists.
  - Where the deck gives a regularized inflow, the upstream outflows are already included and
    QAFL equals QINC. Example: Sobradinho (169), dadvaz `itp=3`, in ONS decks since 2023-02-28.
    In the example pair QAFL_169 = QINC_169 = 940 m3/s at every stage.
  - Never call QINC "natural" for every plant.
- **Synthesis-property relations** are never asserted in this plan (answers A1, A2). If a later
  module asserts them (ADR-006's rework trigger), form (c) `QAFL >= QINC - tol` needs two caveats:
  - it is an equality at regularized-inflow plants;
  - it may fail at a reservoir a pumping station draws from (MM eq. 9.7 subtracts Qb at the
    origin), so those plants must be excluded or verified first.

### Component/Module Breakdown

| Area | Files | Tickets |
| --- | --- | --- |
| Parity test premise | `tests/test_parity.py` | 001 |
| Registries plumbing | `data/registries.py`, `data/consolidate.py` | 002 |
| Catalogue | `charts/specs.py` | 003, 004 |
| Schemas / CLI text | `data/schemas.py`, `cli.py` | 005 |
| Tests | 15+ files under `tests/` | 001-006, 008 |
| Docs | `docs/checklist-manual-dashboard.md`, `README.md` | 007, 009, 010 |

### Data Flow

Unchanged: `sintese/*.parquet -> readers -> consolidate (_load_series) -> DashboardData -> payload
-> dashboard.js`. Only the catalogue (which specs, in what order) and the registry loader's
fictitious set change.

### Testing Strategy

- Existing tests iterate the pinned tuples, so they extend automatically once the pins move (test
  seat). Pins are measured, never copied from this plan.
- R29: Group B shown RED on `main` with `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, then PASSED
  after ticket-001 (simulated in a scratch copy during planning: 11 passed, 4 skipped).
- R27: behavioural regression test in `tests/test_consolidate.py` shown RED on `main` (measured
  during planning: with `fictitious_codes=[99]`, code `11` is hidden and 24 spurious "código(s) de
  submercado" warnings appear; with `[2, 11, 99]`, code `2` stays visible), plus a unit test in
  `tests/test_registries.py`.
- Real-data contract test PASSED (not SKIPPED) under
  `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`; SKIPPED without it.
- Static literal-pin guard test for checklist section 10, like the section 8 and 9 guards (ADR-010).
  It reads nothing from the catalogue (DES-03).
- Gate per ticket: ruff check, ruff format --check, mypy src, then pytest in the background as two
  chunks: `tests/test_[a-l]*.py` then `tests/test_[m-z]*.py --cov-append` (a single `--cov` run has
  been OOM-killed here). Coverage >= 85 %.

## Phases & Milestones

| Epic | Name | Tickets | Detail |
| --- | --- | --- | --- |
| 01 | Pre-existing defects found during planning (R29, R27) | 001-002 | Detailed |
| 02 | Hydro flow charts (feature) | 003-008 | Detailed |
| 03 | README alignment | 009-010 | Outline |

Why this order (K6, ADR-009):

- **Epic 01 first.** Both defects predate the feature and are independent of it. Once they are
  fixed, every later ticket can require `tests/test_parity.py` to pass fully on `examples/`.
  Ticket-001 and ticket-002 both edit `tests/test_parity.py`, and ticket-002 and ticket-004 both
  edit `tests/test_registries.py` and `tests/test_parity.py`, so the strict chain serializes them.
- **R27 before the feature.** R27's RED evidence was measured on `main`; nothing before it touches
  product code, so the measurement still holds.
- **Epic 03 last.** The README tickets consume measured learnings from epics 01-02: the final
  pin-file list, the warning counts, R27's effect on warning shape 7 and the checklist step
  numbers. Collecting those is what progressive outlines are for.

### Execution order

001 -> 002 -> 003 -> 004 -> 005 -> 006 -> 007 -> 008 -> 009 -> 010 (see README dependency graph).
Ticket numbers follow the execution order.

## Risk Analysis

| Risk | Mitigation |
| --- | --- |
| A pin missed in ticket-004 turns a later gate red | Ticket lists every pin measured in a scratch run during planning; AC requires the full chunked suite green. |
| `tests/test_parity.py:594` breaks only with real data after R27 (mypy does not check tests) | Ticket-002 AC requires a full `test_parity.py` pass with `DESSEM_DASHBOARD_EXEMPLO=<repo>/examples`, which ticket-001 makes possible. |
| Group B's deck-count fix weakens the documented-pair check | The expected count is measured from `context.dirs_by_scenario`, which equals the old 2 x 2 = 4 on the documented pair; a `deck_pairs > 0` guard keeps it non-vacuous. |
| Real-data test only runs locally | AC requires a PASSED run shown with `pytest -rs`. |
| The documented `exemplo/caso_oficial`/`caso_gurobi` pair (absent here) might carry warnings, failing the zero-warnings assertion of answer A1 | Unverifiable on this machine; recorded; the assertion is a two-way door (ADR-006). |
| Fixture `METADADOS` never exercises the subtitle path (K2) | Covered on real data by ticket-006; debt record below. |

### Debt record (answer A4 — not scheduled in this plan)

On 2026-11-09 the operator declined a tracked repository register ("Só no plano mestre"). This
record lives only in this master plan; no `DEBT.md` is created and no ticket pays it off. No
`DEBT(...)` breadcrumb is added to source.

```
DEBT (untracked; kept in this master plan only)
what:      tests/fixtures_sintese.py::_metadados_operacao writes nome_longo_variavel = spec.title and
           rows for CUSTO_*/TEMPO_* keys real METADADOS never has
why-now:   inadvertent — found during intake (K2); operator chose not to fix in this plan (A4)
quadrant:  inadvertent x prudent
interest:  fixture documents never show a subtitle, so the subtitle path of every flow chart is
           covered only by the skip-guarded real-data test
payoff:    write realistic long names for flow keys and drop CUSTO_*/TEMPO_* rows; update the
           "no subtitle on unmodified fixture" assertions (about 6 test files)
trigger:   the next change to the subtitle logic in dashboard/payload.py or to fixtures_sintese.py
owner:     repository maintainer (operator)
blast:     tests/fixtures_sintese.py, test_charts_sin/hydro/thermal, test_builder, test_output_size
```

## Success Metrics

- `enabled_specs()` = 31, SIN/UHE orders equal R13, example-pair build: exit 0, 31 charts,
  0 warnings.
- Group B RED on `main` with `examples/` (`assert 2 == (2 * 2)`), PASSED after ticket-001.
- R27 regression test RED on `main`, GREEN after ticket-002.
- `tests/test_parity.py` fully passes on `examples/` after every ticket from 001 on (only the four
  documented-pair pin tests skip).
- Quality gate green with coverage >= 85 % after every ticket; `README.md` quality-gate table
  measured on the final tree.
