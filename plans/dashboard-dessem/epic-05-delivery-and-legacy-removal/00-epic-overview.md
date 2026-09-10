# Epic 05: Delivery, Validation and Legacy Removal

> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Detail level: **outline** — every ticket in this epic carries the `[OUTLINE]` marker and must be
> refined with the learnings of Epics 1 to 4 before dispatch.

## Goal

Close the feature: wire the real pipeline behind the CLI built in Epic 1, run it end to end on real
data, prove parity with the legacy charts, write the user documentation, and only then delete the
legacy scripts.

## Scope

In scope: replacing the `pipeline.run` stub with the real orchestration, the skip-guarded
integration test against a real scenario tree, the legacy parity check, the CLI usability and error
message pass, the final documentation, and the removal of `Leitura/`, `Plotadores/` and `main_*.py`.

Out of scope: any new chart, any new filter, any change to the payload shape, and any change to the
`settings.json` contract, all of which belong to earlier epics or to a future feature.

## Tickets

| Ticket | Title | Points | Detail |
| ------ | ----- | ------ | ------ |
| ticket-033 | Wire the end-to-end pipeline | 3 | outline |
| ticket-034 | Add the example-data integration test | 3 | outline |
| ticket-035 | Run the legacy parity check | 3 | outline |
| ticket-036 | Write the user documentation | 2 | outline |
| ticket-037 | Polish the CLI usability and error messages | 2 | outline |
| ticket-038 | Remove the legacy scripts | 1 | outline |

## Dependency Order

```text
ticket-033 -> ticket-034 -> ticket-035 -> ticket-036 -> ticket-037 -> ticket-038
```

## Refinement Inputs Required

- `epic-04-learnings.md`: the final builder signature, the size measurements observed, and the
  decisions taken on the plant-level payload.
- The local scenario tree `exemplo/caso_oficial/` and `exemplo/caso_gurobi/` (2 decks each; master
  plan open question 5, resolved 2026-09-10). On a machine without it, only the skip paths of
  ticket-034 and ticket-035 can be verified.

## Open Questions for the Epic

- Master plan open questions 4 and 5 are resolved. ticket-038 must still verify a clean
  `git status --short` before deleting the legacy scripts, so that removal is a commit of its own.
- Whether the parity check is a numerical comparison against regenerated legacy HTML files or a
  documented visual comparison. The legacy scripts write one HTML per chart with a hard-coded
  Windows path, so running them at all requires editing them, which conflicts with the plan not
  modifying legacy code.
