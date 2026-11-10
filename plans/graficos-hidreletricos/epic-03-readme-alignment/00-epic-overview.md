# Epic 03: README alignment

## Goal

Bring `README.md` back in line with the code:

- **R24:** the feature facts, measured after epics 01 and 02.
- **R28:** the content that went stale for reasons unrelated to this feature, plus a quality-gate
  table measured on the final tree.

## Requirements covered

R24, R28.

## Decisions realized

ADR-008. The README's chart catalogue also states ADR-003 (no file, no chart) in user-facing terms.

## Specialist chain

open-source-documentation-writer authors both tickets. The dessem-specialist reviews ticket-009's
hydro-flow semantics paragraph against the amended C-SEM.

## Structure budget

The epic edits documentation only and adds no docs-drift test.

## Tickets (outline; refined just-in-time)

| Ticket | Title | Agent |
| --- | --- | --- |
| ticket-009-readme-feature-facts.md | README facts for the flow charts (R24) | open-source-documentation-writer |
| ticket-010-readme-stale-content.md | README stale sections and quality-gate table (R28) | open-source-documentation-writer |

## Phase

The epic is in outline. Learnings to collect from epics 01 and 02 before refining:

- the final list of pin files;
- the measured per-chart warning count (26 x 4 = 104);
- how R27 changes warning shape 7;
- the step numbers in checklist section 10;
- the amended C-SEM (master plan "Domain contracts", from `design/signoff.md` dessem-specialist
  notes (a)-(c), 2026-11-09). It covers QINC as the deck's inflow input, QAFL = QINC at
  regularized-inflow plants such as Sobradinho, and double counting for QAFL/QDEF/QTUR/QVER sums
  but not for QINC. Ticket-009's refinement must cite it, and its semantics paragraph needs a
  dessem-specialist review before the ticket completes.
