# Plan: Hydro flow charts in SIN and Usinas hidrelétricas

- **Branch:** `feat/graficos-de-vazao-no-sin`
- **Master plan:** [00-master-plan.md](00-master-plan.md)
- **Mode:** progressive. Epics 01 and 02 are detailed; epic 03 is an outline.
- **Design Fitness:** 1.00 (independent head score, gate 0.80) — `reports/plan.scorer.1.md`; design critique: 1 round, 4 findings acknowledged and applied (`design/critique/round-1.md`); council sign-off 3 APPROVE / 1 OBJECT resolved by ADR-010 (`design/signoff.md`).

## Progress

<!-- BEGIN plan-progress -->
| Epic | Ticket | Status | Detail | Readiness |
| --- | --- | --- | --- | --- |
| 01 | ticket-001-parity-group-b-measured-deck-count.md | pending | detailed | 1.00 |
| 01 | ticket-002-pass-fictitious-codes-to-registries.md | pending | detailed | 0.975 |
| 02 | ticket-003-reorder-uhe-flow-charts.md | pending | detailed | 1.00 |
| 02 | ticket-004-enable-sin-flow-charts.md | pending | detailed | 0.95 |
| 02 | ticket-005-remove-stale-count-text.md | pending | detailed | 1.00 |
| 02 | ticket-006-real-data-flow-contract-test.md | pending | detailed | 1.00 |
| 02 | ticket-007-checklist-flow-section.md | pending | detailed | 0.97 |
| 02 | ticket-008-checklist-section-10-guard-test.md | pending | detailed | 1.00 |
| 03 | ticket-009-readme-feature-facts.md | pending | outline | - |
| 03 | ticket-010-readme-stale-content.md | pending | outline | - |
<!-- END plan-progress -->

## Epics

| Epic | Name | Tickets |
| --- | --- | --- |
| 01 | Pre-existing defects found during planning (R29, R27) | 001-002 |
| 02 | Hydro flow charts (feature) | 003-008 |
| 03 | README alignment | 009-010 |

## Decision records

| ADR | Title | Requirements | Reversibility | Status |
| --- | --- | --- | --- | --- |
| ADR-001 | Enable and move QDEF_SIN/QTUR_SIN/QVER_SIN after VARMF_SIN | R1, R7, R9, R13, R21 | two-way | accepted |
| ADR-002 | Keep keys, titles and units; reorder UHE in SPECS only | R4, R13, R14, R18 | one-way | accepted |
| ADR-003 | No synthesized file, no chart (no derived series) | R1, R2, R5, R26 | two-way | accepted (amended 2026-11-09, DES-02) |
| ADR-004 | Update count pins in place with measured values | R22, R25 | two-way | accepted |
| ADR-005 | R27 Option A: required fictitious_codes keyword | R27, R23 | two-way | accepted (amended 2026-11-09, DES-04) |
| ADR-006 | Real-data contract-only test in test_integration_exemplo.py | R20, R6, R22, R23 | two-way | accepted (amended 2026-11-09, DES-02) |
| ADR-007 | Append checklist section 10 with a guard test; steps 1-32 never reworded | R20, R24 | one-way | superseded by ADR-010 |
| ADR-008 | Two serialized README tickets (R24, then R28) | R24, R28 | two-way | accepted |
| ADR-009 | Group B measures its deck count; pre-existing defects run first as epic 01 | R29, R27, R22 | two-way | accepted |
| ADR-010 | Append checklist section 10 with a literal-pin guard; freeze step numbers and test-pinned strings, allow only the SIN count fix and one Purpose sentence | R20, R24 | one-way | accepted (supersedes ADR-007) |

## Dependency graph

```
epic 01:  ticket-001 -> ticket-002
epic 02:  -> ticket-003 -> ticket-004 -> ticket-005 -> ticket-006 -> ticket-007 -> ticket-008
epic 03:  -> ticket-009 -> ticket-010
```

## Execution order

Tickets run in the order 001, 002, 003, 004, 005, 006, 007, 008, 009, 010. Ticket numbers follow
the execution order, and the tickets form a strict chain, so none run in parallel. Epic 01 fixes
the two defects found during planning (R29, R27) before the feature work starts. Every later
ticket can then require `tests/test_parity.py` to pass fully on `examples/`.

Every ticket ends with the quality gate:

- ruff check, ruff format --check and mypy src;
- pytest in two background chunks, `tests/test_[a-l]*.py` then `tests/test_[m-z]*.py --cov-append`;
- coverage at least 85%.
