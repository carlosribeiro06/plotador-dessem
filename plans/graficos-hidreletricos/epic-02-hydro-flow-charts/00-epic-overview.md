# Epic 02: Hydro flow charts (SIN and Usinas hidrelétricas)

## Goal

SIN shows Defluência, Turbinamento and Vertimento from the synthesized `QDEF_SIN`, `QTUR_SIN` and
`QVER_SIN` files. The UHE section is in water-balance order (R13). Stale counts are removed (R25). A
real-data contract test and a manual checklist section prove the result on `examples/` (R20).

## Requirements covered

R1, R3, R4, R5, R6, R7, R9, R13, R14, R18, R20, R21, R22, R23, R25, R26 (and R2 by not touching the
Submercado block).

## Decisions realized

ADR-001, ADR-002, ADR-003, ADR-004, ADR-006, ADR-010 (supersedes ADR-007, 2026-11-09).

## Structure budget

The epic adds no abstraction, layer, module, settings key or helper outside tests:

- **Source changes:** tuple-literal edits in `charts/specs.py`, one dict reordering plus comment
  fixes in `data/schemas.py`, and a comment, a docstring and one Portuguese message in `cli.py`.
- **Test changes:** two new test functions: the real-data contract test and the checklist
  section-10 guard, which pins literals and does not read the catalogue (ADR-010, DES-03). One private helper may be added inside `tests/test_integration_exemplo.py`.
- **Debt:** no debt ticket is needed. The only debt found (fixture METADADOS, answer A4) stays
  unscheduled and is recorded in the master plan.

## Tickets (dependency order)

| Ticket | Title | Agent | Door |
| --- | --- | --- | --- |
| ticket-003-reorder-uhe-flow-charts.md | Reorder the UHE block into water-balance order | python-task-automation-developer | two-way |
| ticket-004-enable-sin-flow-charts.md | Enable and move the three SIN flow specs, update every count pin | python-task-automation-developer | one-way (key identity) |
| ticket-005-remove-stale-count-text.md | Regroup FALLBACK_UNITS, fix stale counts and the Avisos log text | python-task-automation-developer | two-way |
| ticket-006-real-data-flow-contract-test.md | Real-data contract test for the flow charts | python-task-automation-developer | two-way |
| ticket-007-checklist-flow-section.md | Manual checklist section 10 and SIN count | open-source-documentation-writer | one-way (step ids and test-pinned strings, ADR-010) |
| ticket-008-checklist-section-10-guard-test.md | Static literal-pin guard test for checklist section 10 | python-task-automation-developer | two-way |

## Phase

The epic is detailed. It starts after epic 01, so `tests/test_parity.py` already passes on
`examples/` and the R27 signature change is in place. All tickets run on branch
`feat/graficos-de-vazao-no-sin`.
