# Score Report

**Mode**: Design
**Ticket**: /home/carlosribeiro/git/plotador-dessem/plans/graficos-hidreletricos
**Composite Score**: 1.00
**Gate**: PASS (threshold: 0.80)

Independent re-score from the on-disk artifacts only; no planner self-score was read (the plan carries none). No flag set: all five dimensions applicable, divisor 1.00.

## Dimensional Breakdown

| Dimension | Weight | Score | Weighted | Evidence Summary |
| --------- | ------ | ----- | -------- | ---------------- |
| Traceability | 0.25 | 1.00 | 0.250 | frac_decisions 9/9, frac_tickets 8/8 |
| Options Considered | 0.15 | 1.00 | 0.150 | 9/9 accepted non-cross_cutting ADRs carry >=2 options + reversibility + rework_trigger |
| Council Coverage | 0.15 | 1.00 | 0.150 | 4/4 briefs, 4/4 sign-off verdicts |
| Durability | 0.25 | 1.00 | 0.250 | 0 unresolved UNDER (DES-01, DES-02, DES-04 resolved) |
| Proportionality | 0.20 | 1.00 | 0.200 | 0 unresolved OVER (DES-03 resolved) |

Composite = (0.25 + 0.15 + 0.15 + 0.25 + 0.20) / 1.00 = 1.00.

## Detailed Evidence

### Traceability (1.00)

- **Scoring Rule**: mean(frac_decisions, frac_tickets) per `rubrics/design.md`.
- **Evidence**: `00-master-plan.md` declares R1-R7, R9, R13, R14, R18, R20-R29. Accepted ADRs: 001-006, 008, 009, 010 (ADR-007 is `superseded` by ADR-010 and excluded). Each cites >=1 declared requirement id (e.g. ADR-001 [R1,R7,R9,R13,R21], ADR-010 [R20,R24]). Tickets carrying `implements:` are 001-008; every id they list (R29, R22, R27, R23, R3, R4, R13, R14, R7, R1, R9, R6, R18, R21, R25, R26, R24, R20, ADR-001..006, ADR-009, ADR-010) resolves to a declared requirement or an accepted decision. Tickets 009-010 are outlines with no `implements:` key, so they are outside the count by the rubric's definition.
- **Score Justification**: frac_decisions = 9/9 = 1.0; frac_tickets = 8/8 = 1.0; mean 1.0.
- **Observation (not scored)**: ADR-008 is realised by outline tickets 009/010, which carry no `implements:` yet; it will trace once they are refined.

### Options Considered (1.00)

- **Scoring Rule**: accepted non-cross_cutting decisions with >=2 options AND reversibility AND rework_trigger, over all such decisions.
- **Evidence**: no ADR is cross_cutting. All nine accepted ADRs list 2-4 options, a `reversibility` tag (two-way, except ADR-002 and ADR-010 one-way) and a `rework_trigger` (several "none known", which is a present field). The reversibility tags fit the Cleanliness Bar: the one-way doors are chart key identity (ADR-002) and the checklist step numbers/pinned strings (ADR-010), both with the durable option chosen.
- **Score Justification**: 9/9 = 1.0.

### Council Coverage (1.00)

- **Scoring Rule**: mean(frac_briefs, frac_signoffs).
- **Evidence**: `design/intake.md` roster has 4 seats (dessem-specialist, python-task-automation-developer, test-strategist, open-source-documentation-writer). `design/council/` holds all four `*.brief.md` (`answers.md` is not a brief). `design/signoff.md` records a verdict for all four domains (3 APPROVE, 1 OBJECT on ADR-007, resolved by operator and ADR-010).
- **Score Justification**: 4/4 and 4/4, mean 1.0. An OBJECT verdict is a recorded verdict; the rubric measures coverage, not unanimity.

### Durability (1.00)

- **Scoring Rule**: unresolved UNDER findings count n; 1.0 if n == 0.
- **Evidence**: `design/critique/round-1.md` has three UNDER findings: DES-01 (MEDIUM), DES-02 (MEDIUM), DES-04 (LOW), all ACKNOWLEDGED. The revision log names the addressing artifact for each, and I verified each landed on disk:
  - DES-01: ticket-005 now measures `dict.fromkeys(s.source_file for s in enabled_specs())`, imports from `charts.registry`, asserts `set(e) <= set(F)`; tickets 003/004/006 filter by `s.group`, not `s.level.value`. Matches `registry.py` (`enabled_specs` at line 128).
  - DES-02: ADR-003 and ADR-006 carry dated `amended:` fields; the master plan has the "Domain contracts (C-SEM amended)" section; epic-03 overview and ticket-009 outline require the amended C-SEM and a dessem-specialist review.
  - DES-04: ADR-005 option-a durability text now states what Option B would revert.
- **Score Justification**: all three resolved (ACKNOWLEDGED plus named ADR/ticket), n = 0.
- **Code cross-checks**: `QDEF_SIN/QTUR_SIN/QVER_SIN` are in `specs.py` and 19 specs carry `enabled=False`; `load_registries` still has the `(11, 99)` default and `consolidate.py:430` computes but does not pass the configured codes at the registry load, confirming ticket-002 targets a real defect; `tests/test_parity.py:608-609` has the `* 2` premise ticket-001 fixes.

### Proportionality (1.00)

- **Scoring Rule**: unresolved OVER findings count n; 1.0 if n == 0.
- **Evidence**: one OVER finding, DES-03 (LOW), ACKNOWLEDGED. Revision log: resolution (a); ticket-008 now pins literals and no longer reads the catalogue (ticket-008 Background and AC1 state `tests/test_renderer_contract.py` must contain no `enabled_specs`/`charts.registry`; ADR-008 already rejects docs-drift tests; ADR-010 names the literal-pin guard).
- **Score Justification**: resolved, n = 0. The plan's other rejected options (derive-sin-sums, centralised pin constant, drift-proof README, synthesis-property module) are explicitly rejected as speculation, consistent with the OVER bar.

## Note on the dispatch's clarification instruction

The REPORT CONTRACT asked for a clarification object with status `clarification_required`. No clarification is needed to score this plan, so the envelope uses `status: complete` and `clarification: null`, as the rubric's consumer rule requires (the object only when status is `clarification_required`).
