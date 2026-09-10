# ticket-020 Export the compact JSON payload

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `data-model-format-specialist`

## Objective

Serialise a `DashboardData` into the compact JSON object embedded in the HTML file, applying the
master plan output size strategy: columnar arrays keyed by chart, entity, scenario and deck, one
shared time axis per deck plus one chained axis, values rounded to `output.decimals`, and absolute
series only.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/payload.py`,
  `tests/test_payload.py`.
- **Key decisions needed**:
  - the JSON key names and nesting, which become the contract the JavaScript renderer reads;
  - whether timestamps are embedded pre-formatted as `%d/%m/%Y %H:%M` strings, as ISO strings, or as
    epoch milliseconds, which trades file size against renderer complexity and must respect
    decision 10 forbidding timezone conversion;
  - whether the chart catalogue, the entity lists and the registries are embedded as separate
    top-level objects or folded into each chart entry.
- **Open questions**:
  - Is a shortened key scheme worth the readability cost at the verified volume of about 0.4 M
    values for two scenarios and two decks?
  - Does the payload carry the Portuguese warnings so the dashboard can display them, and if so
    where do they appear in the layout?
  - Does the payload need a schema version field so a future renderer can reject an old payload?

## Dependencies

- **Blocked By**: `ticket-018-implement-series-consolidation.md`
- **Blocks**: `ticket-021-assemble-single-file-html-shell.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
