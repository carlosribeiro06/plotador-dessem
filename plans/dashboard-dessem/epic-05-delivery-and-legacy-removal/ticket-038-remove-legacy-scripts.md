# ticket-038 Remove the legacy scripts

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-05-delivery-and-legacy-removal` · Recommended agent: `docker-linux-server-architect`

## Objective

Delete the superseded legacy code — `Leitura/`, `Plotadores/` and the five `main_*.py` drivers —
only after the parity check of ticket-035 has passed, so the repository holds one implementation
instead of two.

## Anticipated Scope

- **Files likely to be modified**: `Leitura/leitor_arquivos.py`, `Plotadores/*.py` (seven files),
  `main_cmo.py`, `main_custos.py`, `main_ghid.py`, `main_gter.py`, `main_tempo.py`, `README.md`.
- **Key decisions needed**:
  - whether the files are deleted outright or moved to a `legacy/` directory for one release, given
    that the parity report already captures their behaviour;
  - the message and scope of the removal commit, which this ticket creates and pushes (planning-context
    decision 17);
  - whether `plano_dashboard_dessem.md`, the original spec, stays at the repository root or moves
    under `plans/`.
- **Open questions**:
  - Master plan open question 4 is resolved: the `exemplo` deletions were committed by ticket-001.
    Before deleting anything, verify that `git status --short` is clean so the legacy removal is a
    commit of its own; if it is not clean, stop and ask.
  - Does the README keep a short note recording that the legacy scripts existed and where their
    behaviour is documented, namely the parity report?
  - Are the tracked `Plotadores/__pycache__` entries already removed by ticket-001, or does this
    ticket need to confirm it?

## Dependencies

- **Blocked By**: `ticket-037-polish-cli-usability-and-errors.md`
- **Blocks**: none

## Effort Estimate

**Points**: 1 · **Confidence**: Low (will be re-estimated during refinement)
