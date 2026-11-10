# Epic 01: Pre-existing defects found during planning

## Goal

Fix the two defects found during planning before any feature work begins:

- **R29:** the real-data Group B parity test assumes two decks per scenario, so it fails on any
  other qualifying tree, including `examples/`.
- **R27:** `settings.submarkets.fictitious_codes` never reaches `registries.load_registries`, so
  the hard-coded default `(11, 99)` always decides which submarkets are fictitious.

With both fixed first, every later ticket can require `tests/test_parity.py` to pass fully on
`examples/`. No ticket in this plan has to accept a known failure (ADR-009).

## Requirements covered

R29, R27, R23, R22.

## Decisions realized

ADR-009 (placement and the measured deck count), ADR-005 (R27 Option A, answer A3).

## Structure budget

- **ticket-001:** one local variable plus a non-vacuity assertion in `tests/test_parity.py`. No
  helper and no product code.
- **ticket-002:** one required keyword parameter on `load_registries`, one keyword parameter on the
  private `_load_registries`, one test-module constant in `tests/test_registries.py`, and one
  keyword knob on the `tests/test_consolidate.py` settings builder.
- **Not allowed:** a new policy function, a change to `visible_submarket_codes`, or removing
  `Submarket.fictitious`. Those belong to Option B, which was rejected.
- **Debt:** none.

## Tickets (dependency order)

| Ticket | Title | Agent | Door |
| --- | --- | --- | --- |
| ticket-001-parity-group-b-measured-deck-count.md | Group B parity measures the deck count | python-task-automation-developer | two-way |
| ticket-002-pass-fictitious-codes-to-registries.md | Pass the configured fictitious codes to load_registries | python-task-automation-developer | two-way |

## Phase

The epic is detailed. Both tickets edit `tests/test_parity.py`, so they run in order. Ticket-002
also precedes epic 02, because ticket-004 later edits `tests/test_registries.py` and
`tests/test_parity.py`. R27's RED evidence is measured on `main`, and nothing before ticket-002
touches product code.
