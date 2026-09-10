# ticket-019 Build the brand theme module

> **[OUTLINE]** This ticket requires refinement before execution.
> It will be refined with learnings from earlier epics.
> Implementation mode: Rigoroso — follow the mode policy in CLAUDE.md.
> Epic: `epic-03-dashboard-core` · Recommended agent: `python-task-automation-developer`

## Objective

Create one Python module that is the single source of every visual constant of the dashboard, so
the CSS, the Plotly layout and the scenario colour assignment cannot drift from the ONS brand
manual. It supplies the brand green and gray, the auxiliary palette, the Arial typography, the
scenario colour order and the shared Plotly layout.

## Anticipated Scope

- **Files likely to be modified**: `src/dessem_dashboard/dashboard/__init__.py`,
  `src/dessem_dashboard/dashboard/theme.py`, `tests/test_theme.py`.
- **Key decisions needed**:
  - the scenario colour order beyond the fourth scenario, where `planning-context.md` proposes
    60 percent tints of the first four;
  - whether the reference scenario always takes brand green `#486018` even when it is not the first
    `--casos` argument;
  - how the tint function is computed and whether it lives in Python or in the JavaScript.
- **Open questions**:
  - Does the Plotly layout template live in Python and get serialised into the payload, or is it
    written directly in the JavaScript renderer? The answer decides whether this module produces a
    dictionary or a set of scalars.
  - Are the CSS custom properties generated from this module, or hand-written in `dashboard.css`
    with a test asserting that they match the Python constants?

Verified brand facts to respect, from `planning-context.md`: brand green `#486018`, brand gray
`#606060`, auxiliary yellow `#FBC90B`, orange `#F76C00`, red `#D10429`, blue `#4F8AD8`, at most
three auxiliary colours combined with the brand colours, Arial for web, left-aligned text, sentence
case, white plot background, light-gray grid, and `hovermode` set to `x unified`.

## Dependencies

- **Blocked By**: `ticket-018-implement-series-consolidation.md`
- **Blocks**: `ticket-021-assemble-single-file-html-shell.md`

## Effort Estimate

**Points**: 2 · **Confidence**: Low (will be re-estimated during refinement)
