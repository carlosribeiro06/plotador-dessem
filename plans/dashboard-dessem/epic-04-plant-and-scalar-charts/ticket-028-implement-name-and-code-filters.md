# ticket-028 Implement the name and code filters

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-04-plant-and-scalar-charts` · Recommended agent: `python-task-automation-developer`

## Objective

Implement the two BI-style filters required by spec section 3: one text input searching the plant
name and one searching the plant code, working independently or combined, with incremental search
over the plant registry embedded in the HTML.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/assets/dashboard.js`,
  `src/dessem_dashboard/dashboard/assets/dashboard.html`,
  `src/dessem_dashboard/dashboard/assets/dashboard.css`, `tests/test_payload.py`.
- **Key decisions needed**:
  - the matching rule for names: substring, prefix, or accent-insensitive and case-insensitive
    substring, which matters because plant names such as `SAO SIMAO` and `S.SIMAO` appear
    unaccented in the registry while an operator may type accents;
  - the matching rule for codes: exact, prefix, or substring;
  - the combination semantics when both fields are filled, expected to be a logical AND.
- **Open questions**:
  - Does the filter narrow a selector list, or does it directly select when exactly one plant
    matches, which is the behaviour of many BI tools?
  - Is a no-match state shown with a Portuguese message, and does the previously selected chart stay
    visible?
  - Do the filters apply to the thermal plant view as well, which spec section 3 implies by naming
    both térmicas and hidrelétricas?

## Dependencies

- **Blocked By**: `ticket-027-render-hydro-plant-charts.md`
- **Blocks**: `ticket-029-render-thermal-plant-charts.md`

## Effort Estimate

**Points**: 3 · **Confidence**: Low (will be re-estimated during refinement)
